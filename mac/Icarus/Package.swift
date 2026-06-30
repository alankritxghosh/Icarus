// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "Icarus",
    platforms: [.macOS(.v14)],
    targets: [
        .executableTarget(name: "Icarus", path: "Sources/Icarus")
    ]
)
