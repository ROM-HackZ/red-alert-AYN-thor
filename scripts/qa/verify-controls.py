"""Drive the installed debug APK through Android input and assert live engine state.

Start a mission with friendly units visible, save it, then leave controls untouched.
The probe must already be built and pushed (see docs/Verification.md). This changes
selection, group 1, camera position and zoom, then pauses the mission.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time

from device import Device, ROOT, PACKAGE


def verify(d):
    s = d.state()
    if not s.get("active") or s.get("modal"):
        raise RuntimeError("Load a mission and close its menus before running this check.")
    if (s["inputX"],s["inputY"],s["inputWidth"],s["inputHeight"])!=(0,0,s["width"],s["height"]):
        raise AssertionError("The native input area does not cover the battlefield after loading")
    scenario = s["scenario"]
    d.tap(200, 145, 4)  # Commands tab, then Select view.
    d.tap(527, 646, 4)
    selected = d.wait("Select view selects friendly units", lambda s: s["selected"] > 0)["selected"]
    process = d.probe("chord", 102, 0, -1, 0, 0, 0, 0, 2500, background=True)
    try:
        d.wait("LB opens groups", lambda s:s["wheelGroups"] and s["wheelChoice"]==0)
        d.key(99)
        d.wait("LB + X assigns group 1", lambda s: s["groups"][0] == selected)
    finally:
        process.communicate()
    d.key(97)
    d.wait("B deselects", lambda s: s["selected"] == 0)
    d.probe("chord", 102, 0, -1, 0, 0, 0, 0, 400)
    d.wait("Releasing LB does not recall a group",lambda s:s["selected"]==0)
    process = d.probe("chord",102,0,-1,0,0,0,0,2500,background=True)
    try:
        d.wait("Group 1 highlighted",lambda s:s["wheelChoice"]==0)
        d.key(96)
        d.wait("LB + A recalls group 1",lambda s:s["selected"]==selected)
    finally:
        process.communicate()
    process = d.probe("chord", 105, -.8, -.8, 0, 0, 0, 0, 1600, background=True)
    try:
        d.wait("RT opens command wheel", lambda s: s["wheel"] == "open")
    finally:
        process.communicate()
    d.wait("Wheel releases cleanly", lambda s: s["wheel"] == "closed" and not s["rightTrigger"])
    d.wait("Releasing RT does not execute Deselect",lambda s:s["selected"]==selected)
    process=d.probe("chord",105,-.8,-.8,0,0,0,0,2500,background=True)
    try:
        d.wait("Deselect highlighted",lambda s:s["wheelChoice"]==7)
        d.key(96)
        d.wait("RT + A executes Deselect",lambda s:s["selected"]==0)
    finally:
        process.communicate()
    # Check cursor motion at the edge too: native mouse autoscroll must not pan.
    before=d.state()
    process=d.probe("chord",106,1,0,0,0,0,0,2200,background=True)
    try:
        edge=before["width"]//2+int(before["width"]/before["zoom"])/2-5
        held=d.wait("L3 + left stick reaches visible cursor edge",lambda s:s["leftCursor"] and s["pointerX"]>=edge,3)
        if (held["cameraX"],held["cameraY"])!=(before["cameraX"],before["cameraY"]):
            raise AssertionError("L3 precision cursor panned the camera")
    finally:
        process.communicate()
    after=d.state()
    if (after["cameraX"],after["cameraY"])!=(before["cameraX"],before["cameraY"]):
        raise AssertionError("Releasing L3 after aiming moved the camera")
    d.checks.append({"check":"L3 + left stick moves cursor without panning, including at edge","frame":after["frame"]})
    # Pan away from the nearer edge of this particular map.
    direction=1 if after["cameraX"] < after["mapX"]*256+after["mapW"]*128-after["cameraW"]/2 else -1
    d.probe("axes",direction,0,0,0,0,0,350)
    d.wait("Normal left stick pans beneath centred aim",lambda s:s["cameraX"]!=after["cameraX"] and s["pointerX"]==s["width"]//2 and s["pointerY"]==s["height"]//2)
    d.tap(527,646,4)
    d.wait("Units reselected for touch deselection",lambda s:s["selected"]>0)
    d.probe("two-tap")
    d.wait("Two-finger tap deselects", lambda s: s["selected"] == 0)
    before = d.state()
    # Test both directions: the current camera may already be at a map edge.
    d.probe("pan")
    if d.state()["cameraX"] == before["cameraX"]:
        d.probe("pan-left")
    d.wait("Two-finger drag pans", lambda s: s["cameraX"] != before["cameraX"])
    # Begin below the maximum before checking the positive zoom direction.
    d.probe("axes", 0, 0, 0, 1, 0, 0, 1000)
    zoom = d.state()["zoom"]
    d.probe("axes", 0, 0, 0, -1, 0, 0, 350)
    d.wait("Right stick up zooms in", lambda s: s["zoom"] > zoom)
    d.probe("axes", 0, 0, 0, 1, 0, 0, 1000)
    zoom = d.state()["zoom"]
    d.probe("pinch-out")
    d.wait("Pinch zooms in", lambda s: s["zoom"] > zoom)
    pid = d.adb("shell", "pidof", PACKAGE).strip()
    process = d.probe("chord", 106, 1, 0, 0, 0, 0, 0, 2200, background=True)
    try:
        d.adb("shell", "input", "keyevent", 3)
    finally:
        process.communicate()
    d.adb("shell", "am", "start", "-n", PACKAGE + "/.LauncherActivity")
    s = d.wait("Return clears held input", lambda s: s["leftX"] == 0 and s["rightX"] == 0 and not s["leftCursor"] and not s["rightCursor"] and s["wheel"] == "closed")
    if d.adb("shell", "pidof", PACKAGE).strip() != pid or s["scenario"] != scenario:
        raise AssertionError("Home/launcher restarted the game or changed its mission")
    d.checks.append({"check": "Home/launcher preserves process and mission", "frame": s["frame"]})
    d.key(108)
    d.wait("Start opens pause menu", lambda s: s["modal"])
    d.capture("verified-controls-top.png")
    d.capture("verified-controls-bottom.png", bottom=True)
    return scenario


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adb", required=True)
    parser.add_argument("--serial", required=True)
    args = parser.parse_args()
    d = Device(args.adb, args.serial)
    report = {"started": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "passed": False}
    apk = ROOT / "artifacts/RedAlert-Thor.apk"
    if apk.exists(): report["apkSha256"] = hashlib.sha256(apk.read_bytes()).hexdigest()
    try:
        report["scenario"] = verify(d)
        report["passed"] = True
    except Exception as error:
        report["error"] = str(error)
        raise
    finally:
        report["checks"] = d.checks
        output = ROOT / "artifacts/control-verification.json"
        output.parent.mkdir(exist_ok=True)
        output.write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__": main()
