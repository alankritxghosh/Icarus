// swift-tools-version: 5.10
import PackageDescription

let package = Package(
    name: "Icarus",
    platforms: [.macOS(.v14)],
    dependencies: [
        .package(url: "https://github.com/sindresorhus/KeyboardShortcuts", from: "2.0.0"),
        // Voice-in uses Apple's on-device Speech framework (SFSpeechRecognizer) for
        // real-time streaming dictation — no third-party STT dependency.
    ],
    targets: [
        // Testable, UI-free logic (the brain contract + HTTP client).
        .target(name: "IcarusKit", path: "Sources/IcarusKit"),
        // The app shell (menu bar, hotkey, overlay) — depends on the kit.
        .executableTarget(
            name: "Icarus",
            dependencies: [
                "IcarusKit",
                .product(name: "KeyboardShortcuts", package: "KeyboardShortcuts"),
            ],
            path: "Sources/Icarus"
        ),
        .testTarget(name: "IcarusKitTests", dependencies: ["IcarusKit"], path: "Tests/IcarusKitTests"),
    ]
)
