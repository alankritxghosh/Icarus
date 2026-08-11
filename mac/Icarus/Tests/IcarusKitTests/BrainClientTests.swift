import XCTest
@testable import IcarusKit

/// Captures the outgoing request so we can assert the Authorization header —
/// proving the GitHub token is actually sent to the brain (Option B auth).
final class _CapturingProtocol: URLProtocol {
    nonisolated(unsafe) static var lastRequest: URLRequest?
    nonisolated(unsafe) static var body = Data("{}".utf8)
    nonisolated(unsafe) static var statusCode = 200

    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }

    override func startLoading() {
        Self.lastRequest = request
        let resp = HTTPURLResponse(url: request.url!, statusCode: Self.statusCode,
                                   httpVersion: nil, headerFields: nil)!
        client?.urlProtocol(self, didReceive: resp, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: Self.body)
        client?.urlProtocolDidFinishLoading(self)
    }
    override func stopLoading() {}
}

final class BrainClientTests: XCTestCase {
    private func stubbedSession() -> URLSession {
        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [_CapturingProtocol.self]
        return URLSession(configuration: config)
    }

    func testConnectSendsBearerTokenWhenPresent() async throws {
        _CapturingProtocol.lastRequest = nil
        let client = BrainClient(token: { "tok-123" }, session: stubbedSession())
        try await client.connect(repo: "octo/hello")
        let auth = _CapturingProtocol.lastRequest?.value(forHTTPHeaderField: "Authorization")
        XCTAssertEqual(auth, "Bearer tok-123")
    }

    // MARK: - Refresh (re-read a repository that has moved on)
    // A connected corpus is frozen at its ingested commit; the server has always
    // supported `POST /connect {"refresh": true}` to re-read it, and no client
    // ever sent the flag. These pin the wire contract in both directions --
    // because the two mistakes here are opposite and both expensive: never
    // sending it leaves the staleness banner unactionable, and sending it by
    // accident spends minutes of server CPU republishing a corpus other readers
    // are mid-question on.

    private func connectBody() throws -> [String: Any] {
        // URLProtocol strips httpBody into httpBodyStream, so read whichever survived.
        guard let request = _CapturingProtocol.lastRequest else { return [:] }
        var data = request.httpBody
        if data == nil, let stream = request.httpBodyStream {
            stream.open()
            defer { stream.close() }
            var buffer = [UInt8](repeating: 0, count: 4096)
            let read = stream.read(&buffer, maxLength: buffer.count)
            data = Data(buffer.prefix(max(read, 0)))
        }
        guard let data, !data.isEmpty else { return [:] }
        return (try JSONSerialization.jsonObject(with: data) as? [String: Any]) ?? [:]
    }

    func testConnectSendsTheRefreshFlagWhenRefreshIsRequested() async throws {
        _CapturingProtocol.lastRequest = nil
        let client = BrainClient(session: stubbedSession())
        try await client.connect(repo: "octo/hello", refresh: true)
        let body = try connectBody()
        XCTAssertEqual(body["repo"] as? String, "octo/hello")
        XCTAssertEqual(body["refresh"] as? Bool, true,
                       "a refresh must actually reach the brain, or the banner's button does nothing")
    }

    func testAnOrdinaryConnectNeverAsksForARefresh() async throws {
        // The server treats a missing key as false, and rejects non-booleans --
        // so the safe wire shape is to omit it entirely unless it was asked for.
        _CapturingProtocol.lastRequest = nil
        let client = BrainClient(session: stubbedSession())
        try await client.connect(repo: "octo/hello")
        let body = try connectBody()
        XCTAssertNil(body["refresh"],
                     "an ordinary connect must not spend the re-ingest budget")
    }

    func testARefusedRefreshIsDistinctFromAnOrdinaryRateLimit() async {
        // Both come back 429, but they are different budgets: an ordinary
        // connect limit clears in about a minute, a refresh limit is 2/hour
        // (demo/server.py). Telling someone to "wait a minute" for an hour-long
        // budget is a confident claim the evidence doesn't support.
        let client = BrainClient(session: sessionReturning(status: 429), retryDelay: .milliseconds(1))
        do {
            try await client.connect(repo: "octo/hello", refresh: true)
            XCTFail("expected a refused refresh to throw")
        } catch let error as BrainError {
            XCTAssertEqual(error, .refreshRateLimited)
        } catch {
            XCTFail("expected BrainError.refreshRateLimited, got \(error)")
        }
    }

    func testRefusedRefreshCopyDoesNotPromiseAMinuteItCannotDeliver() {
        let msg = BrainError.refreshRateLimited.userMessage
        XCTAssertFalse(msg.lowercased().contains("a minute"),
                       "the refresh budget is hourly, not a minute: \(msg)")
        XCTAssertFalse(msg.lowercased().contains("internet connection"))
        XCTAssertTrue(msg.lowercased().contains("hour"),
                      "say what the real wait is: \(msg)")
    }

    func testBeginGitHubLoginReturnsAuthorizeURL() async throws {
        _CapturingProtocol.body = Data(#"{"authorize_url":"https://github.com/login/oauth/authorize?client_id=x&state=y"}"#.utf8)
        let client = BrainClient(session: stubbedSession())
        let url = try await client.beginGitHubLogin()
        XCTAssertEqual(url.host, "github.com")
        XCTAssertEqual(url.path, "/login/oauth/authorize")
    }

    func testOrdinarySignInDoesNotAskGitHubForRepoScope() async throws {
        // The consent screen a stranger meets first must not demand read AND
        // WRITE on every private repository they own. If this body ever carries
        // a mode again by default, that screen comes back.
        _CapturingProtocol.lastRequest = nil
        _CapturingProtocol.body = Data(#"{"authorize_url":"https://github.com/x"}"#.utf8)
        let client = BrainClient(session: stubbedSession())
        _ = try await client.beginGitHubLogin()
        XCTAssertNil(try connectBody()["mode"])
    }

    func testPrivateAccessSignInAsksForTheUpgradeMode() async throws {
        _CapturingProtocol.lastRequest = nil
        _CapturingProtocol.body = Data(#"{"authorize_url":"https://github.com/x"}"#.utf8)
        let client = BrainClient(session: stubbedSession())
        _ = try await client.beginGitHubLogin(privateAccess: true)
        XCTAssertEqual(try connectBody()["mode"] as? String, "app-private",
                       "without this the upgrade button silently re-runs an identity-only login")
    }

    func testRedeemGitHubSessionReturnsToken() async throws {
        _CapturingProtocol.body = Data(#"{"token":"gho_redeemed"}"#.utf8)
        let client = BrainClient(session: stubbedSession())
        let token = try await client.redeemGitHubSession("sess-1")
        XCTAssertEqual(token, "gho_redeemed")
    }

    func testCreateAgentSessionUsesGitHubBearerAndDecodesShortCredential() async throws {
        _CapturingProtocol.lastRequest = nil
        _CapturingProtocol.body = Data(
            #"{"token":"short-lived","expires_at":1600,"repo":"octo/public"}"#.utf8
        )
        let client = BrainClient(
            token: { "github-token" },
            session: stubbedSession()
        )

        let session = try await client.createAgentSession()

        let request = _CapturingProtocol.lastRequest
        XCTAssertEqual(request?.url?.path, "/auth/agent/session")
        XCTAssertEqual(request?.httpMethod, "POST")
        XCTAssertEqual(
            request?.value(forHTTPHeaderField: "Authorization"),
            "Bearer github-token"
        )
        XCTAssertEqual(session.token, "short-lived")
        XCTAssertEqual(session.expiresAt, 1600)
        XCTAssertEqual(session.repo, "octo/public")
    }

    func testStatusSendsBearerToken() async throws {
        // In hosted auth mode the brain resolves the caller's library by
        // identity — an unauthenticated /status returns the shared public
        // default, stranding the connect poll. The bearer MUST be attached.
        _CapturingProtocol.lastRequest = nil
        _CapturingProtocol.body = Data(#"{"state":"ready","repo":"o/repo","commit":"c","counts":null,"error":null}"#.utf8)
        let client = BrainClient(token: { "tok-123" }, session: stubbedSession())
        let s = try await client.status()
        XCTAssertEqual(_CapturingProtocol.lastRequest?.url?.path, "/status")
        XCTAssertEqual(_CapturingProtocol.lastRequest?.value(forHTTPHeaderField: "Authorization"), "Bearer tok-123")
        XCTAssertEqual(s.repo, "o/repo")
    }

    func testMemoryGapsRequestsTheServerOwnedLifecycleAndIncludesResolved() async throws {
        _CapturingProtocol.lastRequest = nil
        _CapturingProtocol.body = Data(
            #"{"repo":"o/repo","gaps":[{"id":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","question":"Why auth?","unknown_count":2,"last_asked":10,"status":"open","kind":"undocumented","actionable":true,"resolution_citations":[]}]}"#.utf8
        )
        let client = BrainClient(token: { "tok-123" }, session: stubbedSession())

        let response = try await client.memoryGaps(includeResolved: true)

        let request = _CapturingProtocol.lastRequest
        XCTAssertEqual(request?.url?.path, "/ledger")
        XCTAssertEqual(
            URLComponents(url: request!.url!, resolvingAgainstBaseURL: false)?
                .queryItems?
                .reduce(into: [String: String]()) { $0[$1.name] = $1.value },
            ["gaps": "1", "resolved": "1"]
        )
        XCTAssertEqual(
            request?.value(forHTTPHeaderField: "Authorization"),
            "Bearer tok-123"
        )
        XCTAssertEqual(response.open.first?.question, "Why auth?")
    }

    func testRecordEngineeringMemorySendsTheExactGapAndReturnsObservedPullRequest() async throws {
        _CapturingProtocol.lastRequest = nil
        _CapturingProtocol.body = Data(
            #"{"repo":"o/repo","question":"Why auth?","branch":"icarus/memory-auth","path":"docs/engineering-memory/auth.md","file_url":"https://github.com/o/repo/blob/icarus/memory-auth/auth.md","pull_request_url":"https://github.com/o/repo/pull/42"}"#.utf8
        )
        let client = BrainClient(token: { "tok-123" }, session: stubbedSession())

        let result = try await client.recordEngineeringMemory(
            gapID: "a" + String(repeating: "0", count: 63),
            rationale: "Retries duplicated invoices.",
            tradeoffs: "Higher latency.",
            references: ["PR #418"]
        )

        let request = _CapturingProtocol.lastRequest
        XCTAssertEqual(request?.url?.path, "/memory-gaps/record")
        XCTAssertEqual(request?.httpMethod, "POST")
        XCTAssertEqual(
            request?.value(forHTTPHeaderField: "Authorization"),
            "Bearer tok-123"
        )
        let body = try connectBody()
        XCTAssertEqual(
            body["gap_id"] as? String,
            "a" + String(repeating: "0", count: 63)
        )
        XCTAssertNil(body["question"])
        XCTAssertEqual(body["rationale"] as? String, "Retries duplicated invoices.")
        XCTAssertEqual(body["tradeoffs"] as? String, "Higher latency.")
        XCTAssertEqual(body["references"] as? [String], ["PR #418"])
        XCTAssertEqual(result.pullRequestURL.absoluteString, "https://github.com/o/repo/pull/42")
    }

    func testRecordEngineeringMemoryPreservesARecoverablePartialWriteURL() async {
        _CapturingProtocol.statusCode = 502
        defer { _CapturingProtocol.statusCode = 200 }
        _CapturingProtocol.body = Data(
            #"{"error":"GitHub could not open the pull request","recovery_url":"https://github.com/o/repo/tree/icarus/memory-auth"}"#.utf8
        )
        let client = BrainClient(token: { "tok-123" }, session: stubbedSession())

        do {
            _ = try await client.recordEngineeringMemory(
                gapID: String(repeating: "a", count: 64),
                rationale: "Retries duplicated invoices."
            )
            XCTFail("expected a partial GitHub failure")
        } catch let error as MemoryRecordFailure {
            XCTAssertEqual(error.status, 502)
            XCTAssertEqual(error.message, "GitHub could not open the pull request")
            XCTAssertEqual(
                error.recoveryURL?.absoluteString,
                "https://github.com/o/repo/tree/icarus/memory-auth"
            )
        } catch {
            XCTFail("expected MemoryRecordFailure, got \(error)")
        }
    }

    func testExplainSendsTheSelectionForTheNativeExtensionBridge() async throws {
        _CapturingProtocol.lastRequest = nil
        _CapturingProtocol.body = Data(
            #"{"verdict":"unknown","answer":"","citations":[],"searched":["code:src/auth.ts#L1-L20"],"anchored":[],"indexing":false}"#.utf8
        )
        let client = BrainClient(token: { "tok-123" }, session: stubbedSession())

        let response = try await client.explain(
            repo: "o/repo", path: "src/auth.ts", start: 4, end: 8,
            question: "Why is this synchronous?"
        )

        let request = _CapturingProtocol.lastRequest
        XCTAssertEqual(request?.url?.path, "/explain")
        XCTAssertEqual(request?.httpMethod, "POST")
        XCTAssertEqual(
            request?.value(forHTTPHeaderField: "Authorization"),
            "Bearer tok-123"
        )
        let body = try connectBody()
        XCTAssertEqual(body["repo"] as? String, "o/repo")
        XCTAssertEqual(body["path"] as? String, "src/auth.ts")
        XCTAssertEqual(body["start"] as? Int, 4)
        XCTAssertEqual(body["end"] as? Int, 8)
        XCTAssertEqual(body["question"] as? String, "Why is this synchronous?")
        XCTAssertEqual(response.verdict.rawValue, "unknown")
    }

    func testDisconnectPostsWithBearerAndReturnsSnapshot() async throws {
        _CapturingProtocol.lastRequest = nil
        _CapturingProtocol.body = Data(#"{"state":"ready","repo":"simonw/llm","commit":"94769b8","counts":null,"error":null}"#.utf8)
        let client = BrainClient(token: { "tok-123" }, session: stubbedSession())
        let status = try await client.disconnect()
        let req = _CapturingProtocol.lastRequest
        XCTAssertEqual(req?.url?.path, "/disconnect")
        XCTAssertEqual(req?.httpMethod, "POST")
        XCTAssertEqual(req?.value(forHTTPHeaderField: "Authorization"), "Bearer tok-123")
        // The brain replies with the caller's fresh snapshot (back on the default).
        XCTAssertEqual(status.repo, "simonw/llm")
    }

    func testAskOmitsAuthorizationWhenNoToken() async throws {
        _CapturingProtocol.lastRequest = nil
        _CapturingProtocol.body = Data(#"{"verdict":"unknown","answer":"","citations":[],"searched":[]}"#.utf8)
        let client = BrainClient(token: { nil }, session: stubbedSession())
        _ = try? await client.ask("why?")
        let auth = _CapturingProtocol.lastRequest?.value(forHTTPHeaderField: "Authorization")
        XCTAssertNil(auth)
    }

    // MARK: - Cold-start retry
    // A request-scoped-CPU host (Cloud Run, Azure Container Apps) can transiently
    // fail its FIRST request after scaling to zero, then succeed cleanly moments
    // later with zero code involved -- live-observed on Azure tonight. BrainClient
    // absorbs exactly this shape with one bounded retry, rather than the app
    // surfacing a scary error on a blip that resolves itself.

    func testStatusRetriesOnceAfterATransientFailureAndSucceeds() async throws {
        _FlakyProtocol.attempts = 0
        _FlakyProtocol.failuresRemaining = 1
        _FlakyProtocol.body = Data(#"{"state":"ready","repo":"o/r","commit":"c","counts":null,"error":null,"private":false}"#.utf8)
        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [_FlakyProtocol.self]
        let client = BrainClient(session: URLSession(configuration: config), retryDelay: .milliseconds(1))
        let status = try await client.status()  // must NOT throw -- the retry absorbs the blip
        XCTAssertEqual(status.repo, "o/r")
        XCTAssertEqual(_FlakyProtocol.attempts, 2)  // one failure, one retry
    }

    func testStatusRetryIsBoundedNotInfiniteOnAPersistentFailure() async throws {
        _FlakyProtocol.attempts = 0
        _FlakyProtocol.failuresRemaining = 99  // never recovers
        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [_FlakyProtocol.self]
        let client = BrainClient(session: URLSession(configuration: config), retryDelay: .milliseconds(1))
        do {
            _ = try await client.status()
            XCTFail("expected the persistent failure to still surface after one retry")
        } catch {
            XCTAssertEqual(_FlakyProtocol.attempts, 2)  // exactly one retry, not a retry loop
        }
    }

    // MARK: - Typed refusals (2026-07-14)
    // A refusal the brain actually SENT (401/403/429) must surface as a typed
    // BrainError, never as an opaque failure the UI then blames on the network.
    // This is the client half of the "can't reach the brain" misdiagnosis.

    private func sessionReturning(status: Int) -> URLSession {
        _StatusCodeProtocol.code = status
        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [_StatusCodeProtocol.self]
        return URLSession(configuration: config)
    }

    func testUnauthorizedSurfacesAsTypedError() async {
        let client = BrainClient(session: sessionReturning(status: 401), retryDelay: .milliseconds(1))
        do {
            try await client.connect(repo: "octo/hello")
            XCTFail("expected a 401 to throw")
        } catch let error as BrainError {
            XCTAssertEqual(error, .unauthorized)
        } catch {
            XCTFail("expected BrainError.unauthorized, got \(error)")
        }
    }

    func testRateLimitedSurfacesAsTypedError() async {
        let client = BrainClient(session: sessionReturning(status: 429), retryDelay: .milliseconds(1))
        do {
            try await client.connect(repo: "octo/hello")
            XCTFail("expected a 429 to throw")
        } catch let error as BrainError {
            XCTAssertEqual(error, .rateLimited)
        } catch {
            XCTFail("expected BrainError.rateLimited, got \(error)")
        }
    }

    func testForbiddenSurfacesAsTypedError() async {
        let client = BrainClient(session: sessionReturning(status: 403), retryDelay: .milliseconds(1))
        do {
            try await client.connect(repo: "octo/private")
            XCTFail("expected a 403 to throw")
        } catch let error as BrainError {
            XCTAssertEqual(error, .forbidden)
        } catch {
            XCTFail("expected BrainError.forbidden, got \(error)")
        }
    }

    func testConnectAcceptsA202SoAnAsyncBrainIsNotTreatedAsAFailure() async throws {
        // The brain may answer 202 (accepted, still indexing) rather than 200.
        // That is a SUCCESS -- the client then polls /status.
        let client = BrainClient(session: sessionReturning(status: 202), retryDelay: .milliseconds(1))
        try await client.connect(repo: "octo/hello")  // must not throw
    }

    // MARK: - The copy a refused user actually reads
    // The bug this guards: EVERY refusal below used to render as "check your
    // internet connection", which is false and unactionable. None of them may
    // ever blame the network again.

    func testRefusalCopyNeverBlamesTheNetwork() {
        for error: BrainError in [.unauthorized, .forbidden, .rateLimited, .server(500)] {
            let msg = error.userMessage
            XCTAssertFalse(msg.lowercased().contains("internet connection"),
                           "\(error) must not blame the user's network: \(msg)")
            XCTAssertFalse(msg.isEmpty)
        }
    }

    func testRefusalCopyIsSpecificToTheActualCause() {
        XCTAssertTrue(BrainError.unauthorized.userMessage.lowercased().contains("signed out"))
        XCTAssertTrue(BrainError.rateLimited.userMessage.lowercased().contains("too many"))
        XCTAssertTrue(BrainError.forbidden.userMessage.lowercased().contains("can't read it"))
        // The old copy said "public repositories only", which stopped being true
        // when private repos were re-enabled (2026-07-16) — a refusal that
        // misdescribes the product sends the reader chasing the wrong cause.
        XCTAssertFalse(BrainError.forbidden.userMessage.lowercased().contains("public repositories only"))
        XCTAssertTrue(BrainError.server(503).userMessage.contains("503"))
    }
}

/// Answers every request with a fixed HTTP status code and an empty JSON body --
/// a REAL response from the server (unlike `_FlakyProtocol`, which fails at the
/// transport layer). That distinction is the whole point of `BrainError`.
final class _StatusCodeProtocol: URLProtocol {
    nonisolated(unsafe) static var code = 200

    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }

    override func startLoading() {
        let resp = HTTPURLResponse(url: request.url!, statusCode: Self.code,
                                   httpVersion: nil, headerFields: nil)!
        client?.urlProtocol(self, didReceive: resp, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: Data("{}".utf8))
        client?.urlProtocolDidFinishLoading(self)
    }
    override func stopLoading() {}
}

/// Fails the first `failuresRemaining` loads with a transport-level error (no
/// HTTPURLResponse at all -- matching a genuine "can't reach the host" blip,
/// not a real 4xx/5xx), then succeeds. Counts every attempt made.
final class _FlakyProtocol: URLProtocol {
    nonisolated(unsafe) static var failuresRemaining = 0
    nonisolated(unsafe) static var attempts = 0
    nonisolated(unsafe) static var body = Data("{}".utf8)

    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }

    override func startLoading() {
        Self.attempts += 1
        if Self.failuresRemaining > 0 {
            Self.failuresRemaining -= 1
            client?.urlProtocol(self, didFailWithError: URLError(.cannotConnectToHost))
            return
        }
        let resp = HTTPURLResponse(url: request.url!, statusCode: 200,
                                   httpVersion: nil, headerFields: nil)!
        client?.urlProtocol(self, didReceive: resp, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: Self.body)
        client?.urlProtocolDidFinishLoading(self)
    }
    override func stopLoading() {}
}
