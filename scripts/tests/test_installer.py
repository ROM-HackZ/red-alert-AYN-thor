"""Exercise copy integrity, retries and the boundary around user-owned saves."""
import hashlib
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("installer", Path(__file__).parents[1] / "install-thor.py")
installer = importlib.util.module_from_spec(spec); spec.loader.exec_module(installer)


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(); self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name); self.game = self.root / "Steam game"
        self.game.mkdir(); self.apk = self.root / "test.apk"; self.apk.write_bytes(b"apk")
        self.adb = self.root / ("adb.exe" if installer.os.name == "nt" else "adb"); self.adb.write_bytes(b"tool")
        for name in installer.DATA: (self.game/name.lower()).write_bytes(name.encode()*1000)
        (self.game/"REDALERT.INI").write_text("My original Windows settings")
        (self.game/"SAVEGAME.000").write_bytes(b"valuable save")
        self.remote = {}; self.calls = []; self.corrupt = False

    def fake_adb(self, command, **kwargs):
        args = command[1:]; self.calls.append(args)
        if args[0] == "-s": args = args[2:]
        output = ""
        if args[0] == "devices": output = "List of devices attached\nTEST\tdevice\n"
        elif args[0] == "install": self.remote["/data/app/test/base.apk"] = hashlib.sha256(self.apk.read_bytes()).hexdigest()
        elif args[:3] == ["shell","pm","path"]:
            if "/data/app/test/base.apk" in self.remote: output = "package:/data/app/test/base.apk"
        elif args[:3] == ["shell","df","-k"]: output = "Filesystem 1K-blocks Used Available Use% Mounted\n/data 999999 0 999999 0% /data"
        elif args[0] == "push": self.remote[args[2]] = hashlib.sha256(Path(args[1]).read_bytes()).hexdigest()
        elif args[:3] == ["shell","sh","-c"]:
            path = args[3].strip("'").split()[1]
            if path in self.remote: output = self.remote[path]+"  "+path
        elif args[:2] == ["shell","sha256sum"]:
            output = ("bad-copy" if self.corrupt else self.remote[args[2]])+"  "+args[2]
        elif args[:2] == ["shell","mv"]: self.remote[args[3]] = self.remote.pop(args[2])
        return subprocess.CompletedProcess(command,0,output,"")

    def run_install(self):
        with patch.object(installer.subprocess,"run",side_effect=self.fake_adb):
            installer.install(self.game,str(self.adb),self.apk,log=lambda message:None,launch=False)

    def test_requires_both_expansions_before_modifying_device(self):
        (self.game/"main4.mix").unlink()
        with patch.object(installer.subprocess,"run") as run:
            with self.assertRaisesRegex(ValueError,"MAIN4.MIX"): self.run_install()
            run.assert_not_called()

    def test_retry_reuses_verified_archives_and_leaves_saves_and_pc_settings(self):
        self.run_install()
        self.calls.clear(); self.run_install()
        pushes = [args for args in self.calls if "push" in args]
        self.assertEqual(len(pushes),1) # only the import manifest
        self.assertFalse(any("install" in args or "force-stop" in args for args in self.calls))
        self.assertEqual((self.game/"REDALERT.INI").read_text(),"My original Windows settings")
        self.assertEqual((self.game/"SAVEGAME.000").read_bytes(),b"valuable save")
        self.assertFalse(any("rm" in args or "uninstall" in args or "clear" in args for args in self.calls))
        self.assertEqual(len([p for p in self.remote if p.endswith(".MIX")]),9)

    def test_corrupt_transfer_is_not_promoted_to_live_data(self):
        self.corrupt = True
        with self.assertRaisesRegex(RuntimeError,"verification failed"): self.run_install()
        self.assertTrue(any(path.endswith(".partial") for path in self.remote))
        self.assertFalse(any(path.endswith(".MIX") for path in self.remote))

    def test_includes_steam_campaign_map_and_movie_extras_when_present(self):
        for name in installer.OPTIONAL_DATA: (self.game/name).write_bytes(name.encode()*50)
        self.run_install()
        for name in installer.OPTIONAL_DATA:
            self.assertIn(installer.REMOTE+"/game/"+name,self.remote)


if __name__=="__main__": unittest.main()
