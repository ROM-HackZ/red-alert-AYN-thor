# Verification

These checks use the installed app and its original engine state. A successful
build alone is not a gameplay check. Retail files and temporary results stay out
of Git.

## Device checks

Tested on an unrooted AYN Thor running Android 13, with the game on the 1920×1080
display and the command deck on the 1240×1080 display.

| Area | Observed result |
|---|---|
| Original campaigns | Allied `SCG01EA.INI` and Soviet `SCU01EA.INI` started. |
| Counterstrike | Original mission list, briefing and `SCG20EA.INI` started. |
| Aftermath | Original mission list, briefing and `SCG43EA.INI` started. |
| Ant missions | Bottom-screen button started original `SCA01EA.INI`. |
| Campaign saves | A Counterstrike save loaded after an APK update. An Allied save made without typing a description reloaded at frame 410. The in-app Export saves ZIP matches the latest save byte for byte. Android blocks ordinary USB reads of some app-created files, so export is the supported backup route. |
| Offline skirmish | Native skirmish menu started `SCM22EA.INI`. |
| Production | MCV deployed after moving to clear space. Power plant and barracks placed; rifle infantry trained and appeared in the world. |
| Production cancellation | Pause, resume, cancel/refund and cancelling placement while keeping the completed item passed. |
| Groups | LB + X assigned, LB + A recalled, LT + X added while preserving selection, and Y selected the group for native camera centering. D-pad paging and group 9 assignment passed. |
| Wheels | Both use the left stick and A to confirm. Releasing RT or LB closed the wheel without executing its highlighted action. |
| Cursor | Left stick reached the visible edge without panning. Neutral stick left the cursor parked; a later A press selected the aimed unit. |
| Camera/touch | Right stick panned while keeping the cursor parked and zoom unchanged. R3 + right-stick-up zoomed without panning; down restored 1x. Two-finger pan, pinch and deselection changed the expected live state. |
| Selection rectangles | A held with left-stick cursor movement and a one-finger touch drag both selected multiple units in a loaded campaign. Right-stick deflection did not move the map underneath a box. Pressing/releasing L3 and R3 during a box kept the drag intact; A release finished it without resetting the cursor. The input area covers the full screen after loading a save, including the former top-bar region. |
| Radar | A powered radar dome activated the bottom minimap. Taps, dragging and RB/stick/A navigation moved the camera toward the requested positions. |
| App return | Home followed by the launcher preserved the Linux process and campaign, and cleared held stick/trigger state. |
| Import retry | Running the installer with an identical APK and data preserved the paused mission and process. |
| Audio | Android reported an active 48 kHz stereo track with nonzero gain and advancing output frames after unmuting media volume. |
| Windows installer | The bundled executable opened its setup window without a separate Python installation. Game folder is the main field; custom APK/ADB/device choices are under Advanced. |

This is a development preview. Full campaign playthroughs, every transport and
special weapon, other Android devices, and macOS/Linux desktop UI execution have
not been verified. Android may kill a background process; app-return support does
not recover an unsaved game after process death. The native skirmish menu disables
saving; campaign save/load works.

The signed `0.1.0-dev.3` download was installed over the test build without
uninstalling. Its native libraries match the Android 13 target build that passed
both controller suites. The public APK loaded the existing Allied save, selected
nine units with A plus left stick, and exported all four saves unchanged. Its
manifest has no QA receiver and Android reports it as non-debuggable. Installer
checks passed on Windows, macOS and Linux in GitHub Actions; the Android build
job passed too. These host checks do not verify the desktop UI on macOS/Linux.

## Repeat the controller checks

The exported QA receiver exists only in debug builds. Each state request must get
an `ok` response from the running activity before reading its JSON file. The
reader rejects an old file left behind after the app exits.

Build and push the ADB-only input probe:

```sh
bash scripts/qa/build-probe.sh
adb push artifacts/thor-input-probe.jar /data/local/tmp/redalert-thor-input-probe.jar
```

Load a mission, save it if supported, close its menus and leave the controls
untouched. Friendly units must be visible. Then run:

```sh
python scripts/qa/verify-controls.py --adb /path/to/adb --serial DEVICE_SERIAL
python scripts/qa/verify-precision.py --adb /path/to/adb --serial DEVICE_SERIAL
```

These change groups 1 and 9, selection, camera position and zoom, then pause the game.
Results, APK hash and screenshots go into `artifacts/`. A failed check exits with
an error and keeps its partial report. No campaign success flags or production
completion flags are injected.

For production, use the bottom deck to deploy an MCV in a clear area, place a
power plant, place barracks and train infantry. Assert world counts as well as
the factory state: a completed factory object is not yet a placed building.
Check native refunds, B during placement, new technology choices and the
production tile's original artwork. Test radar only after it is powered and
active; check taps, dragging and RB navigation against live camera coordinates.

For updates, save a campaign, update with `adb install -r`, launch and load it.
For lifecycle checks, record PID/scenario/frame before Home and compare after
returning. Never accept a stale screenshot or JSON file as proof of a live game.

## Local checks

```sh
python -m unittest discover -s scripts/tests -v
python scripts/check-source.py
git diff --check
```

Installer tests cover missing data before device writes, a corrupt transfer not
replacing live data, verified retries, optional movie assets and preservation of
PC saves/settings. The source audit rejects retail archives, videos, palettes and
private signing keys in Git or the APK.

After testing, close the game, restore changed media volume, and remove only the
probe, document-picker dump and QA snapshot created by these tools:

```sh
adb shell am force-stop org.redalertthor.app
adb shell rm -f /data/local/tmp/redalert-thor-input-probe.jar /data/local/tmp/redalert-doc-picker.xml /sdcard/Android/data/org.redalertthor.app/files/qa-state.json
```
