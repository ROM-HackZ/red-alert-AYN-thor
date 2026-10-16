"""Regress physical A repeats: stable drag anchors and no white outline trails.

Requires Pillow, a debug mission and the current input probe. Uses an empty
upper-left portion of the battlefield; do not pan while the check runs.
"""
import argparse
import hashlib
import json
import time

from PIL import Image, ImageChops
from device import Device, ROOT


def white(path, region):
    image = Image.open(path).convert("RGB").crop(region)
    r, g, b = image.split()
    return ImageChops.darker(ImageChops.darker(r, g), b).point(lambda v: 255 if v >= 245 else 0)


def verify(d):
    s=d.state()
    if s.get("modal"): d.button("Resume Mission")
    d.probe("chord",107,0,0,0,1,0,0,1200)
    d.wait("Full view for visual repeat regression",lambda s:s["zoom"]==1)
    d.key(97)
    # Set only the pointer for this fixture; A and all drag motion use Android
    # gamepad events, including the repeated DOWN events a physical hold emits.
    d.command(9,x=400,y=300)
    time.sleep(.15)
    baseline=d.capture("repeat-fixed-baseline.png")
    region=(160,35,850,590)
    mask=white(baseline,region)
    before=d.state()
    d.command(9,x=40,y=30);time.sleep(.15)
    held=d.probe("repeat-key",96,6000,background=True)
    try:
        d.probe("axes",.5,.4,0,0,0,0,650)
        first=d.wait("A repeats leave a live selection box",lambda s:s["dragging"] and s["ignoredARepeats"]>before["ignoredARepeats"])
        anchor=(first["dragStartX"],first["dragStartY"])
        if anchor!=(40,30): raise AssertionError("A repeat moved the original drag anchor: "+str(anchor))
        image=d.capture("repeat-fixed-held.png")
        extra=ImageChops.subtract(white(image,region),mask).histogram()[255]
        if extra<50: raise AssertionError("Live selection outline is not visible")
        time.sleep(.7)
        same=d.state()
        if not same["dragging"] or (same["dragStartX"],same["dragStartY"])!=anchor:
            raise AssertionError("Stationary long hold lost or restarted its rectangle")
        d.probe("axes",-.35,-.3,0,0,0,0,300)
        smaller=d.state()
        if not smaller["dragging"] or (smaller["dragStartX"],smaller["dragStartY"])!=anchor:
            raise AssertionError("Shrinking the rectangle changed its anchor")
        d.capture("repeat-fixed-shrunk.png")
        d.checks.append({"check":"Repeated A-down events preserve drag and anchor while moving, stationary and shrinking","repeatsIgnored":smaller["ignoredARepeats"]-before["ignoredARepeats"]})
    finally: held.communicate()
    d.wait("Only A release ends the box",lambda s:not s["dragging"] and not s["leftMouse"] and not s["selecting"])
    d.command(9,x=400,y=300);time.sleep(.2)
    released=d.capture("repeat-fixed-released.png")
    remaining=ImageChops.subtract(white(released,region),mask).histogram()[255]
    if remaining: raise AssertionError(f"Old selection outlines left {remaining} white pixels behind")
    d.checks.append({"check":"No stale white outline pixels after A release","pixels":remaining})
    # Zoom and reverse-direction drags exercise the cropped viewport too.
    d.probe("chord",107,0,0,0,-1,0,0,1000)
    d.wait("2x view for reverse drag",lambda s:s["zoom"]==2)
    d.command(9,x=400,y=240);time.sleep(.15)
    held=d.probe("repeat-key",96,3000,background=True)
    try:
        d.probe("axes",-.65,-.5,0,0,0,0,1000)
        d.wait("Zoomed reverse drag survives A repeats",lambda s:s["dragging"] and s["dragStartX"]==400 and s["dragStartY"]==240 and s["dragEndX"]<400 and s["dragEndY"]<240)
        d.capture("repeat-fixed-zoomed.png")
    finally:held.communicate()
    d.wait("Zoomed box releases cleanly",lambda s:not s["dragging"] and not s["leftMouse"])
    d.wait("Damaged and selected health-bar mode is active",lambda s:s["healthBarMode"]==0)
    d.key(108)


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--adb",required=True);p.add_argument("--serial",required=True)
    args=p.parse_args();d=Device(args.adb,args.serial)
    report={"passed":False,"apkSha256":hashlib.sha256((ROOT/"artifacts/RedAlert-Thor.apk").read_bytes()).hexdigest()}
    try:verify(d);report["passed"]=True
    finally:
        report["checks"]=d.checks
        (ROOT/"artifacts/drag-repeat-verification.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
