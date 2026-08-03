// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "Icarus",
    platforms: [.macOS(.v14)],
    dependencies: [
        .package(url: "https://github.com/sindresorhus/KeyboardShortcuts", from: "2.0.0"),
        // In-app updates. Sparkle signs its own update feed with an EdDSA key,
        // so it does NOT need an Apple Developer ID -- which is the whole
        // reason it fits here: shipping a fix currently means emailing every
        // tester and asking them to re-download and re-clear Gatekeeper.
        .package(url: "https://github.com/sparkle-project/Sparkle", from: "2.6.0"),
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
                .product(name: "Sparkle", package: "Sparkle"),
            ],
            path: "Sources/Icarus"
        ),
        .testTarget(name: "IcarusKitTests", dependencies: ["IcarusKit"], path: "Tests/IcarusKitTests"),
        .testTarget(name: "IcarusAppTests", dependencies: ["Icarus"], path: "Tests/IcarusAppTests"),
    ]
)
