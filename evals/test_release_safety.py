"""Release distribution must be honest about the current unsigned launch path."""

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


class InstallerSafetyTests(unittest.TestCase):
    def test_unsigned_launch_installer_is_explicit_about_the_alpha_path(self):
        script = (ROOT / "web" / "public" / "install.sh").read_text()
        self.assertIn("not notarized by Apple", script)
        self.assertIn("Developer ID", script)
        self.assertIn("Read it before running it", script)
        self.assertNotIn("stapler validate", script)
        self.assertNotIn("spctl -a", script)
        self.assertNotIn("codesign --verify", script)
        self.assertNotIn("Developer ID Application:", script)

    def test_unsigned_installer_checks_checksum_before_installing(self):
        script = (ROOT / "web" / "public" / "install.sh").read_text()
        expected = script.index('EXPECTED_SHA="')
        actual = script.index('ACTUAL="$(shasum -a 256 "$TMP/Icarus.dmg"')
        mismatch = script.index("Checksum mismatch - not installing.")
        attach = script.index('hdiutil attach "$TMP/Icarus.dmg"')
        copy = script.index('cp -R "$MNT/$APP" "$DEST/"')
        self.assertLess(expected, actual)
        self.assertLess(actual, mismatch)
        self.assertLess(mismatch, attach)
        self.assertLess(mismatch, copy)

    def test_old_vercel_release_script_fails_before_mutating_anything(self):
        script = (ROOT / "site" / "release-dmg.sh").read_text()
        retired = script.index("is retired")
        first_mutation = script.index('SRC=""')
        self.assertLess(retired, first_mutation)
        self.assertIn("exit 1", script[retired:first_mutation])

    def test_packager_points_to_the_independent_verifier_not_retired_publisher(self):
        script = (ROOT / "mac" / "Icarus" / "scripts" / "package_dmg.sh").read_text()
        self.assertIn("verify_distribution.sh", script)
        self.assertNotIn('"${ROOT}/../../site/release-dmg.sh"', script)

    def test_self_signed_hardened_app_allows_bundled_sparkle_framework(self):
        entitlements = (ROOT / "mac" / "Icarus" / "Icarus.entitlements").read_text()
        bundle = (ROOT / "mac" / "Icarus" / "scripts" / "bundle.sh").read_text()
        package = (ROOT / "mac" / "Icarus" / "scripts" / "package_dmg.sh").read_text()
        self.assertIn("com.apple.security.cs.disable-library-validation", entitlements)
        self.assertIn("--entitlements", bundle)
        self.assertIn("Icarus.entitlements", bundle)
        self.assertIn("--entitlements", package)
        self.assertIn("Icarus.entitlements", package)

    def test_remote_release_checker_cannot_stamp_from_nonexistent_local_assets(self):
        script = (ROOT / "scripts" / "check_release.py").read_text()
        self.assertNotIn("def write()", script)
        self.assertNotIn('if "--write" in sys.argv', script)

    def test_website_redirects_come_from_the_release_manifest(self):
        config = (ROOT / "web" / "next.config.ts").read_text()
        self.assertIn('from "./src/generated/release.json"', config)
        self.assertIn("destination: release.url", config)
        self.assertNotRegex(config, r"releases/download/v\d+\.\d+\.\d+")

    def test_website_sets_baseline_browser_security_headers(self):
        config = (ROOT / "web" / "next.config.ts").read_text()
        for header in (
            "Strict-Transport-Security", "X-Content-Type-Options",
            "X-Frame-Options", "Referrer-Policy", "Permissions-Policy",
            "Content-Security-Policy",
        ):
            self.assertIn(header, config)
        for boundary in (
            "object-src 'none'", "frame-ancestors 'none'", "form-action 'self'",
            "connect-src 'self'", "base-uri 'self'",
        ):
            self.assertIn(boundary, config)
        self.assertIn("poweredByHeader: false", config)

    def test_site_deployer_uses_unpredictable_temporary_files(self):
        script = (ROOT / "scripts" / "deploy_site.sh").read_text()
        self.assertIn("mktemp -d", script)
        self.assertNotIn("/tmp/icarus_site_build.log", script)
        self.assertNotIn("/tmp/icarus_vercel.log", script)


if __name__ == "__main__":
    unittest.main()
