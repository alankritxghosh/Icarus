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

    func testDisconnectPostsWithBearerAndReturnsSnapshot() async throws {
        _CapturingProtocol.lastRequest = nil
        _CapturingProtocol.body = Data(#"{"state":"ready","repo":"simonw/llm","commit":"94769b8","counts":null,"error":null,"private":false}"#.utf8)
        let client = BrainClient(token: { "tok-123" }, session: stubbedSession())
        let status = try await client.disconnect()
        let req = _CapturingProtocol.lastRequest
        XCTAssertEqual(req?.url?.path, "/disconnect")
        XCTAssertEqual(req?.httpMethod, "POST")
        XCTAssertEqual(req?.value(forHTTPHeaderField: "Authorization"), "Bearer tok-123")
        // The brain replies with the caller's fresh snapshot (back on the default).
        XCTAssertEqual(status.repo, "simonw/llm")
        XCTAssertFalse(status.isPrivate)
    }

    func testAskOmitsAuthorizationWhenNoToken() async throws {
        _CapturingProtocol.lastRequest = nil
        _CapturingProtocol.body = Data(#"{"verdict":"unknown","answer":"","citations":[],"searched":[]}"#.utf8)
        let client = BrainClient(token: { nil }, session: stubbedSession())
        _ = try? await client.ask("why?")
        let auth = _CapturingProtocol.lastRequest?.value(forHTTPHeaderField: "Authorization")
        XCTAssertNil(auth)
    }
}
