import XCTest
@testable import Icarus
import IcarusKit

@MainActor
final class ConnectModelTests: XCTestCase {
    func testAcceptedRefreshStaysVisiblyInProgressWhileRepositoryIsStillBehind() async throws {
        let defaults = UserDefaults(suiteName: #function)!
        defaults.removePersistentDomain(forName: #function)
        defer { defaults.removePersistentDomain(forName: #function) }

        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [_RefreshProtocol.self]
        let client = BrainClient(session: URLSession(configuration: config),
                                 retryDelay: .milliseconds(1))
        let model = ConnectModel(client: client, saved: SavedConnection(defaults: defaults))

        model.repoInput = "acme/widgets"
        model.connect()
        try await waitUntil { model.isReady }

        model.refreshConnected()
        try await Task.sleep(for: .milliseconds(100))

        XCTAssertTrue(model.isRefreshing,
                      "an accepted background re-read must not immediately look idle")

        let current = try JSONDecoder().decode(
            RepoStatus.self,
            from: Data(#"{"state":"ready","repo":"acme/widgets","commit":"new","counts":null,"error":null,"freshness":{"up_to_date":true,"behind_by":0}}"#.utf8)
        )
        model.noteStatus(current)
        XCTAssertFalse(model.isRefreshing,
                       "the re-read completes only when status confirms the index is current")
    }

    /// The validation complaint must not outlive the text that caused it. Seen
    /// live 2026-08-21: a valid `firecrawl/firecrawl` typed into the field with
    /// "Enter a repository as owner/name" still showing beneath it from an
    /// earlier press, which reads as "this repository is rejected".
    func testEditingTheFieldClearsAStaleValidationComplaint() {
        let model = ConnectModel(client: BrainClient(), saved: SavedConnection(defaults: Self.scratchDefaults(#function)))

        model.repoInput = "firecrawl"
        model.connect()
        guard case .failed = model.state else {
            return XCTFail("a name without owner/ must fail validation")
        }

        model.repoInput = "firecrawl/firecrawl"
        model.repoInputEdited()

        XCTAssertEqual(model.state, .idle,
                       "the complaint describes text the user has already corrected")
    }

    func testRetypingTheSameRejectedTextKeepsTheComplaint() {
        let model = ConnectModel(client: BrainClient(), saved: SavedConnection(defaults: Self.scratchDefaults(#function)))
        model.repoInput = "firecrawl"
        model.connect()

        model.repoInputEdited()          // same text, e.g. a selection change

        guard case .failed = model.state else {
            return XCTFail("nothing changed, so the complaint is still true")
        }
    }

    /// The narrow part, and the one worth guarding: a connection the SERVER
    /// dropped is not made untrue by typing in the box. Reaches `.lost` the
    /// only way the model allows -- connect for real, then see /status report
    /// ready on somebody else's repo.
    func testEditingTheFieldDoesNotClearALostConnection() async throws {
        let defaults = Self.scratchDefaults(#function)
        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [_RefreshProtocol.self]
        let client = BrainClient(session: URLSession(configuration: config),
                                 retryDelay: .milliseconds(1))
        let model = ConnectModel(client: client, saved: SavedConnection(defaults: defaults))

        model.repoInput = "acme/widgets"
        model.connect()
        try await waitUntil { model.isReady }

        let elsewhere = try JSONDecoder().decode(
            RepoStatus.self,
            from: Data(#"{"state":"ready","repo":"simonw/llm","commit":"c","counts":null,"error":null}"#.utf8)
        )
        model.noteStatus(elsewhere)
        guard case .lost = model.state else {
            return XCTFail("a ready status on a different repo is a lost connection")
        }

        model.repoInput = "acme/widget"
        model.repoInputEdited()

        guard case .lost = model.state else {
            return XCTFail("typing must not erase a connection the server really dropped")
        }
    }

    private static func scratchDefaults(_ name: String) -> UserDefaults {
        let d = UserDefaults(suiteName: name)!
        d.removePersistentDomain(forName: name)
        return d
    }

    private func waitUntil(timeout: Duration = .seconds(3),
                           _ condition: @escaping @MainActor () -> Bool) async throws {
        let clock = ContinuousClock()
        let deadline = clock.now.advanced(by: timeout)
        while !condition(), clock.now < deadline {
            try await Task.sleep(for: .milliseconds(10))
        }
        XCTAssertTrue(condition(), "condition did not become true before timeout")
    }
}

private final class _RefreshProtocol: URLProtocol {
    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }

    override func startLoading() {
        let isStatus = request.url?.path == "/status"
        let response = HTTPURLResponse(url: request.url!, statusCode: isStatus ? 200 : 202,
                                       httpVersion: nil, headerFields: nil)!
        let body: Data
        if isStatus {
            body = Data(#"{"state":"ready","repo":"acme/widgets","commit":"old","counts":null,"error":null,"freshness":{"up_to_date":false,"behind_by":1}}"#.utf8)
        } else {
            body = Data("{}".utf8)
        }
        client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: body)
        client?.urlProtocolDidFinishLoading(self)
    }

    override func stopLoading() {}
}
