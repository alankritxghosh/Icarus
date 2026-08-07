import Foundation
import XCTest
@testable import Icarus
import IcarusKit

final class ExtensionBridgeCommandTests: XCTestCase {
    func testSignedOutStatusFailsWithoutCallingTheBrain() async throws {
        let request = try decode(#"{"action":"status"}"#)

        let response = await ExtensionBridgeCommand.handle(
            request, tokenReader: { nil }
        )

        XCTAssertEqual(response["ok"] as? Bool, false)
        XCTAssertEqual(response["status"] as? Int, 401)
    }

    func testStatusAndExplainPreserveTheExtensionContract() async throws {
        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [_BridgeProtocol.self]
        let client = BrainClient(
            base: URL(string: "https://brain.example")!,
            token: { "caller-token" },
            session: URLSession(configuration: config),
            retryDelay: .milliseconds(1)
        )

        let status = await ExtensionBridgeCommand.handle(
            try decode(#"{"action":"status"}"#),
            tokenReader: { "caller-token" },
            client: client
        )
        let statusData = try XCTUnwrap(status["data"] as? [String: Any])
        XCTAssertEqual(status["ok"] as? Bool, true)
        XCTAssertEqual(statusData["repo"] as? String, "acme/api")
        XCTAssertEqual(statusData["private"] as? Bool, true)

        let explain = await ExtensionBridgeCommand.handle(
            try decode(
                #"{"action":"explain","payload":{"repo":"acme/api","path":"src/auth.ts","start":4,"end":8,"question":"Why?"}}"#
            ),
            tokenReader: { "caller-token" },
            client: client
        )
        let explainData = try XCTUnwrap(explain["data"] as? [String: Any])
        XCTAssertEqual(explain["ok"] as? Bool, true)
        XCTAssertEqual(explainData["verdict"] as? String, "answer")
        let citations = try XCTUnwrap(explainData["citations"] as? [[String: Any]])
        XCTAssertEqual(citations.first?["ref"] as? String, "pr:42")
    }

    private func decode(_ json: String) throws -> NativeBridgeRequest {
        try JSONDecoder().decode(NativeBridgeRequest.self, from: Data(json.utf8))
    }
}

private final class _BridgeProtocol: URLProtocol {
    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }

    override func startLoading() {
        let body: Data
        if request.url?.path == "/status" {
            body = Data(
                #"{"state":"ready","repo":"acme/api","commit":"abc123","counts":null,"error":null,"private":true}"#.utf8
            )
        } else {
            body = Data(
                #"{"verdict":"answer","answer":"Because retries duplicated invoices.","citations":[{"ref":"pr:42","url":"https://github.com/acme/api/pull/42","excerpt":"Retries duplicated invoices."}],"searched":["pr:42"],"anchored":["pr:42"],"indexing":false}"#.utf8
            )
        }
        let response = HTTPURLResponse(
            url: request.url!, statusCode: 200,
            httpVersion: nil, headerFields: nil
        )!
        client?.urlProtocol(
            self, didReceive: response, cacheStoragePolicy: .notAllowed
        )
        client?.urlProtocol(self, didLoad: body)
        client?.urlProtocolDidFinishLoading(self)
    }

    override func stopLoading() {}
}
