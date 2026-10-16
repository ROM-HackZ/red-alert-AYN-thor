"""Read real engine diagnostics and drive Android input on the connected test Thor."""
import json
from pathlib import Path
import re
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = "org.redalertthor.app"


class Device:
    def __init__(self, adb, serial):
        self.prefix = [adb, "-s", serial]
        self.checks = []

    def adb(self, *args):
        return subprocess.check_output([*self.prefix, *map(str, args)], encoding="utf-8", errors="replace")

    def state(self):
        reply = self.adb("shell","am","broadcast","-a",PACKAGE+".QA","-n",PACKAGE+"/.QaReceiver")
        if 'data="ok"' not in reply:
            raise RuntimeError("Live game diagnostics unavailable: " + reply.strip())
        return json.loads(self.adb("shell", "cat", f"/sdcard/Android/data/{PACKAGE}/files/qa-state.json"))

    def command(self, kind, a=0, b=0, x=0, y=0):
        return self.adb("shell","am","broadcast","-a",PACKAGE+".QA","-n",PACKAGE+"/.QaReceiver",
                        "--ei","kind",kind,"--ei","a",a,"--ei","b",b,"--ef","x",x,"--ef","y",y)

    def wait(self, label, predicate, seconds=15):
        deadline = time.monotonic() + seconds
        last = None
        while time.monotonic() < deadline:
            try:
                last = self.state()
                if predicate(last):
                    self.checks.append({"check": label, "frame": last.get("frame")})
                    print("PASS", label, flush=True)
                    return last
            except json.JSONDecodeError:
                pass
            time.sleep(.1)
        raise AssertionError(label + ": " + json.dumps(last))

    def tap(self, x, y, display=0, duration=120):
        self.adb("shell", "input", "-d", display, "swipe", x, y, x, y, duration)

    def key(self, key):
        # The Thor advertises its D-pad as joystick hat axes. Test that path
        # directly instead of relying on Android's fallback keyboard events.
        hats = {19: (0, -1), 20: (0, 1), 21: (-1, 0), 22: (1, 0)}
        if key in hats:
            # A real hat event retains the sticks/triggers. Clearing those axes
            # would erase the wheel highlight during a D-pad page change.
            s=self.state()
            def raw(value): return (1 if value>0 else -1)*(.18+.82*abs(value)) if value else 0
            axes=[raw(s.get(name,0)) for name in ("leftX","leftY","rightX","rightY")]
            self.probe("hat", *hats[key], 120, *axes, int(s.get("leftTrigger",False)), int(s.get("rightTrigger",False)))
        else:
            self.probe("keys", key, 120)

    def button(self, label):
        def find(s): return next((n for n in s.get("Navigation", []) if n["Label"].lower() == label.lower()), None)
        state = self.wait("native button available: " + label, find, 45)
        target = find(state)
        scale = min(1920/state["width"],1080/state["height"])
        self.tap(round(target["X"]*scale+(1920-state["width"]*scale)/2), round(target["Y"]*scale+(1080-state["height"]*scale)/2))

    def probe(self, *args, background=False):
        command = [*self.prefix, "shell", "env", "CLASSPATH=/data/local/tmp/redalert-thor-input-probe.jar",
                   "app_process", "/system/bin", "org.redalertthor.qa.ThorInputProbe", *map(str, args)]
        if background:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if process.stdout.readline().strip() != "DOWN":
                raise RuntimeError(process.communicate()[1])
            return process
        subprocess.run(command, check=True, capture_output=True, text=True)

    def capture(self, name, bottom=False):
        ids = re.findall(r"Display (\d+)", self.adb("shell", "dumpsys", "SurfaceFlinger", "--display-id"))
        target = ROOT / "artifacts" / name
        target.parent.mkdir(exist_ok=True)
        target.write_bytes(subprocess.check_output([*self.prefix, "exec-out", "screencap", "-p", "-d", ids[1 if bottom else 0]]))
        return target
