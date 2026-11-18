// Headless libretro host for the Flycast core (development only, never shipped): a hidden SDL OpenGL window gives the core its hardware-render context, frames are read back from the
// core's framebuffer and saved as BMP, scripted button presses navigate the game. No window is shown and no audio is played; the BIOS and save folders are local copies.
// usage: flyhost <flycast_libretro.dll> <system dir (contains dc/dc_boot.bin)> <save dir> <content .cue/.gdi/.chd> <frames> <out prefix> [shots f1,f2,...] [keys "START@100-105;A@200-203"]
// keys: A B X Y START UP DOWN LEFT RIGHT L R, frame ranges inclusive.
// FLYHOST_PER_PIXEL=1 requests Flycast's per-pixel alpha sorting for comparison captures.
#define SDL_MAIN_HANDLED
#include <SDL.h>
#include <SDL_opengl.h>
#include <charconv>
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <map>
#include <set>
#include <string>
#include <vector>
#ifdef _WIN32
#include <windows.h>
#define DLSYM(h, n) GetProcAddress((HMODULE)(h), n)
#else
#include <dlfcn.h>
#define DLSYM(h, n) dlsym(h, n)
#endif
typedef void (*retro_hw_context_reset_t)(void);
typedef uintptr_t (*retro_hw_get_current_framebuffer_t)(void);
typedef void (*retro_proc_address_t)(void);
typedef retro_proc_address_t (*retro_hw_get_proc_address_t)(const char*);
struct retro_hw_render_callback { unsigned context_type; retro_hw_context_reset_t context_reset; retro_hw_get_current_framebuffer_t get_current_framebuffer; retro_hw_get_proc_address_t get_proc_address;
    bool depth, stencil, bottom_left_origin; unsigned version_major, version_minor; bool cache_context; retro_hw_context_reset_t context_destroy; bool debug_context; };
struct retro_game_info { const char* path; const void* data; size_t size; const char* meta; };
struct retro_system_av_info { struct { unsigned base_width, base_height, max_width, max_height; float aspect_ratio; } geometry; struct { double fps, sample_rate; } timing; };
struct retro_variable { const char* key; const char* value; };
typedef bool (*retro_environment_t)(unsigned, void*);
typedef void (*retro_video_refresh_t)(const void*, unsigned, unsigned, size_t);
typedef void (*retro_audio_sample_t)(int16_t, int16_t);
typedef size_t (*retro_audio_sample_batch_t)(const int16_t*, size_t);
typedef void (*retro_input_poll_t)(void);
typedef int16_t (*retro_input_state_t)(unsigned, unsigned, unsigned, unsigned);
typedef void (*retro_log_printf_t)(int, const char*, ...);
struct retro_log_callback { retro_log_printf_t log; };

static std::string gSystem, gSave; static retro_hw_render_callback gHw; static bool gHwSet = false, gGlReady = false;
static SDL_Window* gWin = nullptr; static SDL_GLContext gCtx = nullptr;
static GLuint gFbo = 0, gTex = 0, gDepth = 0; static unsigned gW = 640, gH = 480; static int gFrame = 0;
static std::map<int, std::vector<std::pair<int, int>>> gKeys; static std::set<int> gShots; static std::string gOut;
static unsigned gMaxW = 640, gMaxH = 480; static std::vector<unsigned char> gPix; static unsigned gLastW = 0, gLastH = 0; static bool gHaveFrame = false;
typedef void (APIENTRY* PFNGENFB)(GLsizei, GLuint*); typedef void (APIENTRY* PFNBINDFB)(GLenum, GLuint); typedef void (APIENTRY* PFNFBTEX)(GLenum, GLenum, GLenum, GLuint, GLint);
typedef void (APIENTRY* PFNGENRB)(GLsizei, GLuint*); typedef void (APIENTRY* PFNBINDRB)(GLenum, GLuint); typedef void (APIENTRY* PFNRBSTORE)(GLenum, GLenum, GLsizei, GLsizei); typedef void (APIENTRY* PFNFBRB)(GLenum, GLenum, GLenum, GLuint);
static PFNGENFB glGenFramebuffersP; static PFNBINDFB glBindFramebufferP; static PFNFBTEX glFramebufferTexture2DP; static PFNGENRB glGenRenderbuffersP; static PFNBINDRB glBindRenderbufferP; static PFNRBSTORE glRenderbufferStorageP; static PFNFBRB glFramebufferRenderbufferP;
#define GL_FRAMEBUFFER_ 0x8D40
#define GL_RENDERBUFFER_ 0x8D41
#define GL_COLOR_ATTACHMENT0_ 0x8CE0
#define GL_DEPTH_STENCIL_ATTACHMENT_ 0x821A
#define GL_DEPTH24_STENCIL8_ 0x88F0
#define GL_READ_FRAMEBUFFER_ 0x8CA8

static void logf_(int, const char* fmt, ...) { va_list a; va_start(a, fmt); char b[1024]; vsnprintf(b, sizeof b, fmt, a); va_end(a); fputs(b, stderr); }
static uintptr_t getFbo() { return gFbo; }
static retro_proc_address_t getProc(const char* n) { return (retro_proc_address_t)SDL_GL_GetProcAddress(n); }

static bool createGl(unsigned type, unsigned major, unsigned minor) {
    if (SDL_InitSubSystem(SDL_INIT_VIDEO) != 0) { fprintf(stderr, "SDL video: %s\n", SDL_GetError()); return false; }
    SDL_GL_ResetAttributes();
    if (type == 3) { SDL_GL_SetAttribute(SDL_GL_CONTEXT_PROFILE_MASK, SDL_GL_CONTEXT_PROFILE_CORE); SDL_GL_SetAttribute(SDL_GL_CONTEXT_FLAGS, SDL_GL_CONTEXT_FORWARD_COMPATIBLE_FLAG); }
    else if (type == 1) SDL_GL_SetAttribute(SDL_GL_CONTEXT_PROFILE_MASK, SDL_GL_CONTEXT_PROFILE_COMPATIBILITY);
    else if (type == 2 || type == 4) { SDL_GL_SetAttribute(SDL_GL_CONTEXT_PROFILE_MASK, SDL_GL_CONTEXT_PROFILE_ES); }
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MAJOR_VERSION, major ? (int)major : 3); SDL_GL_SetAttribute(SDL_GL_CONTEXT_MINOR_VERSION, major ? (int)minor : 3);
    SDL_GL_SetAttribute(SDL_GL_DEPTH_SIZE, 24); SDL_GL_SetAttribute(SDL_GL_STENCIL_SIZE, 8);
    gWin = SDL_CreateWindow("flyhost", 0, 0, 64, 64, SDL_WINDOW_OPENGL | SDL_WINDOW_HIDDEN);
    if (!gWin) { fprintf(stderr, "window: %s\n", SDL_GetError()); return false; }
    gCtx = SDL_GL_CreateContext(gWin); if (!gCtx) { fprintf(stderr, "context: %s\n", SDL_GetError()); return false; }
    SDL_GL_MakeCurrent(gWin, gCtx); SDL_GL_SetSwapInterval(0);
    glGenFramebuffersP = (PFNGENFB)SDL_GL_GetProcAddress("glGenFramebuffers"); glBindFramebufferP = (PFNBINDFB)SDL_GL_GetProcAddress("glBindFramebuffer"); glFramebufferTexture2DP = (PFNFBTEX)SDL_GL_GetProcAddress("glFramebufferTexture2D");
    glGenRenderbuffersP = (PFNGENRB)SDL_GL_GetProcAddress("glGenRenderbuffers"); glBindRenderbufferP = (PFNBINDRB)SDL_GL_GetProcAddress("glBindRenderbuffer"); glRenderbufferStorageP = (PFNRBSTORE)SDL_GL_GetProcAddress("glRenderbufferStorage"); glFramebufferRenderbufferP = (PFNFBRB)SDL_GL_GetProcAddress("glFramebufferRenderbuffer");
    fprintf(stderr, "GL %s | %s\n", (const char*)glGetString(GL_VERSION), (const char*)glGetString(GL_RENDERER));
    return glGenFramebuffersP && glBindFramebufferP;
}
static void makeFbo() {
    glGenTextures(1, &gTex); glBindTexture(GL_TEXTURE_2D, gTex); glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, gMaxW, gMaxH, 0, GL_RGBA, GL_UNSIGNED_BYTE, nullptr);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST); glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
    glGenFramebuffersP(1, &gFbo); glBindFramebufferP(GL_FRAMEBUFFER_, gFbo); glFramebufferTexture2DP(GL_FRAMEBUFFER_, GL_COLOR_ATTACHMENT0_, GL_TEXTURE_2D, gTex, 0);
    glGenRenderbuffersP(1, &gDepth); glBindRenderbufferP(GL_RENDERBUFFER_, gDepth); glRenderbufferStorageP(GL_RENDERBUFFER_, GL_DEPTH24_STENCIL8_, gMaxW, gMaxH); glFramebufferRenderbufferP(GL_FRAMEBUFFER_, GL_DEPTH_STENCIL_ATTACHMENT_, GL_RENDERBUFFER_, gDepth);
}
static bool env(unsigned cmd, void* data) {
    cmd &= 0xffff;
    switch (cmd) {
    case 9: *(const char**)data = gSystem.c_str(); return true;                    // GET_SYSTEM_DIRECTORY
    case 31: *(const char**)data = gSave.c_str(); return true;                     // GET_SAVE_DIRECTORY
    case 10: return true;                                                          // SET_PIXEL_FORMAT
    case 3: *(bool*)data = true; return true;                                      // GET_CAN_DUPE
    case 27: ((retro_log_callback*)data)->log = logf_; return true;                // GET_LOG_INTERFACE
    case 15: {                                                                    // GET_VARIABLE
        auto* variable = static_cast<retro_variable*>(data);
        if (getenv("FLYHOST_PER_PIXEL") && strcmp(variable->key, "reicast_alpha_sorting") == 0) {
            variable->value = "per-pixel (accurate)";
            return true;
        }
        return false;
    }
    case 17: *(bool*)data = false; return true;                                    // GET_VARIABLE_UPDATE
    case 51 | 0x10000: return true;                                                // GET_INPUT_BITMASKS
    case 56: *(unsigned*)data = 3; return true;                                    // SET_PREFERRED_HW_RENDER: OpenGL core
    case 14: {                                                                     // SET_HW_RENDER
        retro_hw_render_callback* h = (retro_hw_render_callback*)data; fprintf(stderr, "hw render request: type %u v%u.%u depth %d stencil %d\n", h->context_type, h->version_major, h->version_minor, h->depth, h->stencil);
        if (h->context_type != 1 && h->context_type != 3 && h->context_type != 2 && h->context_type != 4) return false;
        if (!createGl(h->context_type, h->version_major, h->version_minor)) return false;
        h->get_current_framebuffer = getFbo; h->get_proc_address = getProc; gHw = *h; gHwSet = true; return true; }
    case 16: case 11: case 35: case 18: case 36: case 37: case 44: case 51: case 52: case 53: case 65581: return true;   // misc set-only calls
    default: return false;
    }
}
static void video(const void* data, unsigned w, unsigned h, size_t pitch) {
    if (!gHwSet) return;
    if (data != (const void*)(intptr_t)-1) return;
    glBindFramebufferP(GL_READ_FRAMEBUFFER_, gFbo); glPixelStorei(GL_PACK_ALIGNMENT, 1);
    gPix.resize((size_t)w * h * 4); glReadPixels(0, 0, w, h, GL_RGBA, GL_UNSIGNED_BYTE, gPix.data()); gLastW = w; gLastH = h; gHaveFrame = true;
}
static bool saveShot(int frame) {
    if (!gHaveFrame) { fprintf(stderr, "frame %d: no hardware frame yet\n", frame); return false; }
    SDL_Surface* s = SDL_CreateRGBSurfaceWithFormat(0, gLastW, gLastH, 32, SDL_PIXELFORMAT_ABGR8888);
    if (!s) { fprintf(stderr, "frame %d: %s\n", frame, SDL_GetError()); return false; }
    for (unsigned y = 0; y < gLastH; y++) memcpy((unsigned char*)s->pixels + (size_t)y * s->pitch, &gPix[(size_t)(gHw.bottom_left_origin ? gLastH - 1 - y : y) * gLastW * 4], (size_t)gLastW * 4);
    char suffix[32]; snprintf(suffix, sizeof suffix, "_%05d.bmp", frame);
    const std::string name = gOut + suffix;
    const bool saved = SDL_SaveBMP(s, name.c_str()) == 0;
    if (saved) fprintf(stderr, "saved %s (%ux%u)\n", name.c_str(), gLastW, gLastH);
    else fprintf(stderr, "could not save %s: %s\n", name.c_str(), SDL_GetError());
    SDL_FreeSurface(s);
    return saved;
}
static void audio1(int16_t, int16_t) {}
static size_t audioN(const int16_t*, size_t n) { return n; }
static void poll() {}
static constexpr unsigned joypadDevice = 1;
static int16_t input(unsigned port, unsigned device, unsigned, unsigned id) {
    if (port != 0 || device != joypadDevice) return 0;
    if (id == 256) { // RETRO_DEVICE_ID_JOYPAD_MASK
        uint16_t mask = 0;
        for (const auto& [button, ranges] : gKeys) {
            for (const auto& [first, last] : ranges) {
                if (gFrame >= first && gFrame <= last) { mask |= uint16_t(1u << button); break; }
            }
        }
        return static_cast<int16_t>(mask);
    }
    auto it = gKeys.find((int)id); if (it == gKeys.end()) return 0;
    for (auto& r : it->second) if (gFrame >= r.first && gFrame <= r.second) return 1;
    return 0;
}
static int keyId(const std::string& k) {   // RETRO_DEVICE_ID_JOYPAD_*
    static const std::map<std::string, int> m = {{"B", 0}, {"Y", 1}, {"SELECT", 2}, {"START", 3}, {"UP", 4}, {"DOWN", 5}, {"LEFT", 6}, {"RIGHT", 7}, {"A", 8}, {"X", 9}, {"L", 10}, {"R", 11}, {"L2", 12}, {"R2", 13}};   // the Dreamcast triggers are libretro L2 and R2
    auto it = m.find(k); return it == m.end() ? -1 : it->second;
}
int main(int argc, char** argv) {
    if (argc < 7) { fprintf(stderr, "usage: flyhost <core> <system dir> <save dir> <content> <frames> <out prefix> [shots f1,f2] [keys START@100-105;A@200-203]\n"); return 2; }
    gSystem = argv[2]; gSave = argv[3]; gOut = argv[6];
    int frames = 0;
    const char* framesEnd = argv[5] + strlen(argv[5]);
    if (std::from_chars(argv[5], framesEnd, frames).ptr != framesEnd || frames <= 0) {
        fprintf(stderr, "frame count must be a positive integer\n");
        return 2;
    }
    if (argc > 7) {
        const std::string shots = argv[7];
        for (size_t start = 0; start < shots.size();) {
            const size_t comma = shots.find(',', start);
            const size_t end = comma == std::string::npos ? shots.size() : comma;
            int shot = -1;
            const auto parsed = std::from_chars(shots.data() + start, shots.data() + end, shot);
            if (parsed.ec != std::errc{} || parsed.ptr != shots.data() + end ||
                shot < 0 || shot >= frames || comma == shots.size() - 1) {
                fprintf(stderr, "invalid shot list '%s': use comma-separated frame numbers from 0 to %d\n", argv[7], frames - 1);
                return 2;
            }
            gShots.insert(shot);
            start = end + 1;
        }
    }
    if (argc > 8) { std::string s = argv[8]; size_t p = 0; while (p < s.size()) { size_t e = s.find(';', p); if (e == std::string::npos) e = s.size(); std::string t = s.substr(p, e - p); p = e + 1;
        size_t at = t.find('@'), dash = t.find('-', at); if (at == std::string::npos) continue; int id = keyId(t.substr(0, at)); int a = atoi(t.substr(at + 1).c_str()), b = dash == std::string::npos ? a : atoi(t.substr(dash + 1).c_str()); if (id >= 0) gKeys[id].push_back({a, b}); } }
#ifdef _WIN32
    SetErrorMode(GetErrorMode() | SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX);
    SetDllDirectoryA(std::string(argv[1]).substr(0, std::string(argv[1]).find_last_of("\\/")).c_str()); void* lib = LoadLibraryA(argv[1]);
#else
    void* lib = dlopen(argv[1], RTLD_NOW);
#endif
    if (!lib) { fprintf(stderr, "cannot load core\n"); return 3; }
#define FN(t, n) auto n = (t)DLSYM(lib, #n); if (!n) { fprintf(stderr, "missing %s\n", #n); return 3; }
    FN(void (*)(retro_environment_t), retro_set_environment) FN(void (*)(retro_video_refresh_t), retro_set_video_refresh) FN(void (*)(retro_audio_sample_t), retro_set_audio_sample)
    FN(void (*)(retro_audio_sample_batch_t), retro_set_audio_sample_batch) FN(void (*)(retro_input_poll_t), retro_set_input_poll) FN(void (*)(retro_input_state_t), retro_set_input_state)
    FN(void (*)(), retro_init) FN(bool (*)(const retro_game_info*), retro_load_game) FN(void (*)(retro_system_av_info*), retro_get_system_av_info) FN(void (*)(), retro_run)
    FN(void (*)(), retro_unload_game) FN(void (*)(), retro_deinit)
    FN(void* (*)(unsigned), retro_get_memory_data) FN(size_t (*)(unsigned), retro_get_memory_size) FN(size_t (*)(), retro_serialize_size) FN(bool (*)(void*, size_t), retro_serialize)
    FN(void (*)(unsigned, unsigned), retro_set_controller_port_device)
    retro_set_environment(env); retro_set_video_refresh(video); retro_set_audio_sample(audio1); retro_set_audio_sample_batch(audioN); retro_set_input_poll(poll); retro_set_input_state(input);
    retro_init();
    retro_game_info gi{argv[4], nullptr, 0, nullptr};
    if (!retro_load_game(&gi)) { fprintf(stderr, "retro_load_game failed\n"); return 4; }
    retro_set_controller_port_device(0, joypadDevice);
    for (unsigned port = 1; port < 4; ++port) retro_set_controller_port_device(port, 0);
    retro_system_av_info av{}; retro_get_system_av_info(&av); gMaxW = av.geometry.max_width; gMaxH = av.geometry.max_height; fprintf(stderr, "av %ux%u max %ux%u fps %.2f\n", av.geometry.base_width, av.geometry.base_height, gMaxW, gMaxH, av.timing.fps);
    if (!gHwSet) { fprintf(stderr, "the core did not request a hardware context\n"); return 5; }
    makeFbo(); if (gHw.context_reset) gHw.context_reset(); gGlReady = true;
    bool capturesOk = true;
    for (gFrame = 0; gFrame < frames; gFrame++) {
        retro_run();
        if (gShots.count(gFrame) && !saveShot(gFrame)) capturesOk = false;
        if (gShots.count(gFrame) && getenv("FLY_DUMP")) {   // also write the video RAM, main RAM and a full save state (PowerVR registers included) beside the screenshot
            char nm[512]; const char* kinds[2] = {"ram", "vram"}; const unsigned ids[2] = {2, 3};
            for (int k = 0; k < 2; ++k) { void* m = retro_get_memory_data(ids[k]); const size_t n = retro_get_memory_size(ids[k]); snprintf(nm, sizeof nm, "%s%05d.%s", argv[6], gFrame, kinds[k]); if (m && n) { FILE* f = fopen(nm, "wb"); if (f) { fwrite(m, 1, n, f); fclose(f); } } fprintf(stderr, "dump %s: %zu bytes\n", kinds[k], m ? n : (size_t)0); }
            const size_t sn = retro_serialize_size(); std::vector<uint8_t> st(sn); if (sn && retro_serialize(st.data(), sn)) { snprintf(nm, sizeof nm, "%s%05d.state", argv[6], gFrame); FILE* f = fopen(nm, "wb"); if (f) { fwrite(st.data(), 1, sn, f); fclose(f); } fprintf(stderr, "dump state: %zu bytes\n", sn); }
        }
    }
    retro_unload_game();
    if (gHw.context_destroy) gHw.context_destroy();
    retro_deinit();
    SDL_GL_DeleteContext(gCtx);
    SDL_DestroyWindow(gWin);
    SDL_Quit();
    return capturesOk ? 0 : 6;
}
