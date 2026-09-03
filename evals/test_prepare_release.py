"""The final release handoff is local, deterministic, and fail-closed."""

import base64
import json
from pathlib import Path
import tempfile
import unittest

from scripts.prepare_release import ReleasePreparationError, prepare_release


class PrepareReleaseTests(unittest.TestCase):
    VERSION = "1.2.3"
    BUILD = "42"
    BASE = "https://github.com/example/Icarus/releases/download/v1.2.3"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        public = self.root / "web" / "public"
        generated = self.root / "web" / "src" / "generated"
        public.mkdir(parents=True)
        generated.mkdir(parents=True)
        (self.root / "release.json").write_text(json.dumps({"_comment": ["truth"]}))
        (generated / "release.json").write_text("{}")
        (public / "install.sh").write_text(
            '#!/bin/sh\nDMG_URL="https://old/Icarus.dmg"\n'
            f'EXPECTED_SHA="{"0" * 64}"\n')
        (public / "appcast.xml").write_text("<old/>")
        self.dmg = self.root / "Icarus.dmg"
        self.extension = self.root / "icarus-extension.zip"
        self.appcast = self.root / "signed-appcast.xml"
        self.dmg.write_bytes(b"notarized-candidate")
        self.extension.write_bytes(b"extension-candidate")
        signature = base64.b64encode(bytes(range(64))).decode()
        self.appcast.write_text(
            '<?xml version="1.0"?><rss '
            'xmlns:sparkle="http://www.andymatuschak.org/xml-namespaces/sparkle">'
            '<channel><item><title>1.2.3</title>'
            '<sparkle:version>42</sparkle:version>'
            '<sparkle:shortVersionString>1.2.3</sparkle:shortVersionString>'
            f'<enclosure url="{self.BASE}/Icarus.dmg" '
            f'length="{self.dmg.stat().st_size}" '
            f'sparkle:edSignature="{signature}"/></item></channel></rss>')

    def _prepare(self, verifier=lambda _path: None):
        return prepare_release(
            root=self.root, dmg=self.dmg, extension=self.extension,
            signed_appcast=self.appcast, version=self.VERSION, build=self.BUILD,
            assets_base=self.BASE, verifier=verifier)

    def test_one_verified_candidate_updates_every_committed_consumer(self):
        verified = []
        manifest = self._prepare(verifier=lambda path: verified.append(path))
        self.assertEqual(verified, [self.dmg.resolve()])
        committed = json.loads((self.root / "release.json").read_text())
        generated = json.loads(
            (self.root / "web" / "src" / "generated" / "release.json").read_text())
        self.assertEqual(committed, manifest)
        self.assertEqual(generated, manifest)
        self.assertEqual(committed["appcast"]["length"], self.dmg.stat().st_size)
        installer = (self.root / "web" / "public" / "install.sh").read_text()
        self.assertIn(f'DMG_URL="{self.BASE}/Icarus.dmg"', installer)
        self.assertIn(f'EXPECTED_SHA="{manifest["dmg"]["sha256"]}"', installer)
        self.assertEqual(
            (self.root / "web" / "public" / "appcast.xml").read_bytes(),
            self.appcast.read_bytes())

    def test_distribution_rejection_changes_nothing(self):
        before = (self.root / "release.json").read_bytes()

        def reject(_path):
            raise ReleasePreparationError("not notarized")

        with self.assertRaisesRegex(ReleasePreparationError, "not notarized"):
            self._prepare(verifier=reject)
        self.assertEqual((self.root / "release.json").read_bytes(), before)

    def test_appcast_for_different_bytes_changes_nothing(self):
        before = (self.root / "release.json").read_bytes()
        raw = self.appcast.read_text().replace(
            f'length="{self.dmg.stat().st_size}"', 'length="999"')
        self.appcast.write_text(raw)
        with self.assertRaisesRegex(ReleasePreparationError, "length"):
            self._prepare()
        self.assertEqual((self.root / "release.json").read_bytes(), before)

    def test_release_url_must_name_the_same_version(self):
        with self.assertRaisesRegex(ReleasePreparationError, "ending"):
            prepare_release(
                root=self.root, dmg=self.dmg, extension=self.extension,
                signed_appcast=self.appcast, version=self.VERSION, build=self.BUILD,
                assets_base=self.BASE.replace("v1.2.3", "v1.2.2"),
                verifier=lambda _path: None)


if __name__ == "__main__":
    unittest.main()
