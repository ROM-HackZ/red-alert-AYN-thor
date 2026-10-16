"""Package the complete modified engine and build scripts, without local data."""
import hashlib
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    subprocess.run([sys.executable, str(ROOT / "scripts/check-source.py")], check=True)
    files = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=ROOT
    ).decode("utf-8").split("\0")
    archive = ROOT / "artifacts/RedAlert-Thor-Source.zip"
    archive.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as output:
        for name in sorted(set(files) - {""}):
            source = ROOT / name
            if source.is_file(): output.write(source, "RedAlert-Thor/" + name)
    print(archive)
    print("SHA-256:", hashlib.sha256(archive.read_bytes()).hexdigest())


if __name__ == "__main__": main()
