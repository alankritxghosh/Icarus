import XCTest
@testable import Icarus
import IcarusKit

/// The Investigate surface's failure truthfulness.
///
/// A server that REFUSED and a network that never answered mean opposite things
/// to a user: one is "sign in again" or "wait a minute", the other is "check
/// your connection". Collapsing both into a connection message is the same
/// class of dishonesty as rendering a transport failure as an abstention — it
/// reports a state the client does not actually know to be true.
@MainActor
final class InvestigationModelTests: XCTestCase {

    private func model(status: Int, data: String = "{}") -> InvestigationModel {
        _StatusProtocol.status = status
        _StatusProtocol.data = Data(data.utf8)
        _StatusProtocol.failWithTransportError = false
        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [_StatusProtocol.self]
        return InvestigationModel(client: BrainClient(
            session: URLSession(configuration: config), retryDelay: .milliseconds(1)))
    }

    private func message(_ model: InvestigationModel) async throws -> String {
        model.investigate("why did it change?")
        try await waitUntil { if case .failed = model.state { return true }; return false }
        guard case let .failed(message) = model.state else { return "" }
        return message
    }

    func testAServerRefusalIsReportedAsWhatTheServerActuallySaid() async throws {
        // 401/403/429 are answers, not silence. BrainError.userMessage already
        // carries accurate recovery text for each.
        for (status, expected) in [(401, BrainError.unauthorized),
                                   (403, BrainError.forbidden),
                                   (429, BrainError.rateLimited)] {
            let text = try await message(model(status: status))
            XCTAssertEqual(text, expected.userMessage, "HTTP \(status)")
            XCTAssertFalse(text.contains("connection problem"), "HTTP \(status)")
        }
    }

    func testAServerErrorIsReportedAsAServerProblemNotAConnectionOne(  ) async throws {
        let text = try await message(model(status: 503))
        XCTAssertEqual(text, BrainError.server(503).userMessage)
        XCTAssertFalse(text.contains("connection problem"))
    }

    func testARealTransportFailureIsStillReportedAsOne() async throws {
        _StatusProtocol.status = 200
        _StatusProtocol.failWithTransportError = true
        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [_StatusProtocol.self]
        let model = InvestigationModel(client: BrainClient(
            session: URLSession(configuration: config), retryDelay: .milliseconds(1)))
        let text = try await message(model)
        XCTAssertTrue(text.contains("connection"), text)
    }

    func testRepositorySwitchAndSignOutClearTheVisibleTranscript() async throws {
        let payload = """
        {"repo":"first/repo","commit":"abc","verdict":"unknown","answer":"",
         "citations":[],"searched":[],"reason":"no_evidence","indexing":false,
         "investigation":{"objective":"why","subject":[],"findings":[],
          "hypotheses":[],"unknowns":[],"contradictions":[],"trail":[],
          "stopped_because":"nothing left","incomplete_because":null}}
        """
        let model = model(status: 200, data: payload)
        model.investigate("why?")
        try await waitUntil { model.turns.count == 1 }

        model.noteConnectedRepo("second/repo")
        XCTAssertTrue(model.turns.isEmpty)

        model.investigate("why again?")
        try await waitUntil { model.turns.count == 1 }
        model.noteConnectedRepo(nil)
        XCTAssertTrue(model.turns.isEmpty)
    }

    private func waitUntil(timeout: Duration = .seconds(5),
                           _ condition: @escaping @MainActor () -> Bool) async throws {
        let clock = ContinuousClock()
        let deadline = clock.now.advanced(by: timeout)
        while !condition(), clock.now < deadline {
            try await Task.sleep(for: .milliseconds(10))
        }
        XCTAssertTrue(condition(), "condition did not become true before timeout")
    }
}

private final class _StatusProtocol: URLProtocol {
    nonisolated(unsafe) static var status = 200
    nonisolated(unsafe) static var failWithTransportError = false
    nonisolated(unsafe) static var data = Data("{}".utf8)

    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }
    override func startLoading() {
        if Self.failWithTransportError {
            client?.urlProtocol(self, didFailWithError: URLError(.notConnectedToInternet))
            return
        }
        let response = HTTPURLResponse(url: request.url!, statusCode: Self.status,
                                       httpVersion: nil, headerFields: nil)!
        client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: Self.data)
        client?.urlProtocolDidFinishLoading(self)
    }
    override func stopLoading() {}
}
