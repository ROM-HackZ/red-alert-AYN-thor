#!/usr/bin/env python3
"""Bundle the GUI, built APK, and local official platform-tools on this OS.

Requires PyInstaller 6.16.0. Run with --adb-dir pointing at extracted Android SDK
Platform Tools. Retail game files are deliberately excluded from the bundle.
"""
import argparse
import hashlib
from pathlib import Path
import os
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--adb-dir", type=Path, required=True)
    args = p.parse_args()
    subprocess.run([sys.executable, str(ROOT / "scripts/check-source.py")],check=True)
    adb = args.adb_dir.resolve()
    names = ["adb.exe", "AdbWinApi.dll", "AdbWinUsbApi.dll", "libwinpthread-1.dll"] if os.name=="nt" else ["adb"]
    names += ["NOTICE.txt", "source.properties"]
    for name in names:
        if not (adb / name).is_file(): raise ValueError("Missing platform-tools file: " + name)
    bundle = ["--add-data", str(ROOT / "artifacts/RedAlert-Thor.apk") + os.pathsep + "artifacts",
              "--add-data", str(ROOT / "License.txt") + os.pathsep + "licenses"]
    for name in names: bundle += ["--add-data", str(adb / name) + os.pathsep + "platform-tools"]
    subprocess.run([sys.executable,"-m","PyInstaller","--noconfirm","--onefile","--windowed",
                    "--name","RedAlert-Thor-Setup","--distpath",str(ROOT/"artifacts"),
                    "--workpath",str(ROOT/".local/installer-build"),"--specpath",str(ROOT/".local"),
                    *bundle,str(ROOT/"scripts/install-thor.py")],check=True,cwd=ROOT)
    executable = ROOT / "artifacts" / ("RedAlert-Thor-Setup.exe" if os.name=="nt" else "RedAlert-Thor-Setup")
    archive = ROOT / "artifacts" / ("RedAlert-Thor-Setup-" + sys.platform + ".zip")
    with zipfile.ZipFile(archive,"w",zipfile.ZIP_DEFLATED) as z:
        z.write(executable,executable.name)
        z.write(ROOT/"License.txt","licenses/Vanilla-Conquer.txt")
        z.write(adb/"NOTICE.txt","licenses/Android-Platform-Tools.txt")
        for name in ("README.md","THOR-UPSTREAM.json"):
            z.write(ROOT/name,name)
        for source in sorted((ROOT/"docs").rglob("*")):
            if source.is_file(): z.write(source,source.relative_to(ROOT))
    print(archive)
    print("SHA-256:",hashlib.sha256(archive.read_bytes()).hexdigest())


if __name__=="__main__": main()
