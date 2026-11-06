#!/usr/bin/env python3
"""Restore version-pinned EasyEDA release assets without starting any service."""
import hashlib
import json
import os
from pathlib import Path
import platform
import tempfile
from urllib.request import urlopen


def install_asset(asset, destination):
    expected = asset["digest"]
    if not expected.startswith("sha256:"):
        raise ValueError("Release asset has no SHA-256 digest")
    if destination.exists():
        actual = "sha256:" + hashlib.sha256(destination.read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f"Existing file differs from pinned release; preserved: {destination}")
        return
    with urlopen(asset["browser_download_url"], timeout=120) as response:
        data = response.read()
    if "sha256:" + hashlib.sha256(data).hexdigest() != expected:
        raise ValueError(f"Release checksum mismatch: {destination.name}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as output:
        temporary = Path(output.name)
        output.write(data)
    try:
        os.link(temporary, destination)  # Publish complete bytes without replacing another file.
    finally:
        temporary.unlink()


def main():
    root = Path(__file__).resolve().parent
    release = json.loads((root / "release-v0.21.7.json").read_text())
    system = platform.system().lower()
    architecture = {"aarch64": "arm64", "arm64": "arm64", "x86_64": "amd64", "amd64": "amd64"}.get(platform.machine().lower())
    extension = ".exe" if system == "windows" else ""
    assets = {asset["name"]: asset for asset in release["assets"]}
    binary = f"easyeda_{system}_{architecture}{extension}"
    if binary not in assets:
        raise SystemExit(f"No pinned release asset for {system}/{platform.machine()}")
    destination = root / "bin" / f"easyeda{extension}"
    install_asset(assets[binary], destination)
    destination.chmod(0o755)
    connector = root / "easyeda-agent-connector-v0.21.7.eext"
    install_asset(assets["easyeda-agent-connector.eext"], connector)
    print(f"Verified {release['tag_name']}: {destination.name} and {connector.name}")


if __name__ == "__main__":
    main()
