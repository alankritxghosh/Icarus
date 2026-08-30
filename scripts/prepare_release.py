#!/usr/bin/env python3
"""Prepare one already-verified Icarus release without publishing it.

This is the local, reversible bridge between a notarized DMG + signed Sparkle
appcast and the committed release metadata. It performs no network upload,
Git operation, deployment, or account mutation. The public release is still a
separate, explicitly-authorized Gate 6 action.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
SPARKLE = "{http://www.andymatuschak.org/xml-namespaces/sparkle}"


class ReleasePreparationError(ValueError):
    """A candidate or release-metadata invariant failed."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _require_file(path: Path, expected_name: str) -> Path:
    path = path.resolve()
    if path.name != expected_name or not path.is_file():
        raise ReleasePreparationError(
            f"expected readable {expected_name}, got {path}")
    return path


def _verified_appcast(path: Path, *, version: str, build: str, url: str,
                      dmg_bytes: int) -> tuple[bytes, str]:
    raw = path.read_bytes()
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise ReleasePreparationError("signed appcast is not valid XML") from exc
    items = root.findall("./channel/item")
    if len(items) != 1:
        raise ReleasePreparationError("signed appcast must contain exactly one item")
    item = items[0]
    values = {
        "title": item.findtext("title"),
        "version": item.findtext(f"{SPARKLE}version"),
        "shortVersion": item.findtext(f"{SPARKLE}shortVersionString"),
    }
    expected = {"title": version, "version": build, "shortVersion": version}
    if values != expected:
        raise ReleasePreparationError(
            f"signed appcast version fields are {values}, expected {expected}")
    enclosures = item.findall("enclosure")
    if len(enclosures) != 1:
        raise ReleasePreparationError("signed appcast must contain one enclosure")
    enclosure = enclosures[0]
    if enclosure.get("url") != url:
        raise ReleasePreparationError("signed appcast URL does not match assets base")
    if enclosure.get("length") != str(dmg_bytes):
        raise ReleasePreparationError("signed appcast length does not match the DMG")
    signature = enclosure.get(f"{SPARKLE}edSignature", "")
    try:
        decoded = base64.b64decode(signature, validate=True)
    except ValueError as exc:
        raise ReleasePreparationError("Sparkle signature is not valid base64") from exc
    if len(decoded) != 64:
        raise ReleasePreparationError("Sparkle Ed25519 signature must be 64 bytes")
    return raw, signature


def _replace_exact(source: str, pattern: str, replacement: str, label: str) -> str:
    updated, count = re.subn(pattern, replacement, source, flags=re.MULTILINE)
    if count != 1:
        raise ReleasePreparationError(f"expected exactly one {label}, found {count}")
    return updated


def _write_transaction(files: dict[Path, bytes]) -> None:
    originals = {path: path.read_bytes() for path in files}
    staged: dict[Path, Path] = {}
    try:
        for path, data in files.items():
            fd, raw_tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
            tmp = Path(raw_tmp)
            staged[path] = tmp
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
        for path, tmp in staged.items():
            os.replace(tmp, path)
    except Exception:
        for path, original in originals.items():
            path.write_bytes(original)
        raise
    finally:
        for tmp in staged.values():
            tmp.unlink(missing_ok=True)


def prepare_release(*, root: Path, dmg: Path, extension: Path,
                    signed_appcast: Path, version: str, build: str,
                    assets_base: str, verifier) -> dict:
    """Validate all candidate facts, then update the four committed consumers."""
    root = root.resolve()
    dmg = _require_file(dmg, "Icarus.dmg")
    extension = _require_file(extension, "icarus-extension.zip")
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]+){2}", version):
        raise ReleasePreparationError("version must look like 1.2.3")
    if not build.isdigit() or int(build) < 1:
        raise ReleasePreparationError("build must be a positive integer")
    assets_base = assets_base.rstrip("/")
    expected_suffix = f"/releases/download/v{version}"
    if not assets_base.startswith("https://github.com/") \
            or not assets_base.endswith(expected_suffix):
        raise ReleasePreparationError(
            f"assets base must be a GitHub release ending in {expected_suffix}")

    verifier(dmg)
    dmg_size = dmg.stat().st_size
    extension_size = extension.stat().st_size
    url = f"{assets_base}/{dmg.name}"
    appcast_raw, signature = _verified_appcast(
        signed_appcast, version=version, build=build, url=url,
        dmg_bytes=dmg_size,
    )
    manifest_path = root / "release.json"
    generated_path = root / "web" / "src" / "generated" / "release.json"
    installer_path = root / "web" / "public" / "install.sh"
    appcast_path = root / "web" / "public" / "appcast.xml"
    for path in (manifest_path, generated_path, installer_path, appcast_path):
        if not path.is_file():
            raise ReleasePreparationError(f"required release consumer is missing: {path}")

    old_manifest = json.loads(manifest_path.read_text())
    manifest = {
        "_comment": old_manifest.get("_comment", []),
        "version": version,
        "build": build,
        "url": url,
        "dmg": {"name": dmg.name, "bytes": dmg_size, "sha256": _sha256(dmg)},
        "extension": {
            "name": extension.name,
            "bytes": extension_size,
            "sha256": _sha256(extension),
        },
        "appcast": {"length": dmg_size, "edSignature": signature},
        "assets_base": assets_base,
    }
    manifest_raw = (json.dumps(manifest, indent=2) + "\n").encode()
    installer = installer_path.read_text()
    installer = _replace_exact(
        installer, r'^DMG_URL="[^"]*"$', f'DMG_URL="{url}"', "DMG_URL")
    installer = _replace_exact(
        installer, r'^EXPECTED_SHA="[0-9a-f]{64}"$',
        f'EXPECTED_SHA="{manifest["dmg"]["sha256"]}"', "EXPECTED_SHA")
    _write_transaction({
        manifest_path: manifest_raw,
        generated_path: manifest_raw,
        installer_path: installer.encode(),
        appcast_path: appcast_raw,
    })
    return manifest


def _distribution_verifier(dmg: Path) -> None:
    command = [str(ROOT / "mac" / "Icarus" / "scripts" /
                   "verify_distribution.sh"), str(dmg)]
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    if result.returncode:
        detail = (result.stderr or result.stdout).strip().splitlines()
        suffix = f": {detail[-1]}" if detail else ""
        raise ReleasePreparationError(f"distribution verification failed{suffix}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dmg", type=Path, required=True)
    parser.add_argument("--extension", type=Path, required=True)
    parser.add_argument("--signed-appcast", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--build", required=True)
    parser.add_argument("--assets-base", required=True)
    args = parser.parse_args()
    try:
        manifest = prepare_release(
            root=ROOT, dmg=args.dmg, extension=args.extension,
            signed_appcast=args.signed_appcast, version=args.version,
            build=args.build, assets_base=args.assets_base,
            verifier=_distribution_verifier,
        )
    except (OSError, ReleasePreparationError, json.JSONDecodeError) as exc:
        parser.exit(1, f"prepare_release: {exc}\n")
    print(
        f"prepared {manifest['version']} build {manifest['build']} locally; "
        "nothing was uploaded or deployed"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
