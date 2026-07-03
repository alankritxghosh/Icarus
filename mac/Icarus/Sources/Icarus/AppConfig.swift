import Foundation
import IcarusKit

/// App-wide configuration read from the bundle at launch. `brainBaseURL` points
/// at the hosted brain in a shipped build (Info.plist key `ICARUS_BRAIN_URL`,
/// stamped in by `scripts/package_dmg.sh`) and at the local brain otherwise, so
/// `swift run` and a plain `bundle.sh` build keep talking to 127.0.0.1:8000.
enum AppConfig {
    static let brainBaseURL: URL = BrainEndpoint.resolve(from: Bundle.main.infoDictionary)
}
