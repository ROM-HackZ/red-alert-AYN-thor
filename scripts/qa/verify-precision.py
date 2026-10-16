"""Exercise persistent left-stick aiming, box selection and group editing.

Requires a live debug mission with several friendly units visible and the ADB
probe installed. Changes groups 1 and 9, selection, camera and zoom; does not save.
"""
import argparse
import hashlib
import json
import math
import time
from device import Device, ROOT


def verify_rectangles(d):
    d.key(97);d.wait("Deselect before rectangle",lambda s:s["selected"]==0)
    d.probe("axes",-1,-1,0,0,0,0,1400)
    before=d.state()
    process=d.probe("chord",96,.8,.8,1,1,0,0,2000,background=True)
    try:
        s=d.wait("A + left stick draws a native rectangle",lambda s:s["dragging"] and s["leftMouse"],3)
        if (s["cameraX"],s["cameraY"])!=(before["cameraX"],before["cameraY"]):
            raise AssertionError("Right stick moved the map underneath a selection box")
        d.capture("controller-selection-rectangle.png")
    finally: process.communicate()
    s=d.wait("A release completes rectangle and releases mouse",lambda s:s["selected"]>1 and not s["dragging"] and not s["leftMouse"])
    parked=(s["pointerX"],s["pointerY"])
    time.sleep(.3)
    if (d.state()["pointerX"],d.state()["pointerY"])!=parked:
        raise AssertionError("Releasing A reset the cursor")
    # Releasing a stick click halfway through a box must not change its mode.
    d.key(97);d.probe("axes",-1,-1,0,0,0,0,1400)
    held=d.probe("keys",96,4500,background=True)
    try:
        d.probe("axes",.8,.8,0,0,0,0,700)
        d.key(106)
        d.wait("L3 press/release keeps the current selection box",lambda s:s["dragging"] and s["leftMouse"])
        d.key(107)
        d.wait("R3 press/release keeps the current selection box",lambda s:s["dragging"] and s["leftMouse"])
        d.probe("axes",.8,.8,0,0,0,0,1200)
    finally: held.communicate()
    d.wait("Box survives stick-button releases",lambda s:s["selected"]>1 and not s["leftMouse"])
    d.key(97);d.wait("Deselect before touch rectangle",lambda s:s["selected"]==0)
    d.adb("shell","input","swipe",110,15,1800,1040,1200)
    d.wait("Touch rectangle retains control of cursor",lambda s:s["selected"]>1)


def verify(d):
    s=d.state()
    if s.get("modal"): d.button("Resume Mission")
    d.probe("chord",107,0,0,0,1,0,0,1100)
    d.tap(200,145,4); d.tap(527,646,4)
    s=d.wait("Friendly units visible",lambda s:s.get("selected",0)>1)
    wx,wy=s["selectedX"],s["selectedY"]
    tx=(wx-s["cameraX"])*s["width"]/s["cameraW"]
    ty=(wy-s["cameraY"])*s["height"]/s["cameraH"]
    camera=(s["cameraX"],s["cameraY"])
    d.key(97)
    for _ in range(12):
        s=d.state(); dx=tx-s["pointerX"]; dy=ty-s["pointerY"]
        distance=math.hypot(dx,dy)
        if distance<4: break
        def axis(delta): return math.copysign(.18+.82*.6*abs(delta)/distance,delta) if abs(delta)>.5 else 0
        d.probe("axes",axis(dx),axis(dy),0,0,0,0,max(30,min(400,round(distance/(420*.6)*1000))))
    else: raise AssertionError("Joystick cursor did not converge on the unit")
    parked=d.state()
    time.sleep(.4)
    s=d.state()
    if (s["pointerX"],s["pointerY"])!=(parked["pointerX"],parked["pointerY"]):
        raise AssertionError("Neutral left stick reset the cursor")
    d.key(96)
    s=d.wait("Move left stick, release it, then A selects the aimed unit",lambda s:s["selected"]==1)
    if (s["cameraX"],s["cameraY"])!=camera: raise AssertionError("Cursor selection panned the camera")
    before=d.state()
    process=d.probe("chord",107,0,0,0,-.7,0,0,700,background=True)
    try:
        held=d.wait("Hold R3 + right stick up zooms in",lambda s:s["zoomModifier"] and s["zoom"]>before["zoom"])
        if (held["cameraX"],held["cameraY"])!=camera:
            raise AssertionError("Zoom modifier panned the camera")
    finally: process.communicate()
    d.probe("chord",107,0,0,0,1,0,0,1100)
    d.wait("Hold R3 + right stick down zooms back out",lambda s:s["zoom"]==1 and not s["zoomModifier"])
    process=d.probe("chord",102,0,-1,0,0,0,0,4000,background=True)
    try:
        d.wait("Groups opened",lambda s:s["wheelGroups"])
        d.key(22)
        d.wait("D-pad switches to group 9",lambda s:s["wheelChoice"]==8)
        d.key(99)
        d.wait("X assigns group 9",lambda s:s["groups"][8]==1)
    finally: process.communicate()
    old=d.state()["groups"][0]
    process=d.probe("chord",102,0,-1,0,0,0,0,4500,background=True)
    trigger=None
    try:
        d.wait("Group 1 highlighted",lambda s:s["wheelChoice"]==0)
        trigger=d.probe("axes",0,-1,0,0,1,0,2500,background=True)
        d.wait("LT held for adding",lambda s:s["leftTrigger"])
        d.key(99)
        d.wait("LT + X adds to group and preserves selection",lambda s:s["groups"][0]==old+1 and s["selected"]==1)
    finally:
        if trigger: trigger.communicate()
        process.communicate()
    process=d.probe("chord",102,0,-1,0,0,0,0,3000,background=True)
    try:
        d.wait("Group highlighted for centering",lambda s:s["wheelChoice"]==0)
        d.key(100)
        d.wait("Y selects group for native camera centering",lambda s:s["selected"]==s["groups"][0])
    finally: process.communicate()
    verify_rectangles(d)
    d.key(108); d.wait("Mission paused after checks",lambda s:s["modal"])


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("--adb",required=True); p.add_argument("--serial",required=True)
    args=p.parse_args(); d=Device(args.adb,args.serial); report={"passed":False,"apkSha256":hashlib.sha256((ROOT/"artifacts/RedAlert-Thor.apk").read_bytes()).hexdigest()}
    try: verify(d); report["passed"]=True
    finally:
        report["checks"]=d.checks
        (ROOT/"artifacts/precision-verification.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
