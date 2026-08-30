import XCTest
@testable import Icarus
import IcarusKit

private final class _DecisionProtocol: URLProtocol {
    private static let lock = NSLock()
    nonisolated(unsafe) private static var responses: [(Int, Data)] = []
    nonisolated(unsafe) private(set) static var requests: [URLRequest] = []

    static func reset(_ values: [(Int, String)]) {
        lock.lock()
        responses = values.map { ($0.0, Data($0.1.utf8)) }
        requests = []
        lock.unlock()
    }

    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }

    override func startLoading() {
        Self.lock.lock()
        Self.requests.append(request)
        let (status, body) = Self.responses.removeFirst()
        Self.lock.unlock()
        let response = HTTPURLResponse(
            url: request.url!, statusCode: status, httpVersion: nil, headerFields: nil)!
        client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: body)
        client?.urlProtocolDidFinishLoading(self)
    }

    override func stopLoading() {}
}

@MainActor
final class DecisionInboxModelTests: XCTestCase {
    private let candidateJSON = #"{"repo":"o/repo","candidates":[{"id":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","ts":10,"source":"claude_code","decision":"Use SQLite","rationale":"Local and simple.","alternatives":[{"decision":"Use Postgres","rationale":"Better concurrency."}],"affected_paths":["demo/index.py"],"status":"pending"}]}"#

    private func client() -> BrainClient {
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [_DecisionProtocol.self]
        return BrainClient(
            session: URLSession(configuration: configuration),
            retryDelay: .milliseconds(1)
        )
    }

    private func waitUntil(
        timeout: Duration = .seconds(2),
        _ condition: @escaping @MainActor () -> Bool
    ) async throws {
        let clock = ContinuousClock()
        let end = clock.now.advanced(by: timeout)
        while !condition() {
            if clock.now >= end { throw CancellationError() }
            try await Task.sleep(for: .milliseconds(10))
        }
    }

    func testLoadSurfacesPendingAtomicCards() async throws {
        _DecisionProtocol.reset([(200, candidateJSON)])
        let model = DecisionInboxModel(client: client())

        model.load()
        try await waitUntil {
            if case .loaded = model.state { return true }
            return false
        }

        guard case .loaded(let repo, let candidates) = model.state else {
            return XCTFail("expected loaded candidates")
        }
        XCTAssertEqual(repo, "o/repo")
        XCTAssertEqual(candidates.first?.decision, "Use SQLite")
    }

    func testNotSureIsOneActionAndRemovesThePendingCard() async throws {
        let result = #"{"id":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","status":"not_sure","selection":"not_sure","selected_decision":null,"selected_rationale":null,"proposal":null}"#
        _DecisionProtocol.reset([(200, candidateJSON), (200, result)])
        let model = DecisionInboxModel(client: client())
        model.load()
        try await waitUntil { if case .loaded = model.state { return true }; return false }
        guard case .loaded(_, let candidates) = model.state, let item = candidates.first else {
            return XCTFail("expected candidate")
        }

        model.confirm(item, selection: .notSure)
        try await waitUntil {
            if case .succeeded = model.confirmation[item.id] { return true }
            return false
        }

        guard case .loaded(_, let remaining) = model.state else {
            return XCTFail("expected loaded state")
        }
        XCTAssertTrue(remaining.isEmpty)
        XCTAssertEqual(_DecisionProtocol.requests.last?.url?.path, "/agent-mode/confirm")
    }

    func testFailedConfirmationKeepsTheCardAndSurfacesTruthfulFailure() async throws {
        _DecisionProtocol.reset([
            (200, candidateJSON),
            (502, #"{"error":"GitHub could not create the proposal"}"#),
        ])
        let model = DecisionInboxModel(client: client())
        model.load()
        try await waitUntil { if case .loaded = model.state { return true }; return false }
        guard case .loaded(_, let candidates) = model.state, let item = candidates.first else {
            return XCTFail("expected candidate")
        }

        model.confirm(item, selection: .recommended)
        try await waitUntil {
            if case .failed = model.confirmation[item.id] { return true }
            return false
        }

        guard case .loaded(_, let remaining) = model.state else {
            return XCTFail("expected loaded state")
        }
        XCTAssertEqual(remaining.map(\.id), [item.id])
        guard case .failed(let message, _) = model.confirmation[item.id] else {
            return XCTFail("expected visible failure")
        }
        XCTAssertEqual(message, "GitHub could not create the proposal")
    }
}
