import Foundation
import IcarusKit

/// One-process/one-request Chrome native-messaging bridge.
///
/// The extension receives cited answer/status JSON, never the GitHub token.
/// Chrome supplies the calling extension origin in argv; only the canonical
/// allowlisted origin shape is accepted here as defense in depth.
enum ExtensionBridgeCommand {
    static var requestedOrigin: String? {
        for argument in CommandLine.arguments.dropFirst()
            where argument.hasPrefix("chrome-extension://") {
            if let origin = try? NativeHostManifest.validatedOrigin(argument) {
                return origin
            }
        }
        return nil
    }

    static func run() async -> Int32 {
        guard requestedOrigin != nil else { return 1 }
        let response: [String: Any]
        do {
            let body = try NativeMessageCodec.readMessage(from: .standardInput)
            let request = try JSONDecoder().decode(NativeBridgeRequest.self, from: body)
            response = await handle(request)
        } catch NativeMessageCodecError.messageTooLarge {
            response = failure(status: 413, "native message is too large")
        } catch {
            response = failure(status: 400, "malformed native message")
        }

        do {
            let json = try JSONSerialization.data(withJSONObject: response)
            let framed = try NativeMessageCodec.frame(json)
            FileHandle.standardOutput.write(framed)
            return response["ok"] as? Bool == true ? 0 : 1
        } catch {
            return 1
        }
    }

    static func handle(
        _ request: NativeBridgeRequest,
        tokenReader: @Sendable () -> String? = AppConfig.tokenReader,
        client injectedClient: BrainClient? = nil
    ) async -> [String: Any] {
        if request.action == .ping {
            let token = tokenReader()
            return success([
                "app": "Icarus",
                "signed_in": token?.isEmpty == false,
            ])
        }
        guard let token = tokenReader(), !token.isEmpty else {
            return failure(status: 401, "Icarus Mac app is signed out")
        }
        let client = injectedClient ?? BrainClient(
            base: AppConfig.brainBaseURL, token: { token }
        )
        do {
            switch request.action {
            case .ping:
                return success(["app": "Icarus", "signed_in": true])
            case .status:
                let status = try await client.status()
                return success([
                    "state": status.state,
                    "repo": status.repo,
                    "commit": status.commit,
                    "private": status.isPrivate == true,
                    "indexing": status.isIndexing,
                ])
            case .explain:
                guard let payload = request.payload else {
                    return failure(status: 400, "explain payload is required")
                }
                let answer = try await client.explain(
                    repo: payload.repo,
                    path: payload.path,
                    start: payload.start,
                    end: payload.end,
                    question: payload.question
                )
                let citations: [[String: Any]] = answer.citations.map {
                    [
                        "ref": $0.ref,
                        "url": $0.url ?? NSNull(),
                        "excerpt": $0.excerpt ?? NSNull(),
                    ]
                }
                return success([
                    "verdict": answer.verdict.rawValue,
                    "answer": answer.answer,
                    "citations": citations,
                    "searched": answer.searched,
                    "anchored": answer.anchored ?? [],
                    "indexing": answer.indexing == true,
                ])
            }
        } catch let error as BrainError {
            switch error {
            case .unauthorized:
                return failure(status: 401, error.userMessage)
            case .forbidden:
                return failure(status: 403, error.userMessage)
            case .rateLimited, .refreshRateLimited, .memoryRateLimited:
                return failure(status: 429, error.userMessage)
            case .server(let status):
                return failure(status: status, error.userMessage)
            }
        } catch {
            return failure(status: 503, "Icarus's brain is unavailable")
        }
    }

    private static func success(_ data: [String: Any]) -> [String: Any] {
        ["ok": true, "status": 200, "data": data]
    }

    private static func failure(status: Int, _ error: String) -> [String: Any] {
        ["ok": false, "status": status, "error": error]
    }
}
