"""Final-user distribution must never regress to the alpha bypass path."""

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


class InstallerSafetyTests(unittest.TestCase):
    def test_installer_requires_apple_and_developer_id_verification(self):
        script = (ROOT / "web" / "public" / "install.sh").read_text()
        self.assertIn("stapler validate", script)
        self.assertIn("spctl -a", script)
        self.assertIn("codesign --verify", script)
        self.assertIn("Developer ID Application:", script)

    def test_installer_does_not_bypass_gatekeeper_or_delete_the_old_app_first(self):
        script = (ROOT / "web" / "public" / "install.sh").read_text()
        self.assertNotIn("xattr -dr", script)
        self.assertNotIn('rm -rf "${DEST:?}/$APP"', script)
        self.assertIn("Icarus.previous.app", script)

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
