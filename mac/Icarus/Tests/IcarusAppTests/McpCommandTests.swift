import XCTest
@testable import Icarus
@testable import IcarusKit

/// The stdio loop, exercised without a pipe or a Keychain.
///
/// This exists because the first implementation used
/// `FileHandle.standardInput.bytes.lines` and produced a server that consumed
/// input and emitted NOTHING — no output, no error — which unit tests of the
/// message handler could never have caught, since the handler was fine. Driving
/// the real binary found it. These tests pin the loop's own behaviour so the
/// next reader/writer change is checked here rather than by hand.
final class McpCommandTests: XCTestCase {

    private actor SessionFactory {
        private var sessions: [AgentSession]
        private(set) var calls = 0

        init(_ sessions: [AgentSession]) { self.sessions = sessions }

        func next() async throws -> AgentSession {
            calls += 1
            return sessions.removeFirst()
        }
    }

    private final class RetryingProtocol: URLProtocol {
        private static let lock = NSLock()
        nonisolated(unsafe) private static var statuses: [Int] = []
        nonisolated(unsafe) private static var authorization: [String?] = []

        static func reset(statuses: [Int]) {
            lock.lock()
            self.statuses = statuses
            authorization = []
            lock.unlock()
        }

        static var seenAuthorization: [String?] {
            lock.lock(); defer { lock.unlock() }
            return authorization
        }

        override class func canInit(with request: URLRequest) -> Bool { true }
        override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }

        override func startLoading() {
            Self.lock.lock()
            let status = Self.statuses.removeFirst()
            Self.authorization.append(request.value(forHTTPHeaderField: "Authorization"))
            Self.lock.unlock()
            let response = HTTPURLResponse(
                url: request.url!, statusCode: status, httpVersion: nil, headerFields: nil)!
            client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
            let body = status == 200 ? #"{"repo":"octo/repo"}"# : #"{"error":"stale"}"#
            client?.urlProtocol(self, didLoad: Data(body.utf8))
            client?.urlProtocolDidFinishLoading(self)
        }

        override func stopLoading() {}
    }

    /// Collects what the server wrote, decoded per line.
    private final class Output: @unchecked Sendable {
        private let lock = NSLock()
        private var lines: [Data] = []
        func write(_ data: Data) { lock.lock(); lines.append(data); lock.unlock() }
        var objects: [[String: Any]] {
            lock.lock(); defer { lock.unlock() }
            return lines.compactMap {
                (try? JSONSerialization.jsonObject(with: $0)) as? [String: Any]
            }
        }
        var raw: [Data] { lock.lock(); defer { lock.unlock() }; return lines }
    }

    /// A server whose transport is never reached — these tests are about the
    /// loop, and a tool call that touched the network would be a different test.
    private func offlineServer() -> McpServer {
        McpServer { _, _ in [:] }
    }

    /// Hands out the scripted lines then nil (end of input). A class rather
    /// than a captured `var`, which a `@Sendable` closure may not mutate.
    private final class Script: @unchecked Sendable {
        private let lock = NSLock()
        private var remaining: [String]
        init(_ lines: [String]) { remaining = lines }
        func next() -> String? {
            lock.lock(); defer { lock.unlock() }
            return remaining.isEmpty ? nil : remaining.removeFirst()
        }
    }

    private func run(_ input: [String]) async -> Output {
        let output = Output()
        let script = Script(input)
        await McpCommand.serve(
            server: offlineServer(),
            read: { script.next() },
            write: { output.write($0) })
        return output
    }

    func testRespondsToEachRequestAndStopsAtEndOfInput() async {
        let output = await run([
            #"{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}"#,
            #"{"jsonrpc":"2.0","id":2,"method":"tools/list"}"#,
        ])
        // The regression: the earlier reader produced ZERO lines here.
        XCTAssertEqual(output.objects.count, 2)
        XCTAssertEqual(output.objects.first?["id"] as? Int, 1)
        let tools = (output.objects.last?["result"] as? [String: Any])?["tools"]
            as? [[String: Any]]
        XCTAssertEqual(tools?.count, 3)
    }

    func testEveryLineIsNewlineTerminated() async {
        // A client parses newline-delimited JSON; two responses concatenated
        // without a separator are one unparseable line.
        let output = await run([
            #"{"jsonrpc":"2.0","id":1,"method":"ping"}"#,
            #"{"jsonrpc":"2.0","id":2,"method":"ping"}"#,
        ])
        XCTAssertEqual(output.raw.count, 2)
        for line in output.raw { XCTAssertEqual(line.last, 0x0A) }
    }

    func testNotificationProducesNoLineAtAll() async {
        let output = await run([
            #"{"jsonrpc":"2.0","method":"notifications/initialized"}"#,
            #"{"jsonrpc":"2.0","id":9,"method":"ping"}"#,
        ])
        XCTAssertEqual(output.objects.count, 1)
        XCTAssertEqual(output.objects.first?["id"] as? Int, 9)
    }

    func testMalformedLineIsAParseErrorAndTheLoopContinues() async {
        // A client that sends one bad line must not lose the session.
        let output = await run([
            "not json at all",
            #"{"jsonrpc":"2.0","id":5,"method":"ping"}"#,
        ])
        XCTAssertEqual(output.objects.count, 2)
        XCTAssertEqual(
            ((output.objects.first?["error"] as? [String: Any])?["code"]) as? Int, -32700)
        XCTAssertEqual(output.objects.last?["id"] as? Int, 5)
    }

    func testBlankLinesAreIgnoredRatherThanAnswered() async {
        let output = await run(["", "   ", #"{"jsonrpc":"2.0","id":1,"method":"ping"}"#])
        XCTAssertEqual(output.objects.count, 1)
    }

    func testStatusMessagesSeparateRefusalFromUnreachable() {
        // Conflating these tells a signed-out user to check their network.
        XCTAssertTrue(McpCommand.message(forStatus: 401).contains("sign in"))
        XCTAssertTrue(McpCommand.message(forStatus: 403).contains("repository"))
        XCTAssertTrue(McpCommand.message(forStatus: 429).contains("rate limited"))
        XCTAssertTrue(McpCommand.message(forStatus: 0).contains("could not be reached"))
    }

    func testARemintOntoAnotherRepositoryRefusesInsteadOfRetrying() async throws {
        // Raised in review: the preflight validates repo A, the user switches
        // the app to B, the request 403s, the transport remints onto B and
        // resends the ORIGINAL body -- so retrieval, the writer and analytics
        // all run inside a repository the caller never asked about. The
        // postflight rejects the answer, but only after the work happened, and
        // on a private repo that is evidence past a fail-closed boundary.
        RetryingProtocol.reset(statuses: [403, 200])
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [RetryingProtocol.self]
        let factory = SessionFactory([
            AgentSession(token: "a", expiresAt: Date().timeIntervalSince1970 + 10_000,
                         repo: "octo/a"),
            AgentSession(token: "b", expiresAt: Date().timeIntervalSince1970 + 10_000,
                         repo: "octo/b"),
        ])
        let transport = McpCommand.makeTransport(
            baseURL: URL(string: "https://brain.example")!,
            sessionFactory: { try await factory.next() },
            urlSession: URLSession(configuration: configuration))

        do {
            _ = try await transport("/ask", ["question": "why?"])
            XCTFail("expected a refusal rather than a retry against octo/b")
        } catch let error as McpServer.ToolError {
            XCTAssertTrue(error.message.contains("octo/b"), error.message)
        }
        // The decisive assertion: the body was sent ONCE. A second request
        // means the writer ran against the repository nobody asked about.
        XCTAssertEqual(RetryingProtocol.seenAuthorization.count, 1)
    }

    /// The legitimate retry: an EXPIRED grant for the SAME repository.
    ///
    /// The fixture used to hand out `old/repo` then `octo/repo` -- a repository
    /// SWITCH -- and assert the retry went through, so it encoded the defect
    /// found in review rather than the behaviour anyone wanted. The assertions
    /// are unchanged; only the fixture is, to model what the retry is actually
    /// for. The switch case is now its own test directly above, and it refuses.
    func testTransportRemintsAndRetriesOnceWhenRepositoryBoundSessionIsStale() async throws {
        RetryingProtocol.reset(statuses: [403, 200])
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [RetryingProtocol.self]
        let session = URLSession(configuration: configuration)
        let factory = SessionFactory([
            AgentSession(token: "old", expiresAt: Date().timeIntervalSince1970 + 10_000,
                         repo: "octo/repo"),
            AgentSession(token: "fresh", expiresAt: Date().timeIntervalSince1970 + 10_000,
                         repo: "octo/repo"),
        ])
        let transport = McpCommand.makeTransport(
            baseURL: URL(string: "https://brain.example")!,
            sessionFactory: { try await factory.next() },
            urlSession: session)

        let payload = try await transport("/status", nil)
        let factoryCalls = await factory.calls

        XCTAssertEqual(payload["repo"] as? String, "octo/repo")
        XCTAssertEqual(factoryCalls, 2)
        XCTAssertEqual(
            RetryingProtocol.seenAuthorization.compactMap { $0 },
            ["Bearer old", "Bearer fresh"])
    }
}
