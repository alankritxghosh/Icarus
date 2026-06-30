import Foundation

/// GitHub's response to the device-code request (step 1 of OAuth Device Flow).
public struct DeviceCodeResponse: Decodable, Sendable {
    public let deviceCode: String
    public let userCode: String
    public let verificationUri: String
    public let interval: Int
    public let expiresIn: Int

    enum CodingKeys: String, CodingKey {
        case deviceCode = "device_code"
        case userCode = "user_code"
        case verificationUri = "verification_uri"
        case interval
        case expiresIn = "expires_in"
    }
}

/// The result of one token poll. Fails safe: anything unrecognized is `.error`,
/// never `.token` — we never pretend to be authenticated.
public enum PollOutcome: Sendable, Equatable {
    case pending              // authorization_pending — keep polling
    case slowDown(interval: Int) // slow_down — back off to this interval
    case token(String)        // success
    case denied               // access_denied — user rejected
    case expired              // expired_token — start over
    case error(String)        // anything else
}

/// OAuth Device Flow client. The two `async` methods are thin wrappers over the
/// pure, unit-tested parsers (`DeviceCodeResponse` decode + `parsePoll`).
public enum GitHubDeviceAuth {
    static let deviceCodeURL = URL(string: "https://github.com/login/device/code")!
    static let tokenURL = URL(string: "https://github.com/login/oauth/access_token")!

    /// Pure parser: map GitHub's token-poll JSON to a `PollOutcome`. Deterministic.
    public static func parsePoll(_ data: Data) -> PollOutcome {
        struct Raw: Decodable {
            let access_token: String?
            let error: String?
            let interval: Int?
        }
        guard let raw = try? JSONDecoder().decode(Raw.self, from: data) else {
            return .error("unparseable")
        }
        if let token = raw.access_token, !token.isEmpty { return .token(token) }
        switch raw.error {
        case "authorization_pending": return .pending
        case "slow_down": return .slowDown(interval: raw.interval ?? 5)
        case "expired_token": return .expired
        case "access_denied": return .denied
        case let other?: return .error(other)
        case nil: return .error("no token and no error")
        }
    }

    /// Step 1: ask GitHub for a device + user code. `scope` defaults to identity only
    /// (`read:user`) — public repos only; deliberately NOT requesting `repo`.
    public static func requestDeviceCode(clientID: String, scope: String = "read:user") async throws -> DeviceCodeResponse {
        var request = URLRequest(url: deviceCodeURL)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: ["client_id": clientID, "scope": scope])
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse, http.statusCode == 200 else {
            throw URLError(.badServerResponse)
        }
        return try JSONDecoder().decode(DeviceCodeResponse.self, from: data)
    }

    /// Step 2 (one tick): poll once for the token. Caller loops on `.pending`/`.slowDown`
    /// honoring `interval`. Returns a `PollOutcome` via the pure parser.
    public static func pollOnce(clientID: String, deviceCode: String) async throws -> PollOutcome {
        var request = URLRequest(url: tokenURL)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: [
            "client_id": clientID,
            "device_code": deviceCode,
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
        ])
        let (data, _) = try await URLSession.shared.data(for: request)
        return parsePoll(data)
    }
}
