import XCTest
@testable import IcarusKit

final class NativeBridgeCodecTests: XCTestCase {
    func testRoundTripsOneLengthPrefixedMessage() throws {
        let json = Data(#"{"action":"ping"}"#.utf8)
        let framed = try NativeMessageCodec.frame(json)
        let pipe = Pipe()
        try pipe.fileHandleForWriting.write(contentsOf: framed)
        try pipe.fileHandleForWriting.close()
        XCTAssertEqual(
            try NativeMessageCodec.readMessage(from: pipe.fileHandleForReading),
            json
        )
    }

    func testProductionReaderRejectsMalformedAndOversizedMessages() throws {
        let malformed = Pipe()
        try malformed.fileHandleForWriting.write(contentsOf: Data([1, 2, 3]))
        try malformed.fileHandleForWriting.close()
        XCTAssertThrowsError(
            try NativeMessageCodec.readMessage(from: malformed.fileHandleForReading)
        )

        var oversizedLength = UInt32(65_537).littleEndian
        let oversized = Pipe()
        try oversized.fileHandleForWriting.write(
            contentsOf: Data(bytes: &oversizedLength, count: 4)
        )
        try oversized.fileHandleForWriting.close()
        XCTAssertThrowsError(
            try NativeMessageCodec.readMessage(from: oversized.fileHandleForReading)
        )
    }

    func testProductionReaderConsumesOnlyTheFirstFrameForTheOneShotProcess() throws {
        let first = Data(#"{"action":"ping"}"#.utf8)
        let trailing = Data(#"{"action":"status"}"#.utf8)
        var input = try NativeMessageCodec.frame(first)
        input.append(try NativeMessageCodec.frame(trailing))
        let pipe = Pipe()
        try pipe.fileHandleForWriting.write(contentsOf: input)
        try pipe.fileHandleForWriting.close()

        XCTAssertEqual(
            try NativeMessageCodec.readMessage(from: pipe.fileHandleForReading),
            first
        )
    }

    func testUnknownActionFailsClosed() {
        let json = Data(#"{"action":"readKeychain"}"#.utf8)
        XCTAssertThrowsError(try JSONDecoder().decode(NativeBridgeRequest.self, from: json))
    }
}

final class NativeHostManifestTests: XCTestCase {
    func testManifestAllowlistsOnlyTheExactChromeExtensionOrigin() throws {
        let executable = URL(fileURLWithPath: "/Applications/Icarus.app/Contents/MacOS/Icarus")
        let data = try NativeHostManifest.data(
            extensionOrigin: "chrome-extension://abcdefghijklmnopabcdefghijklmnop/",
            executableURL: executable
        )
        let json = try XCTUnwrap(
            JSONSerialization.jsonObject(with: data) as? [String: Any]
        )

        XCTAssertEqual(json["name"] as? String, "com.icarus.extension")
        XCTAssertEqual(json["type"] as? String, "stdio")
        XCTAssertEqual(json["path"] as? String, executable.path)
        XCTAssertEqual(
            json["allowed_origins"] as? [String],
            ["chrome-extension://abcdefghijklmnopabcdefghijklmnop/"]
        )
    }

    func testRefusesNonExtensionAndNonCanonicalOrigins() {
        let executable = URL(fileURLWithPath: "/Applications/Icarus.app/Contents/MacOS/Icarus")
        for origin in [
            "https://evil.example/",
            "chrome-extension://abcdefghijklmnopabcdefghijklmnop/extra",
            "chrome-extension://ABCDEFGHIJKLMNOPABCDEFGHIJKLMNOP/",
            "chrome-extension://short/",
        ] {
            XCTAssertThrowsError(
                try NativeHostManifest.data(
                    extensionOrigin: origin,
                    executableURL: executable
                ),
                origin
            )
        }
    }

    func testInstallURLCarriesOnlyAValidatedOrigin() throws {
        let valid = URL(
            string: "icarus://install-extension-bridge?origin=chrome-extension%3A%2F%2Fabcdefghijklmnopabcdefghijklmnop%2F"
        )!
        XCTAssertEqual(
            try NativeHostManifest.extensionOrigin(fromInstallURL: valid),
            "chrome-extension://abcdefghijklmnopabcdefghijklmnop/"
        )

        for invalid in [
            URL(string: "https://install-extension-bridge?origin=chrome-extension%3A%2F%2Fabcdefghijklmnopabcdefghijklmnop%2F")!,
            URL(string: "icarus://other?origin=chrome-extension%3A%2F%2Fabcdefghijklmnopabcdefghijklmnop%2F")!,
            URL(string: "icarus://install-extension-bridge?origin=https%3A%2F%2Fevil.example%2F")!,
        ] {
            XCTAssertThrowsError(
                try NativeHostManifest.extensionOrigin(fromInstallURL: invalid)
            )
        }
    }
}
