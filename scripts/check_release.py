#!/usr/bin/env python3
"""Prove every place that states a release fact still agrees with release.json.

The same sha256 and byte size were copy-pasted into the website, install.sh and
the Sparkle appcast, and nothing verified they matched. That is not theoretical
here: release-dmg.sh's unanchored stamping regex overwrote the browser
extension's checksum with the DMG's for two releases before anyone noticed.

Checks, all of them against the REAL files on disk:

  1. the DMG exists, and its sha256 and byte count match release.json
  2. the extension zip likewise
  3. appcast.xml's `length=` equals the DMG's real size -- Sparkle refuses an
     update whose length disagrees, so a wrong number here breaks in-app
     updates for every installed copy, silently
  4. install.sh's EXPECTED_SHA equals the DMG's real sha256 -- otherwise the
     installer aborts with "the download was corrupted", which is exactly the
     failure the site shipped for weeks in 2026-08
  5. the appcast points at the URL release.json names

Exits non-zero on any mismatch, so it can gate a deploy.

  python3 scripts/check_release.py            # verify
  python3 scripts/check_release.py --write    # re-stamp release.json from disk
  python3 scripts/check_release.py --selftest # prove the checker can FAIL
"""
import hashlib
import json
import pathlib
import re
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "web" / "public"
MANIFEST = ROOT / "release.json"


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(quiet: bool = False) -> list[str]:
    """Return a list of problems. Empty means everything agrees."""
    problems: list[str] = []
    say = (lambda *_a: None) if quiet else print

    if not MANIFEST.exists():
        return [f"{MANIFEST.name} is missing"]
    m = json.loads(MANIFEST.read_text())

    # The binaries are no longer in the repo OR on the site: they live in
    # GitHub Releases. So verify the thing the world actually downloads, not a
    # local copy of it that may or may not be the same file.
    base = m["assets_base"]
    for key in ("dmg", "extension"):
        spec = m[key]
        url = f"{base}/{spec['name']}"
        try:
            with urllib.request.urlopen(url, timeout=180) as r:
                blob = r.read()
        except Exception as e:                                  # noqa: BLE001
            problems.append(f"{spec['name']}: cannot download {url} ({e})")
            continue
        size, digest = len(blob), hashlib.sha256(blob).hexdigest()
        if size != spec["bytes"]:
            problems.append(f"{spec['name']}: release serves {size} bytes, release.json says {spec['bytes']}")
        elif digest != spec["sha256"]:
            problems.append(f"{spec['name']}: release sha256 {digest[:12]}…, release.json says {spec['sha256'][:12]}…")
        else:
            say(f"  ok  {spec['name']}  {size} bytes  {digest[:12]}…  (from the release)")

    # The app ships a committed copy of this manifest, because a CLI deploy
    # uploads only web/ and the build machine never sees the repo root. Assert
    # the two are identical, or the website can quietly state a release fact
    # that release.json disagrees with -- which is the whole thing this file
    # exists to prevent.
    generated = ROOT / "web" / "src" / "generated" / "release.json"
    if not generated.exists():
        problems.append("web/src/generated/release.json is missing; run web/scripts/sync-release.mjs")
    elif json.loads(generated.read_text()) != m:
        problems.append(
            "web/src/generated/release.json differs from release.json. The site "
            "would render stale release facts. Run: node web/scripts/sync-release.mjs"
        )
    else:
        say("  ok  web/src/generated/release.json matches")

    appcast = (PUBLIC / "appcast.xml").read_text()
    installer = installer_url_src = (PUBLIC / "install.sh").read_text()
    length = re.search(r'length="(\d+)"', appcast)
    if not length:
        problems.append("appcast.xml has no enclosure length")
    elif int(length.group(1)) != m["dmg"]["bytes"]:
        problems.append(
            f"appcast.xml length={length.group(1)} but the DMG is {m['dmg']['bytes']} bytes. "
            f"Sparkle refuses a mismatched length, so in-app updates would break silently."
        )
    else:
        say(f"  ok  appcast.xml length={length.group(1)}")

    if m["url"] not in appcast:
        problems.append(
            f"appcast.xml does not point at {m['url']}. Sparkle would fetch the "
            f"wrong file, or none."
        )
    else:
        say("  ok  appcast.xml enclosure url (GitHub Releases)")

    if m["url"] not in installer_url_src:
        problems.append(f"install.sh does not download from {m['url']}")
    else:
        say("  ok  install.sh DMG_URL")

    expected = re.search(r'EXPECTED_SHA="([0-9a-f]{64})"', installer)
    if not expected:
        problems.append("install.sh has no EXPECTED_SHA")
    elif expected.group(1) != m["dmg"]["sha256"]:
        problems.append(
            f"install.sh EXPECTED_SHA is {expected.group(1)[:12]}… but the DMG is "
            f"{m['dmg']['sha256'][:12]}…. The installer would abort on every run."
        )
    else:
        say("  ok  install.sh EXPECTED_SHA")

    return problems


def write() -> None:
    m = json.loads(MANIFEST.read_text())
    for key in ("dmg", "extension"):
        f = PUBLIC / m[key]["name"]
        m[key]["bytes"], m[key]["sha256"] = f.stat().st_size, sha256(f)
    MANIFEST.write_text(json.dumps(m, indent=2) + "\n")
    print(f"release.json re-stamped from disk: {m['dmg']['sha256'][:12]}…, {m['dmg']['bytes']} bytes")


def selftest() -> int:
    """A passing checker means nothing until it has been shown to fail.

    The binaries are remote now, so this cannot corrupt a file on disk. It
    corrupts the MANIFEST instead -- one character of the expected sha -- and
    asserts the check notices that what the release serves is not what
    release.json claims.
    """
    original = MANIFEST.read_text()
    m = json.loads(original)
    if check(quiet=True):
        print("selftest: cannot run, the real tree already has problems")
        return 1
    try:
        good = m["dmg"]["sha256"]
        m["dmg"]["sha256"] = ("0" if good[0] != "0" else "1") + good[1:]
        MANIFEST.write_text(json.dumps(m, indent=2) + "\n")
        after = check(quiet=True)
        if not after:
            print("selftest FAILED: a wrong sha in release.json tripped nothing")
            return 1
        print("selftest ok: a one-character sha change trips", len(after), "check(s)")
        return 0
    finally:
        MANIFEST.write_text(original)


if __name__ == "__main__":
    if "--write" in sys.argv:
        write()
        sys.exit(0)
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    print("release check:")
    found = check()
    if found:
        print("\nrelease check FAILED:")
        for p in found:
            print("  ✗", p)
        sys.exit(1)
    print("release check clean.")
