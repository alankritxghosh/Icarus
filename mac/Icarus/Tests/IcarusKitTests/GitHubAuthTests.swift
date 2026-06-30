import XCTest
@testable import IcarusKit

/// GitHub OAuth Device Flow: the device-code response decode and the token-poll
/// parser. Pure, deterministic — the part worth unit-testing (the live HTTP is thin).
final class GitHubAuthTests: XCTestCase {

    func testDecodesDeviceCodeResponse() throws {
        let json = Data("""
        {"device_code":"3584d83530557fdd1f46af8289938c8ef79f9dc5",
         "user_code":"WDJB-MJHT",
         "verification_uri":"https://github.com/login/device",
         "expires_in":900,
         "interval":5}
        """.utf8)
        let r = try JSONDecoder().decode(DeviceCodeResponse.self, from: json)
        XCTAssertEqual(r.userCode, "WDJB-MJHT")
        XCTAssertEqual(r.verificationUri, "https://github.com/login/device")
        XCTAssertEqual(r.interval, 5)
        XCTAssertEqual(r.expiresIn, 900)
        XCTAssertFalse(r.deviceCode.isEmpty)
    }

    func testParsePollToken() {
        let data = Data(#"{"access_token":"gho_abc123","token_type":"bearer","scope":"read:user"}"#.utf8)
        XCTAssertEqual(GitHubDeviceAuth.parsePoll(data), .token("gho_abc123"))
    }

    func testParsePollPending() {
        let data = Data(#"{"error":"authorization_pending"}"#.utf8)
        XCTAssertEqual(GitHubDeviceAuth.parsePoll(data), .pending)
    }

    func testParsePollSlowDownCarriesInterval() {
        let data = Data(#"{"error":"slow_down","interval":10}"#.utf8)
        XCTAssertEqual(GitHubDeviceAuth.parsePoll(data), .slowDown(interval: 10))
    }

    func testParsePollExpiredAndDenied() {
        XCTAssertEqual(GitHubDeviceAuth.parsePoll(Data(#"{"error":"expired_token"}"#.utf8)), .expired)
        XCTAssertEqual(GitHubDeviceAuth.parsePoll(Data(#"{"error":"access_denied"}"#.utf8)), .denied)
    }

    func testParsePollUnknownErrorAndGarbageFailSafe() {
        if case .error = GitHubDeviceAuth.parsePoll(Data(#"{"error":"weird_thing"}"#.utf8)) {} else {
            XCTFail("unknown error should map to .error")
        }
        if case .error = GitHubDeviceAuth.parsePoll(Data("not json".utf8)) {} else {
            XCTFail("garbage should fail safe to .error, never .token")
        }
    }
}
