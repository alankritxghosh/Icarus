import XCTest
@testable import IcarusKit

/// Captures the outgoing request so we can assert the Authorization header —
/// proving the GitHub token is actually sent to the brain (Option B auth).
final class _CapturingProtocol: URLProtocol {
    nonisolated(unsafe) static var lastRequest: URLRequest?
    nonisolated(unsafe) static var body = Data("{}".utf8)

    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }

    override func startLoading() {
        Self.lastRequest = request
        let resp = HTTPURLResponse(url: request.url!, statusCode: 200,
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

    func testBeginGitHubLoginReturnsAuthorizeURL() async throws {
        _CapturingProtocol.body = Data(#"{"authorize_url":"https://github.com/login/oauth/authorize?client_id=x&state=y"}"#.utf8)
        let client = BrainClient(session: stubbedSession())
        let url = try await client.beginGitHubLogin()
        XCTAssertEqual(url.host, "github.com")
        XCTAssertEqual(url.path, "/login/oauth/authorize")
    }

    func testRedeemGitHubSessionReturnsToken() async throws {
        _CapturingProtocol.body = Data(#"{"token":"gho_redeemed"}"#.utf8)
        let client = BrainClient(session: stubbedSession())
        let token = try await client.redeemGitHubSession("sess-1")
        XCTAssertEqual(token, "gho_redeemed")
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
        XCTAssertTrue(BrainError.forbidden.userMessage.lowercased().contains("public"))
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
