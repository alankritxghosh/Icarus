import Foundation
import IcarusKit

/// Headless credential bridge used by the Icarus MCP adapter.
///
/// The GitHub credential is read by the app and sent only to the Icarus brain.
/// Stdout contains a short-lived, repository-bound, read-only Icarus session,
/// never the Keychain credential.
enum AgentSessionCommand {
    private struct Output: Encodable {
        let brainURL: String
        let token: String
        let expiresAt: TimeInterval
        let repo: String

        enum CodingKeys: String, CodingKey {
            case brainURL = "brain_url"
            case token
            case expiresAt = "expires_at"
            case repo
        }
    }

    static var requested: Bool {
        CommandLine.arguments.dropFirst().contains("--agent-session")
    }

    static func run() async -> Int32 {
        guard let githubToken = AppConfig.tokenReader(), !githubToken.isEmpty else {
            writeError("Icarus is signed out. Open the app and sign in with GitHub.")
            return 1
        }
        do {
            let session = try await AppConfig.client().createAgentSession()
            let output = Output(
                brainURL: AppConfig.brainBaseURL.absoluteString,
                token: session.token,
                expiresAt: session.expiresAt,
                repo: session.repo
            )
            var data = try JSONEncoder().encode(output)
            data.append(0x0A)
            FileHandle.standardOutput.write(data)
            return 0
        } catch BrainError.forbidden {
            writeError("Icarus agent access requires an active repository you can read.")
            return 1
        } catch BrainError.unauthorized {
            writeError("Icarus sign-in expired. Open the app and sign in again.")
            return 1
        } catch {
            writeError("Icarus could not create an agent session. Try again.")
            return 1
        }
    }

    private static func writeError(_ message: String) {
        FileHandle.standardError.write(Data((message + "\n").utf8))
    }
}
