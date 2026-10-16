#include "wwstd.h"
#include "settings.h"
#include "ini.h"
#include "miscasm.h"
#if ANDROID
#include "SDL.h"
#endif

SettingsClass Settings;

#if ANDROID
extern SDL_Window* window;
static bool g_onScreenControlsActive = true;

extern "C" {
__attribute__((used)) __attribute__((visibility("default")))
void setUseDoseModeState(const bool useDosMode) {
    Settings.Video.DOSMode = useDosMode;
}
__attribute__((used)) __attribute__((visibility("default")))
void setFrameRateLimit(const int frameRateLimit) {
    Settings.Video.FrameLimit = frameRateLimit;
}
__attribute__((used)) __attribute__((visibility("default")))
void setOnScreenControlsState(const bool onScreenControlsActive) {
    g_onScreenControlsActive = onScreenControlsActive;
    if (onScreenControlsActive) {
        Settings.Mouse.RawInput = false;
    }
}
__attribute__((used)) __attribute__((visibility("default")))
void setMouseSensitivity(const int mouseSensitivity) {
    Settings.Mouse.Sensitivity = mouseSensitivity;
}
__attribute__((used)) __attribute__((visibility("default")))
void setControllerPointerSpeed(const int controllerPointerSpeed ) {
    Settings.Mouse.ControllerPointerSpeed = controllerPointerSpeed;
}
__attribute__((used)) __attribute__((visibility("default")))
void updateRawInputState (const bool enableRawInput){
    Settings.Mouse.RawInput = enableRawInput;
    if (window){
        SDL_SetRelativeMouseMode(enableRawInput ? SDL_TRUE : SDL_FALSE);
    }
}
}
#endif

SettingsClass::SettingsClass()
{
    /*
    ** Mouse settings
    */
#ifndef ANDROID
    Mouse.RawInput = true;
#else
    Mouse.RawInput = false;
#endif
    Mouse.Sensitivity = 100;
#ifndef ANDROID
    Mouse.ControllerEnabled = false;
#else
    Mouse.ControllerEnabled = true;
#endif
    Options.MouseWheelScrolling = true;

    Mouse.ControllerPointerSpeed = 10;

    /*
    ** Video settings
    */
    Video.WindowWidth = 640;
    Video.WindowHeight = 400;
    Video.Windowed = false;
    Video.Width = 0;
    Video.Height = 0;
#ifndef ANDROID
    Video.Boxing = true;
#else
    Video.Boxing = true;
#endif
    Video.BoxingAspectRatio = "16:10";
    Video.FrameLimit = 120;
    Video.InterpolationMode = 2;
    Video.HardwareCursor = false;
#ifndef ANDROID
    Video.DOSMode = false;
#else
    Video.DOSMode = true;
#endif
    Video.Scaler = "nearest";
    Video.Driver = "default";
    Video.PixelFormat = "default";
}

void SettingsClass::Load(INIClass& ini)
{
    char buf[128];

    /*
    ** Mouse settings
    */
#ifndef ANDROID
    Mouse.RawInput = ini.Get_Bool("Mouse", "RawInput", Mouse.RawInput);
#else
    Mouse.RawInput = !g_onScreenControlsActive && ini.Get_Bool("Mouse", "RawInput", Mouse.RawInput);
#endif
#ifndef ANDROID
    Mouse.Sensitivity = ini.Get_Int("Mouse", "Sensitivity", Mouse.Sensitivity);
    Mouse.ControllerEnabled = ini.Get_Bool("Mouse", "ControllerEnabled", Mouse.ControllerEnabled);
    Mouse.ControllerPointerSpeed = ini.Get_Int("Mouse", "ControllerPointerSpeed", Mouse.ControllerPointerSpeed);
#endif
    /*
    ** Compatibility with CNCNet configuration for this feature
    */
    Options.MouseWheelScrolling = ini.Get_Bool("Options", "MouseWheelScrolling", Options.MouseWheelScrolling);
    Options.MouseWheelScrolling = ini.Get_Bool("Mouse", "MouseWheelScrolling", Options.MouseWheelScrolling);

    /*
    ** Video settings
    */
    Video.WindowWidth = ini.Get_Int("Video", "WindowWidth", Video.WindowWidth);
    Video.WindowHeight = ini.Get_Int("Video", "WindowHeight", Video.WindowHeight);
    Video.Windowed = ini.Get_Bool("Video", "Windowed", Video.Windowed);
#ifndef ANDROID
    Video.Boxing = ini.Get_Bool("Video", "Boxing", Video.Boxing);
#else
    Video.Boxing = true;
#endif
    Video.BoxingAspectRatio = ini.Get_String("Video", "BoxingAspectRatio", Video.BoxingAspectRatio);
    Video.Width = ini.Get_Int("Video", "Width", Video.Width);
    Video.Height = ini.Get_Int("Video", "Height", Video.Height);
#ifndef ANDROID
    Video.FrameLimit = ini.Get_Int("Video", "FrameLimit", Video.FrameLimit);
    Video.HardwareCursor = ini.Get_Bool("Video", "HardwareCursor", Video.HardwareCursor);
    Video.DOSMode = ini.Get_Bool("Video", "DOSMode", Video.DOSMode);
#endif
    Video.Scaler = ini.Get_String("Video", "Scaler", Video.Scaler);
    Video.Driver = ini.Get_String("Video", "Driver", Video.Driver);
    Video.PixelFormat = ini.Get_String("Video", "PixelFormat", Video.PixelFormat);

    /*
    ** VQA and WSA interpolation mode 0 = scanlines, 1 = vertical doubling, 2 = linear
    */
    Video.InterpolationMode = Bound(ini.Get_Int("Video", "InterpolationMode", Video.InterpolationMode), 0, 2);

    /*
    ** Boxing and raw input require software cursor.
    */
    if (Video.Boxing || Mouse.RawInput || Mouse.ControllerEnabled) {
        Video.HardwareCursor = false;
    }

    ini.Get_String("Video", "ButtonStyle", "Default", buf, sizeof(buf));
    if (!stricmp(buf, "Gold")) {
        Video.ButtonStyle = 1;
    } else if (!stricmp(buf, "Classic") || !stricmp(buf, "DOS")) {
        Video.ButtonStyle = 0;
    } else {
        Video.ButtonStyle = -1;
    }
}

void SettingsClass::Save(INIClass& ini)
{
    /*
    ** Mouse settings
    */
    ini.Put_Bool("Mouse", "RawInput", Mouse.RawInput);
    ini.Put_Int("Mouse", "Sensitivity", Mouse.Sensitivity);
    ini.Put_Bool("Mouse", "ControllerEnabled", Mouse.ControllerEnabled);
    ini.Put_Int("Mouse", "ControllerPointerSpeed", Mouse.ControllerPointerSpeed);
    ini.Put_Bool("Mouse", "MouseWheelScrolling", Options.MouseWheelScrolling);

    /*
    ** Video settings
    */
    ini.Put_Int("Video", "WindowWidth", Video.WindowWidth);
    ini.Put_Int("Video", "WindowHeight", Video.WindowHeight);
    ini.Put_Bool("Video", "Windowed", Video.Windowed);
    ini.Put_Bool("Video", "Boxing", Video.Boxing);
    ini.Put_String("Video", "BoxingAspectRatio", Video.BoxingAspectRatio);
    ini.Put_Int("Video", "Width", Video.Width);
    ini.Put_Int("Video", "Height", Video.Height);
    ini.Put_Int("Video", "FrameLimit", Video.FrameLimit);
    ini.Put_Bool("Video", "HardwareCursor", Video.HardwareCursor);
    ini.Put_Bool("Video", "DOSMode", Video.DOSMode);
    ini.Put_String("Video", "Scaler", Video.Scaler);
    ini.Put_String("Video", "Driver", Video.Driver);
    ini.Put_String("Video", "PixelFormat", Video.PixelFormat);

    /*
    ** VQA and WSA interpolation mode 0 = scanlines, 1 = vertical doubling, 2 = linear
    */
    ini.Put_Int("Video", "InterpolationMode", Video.InterpolationMode);

    ini.Put_String(
        "Video", "ButtonStyle", Video.ButtonStyle == -1 ? "Default" : (Video.ButtonStyle == 1 ? "Gold" : "Classic"));
}
