#!/usr/bin/env python3
"""Prepare the Emscripten toolchain used by the Web export templates."""

import io
from pathlib import Path
import subprocess
import sys
import tarfile
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
VERSION = "4.0.20"
RELEASE = "c387d7a7e9537d0041d2c3ae71b7538cc978104e"
SDK_COMMIT = "e4fe26ef59168ff44f4c23c466e497bf60b3411e"
SDK = ROOT / ".tools" / "emsdk"

if not (SDK / "emsdk.py").exists():
    request = urllib.request.Request(
        f"https://codeload.github.com/emscripten-core/emsdk/tar.gz/{SDK_COMMIT}",
        headers={"User-Agent": "leanclr-godot"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        content = response.read()
    SDK.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(content), mode="r:gz") as archive:
        for member in archive:
            parts = Path(member.name).parts[1:]
            if not parts or ".." in parts or not member.isfile():
                continue
            target = SDK.joinpath(*parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.extractfile(member).read())
            target.chmod(member.mode & 0o777)

target = f"releases-{RELEASE}-64bit"
subprocess.run([sys.executable, str(SDK / "emsdk.py"), "install", target], cwd=SDK, check=True)
subprocess.run([sys.executable, str(SDK / "emsdk.py"), "activate", target], cwd=SDK, check=True)
