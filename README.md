# Red Alert — AYN Thor

Original Red Alert on the Thor. Campaigns, Counterstrike, Aftermath, buttons, sticks, and a proper command deck on the bottom screen.

This uses the original game engine through Vanilla Conquer's Android branch. Bring your own game files. The APK and installer contain no retail game data.

**Development preview 0.1.0-dev.2.** Tested on a Thor: both original campaign starts, Counterstrike, Aftermath, Ant missions, campaign save/load, building placement, infantry production, groups and returning from Home. Every campaign mission has not been played through. See [verification and remaining limits](docs/Verification.md).

## Install

| Computer | Setup |
|---|---|
| Windows | Run `RedAlert-Thor-Setup.exe`, choose your Steam Red Alert folder, then click **Install on Thor**. The packaged installer includes the APK and ADB. |
| macOS / Linux | Run `python3 scripts/install-thor.py` for the same UI. Requires Python with Tkinter, Android SDK Platform Tools and the built APK. A terminal option is below. |

Connect the Thor by USB, unlock it and allow USB debugging. Save your game before updating. Setup verifies each copy and reuses files that already match. App updates keep your saves.

Once installed, open **Red Alert - Thor** and play. It runs on its own after a reboot.

Choose your Steam `Command & Conquer Red Alert` folder. Setup imports the base game, both expansions, all four disc archives, and the campaign map video and trailers when present. Windows executables, DLLs and PC settings stay on your computer.

```sh
python3 scripts/install-thor.py --game "/path/to/Command & Conquer Red Alert" --adb "/path/to/adb" --apk artifacts/RedAlert-Thor.apk
```

## Controls

| Control | Action |
|---|---|
| Left stick | Pan the battlefield beneath a centred aiming cursor, like Generals Thor. Move the cursor in menus. |
| Right stick up / down | Zoom in / out. |
| Hold R3 + right stick | Move the cursor freely. |
| Hold L3 + left stick | Move the cursor freely without panning, leaving your right hand free for A. |
| A | Select, issue an order, or confirm a building placement. Hold A and move a stick to drag a selection box. |
| B | Cancel targeting or placement, keeping your selection. Otherwise deselect or go back. |
| X | Guard area. |
| Y | Stop. |
| Hold LT | Add units to the selection. |
| Hold RT | Command wheel. Choose with the **left stick**, press A to use it. Release RT or press B to close without choosing. |
| Hold LB | Group wheel. Left stick chooses; A recalls, X replaces, LT + X adds, Y centres. D-pad left/right switches groups 1–8 / 9–10. Release LB or press B to close. |
| Tap L3 without moving the stick | Center the camera on the selection. |
| LT + L3 | Select the same unit type on screen. |
| RB | Toggle minimap navigation. Left stick moves the marker; A jumps there; B closes it. Requires working radar. |
| D-pad up / down | Choose a command-deck button. In menus, jump between the game's buttons. |
| D-pad left / right | Change command-deck pages. |
| Hold LT + D-pad | Jump between the game's own buttons. |
| Select | Switch between Commands, Build & Train and Powers. |
| Start | Open the game menu. |

L3 and R3 mean clicking the left and right sticks. Hold L3 while aiming with the left stick; A selects or gives an order at that cursor. Releasing L3 returns to centred aiming. A quick L3 click without moving still centres your selection.

Groups follow the original RA1 rule: each unit belongs to one group. Assigning it to another group moves it out of the previous one.

| Touch gesture | Action |
|---|---|
| Tap | Select or issue an order. |
| One-finger drag | Selection rectangle. |
| Two-finger drag | Pan the map. |
| Pinch | Zoom. |
| Two-finger tap | Deselect. |
| Tap or drag on the bottom-screen minimap | Jump or pan across those map positions. |

## Building, training and powers

**Build & Train** follows the original sidebar. Choices stay available while you have the required buildings; you do not have to keep a production building selected.

| Action | What happens |
|---|---|
| Tap a build tile | Start production, resume a paused job, or use a completed item. |
| Hold a tile during production | Pause it. Hold again to cancel and refund it. |
| Choose a ready building | Enter placement mode. Move to a valid spot and press A. |
| B during placement | Leave placement mode. The completed building is still ready to use. |
| Deploy / unload | Use the selected unit's native ability. MCVs need clear space. Packing a yard is available only when the original rules allow it. |

RA1 has fixed camera and building orientations. Its production limits and technology requirements still apply. **Powers** shows the actual Red Alert powers available to your faction and mission.

The deck reads the engine's selection, build lists, production progress, artwork and radar directly. It does not detect buttons from screenshots. Radar respects the original shroud and availability rules.

The main menu has the original campaign and expansion choices. The bottom screen also has an **Ant missions** button. Saves without a typed description get a default name, so you can save using the controller.

## Files and saves

| Location on the Thor | Contents |
|---|---|
| `Android/data/org.redalertthor.app/files/game/` | Imported retail data. |
| `Android/data/org.redalertthor.app/files/user/vanillara/` | Thor settings and saves. |
| `Android/data/org.redalertthor.app/files/import-manifest.json` | Sizes and SHA-256 hashes of imported files. |

Use saves made by the Thor build. Setup does not copy or change your PC saves. Back up the Thor's `user` folder before uninstalling the app; Android removes app data on uninstall.

Campaigns support save/load. The original skirmish menu disables saving. Save a campaign before leaving it for a long time; Android can close background apps when it needs memory.

If sound is silent, check Android's media volume and the AYN game profile. The test Thor's game assistant had media volume set to zero.

## Build

Dependencies are pinned in [THOR-UPSTREAM.json](THOR-UPSTREAM.json). You need JDK 17, Python 3, CMake, Ninja, Android SDK 36, build-tools 36.0.0, NDK 27.2.12479018, and Gradle 8.11.1. Set `ANDROID_HOME` and `JAVA_HOME` for your machine.

```sh
python scripts/build-thor.py
python -m unittest discover -s scripts/tests -v
python scripts/check-source.py
```

Windows builds use WSL Ubuntu and stage source under `~/.cache/redalert-thor/build` to avoid slow builds through OneDrive. Linux builds run the shell script directly. The APK is written to `artifacts/RedAlert-Thor.apk`.

To package a desktop installer on its target OS, install PyInstaller 6.16.0 and run:

```sh
python scripts/package-installer.py --adb-dir "/path/to/platform-tools"
```

ADB input probes and the exported QA receiver are development tools. The receiver is included only in debug builds. Test scripts live in `scripts/qa/`; temporary results belong in `artifacts/`.

## Upstream

Engine base: [sandstranger/Vanilla-Conquer](https://github.com/sandstranger/Vanilla-Conquer), revision `00733633a026aac4a02e5ccf29a4f14db80441a1`. That Android work is also used by Classic Core. Earlier engine work comes from the Vanilla Conquer contributors and EA's source release.

Updates are deliberate: review the engine changes, update the pin, merge, then rerun campaign, expansion, production, input and lifecycle tests. A new upstream commit does not silently replace the engine in an installed app.

The engine is GPLv3 with EA's additional terms; see [License.txt](License.txt). SDL2 and OpenAL Soft notices are included in the APK. The original upstream README is preserved in [docs/Vanilla-Conquer.md](docs/Vanilla-Conquer.md).
