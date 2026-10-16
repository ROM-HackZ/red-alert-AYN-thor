#include <jni.h>
#include <string>
#include <sys/stat.h>
#include <fstream>
#include <mutex>
#include <vector>
#include <sstream>
#include <cmath>
#include <algorithm>
#include <map>
#include <set>
#include <SDL.h>
#include "redalert/function.h"
#include "common/video.h"
#include "thor_bridge.h"
#include "common/keyframe.h"
extern void* Get_Shape_Header_Data(void*);
bool Thor_ExplicitAction = false;

namespace {
struct Command { int kind, a, b; float x, y; };
struct GadgetRect { int x, y, w, h; std::string label; };
std::mutex bridgeMutex;
std::vector<Command> pending;
std::string snapshot = "{\"active\":false}";
std::vector<jint> radarPixels;
std::map<int, std::vector<jint>> iconPixels;
std::set<int> preparedIcons;
std::string iconScenario;
std::vector<GadgetRect> gadgets;
unsigned gadgetTime = 0;
float stickX = 0, stickY = 0;
float panStickX = 0, panStickY = 0;
float panRemainderX = 0, panRemainderY = 0;
float zoom = 1;
bool pumping = false;
bool gadgetHasTactical = false, wasActive = false;
bool inMission = false;
bool mainMenu = false, antRequest = false;
unsigned previousPump = 0, previousSnapshot = 0;
std::string Quote(const char* text) {
    std::string out = "\"";
    if (text) for (const unsigned char* p = reinterpret_cast<const unsigned char*>(text); *p; ++p) {
        if (*p == '"' || *p == '\\') out += '\\';
        if (*p >= 32) out += *p;
    }
    return out + "\"";
}
bool Modal() { return SDL_GetTicks() - gadgetTime < 500 && !gadgetHasTactical && !gadgets.empty(); }
void Pointer(float x, float y) {
    int oldX, oldY;
    Get_Video_Mouse(oldX, oldY);
    Move_Video_Mouse(x - oldX, y - oldY);
}
void Publish() {
    bool active = inMission && GameActive && PlayerPtr && !InMovie;
    std::ostringstream out;
    out << "{\"active\":" << (active ? "true" : "false") << ",\"movie\":" << (InMovie ? "true" : "false")
        << ",\"modal\":" << (Modal() ? "true" : "false")
        << ",\"mainMenu\":" << (mainMenu ? "true" : "false")
        << ",\"width\":" << ScreenWidth << ",\"height\":" << ScreenHeight
        << ",\"zoom\":" << (active && !Modal() ? zoom : 1);
    out << ",\"inputX\":" << Map.TacButton.X << ",\"inputY\":" << Map.TacButton.Y
        << ",\"inputWidth\":" << Map.TacButton.Width << ",\"inputHeight\":" << Map.TacButton.Height;
    int pointerX, pointerY; Get_Video_Mouse(pointerX, pointerY);
    out << ",\"pointerX\":" << pointerX << ",\"pointerY\":" << pointerY;
    out << ",\"Navigation\":[";
    bool firstGadget = true;
    if (SDL_GetTicks() - gadgetTime < 500) for (auto& g : gadgets) {
        if (!firstGadget) out << ','; firstGadget = false;
        out << "{\"Label\":" << Quote(g.label.c_str()) << ",\"X\":" << g.x+g.w/2 << ",\"Y\":" << g.y+g.h/2 << '}';
    }
    out << ']';
    if (active) {
        int x1, y1, x2, y2; Map.Thor_Selection_Box(x1, y1, x2, y2);
        out << ",\"dragStartX\":" << x1 << ",\"dragStartY\":" << y1
            << ",\"dragEndX\":" << x2 << ",\"dragEndY\":" << y2
            << ",\"healthBarMode\":" << int(Rule.HealthBarDisplayMode);
        if (iconScenario != Scen.ScenarioName) {
            iconScenario = Scen.ScenarioName; preparedIcons.clear();
            std::lock_guard<std::mutex> guard(bridgeMutex); iconPixels.clear();
        }
        int units = 0, buildings = 0, infantry = 0;
        int groups[10] = {};
        for (int layer = 0; layer < LAYER_COUNT; ++layer) for (int i = 0; i < Map.Layer[layer].Count(); ++i) {
            auto* obj = Map.Layer[layer][i];
            if (!obj || !obj->IsActive || obj->IsInLimbo || obj->Owner() != PlayerPtr->Class->House) continue;
            if (obj->What_Am_I() == RTTI_UNIT) ++units;
            if (obj->What_Am_I() == RTTI_BUILDING) ++buildings;
            if (obj->What_Am_I() == RTTI_INFANTRY) ++infantry;
            if (obj->Is_Foot()) { int group = static_cast<FootClass*>(obj)->Group; if (group<10) ++groups[group]; }
        }
        bool deploy = false, canMove = false, canFire = false;
        for (int i = 0; i < CurrentObject.Count(); ++i) {
            auto* obj = CurrentObject[i];
            if (obj->Owner() != PlayerPtr->Class->House) continue;
            canMove = canMove || obj->Can_Player_Move(); canFire = canFire || obj->Can_Player_Fire();
            Thor_ExplicitAction = true;
            if (obj->Is_Foot() && obj->What_Action(obj) == ACTION_SELF) deploy = true;
            if (obj->What_Am_I() == RTTI_BUILDING && obj->Can_Player_Move()) deploy = true;
            Thor_ExplicitAction = false;
        }
        out << ",\"frame\":" << Frame << ",\"scenario\":" << Quote(Scen.ScenarioName)
            << ",\"money\":" << PlayerPtr->Available_Money() << ",\"power\":" << PlayerPtr->Power
            << ",\"drain\":" << PlayerPtr->Drain << ",\"selected\":" << CurrentObject.Count()
            << ",\"selection\":" << Quote(CurrentObject.Count() ? Text_String(CurrentObject[0]->Full_Name()) : "No selection")
            << ",\"targeting\":" << (Map.Thor_Targeting() ? "true" : "false")
            << ",\"dragging\":" << (Map.Thor_Dragging() ? "true" : "false")
            << ",\"tentative\":" << (Map.Thor_Tentative() ? "true" : "false")
            << ",\"leftMouse\":" << (Keyboard->Down(KN_LMOUSE) ? "true" : "false")
            << ",\"radar\":" << (Map.Is_Radar_Active() ? "true" : "false")
            << ",\"deploy\":" << (deploy ? "true" : "false")
            << ",\"canMove\":" << (canMove ? "true" : "false") << ",\"canFire\":" << (canFire ? "true" : "false")
            << ",\"buildings\":" << buildings << ",\"units\":" << units << ",\"infantry\":" << infantry;
        if (CurrentObject.Count()) {
            auto* obj = CurrentObject[0];
            out << ",\"selectedX\":" << Coord_X(obj->Center_Coord()) << ",\"selectedY\":" << Coord_Y(obj->Center_Coord());
        }
        out << ",\"groups\":[";
        for (int i=0; i<10; ++i) { if(i) out<<','; out<<groups[i]; }
        out << ']'
            << ",\"cameraX\":" << Coord_X(Map.TacticalCoord) << ",\"cameraY\":" << Coord_Y(Map.TacticalCoord)
            << ",\"cameraW\":" << Map.TacLeptonWidth << ",\"cameraH\":" << Map.TacLeptonHeight
            << ",\"mapX\":" << Map.MapCellX << ",\"mapY\":" << Map.MapCellY
            << ",\"mapW\":" << Map.MapCellWidth << ",\"mapH\":" << Map.MapCellHeight << ",\"build\":[";
        bool first = true;
        for (int c = 0; c < 2; ++c) {
            auto& strip = Map.Column[c];
            for (int i = 0; i < strip.BuildableCount; ++i) {
                const auto& item = strip.Buildables[i];
                const auto* type = Fetch_Techno_Type(item.BuildableType, item.BuildableID);
                bool special = item.BuildableType == RTTI_SPECIAL;
                if (!type && !special) continue;
                int iconId = int(item.BuildableType) * 1000 + item.BuildableID;
                if (!preparedIcons.count(iconId)) {
                    const void* shape = special ? strip.Get_Special_Cameo(SpecialWeaponType(item.BuildableID)) : type->Get_Cameo_Data();
                    if (shape) {
                        int w = Get_Build_Frame_Width(shape), h = Get_Build_Frame_Height(shape);
                        if (w > 0 && h > 0 && w <= 256 && h <= 256) {
                            std::vector<unsigned char> buffer(w * h);
                            auto theater = IsTheaterShape; IsTheaterShape = false;
                            auto frame = Build_Frame(shape, 0, buffer.data()); IsTheaterShape = theater;
                            if (frame) {
                                const auto* raw = static_cast<const unsigned char*>(Get_Shape_Header_Data(reinterpret_cast<void*>(frame)));
                                const auto* palette = static_cast<const unsigned char*>(CCPalette.Get_Data());
                                std::vector<jint> icon = {w, h};
                                for (int pixel = 0; pixel < w*h; ++pixel) {
                                    int color = raw[pixel];
                                    icon.push_back(0xff000000u | (palette[color*3]*4 << 16) | (palette[color*3+1]*4 << 8) | palette[color*3+2]*4);
                                }
                                std::lock_guard<std::mutex> guard(bridgeMutex); iconPixels[iconId] = std::move(icon);
                                preparedIcons.insert(iconId);
                            }
                        }
                    }
                }
                if (!first) out << ',';
                first = false;
                auto* factory = item.Factory < 0 ? nullptr : Factories.Raw_Ptr(item.Factory);
                bool ready = special ? PlayerPtr->SuperWeapon[item.BuildableID].Is_Ready() : factory && factory->Has_Completed();
                bool busy = !special && !factory && PlayerPtr->Fetch_Factory(item.BuildableType);
                out << "{\"type\":" << int(item.BuildableType) << ",\"id\":" << item.BuildableID
                    << ",\"name\":" << Quote(Text_String(special ? SpecialWeaponHelp[item.BuildableID] : type->Full_Name()))
                    << ",\"cost\":" << (type ? int(type->Cost_Of() * PlayerPtr->CostBias) : 0)
                    << ",\"special\":" << (special ? "true" : "false")
                    << ",\"ready\":" << (ready ? "true" : "false")
                    << ",\"busy\":" << (busy ? "true" : "false")
                    << ",\"progress\":" << (special ? PlayerPtr->SuperWeapon[item.BuildableID].Anim_Stage() : factory ? factory->Completion() : 0)
                    << ",\"producing\":" << (factory ? "true" : "false")
                    << ",\"held\":" << (factory && !factory->Is_Building() && !ready ? "true" : "false") << '}';
            }
        }
        out << ']';
    }
    out << '}';
    std::vector<jint> pixels;
    if (active && Map.Is_Radar_Active()) {
        const auto* colors = static_cast<const unsigned char*>(CCPalette.Get_Data());
        for (int y = 0; y < Map.MapCellHeight; ++y) for (int x = 0; x < Map.MapCellWidth; ++x) {
            auto& cell = Map[XY_Cell(x + Map.MapCellX, y + Map.MapCellY)];
            int color = cell.IsMapped ? cell.Cell_Color() : 0;
            if (cell.IsMapped) {
                auto* obj = cell.Cell_Techno();
                if (obj && obj->Is_Visible_On_Radar() && !obj->Is_Cloaked(PlayerPtr)) color = ColorRemaps[obj->House->RemapColor].Bar;
            }
            pixels.push_back(0xff000000u | (colors[color * 3] * 4 << 16) | (colors[color * 3 + 1] * 4 << 8) | (colors[color * 3 + 2] * 4));
        }
    }
    std::lock_guard<std::mutex> guard(bridgeMutex);
    radarPixels.swap(pixels);
    snapshot = out.str();
}
}

// Android never dereferences engine objects. Commands enter this queue; the
// original engine thread validates and executes them through its own handlers.
extern "C" JNIEXPORT void JNICALL Java_org_redalertthor_app_ThorActivity_command(JNIEnv*, jclass, jint kind, jint a, jint b, jfloat x, jfloat y) {
    std::lock_guard<std::mutex> guard(bridgeMutex);
    if (pending.size() < 256) pending.push_back({kind, a, b, x, y});
}
extern "C" JNIEXPORT jstring JNICALL Java_org_redalertthor_app_ThorActivity_state(JNIEnv* env, jclass) {
    std::lock_guard<std::mutex> guard(bridgeMutex);
    return env->NewStringUTF(snapshot.c_str());
}
extern "C" JNIEXPORT jintArray JNICALL Java_org_redalertthor_app_ThorActivity_radar(JNIEnv* env, jclass) {
    std::lock_guard<std::mutex> guard(bridgeMutex);
    auto array = env->NewIntArray(radarPixels.size());
    if (!radarPixels.empty()) env->SetIntArrayRegion(array, 0, radarPixels.size(), radarPixels.data());
    return array;
}
extern "C" JNIEXPORT jintArray JNICALL Java_org_redalertthor_app_ThorActivity_icon(JNIEnv* env, jclass, jint type, jint id) {
    std::lock_guard<std::mutex> guard(bridgeMutex);
    auto it = iconPixels.find(type * 1000 + id);
    auto array = env->NewIntArray(it == iconPixels.end() ? 0 : it->second.size());
    if (it != iconPixels.end()) env->SetIntArrayRegion(array, 0, it->second.size(), it->second.data());
    return array;
}
void Thor_Gadgets(GadgetClass* first) {
    gadgets.clear();
    gadgetHasTactical = false;
    for (auto* g = first; g && gadgets.size() < 150; g = g->Get_Next()) {
        if (g == &Map.TacButton) gadgetHasTactical = true;
        if (g->Thor_Enabled() && g->Get_ID() && g->Width > 2 && g->Height > 2)
            gadgets.push_back({g->X, g->Y, g->Width, g->Height, g->Thor_Label() ? g->Thor_Label() : ""});
    }
    gadgetTime = SDL_GetTicks();
}
void Thor_Pump() {
    if (pumping || !Keyboard) return;
    pumping = true;
    unsigned now = SDL_GetTicks();
    float dt = std::min(0.05f, (now - previousPump) / 1000.0f);
    previousPump = now;
    std::vector<Command> commands;
    { std::lock_guard<std::mutex> guard(bridgeMutex); commands.swap(pending); }
    bool active = inMission && GameActive && PlayerPtr && !InMovie && !Modal();
    bool enteringMission = active && !wasActive;
    wasActive = active;
    for (auto cmd : commands) {
        switch (cmd.kind) {
        case 1: {
            int x, y;
            if (cmd.x < 0) Get_Video_Mouse(x, y);
            else { x = cmd.x; y = cmd.y; Pointer(x, y); }
            Keyboard->Put_Mouse_Message(cmd.a == 2 ? VK_RBUTTON : VK_LBUTTON, x, y, cmd.b != 0);
            break;
        }
        case 2: Keyboard->Put_Key_Message(cmd.a, cmd.b != 0); break;
        case 3:
            stickX = cmd.x; stickY = cmd.y;
            break;
        case 16:
            panStickX = cmd.x; panStickY = cmd.y;
            break;
        case 4:
            if (active) for (auto& strip : Map.Column) for (int i = 0; i < strip.BuildableCount; ++i)
                if (strip.Buildables[i].BuildableType == cmd.a && strip.Buildables[i].BuildableID == cmd.b)
                    strip.Thor_Click(i, cmd.x != 0);
            break;
        case 5:
            if (!active) break;
            switch (cmd.a) {
            case 0: Unselect_All(); break;
            case 1: Map.Center_Map(); break;
            case 2: Map.Repair_Mode_Control(-1); break;
            case 3: Map.Sell_Mode_Control(-1); break;
            case 4:
                Thor_ExplicitAction = true;
                for (int i = 0; i < CurrentObject.Count(); ++i) {
                    auto* object = CurrentObject[i];
                    if (object->Owner() != PlayerPtr->Class->House) continue;
                    if (object->Is_Foot() && object->What_Action(object) == ACTION_SELF)
                        object->Active_Click_With(ACTION_SELF, object);
                    if (object->What_Am_I() == RTTI_BUILDING && object->Can_Player_Move())
                        static_cast<BuildingClass*>(object)->Active_Click_With(ACTION_MOVE, Coord_Cell(object->Center_Coord()));
                }
                Thor_ExplicitAction = false;
                break;
            case 5: {
                int x,y,w,h; Thor_Viewport(ScreenWidth,ScreenHeight,x,y,w,h);
                Map.Select_These(XY_Coord(Pixel_To_Lepton(x),Pixel_To_Lepton(y)), XY_Coord(Pixel_To_Lepton(x+w),Pixel_To_Lepton(y+h)));
                break;
            }
            case 6: {
                int x,y,w,h; Thor_Viewport(ScreenWidth,ScreenHeight,x,y,w,h);
                if (CurrentObject.Count()) {
                    auto* type = &CurrentObject[0]->Class_Of();
                    for (int layer = 0; layer < LAYER_COUNT; ++layer)
                        for (int i = 0; i < Map.Layer[layer].Count(); ++i) {
                            auto* obj = Map.Layer[layer][i]; int px, py;
                            if (obj && &obj->Class_Of() == type && obj->Owner() == PlayerPtr->Class->House &&
                                Map.Coord_To_Pixel(obj->Center_Coord(), px, py) && px>=x && py>=y && px<x+w && py<y+h) obj->Select();
                        }
                }
                break;
            }
            }
            Map.Flag_To_Redraw(true);
            break;
        case 6:
            if (active && Map.Is_Radar_Active()) {
                int x = (Map.MapCellX + std::max(0.f, std::min(1.f, cmd.x)) * Map.MapCellWidth) * CELL_LEPTON_W;
                int y = (Map.MapCellY + std::max(0.f, std::min(1.f, cmd.y)) * Map.MapCellHeight) * CELL_LEPTON_H;
                Map.Center_Map(XY_Coord(x, y)); Map.Flag_To_Redraw(true);
            }
            break;
        case 7: if (active) zoom = std::max(1.f, std::min(2.f, zoom + cmd.x)); break;
        case 8:
            stickX = stickY = panStickX = panStickY = panRemainderX = panRemainderY = 0;
            Keyboard->Put_Mouse_Message(VK_LBUTTON, 0, 0, true);
            Keyboard->Put_Mouse_Message(VK_RBUTTON, 0, 0, true);
            for (int key : {SDL_SCANCODE_LSHIFT, SDL_SCANCODE_LCTRL, SDL_SCANCODE_LALT}) Keyboard->Put_Key_Message(key, true);
            break;
        case 9: Pointer(cmd.x, cmd.y); break;
        case 10:
            if (active) Map.Set_Tactical_Position(XY_Coord(std::max(0, Coord_X(Map.DesiredTacticalCoord) + int(cmd.x)), std::max(0, Coord_Y(Map.DesiredTacticalCoord) + int(cmd.y))));
            break;
        case 11:
            if (now - gadgetTime < 500) {
                int x, y; Get_Video_Mouse(x, y); float best = 1e9; GadgetRect chosen{};
                for (auto r : gadgets) {
                    float dx = r.x + r.w / 2 - x, dy = r.y + r.h / 2 - y;
                    float along = dx * cmd.a + dy * cmd.b, across = std::abs(dx * cmd.b - dy * cmd.a);
                    if (along > 3 && along + across * 2 < best) { best = along + across * 2; chosen = r; }
                }
                if (best < 1e9) Pointer(chosen.x + chosen.w / 2, chosen.y + chosen.h / 2);
            }
            break;
        case 12:
            if (active && cmd.a >= 0 && cmd.a < 10) {
                if(cmd.b==2) {
                    std::vector<ObjectClass*> selected;
                    for(int i=0;i<CurrentObject.Count();++i) selected.push_back(CurrentObject[i]);
                    Handle_Team(cmd.a,1); Handle_Team(cmd.a,2);
                    Unselect_All();
                    for(auto* object:selected) object->Select();
                } else Handle_Team(cmd.a,cmd.b==1?2:cmd.b==3?3:0);
            }
            break;
        case 14: if (active) Map.Thor_Cancel(); break;
        case 15: if (mainMenu && Is_Counterstrike_Installed()) antRequest = true; break;
        }
    }
    if (std::abs(stickX) + std::abs(stickY) > 0.01f) {
        Move_Video_Mouse(stickX * 420 * dt / (active ? zoom : 1), stickY * 420 * dt / (active ? zoom : 1));
        if(active) {
            int x,y,w,h,px,py; Thor_Viewport(ScreenWidth,ScreenHeight,x,y,w,h); Get_Video_Mouse(px,py);
            Pointer(std::max(x+4,std::min(x+w-5,px)),std::max(y+4,std::min(y+h-5,py)));
        }
    }
    if (active && (std::abs(panStickX) + std::abs(panStickY) > 0.01f)) {
        panRemainderX += panStickX * 2200 * dt; panRemainderY += panStickY * 2200 * dt;
        int dx = int(panRemainderX), dy = int(panRemainderY);
        panRemainderX -= dx; panRemainderY -= dy;
        Map.Set_Tactical_Position(XY_Coord(std::max(0, Coord_X(Map.DesiredTacticalCoord) + dx), std::max(0, Coord_Y(Map.DesiredTacticalCoord) + dy)));
    }
    if (active && Map.IsSidebarActive) Map.Activate(0);
    // Loading a save restores Map's dimensions, but the static tactical gadget
    // and WindowList still carry the old top-bar inset. Rebind both together.
    if (active && (enteringMission || Map.TacPixelX != 0 || Map.TacPixelY != 0
        || Map.TacButton.X != 0 || Map.TacButton.Y != 0
        || Map.TacButton.Width != ScreenWidth || Map.TacButton.Height != ScreenHeight))
        Map.Set_View_Dimensions(0, 0);
    if (now - previousSnapshot >= 100) { previousSnapshot = now; Publish(); }
    pumping = false;
}

void Thor_Viewport(int width, int height, int& x, int& y, int& w, int& h) {
    float scale = inMission && GameActive && PlayerPtr && !InMovie && !Modal() ? zoom : 1;
    w = int(width / scale); h = int(height / scale);
    x = (width - w) / 2; y = (height - h) / 2;
}
void Thor_Mission(bool active) { inMission = active; }
void Thor_Main_Menu(bool active) { mainMenu = active; }
bool Thor_Ants_Requested() { bool value = antRequest; antRequest = false; return value; }
#include "common/settings.h"

extern "C" void setPathToResources(const char*);
extern "C" void setPathToConfigsDirectory(const char*);
extern "C" void setUseDoseModeState(bool);
extern "C" void setFrameRateLimit(int);
extern "C" void setOnScreenControlsState(bool);

extern "C" JNIEXPORT void JNICALL Java_org_redalertthor_app_ThorActivity_configure(JNIEnv* env, jclass, jstring path)
{
    const char* chars = env->GetStringUTFChars(path, nullptr);
    std::string root(chars);
    env->ReleaseStringUTFChars(path, chars);
    mkdir((root + "/user").c_str(), 0700);
    mkdir((root + "/user/vanillara").c_str(), 0700);
    // Never import a Windows INI: its video/audio drivers and paths are invalid here.
    std::string config = root + "/user/vanillara/REDALERT.INI";
    if (!std::ifstream(config).good()) {
        std::ofstream ini(config);
        ini << "[Paths]\nDataPath=" << root << "/game\nUserPath=" << root
            << "/user/vanillara\n[Intro]\nPlayIntro=no\n[Expansions]\nCounterstrikeEnabled=yes\nAftermathEnabled=yes\n";
    }
    setPathToResources((root + "/game").c_str());
    setPathToConfigsDirectory((root + "/user").c_str());
    setUseDoseModeState(false);
    setFrameRateLimit(60);
    setOnScreenControlsState(false);
    Settings.Mouse.RawInput = true;
    Settings.Mouse.ControllerEnabled = false;
    Settings.Video.Boxing = true;
}
