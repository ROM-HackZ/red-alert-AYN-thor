"""Compare the live Thor power display with native engine state.

Requires a debug APK and Pillow. Run in a saved test game with the requested
power level. This reads state and screenshots; it does not change gameplay.
"""
import argparse
import hashlib
import json
import time

from PIL import Image
from device import Device, ROOT


COLORS = [(159, 205, 193), (232, 196, 94), (255, 139, 121)]


def near(color, expected):
    # SurfaceFlinger applies the handheld's display color correction to captures.
    return all(abs(a - b) <= 20 for a, b in zip(color, expected))


def verify(d, level, wait_for_flash=False, seconds=240):
    s = d.state()
    if not s.get("active") or s.get("modal"):
        raise RuntimeError("Open the battlefield before checking indicators.")
    assert s["healthBarMode"] == 2, "Health bars must use the original selected-only default"
    expected = 2 if s["drain"] > s["power"] * 2 else 1 if s["drain"] > s["power"] else 0
    assert s["powerLevel"] == expected == level, (s["power"], s["drain"], s["powerLevel"], level)
    maximum = s["powerGaugeMaximum"]
    assert maximum > 0 and 0 <= s["powerGaugeOutput"] <= maximum
    assert 0 <= s["powerGaugeDemand"] <= maximum
    path = d.capture(f"power-level-{level}-bottom.png", bottom=True)
    with Image.open(path) as image:
        assert image.size == (1240, 1080), "This pixel check is for the Thor's bottom display"
        image = image.convert("RGB")
        label = image.crop((900, 26, 1203, 52)).getcolors(10000)
        assert sum(count for count, color in label if near(color, COLORS[level])) > 20, "Power label has the wrong status color"
        colors = image.crop((900, 64, 1203, 80)).getcolors(10000)
        filled = sum(count for count, color in colors if near(color, COLORS[level]))
        if s["powerGaugeOutput"] > 0:
            assert filled > 0, "Native power output is missing from the visible gauge"
        else:
            assert filled == 0, "The gauge shows power when native output is zero"
        demand_x = round(900 + 302 * s["powerGaugeDemand"] / maximum)
        assert any(image.getpixel((x, 61)) == (255, 255, 255)
                   for x in range(max(0, demand_x - 2), min(1240, demand_x + 3))), "Demand marker is missing"
    report = {key: s[key] for key in ("scenario", "frame", "healthBarMode", "power", "drain", "powerLevel",
                                      "powerGaugeOutput", "powerGaugeDemand", "powerGaugeMaximum")}
    report["visibleGauge"] = True
    report["visibleDemandMarker"] = True
    report["visibleStatusColor"] = True
    if wait_for_flash:
        deadline = time.monotonic() + seconds
        native_flash = visible_flash = False
        while time.monotonic() < deadline and not (native_flash and visible_flash):
            state = d.state()
            native_flash |= state.get("powerFlash", False)
            picture = d.capture(f"power-level-{level}-warning.png", bottom=True)
            with Image.open(picture) as image:
                flashing = near(image.convert("RGB").getpixel((895, 50)), (120, 44, 42))
                if flashing and not visible_flash:
                    (ROOT / f"artifacts/power-level-{level}-warning-visible.png").write_bytes(picture.read_bytes())
                visible_flash |= flashing
            time.sleep(.03)
        assert native_flash, "No original engine warning flash was observed"
        assert visible_flash, "The engine warning never appeared on the command deck"
        report.update(nativeWarningFlash=True, visibleWarningFlash=True)
    report["passed"] = True
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adb", required=True)
    parser.add_argument("--serial", required=True)
    parser.add_argument("--level", required=True, type=int, choices=(0, 1, 2))
    parser.add_argument("--wait-for-flash", action="store_true")
    parser.add_argument("--seconds", type=int, default=240)
    args = parser.parse_args()
    d = Device(args.adb, args.serial)
    report = {"passed": False}
    try:
        report.update(verify(d, args.level, args.wait_for_flash, args.seconds))
        print(json.dumps(report, indent=2))
    except Exception as error:
        report["error"] = str(error)
        raise
    finally:
        report["apkSha256"] = hashlib.sha256((ROOT / "artifacts/RedAlert-Thor.apk").read_bytes()).hexdigest()
        (ROOT / f"artifacts/power-level-{args.level}-verification.json").write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
