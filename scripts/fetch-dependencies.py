"""Fetch checksum-pinned native sources. No game data is downloaded."""
import hashlib
import json
from pathlib import Path
import tarfile
import shutil
import tempfile
import urllib.request

root = Path(__file__).resolve().parents[1]
pins = json.loads((root / "THOR-UPSTREAM.json").read_text())
out = root / ".local/sources"
out.mkdir(parents=True, exist_ok=True)
for key, name in (("sdl", "SDL2-2.32.10"), ("openal", "openal-soft-1.23.1")):
    marker = out / name / ".thor-source-sha256"
    if marker.is_file() and marker.read_text() == pins[key]["sha256"]:
        continue
    archive = out / (name + ".tar.gz")
    if not archive.exists():
        with urllib.request.urlopen(pins[key]["url"], timeout=60) as response:
            archive.write_bytes(response.read())
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == pins[key]["sha256"], name
    with tempfile.TemporaryDirectory(dir=out) as temporary:
        with tarfile.open(archive) as tar:
            # SDL's unused Ant-project symlink points outside its source root.
            # Only regular files/directories are needed by our CMake build.
            tar.extractall(temporary, members=(m for m in tar.getmembers() if m.isfile() or m.isdir()), filter="data")
        target = (out / name).resolve()
        assert target.parent == out.resolve()
        if target.exists():
            shutil.rmtree(target)
        shutil.move(str(Path(temporary) / name), target)
        marker.write_text(pins[key]["sha256"])
    print("Ready:", name, flush=True)
