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
}
