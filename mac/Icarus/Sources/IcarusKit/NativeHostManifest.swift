import Foundation

public enum NativeHostManifestError: Error, Equatable {
    case invalidExtensionOrigin
    case invalidExecutable
}

/// Generates Chrome's per-user native-host manifest. The allowlist contains
/// exactly the extension that initiated the explicit install.
public enum NativeHostManifest {
    public static let hostName = "com.icarus.extension"
    private static let originPattern = try! NSRegularExpression(
        pattern: #"^chrome-extension://[a-p]{32}/$"#
    )

    public static func validatedOrigin(_ origin: String) throws -> String {
        let range = NSRange(origin.startIndex..<origin.endIndex, in: origin)
        guard originPattern.firstMatch(in: origin, range: range)?.range == range else {
            throw NativeHostManifestError.invalidExtensionOrigin
        }
        return origin
    }

    public static func extensionOrigin(fromInstallURL url: URL) throws -> String {
        guard url.scheme == "icarus", url.host == "install-extension-bridge",
              let components = URLComponents(url: url, resolvingAgainstBaseURL: false),
              let origin = components.queryItems?.first(where: { $0.name == "origin" })?.value
        else {
            throw NativeHostManifestError.invalidExtensionOrigin
        }
        return try validatedOrigin(origin)
    }

    public static func data(
        extensionOrigin: String,
        executableURL: URL
    ) throws -> Data {
        let origin = try validatedOrigin(extensionOrigin)
        guard executableURL.isFileURL, executableURL.path.hasPrefix("/") else {
            throw NativeHostManifestError.invalidExecutable
        }
        return try JSONSerialization.data(
            withJSONObject: [
                "name": hostName,
                "description": "Icarus Mac app bridge",
                "path": executableURL.path,
                "type": "stdio",
                "allowed_origins": [origin],
            ],
            options: [.prettyPrinted, .sortedKeys]
        )
    }

    @discardableResult
    public static func install(
        extensionOrigin: String,
        executableURL: URL,
        homeDirectory: URL = FileManager.default.homeDirectoryForCurrentUser
    ) throws -> URL {
        let manifest = try data(
            extensionOrigin: extensionOrigin,
            executableURL: executableURL
        )
        let directory = homeDirectory
            .appendingPathComponent("Library/Application Support/Google/Chrome/NativeMessagingHosts")
        try FileManager.default.createDirectory(
            at: directory, withIntermediateDirectories: true
        )
        let destination = directory.appendingPathComponent("\(hostName).json")
        try manifest.write(to: destination, options: .atomic)
        return destination
    }
}
