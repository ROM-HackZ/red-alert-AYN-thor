#!/usr/bin/env python3
"""Import an owned Steam installation without extracting or redistributing its data.

Run without arguments for the desktop UI. --game and --adb provide the same flow
from a terminal on Windows, macOS, or Linux. No shell interpolation is used.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import threading
import tempfile

ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
PACKAGE = "org.redalertthor.app"
REMOTE = f"/sdcard/Android/data/{PACKAGE}/files"
ADB_NAME = "adb.exe" if os.name == "nt" else "adb"
DEFAULT_ADB = str(ROOT / "platform-tools" / ADB_NAME) if (ROOT / "platform-tools" / ADB_NAME).is_file() else shutil.which("adb") or "adb"
# These folder names and disc order match the engine's Change_Local_Dir layout.
DATA = {
    "REDALERT.MIX": "REDALERT.MIX",
    "EXPAND.MIX": "EXPAND.MIX", "EXPAND2.MIX": "EXPAND2.MIX",
    "HIRES1.MIX": "HIRES1.MIX", "LORES1.MIX": "LORES1.MIX",
    "MAIN1.MIX": "allied/MAIN.MIX", "MAIN2.MIX": "soviet/MAIN.MIX",
    "MAIN3.MIX": "counterstrike/MAIN.MIX", "MAIN4.MIX": "aftermath/MAIN.MIX",
}
OPTIONAL_DATA = ("BMAP.VQA", "BMAP.VQP", "SIZZLE.VQA", "SIZZLE.VQP", "SIZZLE2.VQA", "SIZZLE2.VQP")


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def install(game, adb, apk, serial=None, log=print, launch=True):
    game, apk = Path(game).resolve(), Path(apk).resolve()
    sources = {name.name.upper(): name for name in game.iterdir() if name.is_file()}
    missing = DATA.keys() - sources.keys()
    if missing:
        raise ValueError("Select the Steam Red Alert folder. Missing: " + ", ".join(sorted(missing)))
    copies = dict(DATA)
    copies.update({name:name for name in OPTIONAL_DATA if name in sources})
    if not apk.is_file():
        raise ValueError("APK not found: " + str(apk))
    adb = str(Path(adb).resolve()) if Path(adb).is_file() else shutil.which(adb)
    if not adb:
        raise ValueError("Select adb from Android SDK Platform Tools.")
    if os.name != "nt" and not os.access(adb, os.X_OK):
        os.chmod(adb, 0o755)
    def run(*args):
        p = subprocess.run([adb, *args], capture_output=True, text=True, encoding="utf-8", errors="replace",
                           creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        if p.returncode:
            raise RuntimeError((p.stderr or p.stdout).strip())
        return p.stdout.strip()
    if not serial:
        devices = [line.split()[0] for line in run("devices").splitlines()[1:] if line.endswith("\tdevice")]
        if len(devices) != 1:
            raise ValueError("Connect and unlock one Android device, allow USB debugging, then try again.")
        serial = devices[0]
    def device(*args):
        return run("-s", serial, *args)
    same_app = False
    try:
        installed = device("shell", "pm", "path", PACKAGE)
        base = next((line.removeprefix("package:") for line in installed.splitlines() if line.endswith("/base.apk")), "")
        if base: same_app = device("shell", "sha256sum", base).split()[0] == digest(apk)
    except RuntimeError:
        pass # A first install has no package path yet; install reports connection errors.
    if same_app:
        log("App already matches. Checking your game files…")
    else:
        log("Installing app (existing saves are kept)…")
        device("install", "-r", str(apk))
    # The APK must be installed before Android grants this package its external directory.
    device("shell", "mkdir", "-p", REMOTE + "/game", REMOTE + "/user")
    free = device("shell", "df", "-k", REMOTE).splitlines()[-1].split()
    if int(free[3]) * 1024 < sum(sources[n].stat().st_size for n in copies) + 128 * 1024 * 1024:
        # Existing matching imports consume no additional space; report before partial transfers.
        log("Storage is tight. Existing matching files will be reused; incomplete copies may need space freed.")
    manifest = {"format": 1, "files": {}}
    stopped_for_data = not same_app
    for index, (name, relative) in enumerate(copies.items(), 1):
        source = sources[name]
        log(f"[{index}/{len(copies)}] Checking {name}…")
        expected = digest(source)
        target = REMOTE + "/game/" + relative
        device("shell", "mkdir", "-p", target.rsplit("/", 1)[0])
        current = device("shell", "sh", "-c", f"'sha256sum {target} 2>/dev/null || true'").split()
        if not current or current[0] != expected:
            if not stopped_for_data:
                device("shell", "am", "force-stop", PACKAGE)
                stopped_for_data = True
            log(f"Copying {name} ({source.stat().st_size // (1024*1024)} MB)…")
            device("push", str(source), target + ".partial")
            actual = device("shell", "sha256sum", target + ".partial").split()[0]
            if actual != expected:
                raise RuntimeError(f"Copy verification failed for {name}. Retry the installer.")
            device("shell", "mv", target + ".partial", target)
        manifest["files"][relative] = {"size": source.stat().st_size, "sha256": expected}
    with tempfile.TemporaryDirectory(prefix="redalert-thor-") as temporary:
        manifest_file = Path(temporary) / "import-manifest.json"
        manifest_file.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        device("push", str(manifest_file), REMOTE + "/import-manifest.json")
    if launch:
        device("shell", "am", "start", "-n", PACKAGE + "/.LauncherActivity")
    log("Ready. The original campaigns, Counterstrike and Aftermath are installed.")


def gui():
    import tkinter as tk
    from tkinter import filedialog, ttk
    app = tk.Tk()
    app.title("Red Alert — Thor setup")
    app.geometry("760x540")
    app.configure(padx=24, pady=20)
    ttk.Label(app, text="Red Alert on your Thor", font=("Segoe UI", 20, "bold")).pack(anchor="w")
    ttk.Label(app, text="Connect your Thor by USB, unlock it, and allow USB debugging.\nChoose your Steam game folder. Save your game before updating; existing saves are kept.").pack(anchor="w", pady=12)
    values = {}
    defaults = {"Game folder": r"D:\Steam\steamapps\common\Command & Conquer Red Alert" if os.name == "nt" else "",
                "adb": DEFAULT_ADB, "APK": str(ROOT / "artifacts/RedAlert-Thor.apk")}
    for label, default in defaults.items():
        ttk.Label(app, text=label).pack(anchor="w")
        row = ttk.Frame(app); row.pack(fill="x", pady=(0, 8))
        value = tk.StringVar(value=default); values[label] = value
        ttk.Entry(row, textvariable=value).pack(side="left", fill="x", expand=True)
        def browse(v=value, folder=label == "Game folder"):
            path = filedialog.askdirectory() if folder else filedialog.askopenfilename()
            if path: v.set(path)
        ttk.Button(row, text="Browse", command=browse).pack(side="right", padx=(8, 0))
    output = tk.Text(app, height=8, state="disabled", wrap="word")
    events = queue.Queue()
    def start():
        button.configure(state="disabled")
        selected = {name: value.get() for name, value in values.items()}
        def work():
            try: install(selected["Game folder"], selected["adb"], selected["APK"], log=events.put)
            except Exception as error: events.put("Setup stopped: " + str(error))
            finally: events.put(None)
        threading.Thread(target=work, daemon=True).start()
    button = ttk.Button(app, text="Install on Thor", command=start)
    button.pack(anchor="w", pady=8); output.pack(fill="both", expand=True)
    def pump():
        while not events.empty():
            line = events.get()
            if line is None: button.configure(state="normal")
            else:
                output.configure(state="normal"); output.insert("end", line + "\n")
                output.see("end"); output.configure(state="disabled")
        app.after(100, pump)
    pump(); app.mainloop()


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--game"); p.add_argument("--adb", default=DEFAULT_ADB)
    p.add_argument("--apk", default=str(ROOT / "artifacts/RedAlert-Thor.apk"))
    p.add_argument("--serial"); p.add_argument("--no-launch", action="store_true")
    args = p.parse_args()
    if args.game: install(args.game, args.adb, args.apk, args.serial, launch=not args.no_launch)
    else: gui()
