import XCTest
import IcarusKit
@testable import Icarus

@MainActor
final class SettingsViewTests: XCTestCase {
    func testFailedDisconnectMessageIsPreservedForTheSettingsSurface() {
        let message = "The server did not confirm deleting your data."
        XCTAssertEqual(
            SettingsView.repositoryStateMessage(for: .failed(message)),
            message
        )
    }

    func testSettingsRejectsStatusCountsFromAnotherRepository() throws {
        let status = try JSONDecoder().decode(
            RepoStatus.self,
            from: Data(
                #"{"state":"ready","repo":"acme/old","commit":"abc","counts":{"pr":42,"issue":3,"code":7},"error":null}"#.utf8
            )
        )

        XCTAssertNil(SettingsView.matchingStatus(status, for: "acme/new"))
        XCTAssertEqual(SettingsView.matchingStatus(status, for: "ACME/OLD")?.counts?.pr, 42)
    }
}
