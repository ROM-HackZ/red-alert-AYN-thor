#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
build_type="${THOR_BUILD_TYPE:-debug}"
case "$build_type" in
    debug) gradle_task=assembleDebug; apk_name=app-debug.apk ;;
    release)
        : "${THOR_SIGNING_STORE:?Set THOR_SIGNING_STORE to your private signing key}"
        : "${THOR_SIGNING_PASSWORD:?Set THOR_SIGNING_PASSWORD}"
        : "${THOR_SIGNING_ALIAS:?Set THOR_SIGNING_ALIAS}"
        : "${THOR_KEY_PASSWORD:?Set THOR_KEY_PASSWORD}"
        gradle_task=assembleRelease; apk_name=app-release.apk ;;
    *) echo "THOR_BUILD_TYPE must be debug or release" >&2; exit 1 ;;
esac
export ANDROID_HOME="${ANDROID_HOME:-$HOME/Android/Sdk}"
export JAVA_HOME="${JAVA_HOME:-/usr/lib/jvm/java-17-openjdk-amd64}"
export PATH="$HOME/.local/bin:$JAVA_HOME/bin:$PATH"
ndk="${ANDROID_NDK_HOME:-$ANDROID_HOME/ndk/27.2.12479018}"
mkdir -p artifacts logs .local
python3 scripts/fetch-dependencies.py
toolchain=(-DCMAKE_TOOLCHAIN_FILE="$ndk/build/cmake/android.toolchain.cmake" -DANDROID_ABI=arm64-v8a -DANDROID_PLATFORM=android-24 -DCMAKE_BUILD_TYPE=Release -DCMAKE_POSITION_INDEPENDENT_CODE=ON)
if [ ! -f .local/sdl-build/build.ninja ]; then
cmake -S .local/sources/SDL2-2.32.10 -B .local/sdl-build -G Ninja "${toolchain[@]}" -DSDL_SHARED=ON -DSDL_STATIC=OFF -DSDL_TEST=OFF -DSDL_TESTS=OFF -DSDL_HIDAPI=ON > logs/dependencies.log 2>&1
fi
cmake --build .local/sdl-build -j 6 >> logs/dependencies.log 2>&1
if [ ! -f .local/al-build/build.ninja ]; then
cmake -S .local/sources/openal-soft-1.23.1 -B .local/al-build -G Ninja "${toolchain[@]}" -DALSOFT_UTILS=OFF -DALSOFT_EXAMPLES=OFF -DALSOFT_TESTS=OFF >> logs/dependencies.log 2>&1
fi
cmake --build .local/al-build -j 6 >> logs/dependencies.log 2>&1
cmake -S . -B .local/android-native -G Ninja "${toolchain[@]}" -DTHOR_ANDROID=ON -DBUILD_VANILLATD=OFF -DNETWORKING=OFF -DSDL2_LIBRARY="$PWD/.local/sdl-build/libSDL2.so" -DSDL2_INCLUDE_DIR="$PWD/.local/sources/SDL2-2.32.10/include" -DOPENAL_LIBRARY="$PWD/.local/al-build/libopenal.so" -DOPENAL_INCLUDE_DIR="$PWD/.local/sources/openal-soft-1.23.1/include" > logs/native-build.log 2>&1
cmake --build .local/android-native -j 6 >> logs/native-build.log 2>&1 || { tail -n 65 logs/native-build.log; exit 1; }
mkdir -p android/app/src/main/jniLibs/arm64-v8a android/app/build/generated/sdl
cp .local/android-native/redalert/libvanillara.so .local/sdl-build/libSDL2.so .local/al-build/libopenal.so android/app/src/main/jniLibs/arm64-v8a/
cp -r .local/sources/SDL2-2.32.10/android-project/app/src/main/java/org android/app/build/generated/sdl/
python3 scripts/package-notices.py
gradle="${THOR_GRADLE:-$(command -v gradle || true)}"
if [ -z "$gradle" ] && [ -d "$HOME/.gradle/wrapper/dists/gradle-8.11.1-bin" ]; then
    gradle="$(find "$HOME/.gradle/wrapper/dists/gradle-8.11.1-bin" -path '*/bin/gradle' -type f -print -quit)"
fi
if [ -z "$gradle" ]; then
    echo "Install Gradle 8.11.1 on PATH or set THOR_GRADLE to its bin/gradle executable." >&2
    exit 1
fi
(cd android; "$gradle" --no-daemon "$gradle_task" > ../logs/apk-build.log 2>&1) || { tail -n 65 logs/apk-build.log; exit 1; }
cp "android/app/build/outputs/apk/$build_type/$apk_name" artifacts/RedAlert-Thor.apk
sha256sum artifacts/RedAlert-Thor.apk
