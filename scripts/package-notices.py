"""Carry the engine and native dependency licenses inside every APK."""
from pathlib import Path
import shutil

root = Path(__file__).resolve().parents[1]
target = root / "android/app/build/generated/licenses/licenses"
target.mkdir(parents=True,exist_ok=True)
sources = {"Vanilla-Conquer.txt":root/"License.txt",
           "SDL2.txt":root/".local/sources/SDL2-2.32.10/LICENSE.txt",
           "OpenAL-Soft.txt":root/".local/sources/openal-soft-1.23.1/COPYING",
           "OpenAL-BSD-3-Clause.txt":root/".local/sources/openal-soft-1.23.1/BSD-3Clause"}
for name,source in sources.items(): shutil.copyfile(source,target/name)
