"""Check build inputs and staging for accidental retail data or private keys."""
import json
from pathlib import Path
import re
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = {".mix", ".vqa", ".vqp", ".aud", ".keystore", ".jks"}


def check():
    pins = json.loads((ROOT / "THOR-UPSTREAM.json").read_text())
    for name in ("sdl", "openal"):
        if not re.fullmatch(r"[0-9a-f]{64}", pins[name]["sha256"]):
            raise ValueError("Dependency needs a SHA-256 pin: " + name)
        if not pins[name]["url"].startswith("https://"):
            raise ValueError("Dependency URL must use HTTPS: " + name)
    if not (ROOT / "License.txt").is_file():
        raise ValueError("Upstream license is missing")
    if (ROOT / ".git").exists():
        paths = subprocess.check_output(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=ROOT).decode().split("\0")
        bad = [name for name in paths if Path(name).suffix.lower() in FORBIDDEN]
        if bad:
            raise ValueError("Keep retail files and signing keys outside Git: " + ", ".join(bad))
    apk = ROOT / "artifacts/RedAlert-Thor.apk"
    if apk.exists():
        with zipfile.ZipFile(apk) as z:
            bad = [name for name in z.namelist() if Path(name).suffix.lower() in FORBIDDEN]
            if bad: raise ValueError("Retail data or signing keys packaged in APK: " + ", ".join(bad))
    print("Source, dependency pins and APK data separation checked.")


if __name__ == "__main__":
    try: check()
    except (ValueError, OSError) as error:
        print(str(error), file=sys.stderr); sys.exit(1)
