// Re-Nyastered game app (vertical slice, in progress): menu, puzzle mode and battle mode vs CPU players with extracted iOS art.
// usage: ccr <cache assets dir> [mode: menu|puzzle|battle] [stage] [seed] [cpu levels e.g. 3,3,3]
// Simulation: fixed 60 Hz (verified against the original); drawing is interpolated and resolution independent (logical 768x640 scaled to the window).
// Env: CCR_SIZE=3840x2160 CCR_FULLSCREEN=1 CCR_VSYNC=0 CCR_FILTER=nearest|linear CCR_MINUTES=1..3; CCR_SHOT=<bmp> CCR_TICKS=n renders headlessly (dummy video/audio, software renderer).
#define SDL_MAIN_HANDLED
#include <SDL.h>
#include "../core/battle.hpp"
#include "../core/angle.hpp"
#include <array>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <memory>
#include <string>
#include <functional>
#include <map>
#ifdef __EMSCRIPTEN__
#include <emscripten.h>
#endif
#include <vector>
#include <filesystem>
#include <algorithm>
extern "C" {
#include "stb_vorbis.c"
}
using namespace ccr;

static const int CELL = 64, W = 12 * CELL, H = 9 * CELL + 64;
static const SDL_Color pcol[4] = {{60, 120, 255, 255}, {40, 190, 70, 255}, {240, 60, 60, 255}, {250, 170, 30, 255}};

struct Sheet { SDL_Texture* tex = nullptr; int w = 0, h = 0; std::vector<SDL_Rect> fr; std::vector<SDL_Point> off; };   // off = the frame record's draw offset (xoff, yoff) from the anchor, in sheet pixels

struct Stages { struct E { Stage st; std::vector<std::array<uint8_t, 3>> sol; char title[33]; int src, idx; }; std::vector<E> list; };
static bool loadStages(const char* path, Stages& out, int onlySrc) {
    FILE* f = fopen(path, "rb"); if (!f) return false;
    uint32_t n; if (fread(&n, 4, 1, f) != 1) { fclose(f); return false; }
    for (uint32_t i = 0; i < n; i++) {
        uint8_t h[4], w[237]; Stages::E e;
        if (fread(h, 1, 4, f) != 4 || fread(e.st.tiles, 1, 108, f) != 108 || fread(w, 1, 237, f) != 237) break;
        e.sol.resize(h[1]); bool bad = false; for (auto& s : e.sol) if (fread(s.data(), 1, 3, f) != 3) bad = true;
        if (bad || fread(e.title, 1, 32, f) != 32) break;
        e.title[32] = 0; e.src = h[0]; e.idx = h[2] | (h[3] << 8);
        for (int r = 0; r < 10; r++) for (int c = 0; c < 12; c++) e.st.hw[r * 12 + c] = w[25 * r + c];
        for (int r = 0; r < 9; r++) for (int c = 0; c < 13; c++) e.st.vw[r * 13 + c] = w[25 * r + 12 + c];
        if (h[0] == onlySrc) out.list.push_back(e);
    }
    fclose(f); return !out.list.empty();
}

struct App {
    SDL_Window* win = nullptr; SDL_Renderer* ren = nullptr; std::string root; bool headless = false, quit = false, vsync = true;
    Sheet atlas, cat, mouse, gold, digits, crowns, timefont, font;
    Sheet catV[3], mouseV[3], goldV[3]; bool walkOk = false;   // walk cycles per view (0 side, 1 back, 2 front): cat r0420/r0429/r0438 (20 frames), mouse r0491/r0495/r0499 and gold mouse r0472/r0476/r0480 (11 frames)
    Sheet tbg, tprompt, trocket, tlogo, mbg, mbtn, mdeco, dlogo; bool dlogoOk = false;
    Sheet pbg, pprompt, procket, pdeco, pbtn, pmbg; bool padOk = false; bool titleOk = false, menuOk = false;   // iPad HD layout: the highest-resolution mobile art (tools/export_tilemaps.py, tools/export_pad_ui.py)
    std::map<int, std::string> strs;   // localized UI strings (Android resources, tools/export_strings.py), text as single-byte codes of the glyph sheet
    const std::string& str(int id) { static const std::string none; auto it = strs.find(id); return it == strs.end() ? none : it->second; }
    void loadStrings() {
        const char* lg = getenv("CCR_LANG"); std::string lang = lg ? lg : "en"; FILE* f = fopen((root + "/strings/" + lang + ".tsv").c_str(), "rb"); if (!f) return;
        std::string all; char buf[4096]; size_t n; while ((n = fread(buf, 1, sizeof buf, f)) > 0) all.append(buf, n); fclose(f);
        size_t pos = 0; while (pos < all.size()) { size_t e = all.find(0x0a, pos); if (e == std::string::npos) e = all.size(); std::string line = all.substr(pos, e - pos); pos = e + 1; size_t t = line.find(0x09); if (t == std::string::npos) continue;
            std::string txt = line.substr(t + 1), out; for (size_t i = 0; i < txt.size(); i++) { unsigned char c = (unsigned char)txt[i];
                if (c == 0x5c && i + 1 < txt.size() && txt[i + 1] == 'n') { out += (char)0x0a; i++; }
                else if (c < 0x80) out += (char)c; else if ((c & 0xe0) == 0xc0 && i + 1 < txt.size()) { unsigned cp = ((c & 0x1f) << 6) | ((unsigned char)txt[i + 1] & 0x3f); i++; out += cp < 256 ? (char)cp : '?'; } else { while (i + 1 < txt.size() && ((unsigned char)txt[i + 1] & 0xc0) == 0x80) i++; out += '?'; } }
            strs[atoi(line.substr(0, t).c_str())] = out; }
    }   // Android title screen art (tools/export_android_ui.py)
    // Audio: one callback-driven mixer (looped music stream + one-shot SFX voices), device format 44.1 kHz stereo s16.
    SDL_AudioDeviceID adev = 0; // Music: the 15 songs of the original (song n = mobile file Mnn = Dreamcast CD track n+4). Loaded on demand; loops from the end of the disc's 2 s lead-in over the length of the mobile file (the disc stores four repetitions of some songs).
    struct Song { std::vector<int16_t> pcm; size_t loopStart = 0, loopEnd = 0; bool loop = true, tried = false; }; Song songs[15]; int curTrack = -1; size_t musPos = 0; bool musOn = false;
    std::vector<std::vector<int16_t>> sfx; struct Voice { const std::vector<int16_t>* d; size_t pos; }; std::vector<Voice> voices;

    bool loadSheet(const std::string& base, Sheet& s) {
        FILE* f = fopen((base + ".tex.bin").c_str(), "rb"); if (!f) return false;
        uint32_t wh[2]; if (fread(wh, 4, 2, f) != 2) { fclose(f); return false; }
        s.w = (int)wh[0]; s.h = (int)wh[1]; std::vector<uint8_t> px((size_t)s.w * s.h * 4);
        if (fread(px.data(), 1, px.size(), f) != px.size()) { fclose(f); return false; }
        fclose(f);
        s.tex = SDL_CreateTexture(ren, SDL_PIXELFORMAT_ABGR8888, SDL_TEXTUREACCESS_STATIC, s.w, s.h);
        SDL_UpdateTexture(s.tex, nullptr, px.data(), s.w * 4); SDL_SetTextureBlendMode(s.tex, SDL_BLENDMODE_BLEND);
        f = fopen((base + ".frames.bin").c_str(), "rb"); if (!f) return false;
        uint32_t n; if (fread(&n, 4, 1, f) != 1) { fclose(f); return false; }
        std::vector<float> fl(n * 9); if (fread(fl.data(), 4, fl.size(), f) != fl.size()) { fclose(f); return false; } fclose(f);
        for (uint32_t i = 0; i < n; i++) { const float* e = &fl[i * 9];
            s.fr.push_back({(int)std::lround(e[0] * s.w), (int)std::lround(e[1] * s.h), (int)std::lround((e[2] - e[0]) * s.w), (int)std::lround((e[3] - e[1]) * s.h)});
            int16_t v[10]; memcpy(v, &e[4], 20); s.off.push_back({v[4], v[5]}); }
        return true;
    }
    bool init() {
        headless = getenv("CCR_SHOT") || getenv("CCR_HEADLESS") || getenv("CCR_BENCH");
        bool gpu = getenv("CCR_GPU") != nullptr;   // CCR_GPU=1 with CCR_BENCH: accelerated renderer on a HIDDEN window (nothing is shown, no audio)
        if (headless) { if (!gpu) SDL_setenv("SDL_VIDEODRIVER", "dummy", 1); SDL_setenv("SDL_AUDIODRIVER", "dummy", 1); if (!gpu) SDL_SetHint(SDL_HINT_RENDER_DRIVER, "software"); }   // never take the user's screen/audio
        if (SDL_Init(SDL_INIT_VIDEO | SDL_INIT_AUDIO | SDL_INIT_GAMECONTROLLER) != 0) { printf("SDL: %s\n", SDL_GetError()); return false; }
        int winW = W, winH = H; if (const char* sz = getenv("CCR_SIZE")) { int a = 0, b = 0; if (sscanf(sz, "%dx%d", &a, &b) == 2 && a > 0 && b > 0) { winW = a; winH = b; } }
        SDL_SetHint(SDL_HINT_RENDER_SCALE_QUALITY, getenv("CCR_FILTER") ? getenv("CCR_FILTER") : "linear");
        Uint32 wf = SDL_WINDOW_RESIZABLE | SDL_WINDOW_ALLOW_HIGHDPI | (getenv("CCR_FULLSCREEN") ? SDL_WINDOW_FULLSCREEN_DESKTOP : 0) | (headless ? SDL_WINDOW_HIDDEN : 0);
#ifdef __EMSCRIPTEN__
        wf = 0;   // browser: fixed canvas of the logical size; the page's CSS scales it (a resizable SDL window would take its size from the CSS box)
#endif
        win = SDL_CreateWindow("ChuChu Rocket! Re-Nyastered", SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED, winW, winH, wf);
        vsync = !(getenv("CCR_VSYNC") && atoi(getenv("CCR_VSYNC")) == 0);
        ren = SDL_CreateRenderer(win, -1, headless ? (gpu ? SDL_RENDERER_ACCELERATED : SDL_RENDERER_SOFTWARE) : (SDL_RENDERER_ACCELERATED | (vsync ? SDL_RENDERER_PRESENTVSYNC : 0)));
        SDL_RenderSetLogicalSize(ren, W, H);
        std::string ret = root + "/ret_all/";
        if (!(loadSheet(ret + "r0930", atlas) && loadSheet(ret + "r0447", cat) && loadSheet(ret + "r0503", mouse) && loadSheet(ret + "r0484", gold) && loadSheet(ret + "r0729", digits) &&
              loadSheet(ret + "r0726", crowns) && loadSheet(ret + "r0749", timefont) && loadSheet(ret + "r0023", font))) { printf("missing sprite sheets in %s (tools/export_sprites.py <ccrret> <dir> all)\n", ret.c_str()); return false; }
        { std::string ret2 = root + "/ret_all/"; titleOk = loadSheet(ret2 + "a0090", tbg) && loadSheet(ret2 + "a0097", tprompt) && loadSheet(ret2 + "a0100", trocket) && loadSheet(ret2 + "a0042", tlogo); menuOk = loadSheet(ret2 + "a0134", mbg) && loadSheet(ret2 + "a0113", mbtn) && loadSheet(ret2 + "a0110", mdeco); dlogoOk = loadSheet(ret2 + "dlogo", dlogo); padOk = dlogoOk && loadSheet(ret2 + "bg0877", pbg) && loadSheet(ret2 + "pprompt", pprompt) && loadSheet(ret2 + "procket", procket) && loadSheet(ret2 + "pdeco", pdeco) && loadSheet(ret2 + "pbtn", pbtn) && loadSheet(ret2 + "bg0879", pmbg); loadStrings(); }
        { static const char* cv[3] = {"r0420", "r0429", "r0438"}, *mv[3] = {"r0491", "r0495", "r0499"}, *gv[3] = {"r0472", "r0476", "r0480"}; walkOk = true;
          for (int k = 0; k < 3; k++) walkOk = loadSheet(ret + cv[k], catV[k]) && loadSheet(ret + mv[k], mouseV[k]) && loadSheet(ret + gv[k], goldV[k]) && walkOk; }
        loadFontMetrics();
        loadAudio();
        return true;
    }
    static void audioCb(void* ud, Uint8* stream, int len) {
        App* a = (App*)ud; int16_t* out = (int16_t*)stream; int n = len / 4; std::fill(out, out + n * 2, (int16_t)0);
        if (a->musOn && a->curTrack >= 0 && !a->songs[a->curTrack].pcm.empty()) {
            Song& sg = a->songs[a->curTrack]; const auto& m = sg.pcm;
            for (int i = 0; i < n * 2; i++) { if (a->musPos >= sg.loopEnd) { if (!sg.loop) { a->musOn = false; break; } a->musPos = sg.loopStart; } out[i] = (int16_t)(m[a->musPos++] * 0.6f); }
        }
        for (auto& v : a->voices) for (int i = 0; i < n * 2 && v.pos < v.d->size(); i++) { int s2 = out[i] + (*v.d)[v.pos++]; out[i] = (int16_t)std::max(-32768, std::min(32767, s2)); }
        a->voices.erase(std::remove_if(a->voices.begin(), a->voices.end(), [](const Voice& v) { return v.pos >= v.d->size(); }), a->voices.end());
    }
    static void toStereo44k(const short* pcm, int frames, int ch, int rate, std::vector<int16_t>& out) {
        double step = (double)rate / 44100.0; int outFrames = (int)(frames / step); out.resize((size_t)outFrames * 2);
        for (int i = 0; i < outFrames; i++) { int si = std::min(frames - 1, (int)(i * step)); out[2 * i] = pcm[si * ch]; out[2 * i + 1] = pcm[si * ch + (ch > 1 ? 1 : 0)]; }
    }
    void loadAudio() {
        namespace fs = std::filesystem;
        std::string sfxDir; std::error_code ec;
        for (auto& e : fs::directory_iterator(root + "/ios", ec)) if (fs::exists(e.path() / "audio_sfx" / "000.ogg")) sfxDir = (e.path() / "audio_sfx").string();
        sfx.resize(29);
        for (int i = 0; i < 29 && !sfxDir.empty(); i++) { char nm[16]; snprintf(nm, sizeof nm, "%03d.ogg", i); int ch, rate; short* pcm; int fr = stb_vorbis_decode_filename((sfxDir + "/" + nm).c_str(), &ch, &rate, &pcm);
            if (fr > 0) { toStereo44k(pcm, fr, ch, rate, sfx[i]); free(pcm); } }
        if (headless && !getenv("CCR_AUDIO_TEST")) return;   // CCR_AUDIO_TEST=1: open the (dummy) audio device in headless runs to exercise the music code
        SDL_AudioSpec want{}; want.freq = 44100; want.format = AUDIO_S16SYS; want.channels = 2; want.samples = 1024; want.callback = audioCb; want.userdata = this; SDL_AudioSpec have;
        adev = SDL_OpenAudioDevice(nullptr, 0, &want, &have, 0); if (adev) SDL_PauseAudioDevice(adev, 0);
    }
    void playSfx(int id) { if (!adev || id < 0 || id >= (int)sfx.size() || sfx[id].empty()) return; SDL_LockAudioDevice(adev); voices.push_back({&sfx[id], 0}); SDL_UnlockAudioDevice(adev); }
    void loadSong(int n) {
        Song& sg = songs[n]; if (sg.tried) return; sg.tried = true; namespace fs = std::filesystem; std::error_code ec;
        char nm[16]; snprintf(nm, sizeof nm, "M%02d.ogg", n); std::vector<int16_t> mobile; int mobileFrames = 0;
        for (auto& e : fs::directory_iterator(root + "/ios", ec)) { std::string pth = (e.path() / "audio_song" / nm).string(); if (!fs::exists(pth)) continue;
            int ch, rate; short* pcm; int fr = stb_vorbis_decode_filename(pth.c_str(), &ch, &rate, &pcm); if (fr > 0) { toStereo44k(pcm, fr, ch, rate, mobile); free(pcm); mobileFrames = fr; break; } }
        char wp[512]; snprintf(wp, sizeof wp, "%s/dreamcast/audio/track%02d.wav", root.c_str(), n + 4); SDL_AudioSpec sp; Uint8* buf; Uint32 len;
        if (n != 14 && SDL_LoadWAV(wp, &sp, &buf, &len)) {                       // best source: the lossless Dreamcast CD track
            if (sp.format == AUDIO_S16LSB && sp.channels == 2 && sp.freq == 44100) { sg.pcm.assign((int16_t*)buf, (int16_t*)(buf + len)); sg.loopStart = (size_t)(2.0 * 44100) * 2;
                sg.loopEnd = mobileFrames > 0 ? std::min(sg.pcm.size(), sg.loopStart + (size_t)mobileFrames * 2) : sg.pcm.size(); }
            SDL_FreeWAV(buf); }
        if (sg.pcm.empty() && !mobile.empty()) { sg.pcm = mobile; sg.loopStart = 0; sg.loopEnd = sg.pcm.size(); }   // fallback: the mobile Ogg
        if (n == 14 && !mobile.empty()) { sg.pcm = mobile; sg.loopStart = 0; sg.loopEnd = sg.pcm.size(); sg.loop = false; }   // song 14 is a 5 s jingle
    }
    // AppData::playSong(song): switch to a song (restarts only when it is a different one)
    void playSong(int n) { if (!adev || n < 0 || n > 14) return; if (n == curTrack && musOn) return; loadSong(n); if (songs[n].pcm.empty()) return;
        SDL_LockAudioDevice(adev); curTrack = n; musPos = songs[n].loop ? songs[n].loopStart : 0; musOn = true; SDL_UnlockAudioDevice(adev); }
    void pumpMusic(int song) { playSong(song); }
    // --- drawing helpers ---
    void number(int v, int x, int y, int hgt) {
        std::string s = std::to_string(v); int cx = x;
        for (char c : s) { const SDL_Rect& fr = digits.fr[c - '0']; int w = fr.w * hgt / fr.h; SDL_Rect d{cx, y, w, hgt}; SDL_RenderCopy(ren, digits.tex, &fr, &d); cx += w + 2; }
    }
    // Glyph sheet r0023 (frame = character code). Per-glyph record (36 bytes): u0 v0 u1 v1 floats, then int16 w, h, 64, 64, xoff, yoff (drawn at pen + offset, line top at y): the pen advances by xoff + w.
    // hgt is the cap height in pixels (cap glyphs are 39 sheet pixels tall).
    struct GlyphMet { int w = 0, h = 0, xo = 0, yo = 0; }; GlyphMet gm[256];
    void loadFontMetrics() { FILE* f = fopen((root + "/ret_all/r0023.frames.bin").c_str(), "rb"); if (!f) return; uint32_t n = 0; if (fread(&n, 4, 1, f) != 1) { fclose(f); return; }
        for (uint32_t i = 0; i < n && i < 256; i++) { uint8_t rec[36]; if (fread(rec, 1, 36, f) != 36) break; int16_t v[10]; memcpy(v, rec + 16, 20); gm[i] = {v[0], v[1], v[4], v[5]}; } fclose(f); }
    int textWidth(const std::string& s, int hgt) { float sc = hgt / 39.0f, w = 0; for (unsigned char c : s) w += gm[c].h ? (gm[c].xo + gm[c].w) * sc : 20 * sc; return (int)w; }
    void text(const std::string& s, int x, int y, int hgt) {
        float sc = hgt / 39.0f, pen = (float)x;
        for (unsigned char c : s) { const SDL_Rect& fr = font.fr[c]; const GlyphMet& g = gm[c]; if (!fr.h) { pen += 20 * sc; continue; }
            SDL_Rect d{(int)std::lround(pen + g.xo * sc), (int)std::lround(y + (g.yo - 12) * sc), (int)std::lround(g.w * sc), (int)std::lround(g.h * sc)}; SDL_RenderCopy(ren, font.tex, &fr, &d); pen += (g.xo + g.w) * sc; }
    }
    void board(const Stage& st) {
        for (int r = 0; r < 9; r++) for (int c = 0; c < 12; c++) {
            SDL_Rect dst{c * CELL, r * CELL, CELL, CELL}; SDL_RenderCopy(ren, atlas.tex, &atlas.fr[8 + ((r + c) & 1)], &dst);
            uint8_t t = st.tiles[r * 12 + c];
            if (t >= 1 && t <= 4) { static const int sph[4] = {20, 21, 22, 23}; SDL_RenderCopy(ren, atlas.tex, &atlas.fr[sph[t - 1]], &dst); }
            if (t >= 5 && t <= 8) SDL_RenderCopy(ren, atlas.tex, &atlas.fr[7], &dst);
        }
        SDL_SetRenderDrawColor(ren, 20, 20, 90, 255);
        for (int r = 0; r < 10; r++) for (int c = 0; c < 12; c++) if (st.hw[r * 12 + c]) { SDL_Rect q{c * CELL - 1, r * CELL - 3, CELL + 2, 6}; SDL_RenderFillRect(ren, &q); }
        for (int r = 0; r < 9; r++) for (int c = 0; c < 13; c++) if (st.vw[r * 13 + c]) { SDL_Rect q{c * CELL - 3, r * CELL - 1, 6, CELL + 2}; SDL_RenderFillRect(ren, &q); }
    }
    void arrow(int x, int y, int dir, SDL_Color col) { arrowPx((x + 0.5f) * CELL, (y + 0.5f) * CELL, dir, col, 1.0f); }
    void arrowPx(float cx, float cy, int dir, SDL_Color col, float sc) {
        static const float dx[4] = {0, -1, 0, 1}, dy[4] = {1, 0, -1, 0};
        float ux = dx[dir], uy = dy[dir];
        float px = -dy[dir], py = dx[dir];
        SDL_Vertex v[3] = {{{cx + ux * 24 * sc, cy + uy * 24 * sc}, col, {0, 0}}, {{cx - ux * 12 * sc + px * 20 * sc, cy - uy * 12 * sc + py * 20 * sc}, col, {0, 0}}, {{cx - ux * 12 * sc - px * 20 * sc, cy - uy * 12 * sc - py * 20 * sc}, col, {0, 0}}};
        SDL_RenderGeometry(ren, nullptr, v, 3, nullptr, 0);
    }
    // Turn animation exactly as the original (Core::adjustAngle/diffAngle, entity fields +0x20 current angle, +0x24 target = heading << 14, +0x28 step = int(speed * 32768 / 12)):
    // the sprite sheets are 32-angle turntables, frame = angle >> 11. Called once per simulation tick.
    std::vector<int> angs; std::vector<float> cphase; int gtime = 0;   // cat walk phase (+0.45 per tick, wraps at 20.0: FUN_00028ffc), global tick for the mouse walk frame (TI_GetGlobalTime mod 11: FUN_000353e0)
    void stepAngles(const Sim& sim) {
        gtime++; while (cphase.size() < sim.ents.size()) cphase.push_back(0.0f);
        for (size_t i = 0; i < sim.ents.size(); i++) if (!sim.ents[i].mouse && sim.ents[i].alive) { cphase[i] += 0.45f; if (cphase[i] >= 20.0f) cphase[i] -= 20.0f; }                       // original turn logic (core/angle.hpp), once per simulation tick
        while (angs.size() < sim.ents.size()) angs.push_back(sim.ents[angs.size()].heading << 14);
        for (size_t i = 0; i < sim.ents.size(); i++) { const Entity& e = sim.ents[i]; angs[i] = stepAngle(angs[i], e.heading, e.mouse ? sim.mouseSpeed : sim.catSpeed); }
    }
    void entities(const Sim& sim, std::vector<std::pair<float, float>>& prev, float alpha) {
        while (prev.size() < sim.ents.size()) prev.push_back({sim.ents[prev.size()].x, sim.ents[prev.size()].z});
        for (size_t i = 0; i < sim.ents.size(); i++) {
            const Entity& en = sim.ents[i]; if (!en.alive || en.done || en.rocketIn) continue;
            float x = prev[i].first + (en.x - prev[i].first) * alpha, z = prev[i].second + (en.z - prev[i].second) * alpha;
            if (std::fabs(en.x - prev[i].first) > 100 || std::fabs(en.z - prev[i].second) > 100) { x = en.x; z = en.z; }
            int ang = (i < angs.size() ? angs[i] : en.heading << 14);
            if (walkOk) {   // original view choice (CA_CatDrawSTPriority / FUN_0003582c, literals from the code): back view for angles in [0x6001, 0xA000], front outside [0x2001, 0xE000], side otherwise
                unsigned a = (unsigned)ang & 0xffff; int view = (a >= 0x6001 && a <= 0xA000) ? 1 : ((a < 0x2001 || a > 0xE000) ? 2 : 0);
                Sheet& sh = !en.mouse ? catV[view] : (en.type == 1 ? goldV[view] : mouseV[view]);
                int frame = !en.mouse ? (i < cphase.size() ? (int)cphase[i] : 0) : gtime % 11; frame = std::min(frame, (int)sh.fr.size() - 1);
                const SDL_Rect& fr = sh.fr[frame]; const SDL_Point& of = sh.off[frame]; float sc = CELL / 64.0f;   // iPad pack: 64 px per cell
                SDL_Rect dst{(int)std::lround(x * (CELL / 15.0f) + of.x * sc), (int)std::lround(z * (CELL / 15.0f) + of.y * sc), (int)std::lround(fr.w * sc), (int)std::lround(fr.h * sc)};
                bool flip = view == 0 && a > 0x2000 && a < 0x8000;   // the side art faces east; west-facing is mirrored (unverified: the flag the original passes to drawImage is not in the decompile)
                SDL_RenderCopyEx(ren, sh.tex, &fr, &dst, 0.0, nullptr, flip ? SDL_FLIP_HORIZONTAL : SDL_FLIP_NONE); continue;
            }
            Sheet& sh = !en.mouse ? cat : (en.type == 1 ? gold : mouse);
            const SDL_Rect& fr = sh.fr[(ang >> 11) & 31]; float sc = CELL * 0.95f / fr.w; int dw = (int)(fr.w * sc), dh = (int)(fr.h * sc);
            SDL_Rect dst{(int)(x * (CELL / 15.0f)) - dw / 2, (int)(z * (CELL / 15.0f)) - dh * 2 / 3, dw, dh}; SDL_RenderCopy(ren, sh.tex, &fr, &dst);
        }
    }
};

static App* gApp = nullptr;   // for sound hooks
struct Screen { virtual ~Screen() {} virtual void event(App&, const SDL_Event&) {} virtual void tick(App&) {} virtual void draw(App&, float) {} virtual int music() { return -1; } virtual const char* next() { return nullptr; } };

// ---------------------------------------------------------------- title (Android TitleScreen, phone layout 480x320)
// State machine and constants read from the original (docs/ui_art.md): state 0xB fade-in 0.5 s (black rectangle, alpha = timer / 500000 * 255), 0xC wait (song 0 plays, the rocket orbits
// centre (196,110) radius 130 at +1 degree per 60 Hz frame and turns with it, "TAP THE SCREEN!" at (132,251) is visible while the blink timer, +16384 us per frame and wrapping at 500000, is <= 333333),
// 0xD fade-out 0.5 s after a tap, then the menu. The logo is frame 0 of the logo atlas, placed at (12,28); the background is drawn whole at (0,0).
struct TitleMode : Screen {
    int state = 0xB; double timer = 500000.0, blink = 0.0, angle = 0.0; bool leave = false;
    int music() override { return state == 0xB ? -1 : 0; }
    void event(App&, const SDL_Event& e) override {
        if (state == 0xC && (e.type == SDL_KEYDOWN || e.type == SDL_MOUSEBUTTONDOWN || e.type == SDL_CONTROLLERBUTTONDOWN || e.type == SDL_FINGERDOWN)) { state = 0xD; timer = 0; }
    }
    void tick(App&) override {
        const double dt = 1000000.0 / 60.0;
        if (state == 0xB) { timer -= dt; if (timer <= 0) { timer = 0; state = 0xC; blink = 0; } }
        else if (state == 0xC) { angle += 1.0; blink += 16384.0; if (blink >= 500000.0) blink -= 500000.0; }
        else if (state == 0xD) { timer += dt; if (timer >= 500000.0) { timer = 500000.0; leave = true; } }
    }
    const char* next() override { if (leave) { leave = false; return "MENU"; } return nullptr; }
    void draw(App& a, float alpha) override {
        // Two layouts of the original (docs/ui_art.md): the iPad-class layout (1024x768: tile-map background, orbit centre (453,316) radius 174, logo (208,208), prompt (368,504)) with the largest art, or the phone layout (480x320).
        const bool pad = a.padOk; const int LW = pad ? 1024 : 480, LH = pad ? 768 : 320; const double ocx = pad ? 453 : 196, ocy = pad ? 316 : 110, orad = pad ? 174 : 130; const int px = pad ? 368 : 132, py = pad ? 504 : 251;
        SDL_RenderSetLogicalSize(a.ren, LW, LH); SDL_SetRenderDrawColor(a.ren, 0, 0, 0, 255); SDL_RenderClear(a.ren);
        Sheet& bg = pad ? a.pbg : a.tbg; SDL_Rect bs{0, 0, LW, LH}; SDL_RenderCopy(a.ren, bg.tex, nullptr, &bs);
        double ang = (angle + (state == 0xC ? alpha : 0.0)); const double rad = 0.0174533; Sheet& rk = pad ? a.procket : a.trocket; const SDL_Rect& rf = rk.fr[0];
        SDL_Rect rd{(int)std::lround(ocx + std::cos(ang * rad) * orad - rf.w / 2.0), (int)std::lround(ocy + std::sin(ang * rad) * orad - rf.h / 2.0), rf.w, rf.h};
        SDL_RenderCopyEx(a.ren, rk.tex, &rf, &rd, ang + 180.0, nullptr, SDL_FLIP_NONE);
        if (a.dlogoOk) { int lw = pad ? 337 : 190, lx = pad ? 208 : 8, ly = pad ? 208 : 24; SDL_Rect ld{lx, ly, lw, lw * a.dlogo.h / a.dlogo.w}; SDL_RenderCopy(a.ren, a.dlogo.tex, nullptr, &ld); }   // best source: the Dreamcast logo
        else { const SDL_Rect& lf = a.tlogo.fr[0]; SDL_Rect ld{12, 28, lf.w, lf.h}; SDL_RenderCopy(a.ren, a.tlogo.tex, &lf, &ld); }
        if (state == 0xC && blink <= 333333.0) { Sheet& pr = pad ? a.pprompt : a.tprompt; const SDL_Rect& pf = pr.fr[0]; SDL_Rect pd{px, py, pf.w, pf.h}; SDL_RenderCopy(a.ren, pr.tex, &pf, &pd); }
        if (state != 0xC) { SDL_SetRenderDrawBlendMode(a.ren, SDL_BLENDMODE_BLEND); SDL_SetRenderDrawColor(a.ren, 0, 0, 0, (Uint8)std::max(0.0, std::min(255.0, timer / 500000.0 * 255.0))); SDL_Rect all{0, 0, LW, LH}; SDL_RenderFillRect(a.ren, &all); }
        SDL_RenderSetLogicalSize(a.ren, W, H);
    }
};

// ---------------------------------------------------------------- menu
struct MenuMode : Screen {
    // Original main menu (docs/ui_art.md). iPad class (1024x768; art = iPad HD pack: yellow tile-map background 879, 340-wide bars, cat decoration at (208,50)): items at (184,173) (264,263) (344,353) (424,443) (504,533);
    // phone class (480x320): 200x38 bars at (35,50) (75,100) (115,150) (155,200) (195,250). Bars are frames 0 (purple) / 1 (orange = selected); labels are the localized strings 0152 The Basics, 0153 Puzzle,
    // 0154 Stage Challenge, 0155 Battle, 0157 Options, centred in the bar and shrunk to fit. Only Puzzle and Battle exist in this game so far.
    int sel = 1; const char* chosen = nullptr; bool back = false; static constexpr int N = 5; static constexpr int sid[N] = {152, 153, 154, 155, 157};
    static constexpr int pbx[N] = {35, 75, 115, 155, 195}, pby[N] = {50, 100, 150, 200, 250}, ibx[N] = {184, 264, 344, 424, 504}, iby[N] = {173, 263, 353, 443, 533};
    bool avail(int i) const { return i == 1 || i == 3; }
    int music() override { return 0; }
    void geom(App& a, int i, int& x, int& y, int& w, int& h) { if (a.padOk) { const SDL_Rect& f = a.pbtn.fr[0]; x = ibx[i]; y = iby[i]; w = f.w; h = f.h; } else { const SDL_Rect& f = a.mbtn.fr[0]; x = pbx[i]; y = pby[i]; w = f.w; h = f.h; } }
    void event(App& a, const SDL_Event& e) override {
        if (e.type == SDL_KEYDOWN) { SDL_Keycode k = e.key.keysym.sym;
            if (k == SDLK_DOWN) sel = (sel + 1) % N; else if (k == SDLK_UP) sel = (sel + N - 1) % N; else if (k == SDLK_RETURN || k == SDLK_SPACE) choose(a); else if (k == SDLK_ESCAPE) back = true; }
        else if (e.type == SDL_MOUSEMOTION || (e.type == SDL_MOUSEBUTTONDOWN && e.button.button == SDL_BUTTON_LEFT)) {
            int mx = e.type == SDL_MOUSEMOTION ? e.motion.x : e.button.x, my = e.type == SDL_MOUSEMOTION ? e.motion.y : e.button.y;
            SDL_RenderSetLogicalSize(a.ren, a.padOk ? 1024 : 480, a.padOk ? 768 : 320); float lx, ly; SDL_RenderWindowToLogical(a.ren, mx, my, &lx, &ly); SDL_RenderSetLogicalSize(a.ren, W, H);
            for (int i = 0; i < N; i++) { int x, y, w, h; geom(a, i, x, y, w, h); if (lx >= x && lx < x + w && ly >= y && ly < y + h) { sel = i; if (e.type == SDL_MOUSEBUTTONDOWN) choose(a); } } }
    }
    void choose(App& a) { if (sel == 1) chosen = "PUZZLE"; else if (sel == 3) chosen = "BATTLE"; else a.playSfx(0x13); }
    const char* next() override { if (back) { back = false; return "TITLE"; } const char* c = chosen; chosen = nullptr; return c; }
    void draw(App& a, float) override {
        if (!a.menuOk) { SDL_SetRenderDrawColor(a.ren, 24, 24, 60, 255); SDL_RenderClear(a.ren); return; }
        const bool pad = a.padOk; const int LW = pad ? 1024 : 480, LH = pad ? 768 : 320;
        SDL_RenderSetLogicalSize(a.ren, LW, LH); SDL_SetRenderDrawColor(a.ren, 0, 0, 0, 255); SDL_RenderClear(a.ren);
        SDL_Rect bs{0, 0, LW, LH}; SDL_RenderCopy(a.ren, (pad ? a.pmbg : a.mbg).tex, nullptr, &bs);
        { Sheet& dc = pad ? a.pdeco : a.mdeco; SDL_Rect dd{pad ? 208 : 11, pad ? 50 : 3, dc.w, dc.h}; SDL_RenderCopy(a.ren, dc.tex, nullptr, &dd); }   // two-cat decoration
        Sheet& bt = pad ? a.pbtn : a.mbtn;
        for (int i = 0; i < N; i++) { int x, y, w, h; geom(a, i, x, y, w, h); const SDL_Rect& f = bt.fr[i == sel ? 1 : 0]; SDL_Rect d{x, y, f.w, f.h}; SDL_RenderCopy(a.ren, bt.tex, &f, &d);
            const std::string& t = a.str(sid[i]); int th = pad ? 38 : 22; int tw = a.textWidth(t, th); const int room = f.w - (pad ? 70 : 40); if (tw > room) { th = th * room / tw; tw = a.textWidth(t, th); } a.text(t, x + (f.w - tw) / 2, y + (f.h - th) / 2 - 1, th); }
        SDL_RenderSetLogicalSize(a.ren, W, H);
    }
};

// ---------------------------------------------------------------- puzzle
struct PuzzleMode : Screen {
    Stages stages; int cur = 0; Sim sim; std::vector<std::pair<float, float>> prev; bool running = false; int state = 0;   // 0 planning, 1 running, 2 clear, 3 miss
    int stock[4] = {0, 0, 0, 0}; int totalMice = 0; bool back = false;
    int music() override { return 9; }   // PuzzleInit: BGM_Play(0xd) = song 9
    bool load(const std::string& root, int stage) { if (!loadStages((root + "/gba/gba_stages.bin").c_str(), stages, 0)) return false; cur = stage % (int)stages.list.size(); reset(); return true; }
    void reset() {
        sim.load(stages.list[cur].st); prev.clear(); if (gApp) gApp->angs.clear(); running = false; state = 0; totalMice = 0;
        for (auto& e : sim.ents) if (e.mouse) totalMice++;
        for (int d = 0; d < 4; d++) stock[d] = 0;
        for (auto& s : stages.list[cur].sol) stock[s[2] & 3]++;       // arrow stock from the reference solution (stage struct counts not exported yet)
    }
    int used(int d) const { int n = 0; for (auto& a : sim.arrows) if (a.live && a.dir == d) n++; return n; }
    void event(App& a, const SDL_Event& e) override {
        if (e.type == SDL_KEYDOWN) { SDL_Keycode k = e.key.keysym.sym;
            if (k == SDLK_SPACE) { if (state == 0) { state = 1; running = true; } else if (state >= 2) reset(); }
            else if (k == SDLK_r) reset(); else if (k == SDLK_ESCAPE) back = true;
            else if (k == SDLK_RIGHT) { cur = (cur + 1) % (int)stages.list.size(); reset(); } else if (k == SDLK_LEFT) { cur = (cur + (int)stages.list.size() - 1) % (int)stages.list.size(); reset(); } }
        else if (e.type == SDL_MOUSEBUTTONDOWN && state == 0) {
            float lx, ly; SDL_RenderWindowToLogical(a.ren, e.button.x, e.button.y, &lx, &ly); int cx = (int)(lx / CELL), cy = (int)(ly / CELL);
            if (cx < 0 || cx >= 12 || cy < 0 || cy >= 9) return;
            int ex = -1; for (auto& ar : sim.arrows) if (ar.live && ar.x == cx && ar.y == cy) ex = ar.dir;
            if (e.button.button == SDL_BUTTON_RIGHT) { if (ex >= 0) sim.removeArrow(cx, cy); return; }
            if (ex >= 0) { sim.removeArrow(cx, cy); int d = (ex + 1) & 3; for (int k = 0; k < 4 && used(d) >= stock[d]; k++) d = (d + 1) & 3; if (used(d) < stock[d] && d != ex) sim.placeArrow(cx, cy, d); return; }
            for (int d = 0; d < 4; d++) if (used(d) < stock[d]) { sim.placeArrow(cx, cy, d); return; }
        }
    }
    void tick(App& a) override {
        for (size_t i = 0; i < sim.ents.size() && i < prev.size(); i++) prev[i] = {sim.ents[i].x, sim.ents[i].z};
        if (!running) return;
        sim.tick(); a.stepAngles(sim);
        int alive = 0; for (auto& e : sim.ents) if (e.mouse && e.alive && !e.done) alive++;
        if (sim.killed > 0) { state = 3; running = false; } else if (alive == 0 && sim.saved == totalMice) { state = 2; running = false; }
    }
    const char* next() override { if (back) { back = false; return "MENU"; } return nullptr; }
    void draw(App& a, float alpha) override {
        SDL_SetRenderDrawColor(a.ren, 24, 24, 40, 255); SDL_RenderClear(a.ren);
        a.board(stages.list[cur].st);
        for (auto& ar : sim.arrows) if (ar.live) a.arrow(ar.x, ar.y, ar.dir, {250, 220, 40, 255});
        a.entities(sim, prev, running ? alpha : 1.0f);
        for (int d = 0; d < 4; d++) { int x = 12 + d * 100; SDL_Rect bx{x, 9 * CELL + 8, 90, 48}; SDL_SetRenderDrawColor(a.ren, 40, 40, 90, 255); SDL_RenderFillRect(a.ren, &bx);
            a.arrowPx(x + 24, 9 * CELL + 32, d, {250, 220, 40, 255}, 0.7f); a.number(stock[d] - used(d), x + 52, 9 * CELL + 14, 36); }
        std::string t = state == 2 ? "CLEAR!" : state == 3 ? "MISS" : state == 0 ? "SPACE=GO" : ""; if (!t.empty()) a.text(t, W - a.textWidth(t, 44) - 90, 9 * CELL + 10, 44);
        a.number(cur + 1, W - 80, 9 * CELL + 14, 36);
    }
};

// ---------------------------------------------------------------- battle
struct BattleMode : Screen {
    Stages stages; int cur = 0; uint32_t seed = 1; int lv[4] = {-1, 3, 3, 3}; BattleGame game; std::vector<std::pair<float, float>> prev; bool paused = false, back = false;
    // 4-player local input: mouse = player 1; keyboard sets WASD+Q (P1), IJKL+U (P2), keypad 8456+0 (P3); gamepads in connection order (D-pad moves the cursor, DC buttons Y/A/X/B place up/down/left/right)
    int lastCatSfx = -100; int curX[4] = {2, 9, 2, 9}, curY[4] = {2, 2, 6, 6}; SDL_GameController* pads[4] = {nullptr, nullptr, nullptr, nullptr};
    void place(int p, int cx, int cy, int d) { if (lv[p] >= 0 || p >= 4) return; if (d < 0) { d = 0; for (auto& ar : game.sim.arrows) if (ar.live && ar.x == cx && ar.y == cy && ar.owner == p) d = (ar.dir + 1) & 3; } game.placeArrow(p, cx, cy, d); }
    void moveCur(int p, int dx, int dy) { curX[p] = std::max(0, std::min(11, curX[p] + dx)); curY[p] = std::max(0, std::min(8, curY[p] + dy)); }
    bool keyPlayer(SDL_Keycode k) {
        static const SDL_Keycode map[3][5] = {{SDLK_w, SDLK_s, SDLK_a, SDLK_d, SDLK_q}, {SDLK_i, SDLK_k, SDLK_j, SDLK_l, SDLK_u}, {SDLK_KP_8, SDLK_KP_5, SDLK_KP_4, SDLK_KP_6, SDLK_KP_0}};
        for (int p = 0; p < 3; p++) { if (lv[p] >= 0) continue;
            if (k == map[p][0]) { moveCur(p, 0, -1); return true; } if (k == map[p][1]) { moveCur(p, 0, 1); return true; } if (k == map[p][2]) { moveCur(p, -1, 0); return true; } if (k == map[p][3]) { moveCur(p, 1, 0); return true; }
            if (k == map[p][4]) { place(p, curX[p], curY[p], -1); return true; } }
        return false;
    }
    void padButton(int p, int button) {
        if (p < 0 || p > 3 || lv[p] >= 0) return;
        switch (button) { case SDL_CONTROLLER_BUTTON_DPAD_UP: moveCur(p, 0, -1); break; case SDL_CONTROLLER_BUTTON_DPAD_DOWN: moveCur(p, 0, 1); break; case SDL_CONTROLLER_BUTTON_DPAD_LEFT: moveCur(p, -1, 0); break; case SDL_CONTROLLER_BUTTON_DPAD_RIGHT: moveCur(p, 1, 0); break;
            case SDL_CONTROLLER_BUTTON_Y: place(p, curX[p], curY[p], 2); break; case SDL_CONTROLLER_BUTTON_A: place(p, curX[p], curY[p], 0); break; case SDL_CONTROLLER_BUTTON_X: place(p, curX[p], curY[p], 1); break; case SDL_CONTROLLER_BUTTON_B: place(p, curX[p], curY[p], 3); break; default: break; }
    }
    bool load(const std::string& root, int stage, uint32_t sd) {
        if (!loadStages((root + "/battle_stages.bin").c_str(), stages, 2)) return false; cur = stage % (int)stages.list.size(); seed = sd;
        game.rouletteManager = true; game.rotateOwn = true; game.baseScale = 1.0f; int minutes = getenv("CCR_MINUTES") ? atoi(getenv("CCR_MINUTES")) : 3; game.roundFrames = 60 * 60 * minutes;   // 1-3 minute rounds (NGI_SetGameTimer)
        if (const char* h = getenv("CCR_HUMANS")) { int n = std::max(1, std::min(4, atoi(h))); for (int p = 0; p < 4; p++) lv[p] = p < n ? -1 : (lv[p] < 0 ? 3 : lv[p]); }   // CCR_HUMANS=1..4 human players, the rest CPU
        for (int p = 0; p < 4; p++) game.setCpu(p, lv[p]);
        game.sfx = [this](int id) { if (id == 7) { if (game.frame - lastCatSfx < 3) return; lastCatSfx = game.frame; } if (gApp) gApp->playSfx(id); }; game.localPlayer = 0;   // ChuSECall(id) plays SFX index id (Android table at 0x63a00, ids 0..28 map to themselves); id 7 is dropped when it repeats within 3 ticks
        restart(); return true;
    }
    void restart() { game.start(stages.list[cur].st, seed); prev.clear(); if (gApp) gApp->angs.clear(); }
    // Original battle music (Android FUN_0003c56c / FUN_0003c534 / FUN_0003c828): while a roulette event runs the song depends on the outcome (table 0x63994: events 0..3 -> BGM ids 10, 9, 7, 8,
    // i.e. songs 6, 5, 3, 4); otherwise (and after the event) song 1 while more than 30 s are left (TI_CountDownBCDTimer > 0x2fff), song 2 in the last 30 s.
    int music() override { static const int evSong[4] = {6, 5, 3, 4}; int k = game.activeEventKind(); if (k >= 0 && k < 4) return evSong[k]; return game.frame > game.roundFrames - 60 * 30 ? 2 : 1; }
    void event(App& a, const SDL_Event& e) override {
        if (e.type == SDL_CONTROLLERDEVICEADDED) { for (int p = 0; p < 4; p++) if (!pads[p]) { pads[p] = SDL_GameControllerOpen(e.cdevice.which); break; } }
        else if (e.type == SDL_CONTROLLERBUTTONDOWN) { for (int p = 0; p < 4; p++) if (pads[p] && SDL_JoystickInstanceID(SDL_GameControllerGetJoystick(pads[p])) == e.cbutton.which) padButton(p, e.cbutton.button); }
        else if (e.type == SDL_KEYDOWN && keyPlayer(e.key.keysym.sym)) {}
        else if (e.type == SDL_KEYDOWN) { SDL_Keycode k = e.key.keysym.sym;
            if (k == SDLK_SPACE) paused = !paused; else if (k == SDLK_r) restart(); else if (k == SDLK_ESCAPE) back = true;
            else if (k == SDLK_RIGHT) { cur = (cur + 1) % (int)stages.list.size(); restart(); } else if (k == SDLK_LEFT) { cur = (cur + (int)stages.list.size() - 1) % (int)stages.list.size(); restart(); } }
        else if (e.type == SDL_MOUSEBUTTONDOWN && e.button.button == SDL_BUTTON_LEFT) {
            float lx, ly; SDL_RenderWindowToLogical(a.ren, e.button.x, e.button.y, &lx, &ly); int cx = (int)(lx / CELL), cy = (int)(ly / CELL);
            if (cx >= 0 && cx < 12 && cy >= 0 && cy < 9) { int d = 0; for (auto& ar : game.sim.arrows) if (ar.live && ar.x == cx && ar.y == cy && ar.owner == 0) d = (ar.dir + 1) & 3; game.placeArrow(0, cx, cy, d); }
        }
    }
    void tick(App& a) override { if (paused) return; for (size_t i = 0; i < game.sim.ents.size() && i < prev.size(); i++) prev[i] = {game.sim.ents[i].x, game.sim.ents[i].z}; game.tick(); a.stepAngles(game.sim); }
    const char* next() override { if (back) { back = false; return "MENU"; } return nullptr; }
    void draw(App& a, float alpha) override {
        SDL_SetRenderDrawColor(a.ren, 24, 24, 40, 255); SDL_RenderClear(a.ren);
        a.board(stages.list[cur].st);
        for (auto& ar : game.sim.arrows) if (ar.live) a.arrow(ar.x, ar.y, ar.dir, pcol[ar.owner & 3]);
        a.entities(game.sim, prev, paused ? 1.0f : alpha);
        for (int p = 1; p < 4; p++) if (lv[p] < 0) { SDL_Rect c{curX[p] * CELL + 2, curY[p] * CELL + 2, CELL - 4, CELL - 4}; SDL_SetRenderDrawColor(a.ren, pcol[p].r, pcol[p].g, pcol[p].b, 255); SDL_RenderDrawRect(a.ren, &c); }
        for (int p = 0; p < 4; p++) { SDL_Rect b{p * (W / 4) + 6, 9 * CELL + 6, W / 4 - 12, 52}; SDL_SetRenderDrawColor(a.ren, pcol[p].r, pcol[p].g, pcol[p].b, 255); SDL_RenderFillRect(a.ren, &b);
            a.number(game.score.player[p], b.x + 12, b.y + 8, 36);
            if (game.over) { int rk = game.rankOf(p); const SDL_Rect& fr = a.crowns.fr[rk < 4 ? rk : 3]; int ch = 44, cw = fr.w * ch / fr.h; SDL_Rect d{b.x + b.w - cw - 8, b.y + 4, cw, ch}; SDL_RenderCopy(a.ren, a.crowns.tex, &fr, &d); } }
        int rem = game.over ? 0 : (game.roundFrames - game.frame) / 60; int m = rem / 60, sec = rem % 60; int x = W / 2 - 60; const int hgt = 28;
        auto glyph = [&](int idx) { const SDL_Rect& fr = a.timefont.fr[idx]; int w = fr.w * hgt / fr.h; SDL_Rect d{x, 6, w, hgt}; SDL_RenderCopy(a.ren, a.timefont.tex, &fr, &d); x += w + 1; };
        glyph(m % 10); glyph(10); glyph(sec / 10); glyph(sec % 10);
    }
};

int main(int argc, char** argv) {
    // Asset folder: first argument, else CCR_ASSETS, else the usual places (next to the exe, the repo's local cache, %APPDATA%/ReNyastered/assets).
    std::string root; int shift = 0;
    auto hasAssets = [](const std::string& d) { FILE* f = fopen((d + "/ret_all/r0930.tex.bin").c_str(), "rb"); if (f) { fclose(f); return true; } return false; };
    if (argc >= 2 && std::string(argv[1]) != "menu" && std::string(argv[1]) != "puzzle" && std::string(argv[1]) != "battle") { root = argv[1]; shift = 1; }
    else {
        std::vector<std::string> cand; if (const char* e = getenv("CCR_ASSETS")) cand.push_back(e);
        char* bp = SDL_GetBasePath(); std::string base = bp ? bp : ""; if (bp) SDL_free(bp);
        cand.push_back(base + "assets"); cand.push_back(base + "../../local/cache/assets"); cand.push_back(base + "../../../local/cache/assets"); cand.push_back("local/cache/assets");
        if (const char* ap = getenv("APPDATA")) cand.push_back(std::string(ap) + "/ReNyastered/assets");
        for (auto& c : cand) if (hasAssets(c)) { root = c; break; }
        if (root.empty()) {
            const char* msg = "Game assets not found.\n\nRun setup.cmd (it extracts them from your own copies of the game), start ccr with the asset folder as its first argument, or set CCR_ASSETS.";
            printf("%s\n", msg); if (!getenv("CCR_SHOT") && !getenv("CCR_HEADLESS") && !getenv("CCR_BENCH") && SDL_Init(SDL_INIT_VIDEO) == 0) { SDL_ShowSimpleMessageBox(SDL_MESSAGEBOX_ERROR, "ChuChu Rocket! Re-Nyastered", msg, nullptr); SDL_Quit(); } return 2;
        }
    }
    App app; app.root = root; if (!app.init()) return 2; gApp = &app;
    std::string start = argc > 1 + shift ? argv[1 + shift] : "title"; int stageNo = argc > 2 + shift ? atoi(argv[2 + shift]) : 0; uint32_t seed = argc > 3 + shift ? (uint32_t)atoi(argv[3 + shift]) : 1;
    int lv[4] = {-1, 3, 3, 3}; if (argc > 4 + shift) { int k = 1; for (const char* p = argv[4 + shift]; *p && k < 4; ) { lv[k++] = atoi(p); while (*p && *p != ',') p++; if (*p == ',') p++; } }
    std::unique_ptr<Screen> mode;
    auto enter = [&](const std::string& name) -> bool {
        if ((name == "TITLE" || name == "title") && app.titleOk) mode = std::make_unique<TitleMode>();
        else if (name == "PUZZLE" || name == "puzzle") { auto m = std::make_unique<PuzzleMode>(); if (!m->load(app.root, stageNo)) { printf("cannot load puzzle stages\n"); return false; } mode = std::move(m); }
        else if (name == "BATTLE" || name == "battle") { auto m = std::make_unique<BattleMode>(); memcpy(m->lv, lv, sizeof lv); if (!m->load(app.root, stageNo, seed)) { printf("cannot load battle stages\n"); return false; } mode = std::move(m); }
        else mode = std::make_unique<MenuMode>();
        return true;
    };
    if (!enter(start)) return 2;
    const double dt = 1.0 / 60.0; double acc = 0;
    if (const char* shot = getenv("CCR_SHOT")) {
        int ticks = getenv("CCR_TICKS") ? atoi(getenv("CCR_TICKS")) : 600;
        if (const char* keys = getenv("CCR_KEYS")) for (const char* p = keys; *p; p++) { SDL_Event e{}; e.type = SDL_KEYDOWN; e.key.keysym.sym = (*p == ' ') ? SDLK_SPACE : (*p == 'D') ? SDLK_DOWN : (*p == 'E') ? SDLK_RETURN : *p; mode->event(app, e); if (const char* nx = mode->next()) enter(nx); }
        int lastSong = -2; for (int i = 0; i < ticks; i++) { mode->tick(app); if (getenv("CCR_AUDIO_TEST") && mode->music() >= 0) { app.pumpMusic(mode->music()); if (app.curTrack != lastSong) { lastSong = app.curTrack; printf("tick %d: song %d (DC track %d), loop %zu..%zu of %zu samples\n", i, lastSong, lastSong + 4, app.songs[lastSong].loopStart, app.songs[lastSong].loopEnd, app.songs[lastSong].pcm.size()); } } }
        mode->draw(app, 1.0f); SDL_Surface* s = SDL_CreateRGBSurfaceWithFormat(0, W, H, 32, SDL_PIXELFORMAT_ARGB8888);
        SDL_RenderReadPixels(app.ren, nullptr, SDL_PIXELFORMAT_ARGB8888, s->pixels, s->pitch); SDL_SaveBMP(s, shot); SDL_FreeSurface(s); SDL_Quit(); return 0;
    }
    if (getenv("CCR_BENCH")) {   // headless render benchmark: CCR_BENCH=<frames> CCR_HZ=<simulated display rate> CCR_SIZE=WxH; fixed 60 Hz ticks, interpolated draws at the output size
        int frames = atoi(getenv("CCR_BENCH")); double hz = getenv("CCR_HZ") ? atof(getenv("CCR_HZ")) : 60.0; double a2 = 0; long ticks = 0;
        Uint64 t0 = SDL_GetPerformanceCounter(); double drawMs = 0;
        for (int f = 0; f < frames; f++) {
            a2 += 1.0 / hz; while (a2 >= dt) { mode->tick(app); a2 -= dt; ticks++; }
            Uint64 d0 = SDL_GetPerformanceCounter(); mode->draw(app, (float)(a2 / dt)); SDL_RenderPresent(app.ren); if (getenv("CCR_GPU")) { Uint32 px; SDL_Rect r1{0, 0, 1, 1}; SDL_RenderReadPixels(app.ren, &r1, SDL_PIXELFORMAT_ARGB8888, &px, 4); } drawMs += 1000.0 * (SDL_GetPerformanceCounter() - d0) / SDL_GetPerformanceFrequency();
        }
        double sec = (double)(SDL_GetPerformanceCounter() - t0) / SDL_GetPerformanceFrequency(); int ow = 0, oh = 0; SDL_GetRendererOutputSize(app.ren, &ow, &oh);
        printf("output %dx%d simulated %.0f Hz: %d frames, %ld sim ticks (%.3f s simulated, %.1f ticks/s), draw %.2f ms/frame (%s renderer)\n", ow, oh, hz, frames, ticks, frames / hz, ticks / (frames / hz), drawMs / frames, getenv("CCR_GPU") ? "GPU" : "software");
        if (const char* out = getenv("CCR_OUT")) { SDL_Surface* s = SDL_CreateRGBSurfaceWithFormat(0, ow, oh, 32, SDL_PIXELFORMAT_ARGB8888); SDL_RenderReadPixels(app.ren, nullptr, SDL_PIXELFORMAT_ARGB8888, s->pixels, s->pitch); SDL_SaveBMP(s, out); SDL_FreeSurface(s); }
        (void)sec; SDL_Quit(); return 0;
    }
    Uint64 last = SDL_GetPerformanceCounter();
    std::function<void()> frame = [&]() {
        SDL_Event e;
        while (SDL_PollEvent(&e)) {
            if (e.type == SDL_QUIT) app.quit = true;
            else if (e.type == SDL_KEYDOWN && e.key.keysym.sym == SDLK_F11) { Uint32 f = SDL_GetWindowFlags(app.win); SDL_SetWindowFullscreen(app.win, (f & SDL_WINDOW_FULLSCREEN_DESKTOP) ? 0 : SDL_WINDOW_FULLSCREEN_DESKTOP); }
            else if (e.type == SDL_KEYDOWN && e.key.keysym.sym == SDLK_v) { app.vsync = !app.vsync; SDL_RenderSetVSync(app.ren, app.vsync); }
            else { mode->event(app, e); if (const char* nx = mode->next()) { enter(nx); acc = 0; } }
        }
        Uint64 now = SDL_GetPerformanceCounter(); acc += (double)(now - last) / (double)SDL_GetPerformanceFrequency(); last = now; if (acc > 0.25) acc = 0.25;
        while (acc >= dt) { mode->tick(app); acc -= dt; }
        if (mode->music() >= 0) app.pumpMusic(mode->music());
        mode->draw(app, (float)(acc / dt)); SDL_RenderPresent(app.ren);
    };
#ifdef __EMSCRIPTEN__
    emscripten_set_main_loop_arg([](void* f) { (*(std::function<void()>*)f)(); }, &frame, 0, 1);   // browser drives the frames (requestAnimationFrame); never returns
#else
    while (!app.quit) frame();
#endif
    SDL_Quit(); return 0;
}
