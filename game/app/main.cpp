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
// iPad-class layout (Core::settingsInit iOS 0x135cc + the static layout struct at 0x131028, read 2026-11-14): screen 1024 x 768, cell pitch 64 (= 4.2667 px per world unit), field origin (184, 32); other layouts: Android 800x480 (pitch 50, origin 160,18), 480x320 (pitch 35, origin 61,4).
static const int GW = 1024, GH = 768, OX = 184, OY = 32;
static const SDL_Color pcol[4] = {{60, 120, 255, 255}, {250, 170, 30, 255}, {240, 60, 60, 255}, {40, 190, 70, 255}};   // player order of the original art (arrow sheet r0645, cursor sheet r0732, rocket sheets r0651/r0663/r0675/r0687): blue, orange, red, green

struct Sheet { SDL_Texture* tex = nullptr; int w = 0, h = 0; std::vector<SDL_Rect> fr; std::vector<SDL_Point> off; std::vector<float> fit; std::vector<SDL_Point> box; std::vector<SDL_Point> sz; };   // sz = frame record shorts 0, 1 (the size the panel calls use), box = shorts 2, 3   // box = frame record shorts 2, 3 (the draw box BHLib_RenderTexture callers use, minus 2)   // fit: per-frame scale to the original iPad (HD 1.0) frame width   // off = the frame record's draw offset (xoff, yoff) from the anchor, in sheet pixels

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

// Puzzle stage sets: 0 = the 100 main stages, 1 = the 2,466 further GBA stages, 2 = the Dreamcast Express DLC pack "DEPuzzle" (25 puzzles with the arrow stock decoded from the slot, docs/dlc.md; PuzzleP is left out until its stock is verified)
static const int kStageSets = 3;
static bool loadStageSet(const std::string& root, int set, Stages& out) { return set == 2 ? loadStages((root + "/gba/dlc_stages.bin").c_str(), out, 3) : loadStages((root + "/gba/gba_stages.bin").c_str(), out, set); }

struct App {
    SDL_Window* win = nullptr; SDL_Renderer* ren = nullptr; std::string root; bool headless = false, quit = false, vsync = true;
    int stageSet = 0;     // puzzle stage group: 0 = the 100 main stages, 1 = the 2,466 further GBA stages
    uint32_t clr[4] = {0, 0, 0, 0}; bool clrLoaded = false;   // VMU puzzle-cleared bits: word = stage / 25, bit = stage % 25 (VMU::isPuzzleCleared 0x37154); persisted in <assets>/progress.bin
    void loadProgress() { if (clrLoaded) return; clrLoaded = true; if (FILE* f = fopen((root + "/progress.bin").c_str(), "rb")) { if (fread(clr, 4, 4, f) != 4) memset(clr, 0, sizeof clr); fclose(f); } if (getenv("CCR_CLEAR_ALL")) for (int i = 0; i < 4; i++) clr[i] = 0x1ffffff; }
    bool isCleared(int s) { loadProgress(); return s >= 0 && s < 100 && ((clr[s / 25] >> (s % 25)) & 1); }
    int maxStage() { loadProgress(); for (int i = 0; i < 3; i++) if ((clr[i] & 0x1ffffff) != 0x1ffffff) return i; return 3; }   // VMU::getPuzzleMaxStage 0x372b4
    void setCleared(int s) { loadProgress(); if (s < 0 || s >= 100 || isCleared(s)) return; clr[s / 25] |= 1u << (s % 25); if (FILE* f = fopen((root + "/progress.bin").c_str(), "wb")) { fwrite(clr, 4, 4, f); fclose(f); } }
    int nextStage = -1;   // stage chosen on the stage-select screen (consumed when the puzzle starts)
    Sheet atlas, cat, mouse, gold, digits, crowns, timefont, font;
    Sheet arw, cur, rk[4], hdTime, hdHud65, hdHud68, hdPhud, hdStageNum, hdFrame78, hdFont, hdFont1, hdPause, ssBg, ssBubble, ssCells, ssTab, ssPanel, ssArrows, ssHdr, hdBub9, hdBubTail, mnBg, mnBars, mnMasc, mnDeco, opBg, opHdr, langJa, opSnd, opSld, hlHdr, hlTab, hlFrm, hlDia, plPanels, plLabels, plBottom, plTiles; std::vector<std::string>* bubbleLog = nullptr; SDL_Texture* ssPrev = nullptr; int ssPrevKey = -1; std::vector<uint8_t> hdFontW, hdFontW1; std::map<int, std::string> hdText; std::map<int, int> hdTextMap; bool gameArtOk = false;   // original in-play art: arrows (r0645, frame = owner), cursors (r0732: frames 0..3 = players, 4 = square bracket), closed rocket sphere = frame 0 of r0651/r0663/r0675/r0687
    Sheet catV[3], mouseV[3], goldV[3]; bool walkOk = false;   // walk cycles per view (0 side, 1 back, 2 front): cat r0420/r0429/r0438 (20 frames), mouse r0491/r0495/r0499 and gold mouse r0472/r0476/r0480 (11 frames)
    Sheet tbg, tprompt, trocket, tlogo, mbg, mbtn, mdeco, dlogo, dpress; bool dlogoOk = false, dpressOk = false;
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

    // HD 1.0 frame table (int16 w at record offset 16): draw size of each frame on the original iPad
    void loadFit(const std::string& path, Sheet& s) {
        FILE* f = fopen(path.c_str(), "rb"); if (!f) return; uint32_t n = 0; if (fread(&n, 4, 1, f) != 1) { fclose(f); return; }
        std::vector<uint8_t> b(36 * n); size_t got = fread(b.data(), 1, b.size(), f); fclose(f); if (got != b.size()) return;
        s.fit.assign(s.fr.size(), 1.0f);
        for (uint32_t i = 0; i < n && i < s.fr.size(); i++) { int16_t w; memcpy(&w, &b[36 * i + 16], 2); if (s.fr[i].w > 0) s.fit[i] = (float)w / (float)s.fr[i].w; }
    }
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
            int16_t v[10]; memcpy(v, &e[4], 20); s.off.push_back({v[4], v[5]}); s.box.push_back({v[2], v[3]}); s.sz.push_back({v[0], v[1]}); }
        return true;
    }
    bool init() {
        headless = getenv("CCR_SHOT") || getenv("CCR_HEADLESS") || getenv("CCR_BENCH");
        bool gpu = getenv("CCR_GPU") != nullptr;   // CCR_GPU=1 with CCR_BENCH: accelerated renderer on a HIDDEN window (nothing is shown, no audio)
        if (headless) { if (!gpu) SDL_setenv("SDL_VIDEODRIVER", "dummy", 1); SDL_setenv("SDL_AUDIODRIVER", "dummy", 1); if (!gpu) SDL_SetHint(SDL_HINT_RENDER_DRIVER, "software"); }   // never take the user's screen/audio
        if (SDL_Init(SDL_INIT_VIDEO | SDL_INIT_AUDIO | SDL_INIT_GAMECONTROLLER) != 0) { printf("SDL: %s\n", SDL_GetError()); return false; }
        int winW = GW, winH = GH; if (const char* sz = getenv("CCR_SIZE")) { int a = 0, b = 0; if (sscanf(sz, "%dx%d", &a, &b) == 2 && a > 0 && b > 0) { winW = a; winH = b; } }
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
        gameArtOk = loadSheet(ret + "r0645", arw) && loadSheet(ret + "r0732", cur) && loadSheet(ret + "r0651", rk[0]) && loadSheet(ret + "r0663", rk[1]) && loadSheet(ret + "r0675", rk[2]) && loadSheet(ret + "r0687", rk[3]); if (gameArtOk) { loadFit(ret + "hd_arrows.frames.bin", arw); loadFit(ret + "hd_cursors.frames.bin", cur); loadSheet(ret + "hd_time", hdTime); loadSheet(ret + "hd_bhud65", hdHud65); loadSheet(ret + "hd_bhud68", hdHud68); loadSheet(ret + "hd_stagenum", hdStageNum); loadSheet(ret + "hd_frame78", hdFrame78); loadSheet(ret + "hd_font0", hdFont); loadSheet(ret + "hd_font1", hdFont1); loadSheet(ret + "hd_ss_bg", ssBg); loadSheet(ret + "hd_ss_bubble", ssBubble); loadSheet(ret + "hd_ss_cells", ssCells); loadSheet(ret + "hd_ss_tab", ssTab); loadSheet(ret + "hd_ss_panel", ssPanel); loadSheet(ret + "hd_ss_arrows", ssArrows); loadSheet(ret + "hd_bub9", hdBub9); loadSheet(ret + "hd_mn_bg", mnBg); loadSheet(ret + "hd_mn_bars", mnBars); loadSheet(ret + "hd_mn_masc", mnMasc); loadSheet(ret + "hd_op_bg", opBg); loadSheet(ret + "hd_lang_ja", langJa); loadSheet(ret + "hd_op_snd", opSnd); loadSheet(ret + "hd_hlp_hdr", hlHdr); loadSheet(ret + "hd_hlp_tab", hlTab); loadSheet(ret + "hd_hlp_frm", hlFrm); loadSheet(ret + "hd_hlp_dia", hlDia); loadSheet(ret + "img/hd_35", plPanels); loadSheet(ret + "img/hd_36", plLabels); loadSheet(ret + "img/hd_12", plBottom); loadSheet(ret + "img/hd_28", plTiles); loadSheet(ret + "hd_op_sld", opSld); loadSheet(ret + "hd_bubtail", hdBubTail); loadHdText(ret); loadLocale(ret); }
        loadFit(ret + "hd_crowns.frames.bin", crowns);
        if (!(loadSheet(ret + "r0930", atlas) && loadSheet(ret + "r0447", cat) && loadSheet(ret + "r0503", mouse) && loadSheet(ret + "r0484", gold) && loadSheet(ret + "r0729", digits) &&
              loadSheet(ret + "r0726", crowns) && loadSheet(ret + "r0749", timefont) && loadSheet(ret + "r0023", font))) { printf("missing sprite sheets in %s (tools/export_sprites.py <ccrret> <dir> all)\n", ret.c_str()); return false; }
        { std::string ret2 = root + "/ret_all/"; titleOk = loadSheet(ret2 + "a0090", tbg) && loadSheet(ret2 + "a0097", tprompt) && loadSheet(ret2 + "a0100", trocket) && loadSheet(ret2 + "a0042", tlogo); menuOk = loadSheet(ret2 + "a0134", mbg) && loadSheet(ret2 + "a0113", mbtn) && loadSheet(ret2 + "a0110", mdeco); dlogoOk = loadSheet(ret2 + "dlogo", dlogo); dpressOk = loadSheet(ret2 + "dpress", dpress); padOk = dlogoOk && loadSheet(ret2 + "bg0877", pbg) && loadSheet(ret2 + "pprompt", pprompt) && loadSheet(ret2 + "procket", procket) && loadSheet(ret2 + "pdeco", pdeco) && loadSheet(ret2 + "pbtn", pbtn) && loadSheet(ret2 + "bg0879", pmbg); loadStrings(); }
        { static const char* cv[3] = {"r0420", "r0429", "r0438"}, *mv[3] = {"r0491", "r0495", "r0499"}, *gv[3] = {"r0472", "r0476", "r0480"}; walkOk = true;
          for (int k = 0; k < 3; k++) { walkOk = loadSheet(ret + cv[k], catV[k]) && loadSheet(ret + mv[k], mouseV[k]) && loadSheet(ret + gv[k], goldV[k]) && walkOk;
            loadFit(ret + "hd_cat" + std::to_string(k) + ".frames.bin", catV[k]); loadFit(ret + "hd_mouse" + std::to_string(k) + ".frames.bin", mouseV[k]); loadFit(ret + "hd_gold" + std::to_string(k) + ".frames.bin", goldV[k]); } }
        loadFontMetrics();
        loadAudio();
        return true;
    }
    static void audioCb(void* ud, Uint8* stream, int len) {
        App* a = (App*)ud; int16_t* out = (int16_t*)stream; int n = len / 4; std::fill(out, out + n * 2, (int16_t)0);
        if (a->musOn && a->curTrack >= 0 && !a->songs[a->curTrack].pcm.empty()) {
            Song& sg = a->songs[a->curTrack]; const auto& m = sg.pcm;
            for (int i = 0; i < n * 2; i++) { if (a->musPos >= sg.loopEnd) { if (!sg.loop) { a->musOn = false; break; } a->musPos = sg.loopStart; } out[i] = (int16_t)(m[a->musPos++] * ((float)a->musicVol / 255.0f)); }   // AppData::playSong: volume = +0x54 / 255
        }
        for (auto& v : a->voices) for (int i = 0; i < n * 2 && v.pos < v.d->size(); i++) { int s2 = out[i] + (int)((*v.d)[v.pos++] * ((float)a->sfxVol / 255.0f));   // playSFX: +0x58 / 255 (the per-sound base volume of the original is not applied)
             out[i] = (int16_t)std::max(-32768, std::min(32767, s2)); }
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
    // Original sprite blit: every frame record carries its anchor offset (the frame is centred on its anchor: -w/2, -h/2); sprites are drawn at native pixels (logical 768x576 field = 64 px cells, as the iPad layout).
    void blit(Sheet& sh, int frame, float ax, float ay, float scale = 1.0f, double angle = 0.0, int cropTL = 0) {
        if (frame < 0 || frame >= (int)sh.fr.size()) return;
        if (frame < (int)sh.fit.size()) scale *= sh.fit[frame];   // geometry of the original iPad build
        SDL_Rect fr = sh.fr[frame]; const SDL_Point& of = sh.off[frame];
        SDL_Rect dst{(int)std::lround(ax + of.x * scale), (int)std::lround(ay + of.y * scale), (int)std::lround(fr.w * scale), (int)std::lround(fr.h * scale)};
        if (cropTL) { fr.x += 1; fr.y += 1; fr.w -= 1; fr.h -= 2; dst.x += 1; dst.y += 1; dst.w -= 1; dst.h -= 2; }   // buildPlayfield copies a tile without its first column and first and last row
        SDL_Point c{(int)std::lround(-of.x * scale), (int)std::lround(-of.y * scale)};
        SDL_RenderCopyEx(ren, sh.tex, &fr, &dst, angle, angle != 0.0 ? &c : nullptr, SDL_FLIP_NONE);
    }
    // Render::buildPlayfield (Android 0x37c50), read from the code: for every cell the floor tile atlas frame 8 + colour * 2 + ((col ^ row) & 1) (a pit, tile 0x11, replaces the floor with frame 7), a rocket cell gets its round base (frame 6), a
    // generator cell the ring frame table[(col >> 2) + 3 * (row / 3)] (frames 26..34); then every wall edge as a bar of frame wallColor (horizontal, edge row 0..9) or wallColor + 3 (vertical, edge column 0..12), anchored at the edge centre.
    // Colours by game type (Render::createPlayfieldPreview, 0x38458): free-for-all and team battle: floor {1,3,4,5}[stage & 3], wall 0; challenge: floor 1, wall 1; puzzle: floor (group & 3) + 2, wall 2.
    void board(const Stage& st, int floorColor = 0, int wallColor = 0) {
        static const int ring[9] = {0x1b, 0x1c, 0x1d, 0x22, 0x1a, 0x1e, 0x21, 0x20, 0x1f};
        for (int r = 0; r < 9; r++) for (int c = 0; c < 12; c++) {
            float ax = c * CELL + CELL / 2.0f, ay = r * CELL + CELL / 2.0f; uint8_t t = st.tiles[r * 12 + c];
            if (t == 0x11) { blit(atlas, 7, ax, ay); continue; }
            blit(atlas, 8 + floorColor * 2 + ((c ^ r) & 1), ax, ay, 1.0f, 0.0, 1);
            if (t >= 1 && t <= 4) blit(atlas, 6, ax, ay);
            else if (t >= 5 && t <= 8) blit(atlas, ring[(c >> 2) + 3 * (r / 3)], ax, ay);
        }
        for (int r = 0; r < 10; r++) for (int c = 0; c < 12; c++) if (st.hw[r * 12 + c]) blit(atlas, wallColor, c * CELL + CELL / 2.0f, (float)(r * CELL));
        for (int r = 0; r < 9; r++) for (int c = 0; c < 13; c++) if (st.vw[r * 13 + c]) blit(atlas, wallColor + 3, (float)(c * CELL), r * CELL + CELL / 2.0f);
    }
    // In-play rockets: frame 0 (closed sphere) of the owner's rocket sheet at the rocket cell, scale = size value x 0.8 (RO_RocketSetPukuPuku, FUN_0003be00).
    void rockets(const Sim& sim, const float* puku) {
        for (int p = 0; p < 4; p++) blit(rk[p], 0, sim.rocketPos[p][0] * CELL + CELL / 2.0f, sim.rocketPos[p][1] * CELL + CELL / 2.0f, (puku ? puku[p] : 1.0f) * 0.8f);
    }
    // Arrow sprite (image 0x5f, frame = owner; the art points up, rotated clockwise by the heading); a struck arrow is drawn at 0.7 (AR_ArrowDrawPriority).
    void arrow(int x, int y, int dir, int owner, int hits = 0, int ttl = -1) {
        if (ttl >= 0 && !(ttl > 60 || (ttl > 0 && (ttl & 1)))) return;   // in the last 60 ticks the arrow flickers (drawn only on odd ticks)
        static const double rot[4] = {180.0, 270.0, 0.0, 90.0};   // south, west, north, east
        blit(arw, owner & 3, (x + 0.5f) * CELL, (y + 0.5f) * CELL, hits ? 0.7f : 1.0f, rot[dir & 3]);
    }
    void arrowIcon(float cx, float cy, int dir, int owner, float sc) { static const double rot[4] = {180.0, 270.0, 0.0, 90.0}; blit(arw, owner & 3, cx, cy, sc, rot[dir & 3]); }
    // Cursor (image 0x6b: frame = player; CU_CursorDrawPriority/DispCursorPriority): scale 1 + 0.1 sin(angle), angle = (player << 14) + 0x1000 per tick (CU_CursorCons, FUN_0002b344); over a cell with an object
    // (collision bits 0xF00) the square bracket (frame 4) is drawn with scale 1 + 0.075 sin(2 angle) (CU_CursorDrawPrioritySquare).
    // Render::drawFrame type 5 (HD 1.0 0x1a60c): image 0x78 (frame table record 720: 58 px tiles), tile = 58 - 2; n = width / tile pieces centred on x: frames 0, 1..., 2 at y
    // HD 1.0 text (Render::printString 0x1a19c -> BHLib_PrintString 0x9dc0, Latin branch): font 0 = image 0 (texture ccrpad rec 0, frames rec 3, per-glyph advance = rec 874), glyph index = character code
    // Language packs (Latin languages of HD 1.0; locale index of the original: 0 en, 1 fr, 2 it, 3 de, 4 es, 5 ja = no pack in this build): language-pack sheets and the text table (tools/export_hd_locale.py)
    int lang = 0, musicVol = 75, sfxVol = 100; std::string retDir;   // AppData +0x54 / +0x58 (initializeOptionsData: 0x4b and 100), 0..255
    static const char* langDir(int l) { static const char* n[6] = {"en", "fr", "it", "de", "es", "ja"}; return n[l < 0 || l > 5 ? 0 : l]; }
    void freeSheet(Sheet& s) { if (s.tex) SDL_DestroyTexture(s.tex); s = Sheet(); }
    bool langAvailable(int l) { FILE* f = fopen((retDir + "loc_" + langDir(l) + "/hd_text.tsv").c_str(), "rb"); if (f) fclose(f); return f != nullptr; }
    void loadLocale(const std::string& ret) {
        retDir = ret; if (const char* e = getenv("CCR_LANG")) for (int i = 0; i < 6; i++) if (!strcmp(e, langDir(i))) lang = i;
        if (FILE* f = fopen((root + "/options.bin").c_str(), "rb")) { unsigned char c = 0; if (fread(&c, 1, 1, f) == 1 && c < 6 && !getenv("CCR_LANG")) lang = c; unsigned char v[2]; if (fread(v, 1, 2, f) == 2) { musicVol = v[0]; sfxVol = v[1]; } fclose(f); }
        if (!langAvailable(lang)) lang = 0; applyLocale(); }
    void saveOptions() { if (FILE* f = fopen((root + "/options.bin").c_str(), "wb")) { unsigned char c[3] = {(unsigned char)lang, (unsigned char)std::max(0, std::min(255, musicVol)), (unsigned char)std::max(0, std::min(255, sfxVol))}; fwrite(c, 1, 3, f); fclose(f); } }
    void setLanguage(int l) { if (!langAvailable(l)) return; lang = l; applyLocale(); saveOptions(); }
    void applyLocale() {
        dropImages();
        std::string d = retDir + "loc_" + langDir(lang) + "/"; Sheet* sh[5] = {&hdPhud, &hdPause, &ssHdr, &mnDeco, &opHdr}; const char* nm[5] = {"hd_phud5c", "hd_pause79", "hd_ss_hdr", "hd_mn_deco", "hd_op_hdr"};
        for (int i = 0; i < 5; i++) { freeSheet(*sh[i]); loadSheet(d + nm[i], *sh[i]); }
        hdText.clear(); FILE* g = fopen((d + "hd_text.tsv").c_str(), "rb"); if (!g) return; std::string all; char bb[4096]; size_t n; while ((n = fread(bb, 1, sizeof bb, g)) > 0) all.append(bb, n); fclose(g);
        size_t pos = 0; while (pos < all.size()) { size_t e = all.find((char)10, pos); if (e == std::string::npos) e = all.size(); std::string line = all.substr(pos, e - pos); pos = e + 1; size_t t = line.find((char)9); if (t != std::string::npos) { std::string v = line.substr(t + 1); for (auto& ch : v) if (ch == 11) ch = 10; hdText[atoi(line.c_str())] = v; } } }
    void loadHdText(const std::string& ret) {
        FILE* f = fopen((ret + "hd_font0.widths.bin").c_str(), "rb"); if (f) { hdFontW.resize(256); if (fread(hdFontW.data(), 1, 256, f) != 256) hdFontW.clear(); fclose(f); }
        f = fopen((ret + "hd_font1.widths.bin").c_str(), "rb"); if (f) { hdFontW1.resize(256); if (fread(hdFontW1.data(), 1, 256, f) != 256) hdFontW1.clear(); fclose(f); }
        auto tsv = [&](const char* name, auto&& put) { FILE* g = fopen((ret + name).c_str(), "rb"); if (!g) return; std::string all; char b[4096]; size_t n; while ((n = fread(b, 1, sizeof b, g)) > 0) all.append(b, n); fclose(g);
            size_t pos = 0; while (pos < all.size()) { size_t e = all.find((char)10, pos); if (e == std::string::npos) e = all.size(); std::string line = all.substr(pos, e - pos); pos = e + 1; size_t t = line.find((char)9); if (t != std::string::npos) put(atoi(line.c_str()), line.substr(t + 1)); } };
         tsv("hd_textmap.tsv", [&](int k, const std::string& v) { hdTextMap[k] = atoi(v.c_str()); });
    }
    const std::string* hdString(int key) { auto m = hdTextMap.find(key); if (m == hdTextMap.end()) return nullptr; auto t = hdText.find(m->second); return t == hdText.end() ? nullptr : &t->second; }
    int hdTextWidth(const std::string& s, size_t from, float scale, int fontNo = 0) { const std::vector<uint8_t>& fw = fontNo == 1 ? hdFontW1 : hdFontW; int w = 0; for (size_t i = from; i < s.size() && s[i] != 10; i++) w += fw[(uint8_t)s[i]]; return (int)((float)w * scale); }
    // align 0 centred, 1 left, 2 right (BHLib_PrintString param_10); vcenter = param_11 (y -= 0.5 * line height * scale); line height = short at frame 91 + 22 of the frame table (CreateFont: texture + 0x28 -> +0xce6) = 32 for font 0
    void printString(const std::string& s, float x, float y, int r, int g, int b, int al, float scale, int align, bool vcenter, int fontNo = 0) {
        if (uiLog) { char t[300]; std::string q = s; for (auto& ch : q) if (ch == 10) ch = 124; snprintf(t, sizeof t, "PS %s %.1f %.1f %.3f %d", q.c_str(), x, y, scale, align); uiLog->push_back(t); return; }
        Sheet& hdFont = fontNo == 1 ? hdFont1 : this->hdFont; const std::vector<uint8_t>& fw = fontNo == 1 ? hdFontW1 : hdFontW; if (!hdFont.tex || fw.empty() || hdFont.box.size() < 92) return; const float lineH = (float)hdFont.box[91].y;
        int cy = (int)y; if (vcenter) cy = (int)((float)cy + lineH * scale * -0.5f);
        auto startX = [&](size_t from) { int w = hdTextWidth(s, from, scale, fontNo); return align == 1 ? (int)x : (int)(x - (float)(align == 0 ? w / 2 : w)); };
        int cx = startX(0); SDL_SetTextureColorMod(hdFont.tex, (Uint8)r, (Uint8)g, (Uint8)b); SDL_SetTextureAlphaMod(hdFont.tex, (Uint8)al);
        for (size_t i = 0; i < s.size(); i++) { uint8_t c = (uint8_t)s[i];
            if (c == 10) { cy = (int)((float)cy + lineH * scale); if (i + 1 < s.size() && align != 1) cx = startX(i + 1); else cx = (int)x; continue; }
            if (c != 0x20 && c < hdFont.fr.size()) { const SDL_Rect& fr = hdFont.fr[c]; const SDL_Point& of = hdFont.off[c];
                int x0 = (int)((float)cx + (float)of.x * scale), y0 = (int)((float)cy + (float)of.y * scale), x1 = (int)((float)cx + (float)(fr.w + of.x) * scale), y1 = (int)((float)cy + (float)(fr.h + of.y) * scale);
                SDL_Rect dst{x0, y0, x1 - x0, y1 - y0}; SDL_RenderCopy(ren, hdFont.tex, &fr, &dst); }
            cx = (int)((float)cx + (float)fw[c] * scale); }
        SDL_SetTextureColorMod(hdFont.tex, 255, 255, 255); SDL_SetTextureAlphaMod(hdFont.tex, 255);
    }
    // BHLib_RenderTexture(x, y, w, h, frame uv): the frame's pixels are scaled to (w, h); tint white
    std::vector<std::string>* uiLog = nullptr;   // when set, rtex / rtexRaw / printString / fillRect record 'RT x y w h', 'PS text x y scale align' and 'FR x y w h' instead of drawing
    void logRT(float x, float y, int w, int h) { char t[100]; snprintf(t, sizeof t, "RT %.1f %.1f %d %d", x, y, w, h); uiLog->push_back(t); }
    void fillRect(int x, int y, int w, int h, int r, int g, int bl, int al) { if (uiLog) { char t[100]; snprintf(t, sizeof t, "FR %d %d %d %d", x, y, w, h); uiLog->push_back(t); return; } SDL_SetRenderDrawBlendMode(ren, SDL_BLENDMODE_BLEND); SDL_SetRenderDrawColor(ren, r, g, bl, al); SDL_Rect q{x, y, w, h}; SDL_RenderFillRect(ren, &q); }
    void rtex(Sheet& sh, int frame, float x, float y, int w, int h) { if (uiLog) { logRT(x, y, w, h); return; } if (!sh.tex || frame < 0 || frame >= (int)sh.fr.size()) return; SDL_Rect s = sh.fr[frame]; s.x += 1; s.y += 1; s.w = w; s.h = h; SDL_Rect d{(int)x, (int)y, w, h}; SDL_RenderCopy(ren, sh.tex, &s, &d); }   // the 1 px ring around each frame is padding: the call's size (frame box - 2) is the inner area
    void rtexRaw(Sheet& sh, int frame, float x, float y, int w, int h) { if (uiLog) { logRT(x, y, w, h); return; } if (!sh.tex || frame < 0 || frame >= (int)sh.fr.size()) return; SDL_Rect d{(int)x, (int)y, w, h}; SDL_RenderCopy(ren, sh.tex, &sh.fr[frame], &d); }   // frames without the 1 px ring (exact sheets)
    void rtexBox(Sheet& sh, int frame, float x, float y) { if (frame >= 0 && frame < (int)sh.box.size()) rtex(sh, frame, x, y, sh.box[frame].x - 2, sh.box[frame].y - 2); }   // the common call: size = frame box shorts - 2
    void blitFlip(Sheet& sh, int frame, float ax, float ay, float scale, bool mirror) {   // Render::drawImage flags & 2 = swap u0/u1 (horizontal mirror of the frame in place; these frames are centred on their anchor)
        if (frame < 0 || frame >= (int)sh.fr.size()) return; SDL_Rect fr = sh.fr[frame]; const SDL_Point& of = sh.off[frame];
        SDL_Rect dst{(int)std::lround(ax + of.x * scale), (int)std::lround(ay + of.y * scale), (int)std::lround(fr.w * scale), (int)std::lround(fr.h * scale)}; SDL_RenderCopyEx(ren, sh.tex, &fr, &dst, 0.0, nullptr, mirror ? SDL_FLIP_HORIZONTAL : SDL_FLIP_NONE); }
    // ---- Render::drawBubble (HD 1.0 0x1ae80): word-wrapped text in a bubble built from 34 px tiles of image 0x9c (3 x 3 style body, frames 4..7 = the tail notch), plus a tail image (image 0xb for flag 1, image 0x9c frame 8 scaled 0.6 otherwise).
    // Checked against the original under Unicorn (tools/oracle/hd_bubble_probe.py) by tools/bubble_diff.py.
    static int wrapText(const std::vector<uint8_t>& fw, const std::string& s, std::vector<uint16_t>& out, int maxLines, int maxW, float scale) {   // _BHLib_WrapText 0x9aac, Latin branch
        out.assign(maxLines, 0); int len = (int)s.size(), i = 0, start = 0, line = 0; float acc = 0.0f;
        while (i < len) { unsigned char c = (unsigned char)s[i];
            if (c == 10) { out[line] = (uint16_t)start; line++; if (line == maxLines) return 0; start = i + 1; i++; acc = 0.0f; }
            else { float w = (float)fw[c] * scale; float na = acc + w; if (na <= (float)maxW) { acc = (float)(int)na; i++; }
                else { out[line] = (uint16_t)start; line++; if (line == maxLines) return 0; int j = i - 1; int k = j; while (k >= 0 && s[k] != ' ' && s[k] != 10) k--;
                    if (k < (int)out[line - 1]) k = j; start = k + 1; i = k + 1; acc = 0.0f; } } }
        out[line] = (uint16_t)start; line++; if (line == maxLines) return 0; out[line] = (uint16_t)((start == 0 ? len : i) + 1); return line; }
    void imgDraw(int id, int frame, float x, float y, int flags, float scale, int alpha) {
        if (bubbleLog) { char b[160]; snprintf(b, sizeof b, "drawImage %d %d %.1f %.1f %d %.4f %d", id, frame, x, y, flags, scale, alpha); bubbleLog->push_back(b); return; }
        Sheet& sh = id == 11 ? hdBubTail : hdBub9; if (!sh.tex || frame < 0 || frame >= (int)sh.fr.size()) return; const SDL_Rect& fr = sh.fr[frame]; const SDL_Point& of = sh.off[frame];
        const SDL_Point& size = sh.sz[frame];
        // HD drawImage mirrors the horizontal offset about the anchor before
        // swapping the U coordinates. The tail notch tiles are asymmetric.
        const int offsetX = (flags & 2) ? -of.x - size.x : of.x;
        SDL_Rect dst{static_cast<int>(x + offsetX * scale), static_cast<int>(y + of.y * scale),
                     static_cast<int>(std::lround(size.x * scale)), static_cast<int>(std::lround(size.y * scale))};
        SDL_SetTextureAlphaMod(sh.tex, (Uint8)alpha); SDL_RenderCopyEx(ren, sh.tex, &fr, &dst, 0.0, nullptr, (SDL_RendererFlip)((flags & 2 ? SDL_FLIP_HORIZONTAL : 0) | (flags & 4 ? SDL_FLIP_VERTICAL : 0))); SDL_SetTextureAlphaMod(sh.tex, 255); }
    void drawBubbleBorderJoin(int x, int y, int alpha) {
        if (bubbleLog) return;
        // The mirrored notch and the next bottom tile meet at their transparent
        // gutters. Continue the straight bottom edge through those two pixels.
        const SDL_Rect& edge = hdBub9.fr[2];
        SDL_Rect src{edge.x + edge.w / 2, edge.y, 2, edge.h};
        SDL_Rect dst{x, y - edge.h / 2, 2, edge.h};
        SDL_SetTextureAlphaMod(hdBub9.tex, (Uint8)alpha);
        SDL_RenderCopyEx(ren, hdBub9.tex, &src, &dst, 0.0, nullptr, SDL_FLIP_VERTICAL);
        SDL_SetTextureAlphaMod(hdBub9.tex, 255);
    }
    void drawBubble(int x, int y, int width, const std::string& text, int f, int p6, int alpha, int tex = -1) {
        const float L534 = 0.8f; const bool pad = true;   // layout +0x534 (text scale); the global 0x172c10 == 1 on the iPad class
        Sheet& tb = hdBubTail; Sheet& t9 = hdBub9; if (!t9.tex || !tb.tex || hdFontW.empty() || hdFont.box.size() < 92) return;
        float tailW, tailH, tailScale; if (f & 1) { tailH = (float)(tb.box[0].y - 2); tailW = (float)(tb.box[0].x - 2); tailScale = 1.0f; } else { tailH = (float)(t9.box[8].y - 2) * 0.6f; tailW = (float)(t9.box[8].x - 2) * 0.6f; tailScale = 0.6f; }
        const int tile = t9.box[0].x - 2; int ip0 = (int)((float)y + tailH * -0.5f); int s26 = ip0 - tile;
        std::vector<uint16_t> out; int lines = wrapText(hdFontW, text, out, 0x100, (width - 2 * tile) & 0xffff, L534);
        const float fh = (float)hdFont.box[91].y; const float s22 = fh * L534; const float s24 = pad ? fh * 0.9f : s22;
        float total = (float)lines * s22 + (float)tile; int tot = (int)total; int rows = tot / tile; if (tile * rows != tot) rows++; int rt = tile * rows;
        int fb = width / tile, rw = tile * fb; if (rw != width) { fb++; rw = tile * fb; } int lastCol = fb - 1, halfW = rw / 2, sb = tile / 2;
        int tc = (f & 4) == 0 ? fb - 7 : 5; int mode58 = 0; if (pad && (f & 1)) { tc = 4; mode58 = 1; }
        float s28 = 0.0f, s30 = 0.0f; float rowY = (float)(s26 + sb - rt);
        for (int ip = 0; ip < rows + 1; ip++, rowY += (float)tile) {
            int cx = x + sb - halfW, sl = x + tile + sb - halfW, r8 = x + sb - tile - halfW;
            for (int col = 0; col < fb; col++, cx += tile, sl += tile, r8 += tile) {
                int fr = -1, fl = 0, adj = 0;
                if (ip == 0) { if (col == 0) { fr = 0; } else if (col == lastCol) { fr = 0; fl = 2; adj = 2; } else fr = 2; }
                else if (ip == rows - 1) {
                    if (col == 0) { fr = 0; fl = 4; } else if (col == lastCol) { fr = 0; fl = 6; adj = 2; }
                    else if (col == tc) { if ((f & 4) != 0 || mode58 != 0) { fr = 5; fl = 2; adj = 2; } else { fr = 4; } }
                    else if (col == tc + 1) { if ((f & 4) == 0 && mode58 == 0) { fr = 5; } else { fr = 4; fl = 2; adj = 2; } }
                    else { fr = 2; fl = 4; } }
                else if (ip == rows) {
                    if (col == tc) { if ((f & 4) == 0 && mode58 == 0) { s30 = (float)sl; s28 = rowY; fr = 6; } else { fr = 7; fl = 2; adj = 2; } }
                    else if (col == tc + 1) { if ((f & 4) == 0 && mode58 == 0) { fr = 7; } else { s30 = (float)r8; s28 = rowY; fr = 6; fl = 2; adj = 2; } } }
                else { if (col == 0) fr = 1; else if (col == lastCol) { fr = 1; fl = 2; adj = 2; } else fr = 3; }
                if (fr >= 0) imgDraw(0x9c, fr, (float)(cx - adj), rowY, fl, 1.0f, alpha);
                if (fr == 4 && fl == 2 && col + 1 < lastCol) drawBubbleBorderJoin(cx + sb - adj, (int)rowY, alpha);
            }
        }
        float ty = ((float)s26 - (float)lines * s24) + s24 * -0.5f + (float)sb;
        for (int k = 0; k < lines; k++) { int a0 = out[k], len = (int)out[k + 1] - a0; std::string ln = (text + std::string(1, (char)0)).substr(a0, std::max(0, len)); if (!ln.empty()) ln.pop_back();   // strncpy copies the source's terminator for the last line, so only the separator of the other lines is dropped
            if (!ln.empty()) { if (bubbleLog) { char bb[200]; snprintf(bb, sizeof bb, "printString %s %.1f %.4f %d %d %d %d %.4f %d %d %d", ln.c_str(), (float)x, ty, 16, 16, 112, alpha & 255, L534, 0, 1, tex); bubbleLog->push_back(bb); } else printString(ln, (float)x, ty, 16, 16, 112, alpha & 255, L534, 0, true); }
            ty += s22; }
        if (f & 1) { int lr = (f & 4) ? 2 : 0; int s10 = (f & 4) ? (int)(-tailW) : 0; if (mode58) s10 = (int)((float)s10 - tailW); imgDraw(11, p6, (float)s10 + s30, s28 + 0.0f, lr, tailScale, alpha); }
        else { int lr = (f & 4) ? 2 : 0; int hx = (int)(tailW * 0.5f); float tx = (float)((f & 4) ? -hx : hx) + s30; float tyy = (float)(int)(tailH * 0.5f) + s28; imgDraw(0x9c, 8, tx, tyy, lr, tailScale, alpha); } }
    // ---- Render::drawImage(id, frame, x, y, flags, scale, alpha) for any HD image id (tools/export_hd_images.py): the frame is drawn centred on its anchor (+ record offsets) at frame size * scale; flags 2 / 4 mirror
    std::map<int, Sheet> imgCache; std::vector<std::string>* imgLog = nullptr;
    Sheet* imgSheet(int id) { auto it = imgCache.find(id); if (it != imgCache.end()) return it->second.tex ? &it->second : nullptr; Sheet& s = imgCache[id];
        if (!loadSheet(retDir + "img/hd_" + std::to_string(id), s)) { freeSheet(s); loadSheet(retDir + "loc_" + langDir(lang) + "/img_" + std::to_string(id), s); } return s.tex ? &s : nullptr; }
    void dropImages() { for (auto& kv : imgCache) freeSheet(kv.second); imgCache.clear(); }
    void drawImage(int id, int frame, float x, float y, int flags, float scale, int alpha) {
        if (imgLog) { char t[160]; snprintf(t, sizeof t, "drawImage %d %d %.2f %.2f %d %.3f %d", id, frame, x, y, flags, scale, alpha); imgLog->push_back(t); return; }
        Sheet* sh = imgSheet(id); if (!sh || frame < 0 || frame >= (int)sh->fr.size()) return; const SDL_Rect& fr = sh->fr[frame]; const SDL_Point& of = sh->off[frame];
        SDL_Rect dst{(int)std::lround(x + of.x * scale), (int)std::lround(y + of.y * scale), (int)std::lround(fr.w * scale), (int)std::lround(fr.h * scale)};
        SDL_SetTextureAlphaMod(sh->tex, (Uint8)alpha); SDL_RenderCopyEx(ren, sh->tex, &fr, &dst, 0.0, nullptr, (SDL_RendererFlip)((flags & 2 ? SDL_FLIP_HORIZONTAL : 0) | (flags & 4 ? SDL_FLIP_VERTICAL : 0))); SDL_SetTextureAlphaMod(sh->tex, 255); }
    // Battle banner tasks (HD 1.0 BattleCountDrawPriority 0x1f580 and RoundCountDrawPriority 0x205fc; checked against the original with tools/oracle/hd_task_probe.py)
    static int countLife(int m) { return m > 5 ? 45 : (m <= 2 ? 60 : 120); }
    void battleCount(int m, int t) {
        static const int tab[7][2] = {{107, 0}, {107, 1}, {107, 2}, {108, 2}, {108, 0}, {108, 1}, {109, 0}};   // table at 0xe76a4 (image id, frame); modes 0..2 = the big 3-2-1 digits, 3..5 = 30 seconds / 1 minute / 2 minutes left, 6 = Round START
        float base = m > 5 ? (float)t * 0.09f : (m <= 2 ? 8.0f + (float)t * -0.13f : 4.0f + (float)t * -0.033f);
        drawImage(tab[m][0], tab[m][1], 600.0f, 350.0f, 0, base * 2.0f, 255); }
    void roundPanel(int n, int t) {   // RoundCountDrawPriority: the "Round" label and the two digits of the round number, moving and growing for 75 ticks
        float ft = (float)t; float y = 350.0f + ft * -0.21f;
        drawImage(109, 1, 570.0f + ft * -3.67f, y, 0, ft * 0.04f, 255);
        drawImage(95, (n / 10) % 10, 630.0f + ft * 0.33f, y, 0, ft * 0.08f, 255); drawImage(95, n % 10, 630.0f + ft * 2.4f, y, 0, ft * 0.08f, 255); }
    // iPad layout struct of HD 1.0 (device layout selected in Core::settingsInit; local/cache/assets/hd10_layout.bin, 0x700 bytes)
    std::vector<uint8_t> lay; bool layLoaded = false;
    float layF(int off) { if (!layLoaded) { layLoaded = true; if (FILE* f = fopen((root + "/hd10_layout.bin").c_str(), "rb")) { lay.resize(0x700); size_t n = fread(lay.data(), 1, lay.size(), f); lay.resize(n); fclose(f); } } float v = 0; if (off + 4 <= (int)lay.size()) memcpy(&v, &lay[off], 4); return v; }
    // JudgeWinPriority (HD 1.0 0x1c99c): the round / match result screen; scores, dense ranks (0 = best), wins shown (already minus the win of this round while it is being awarded), win point target, reach mask
    // checked against the original with tools/oracle/hd_judge_probe.py (tools/judge_diff.py)
    void judgeWin(const int score[4], const int rank[4], const int wins[4], int roundWinner, int drawFlag, int wp, int reach, bool gameFlag = false) {   // gameFlag = GA_GetGameFlag (set by GA_OnGameFlag for the whole battle)
        int cnt = (1 - rank[0] < 0 ? 0 : 1 - rank[0]) + (rank[1] == 0) + (rank[2] == 0) + (rank[3] == 0); int w = rank[3] == 0 ? 3 : rank[2] == 0 ? 2 : rank[1] == 0 ? 1 : 0;   // the (last) player with rank 0
        if (cnt == 1) { drawImage(0x87, 4, layF(0x148), layF(0x14c), 0, layF(0x144), 255); drawImage(0x87, w, layF(0x150), layF(0x154), 0, layF(0x144), 255); drawImage(0x88, 0, layF(0x158), layF(0x15c), 0, 1.0f, 255); drawImage(0x62, w, layF(0x160), layF(0x164), 0, 2.0f, 0xde); }
        else drawImage(0x89, 0, layF(0x10c), layF(0x110), 0, 1.0f, 255);
        for (int k = 0; k < 4; k++) drawImage(0x6a, 2 * k, layF(0x104) + (float)k * layF(0x108), layF(0xfc), 0, 1.0f, 255);
        for (int k = 0; k < 4; k++) drawImage(0x6a, 2 * k + 1, layF(0x104) + (float)k * layF(0x108), layF(0x100), 0, 1.0f, 255);
        float yd = (float)(int)layF(0x184);
        for (int p = 0; p < 4; p++) { int sc = score[p]; float x = (float)(int)((float)p * layF(0x18c) + layF(0x188)); drawImage(0x5f, (sc / 100) % 10, x, yd, 0, layF(0x194), 255); x = (float)(int)(x + layF(0x190)); drawImage(0x5f, (sc / 10) % 10, x, yd, 0, layF(0x194), 255); x = (float)(int)(x + layF(0x190)); drawImage(0x5f, sc % 10, x, yd, 0, layF(0x194), 255); }
        for (int p = 0; p < 4; p++) { float x = layF(0x104) + (float)p * layF(0x108), y = layF(0xfc);
            drawImage(0x6a, p * 2, x, y, 0, 1.0f, 255);
            int shown = wins[p];
            if (!gameFlag && p == roundWinner && drawFlag != 1) shown--;   // [0x2596c4 + 0x28] != 1: the round's win is not counted yet (flag [0x28] set when the round was a draw)
            int lit = shown < 0 ? 0 : shown;
            for (int k = 0; k <= wp; k++) drawImage(0x5d, p, x + layF(0x19c + wp * 0x14 + 4 * k), y + layF(0x198), 0, 1.0f, lit <= k ? 0x22 : 0xff);
            if ((reach >> p) & 1) drawImage(0x91, 0, x + layF(0x200), y + layF(0x204), 0, 1.0f, 255); } }
    // JudgeWinTeamPriority (HD 1.0 0x1ce64): the result screen of team battles (two teams: players 0 / 2 and 1 / 3); checked with tools/oracle/hd_judge_probe.py (tools/judge_team_diff.py)
    void judgeWinTeam(const int tscore[2], const int trank[2], const int wins[2], int roundWinner, int drawFlag, int wp, int reach, bool gameFlag = false) {
        int cnt = (trank[0] == 0) + (trank[1] == 0); int sl = trank[1] == 0 ? 1 : 0;
        if (cnt == 1) { drawImage(0x87, 4, layF(0x148), layF(0x14c), 0, layF(0x144), 255); drawImage(0x87, sl, layF(0x150), layF(0x154), 0, layF(0x144), 255); drawImage(0x88, 0, layF(0x158), layF(0x15c), 0, 1.0f, 255);
            drawImage(0x62, sl, layF(0x3d4), layF(0x3dc), 0, 2.0f, 0xde); drawImage(0x62, sl + 2, layF(0x3d8), layF(0x3dc), 0, 2.0f, 0xde); }
        else drawImage(0x89, 0, layF(0x10c), layF(0x110), 0, 1.0f, 255);
        for (int k = 0; k < 2; k++) drawImage(0x6a, 12 + k, (float)k * layF(0x3e8) + layF(0x3e4), layF(0x3e0), 0, 1.0f, 255);
        float yd = (float)(int)layF(0x400);
        for (int t = 0; t < 2; t++) { int sc = tscore[t]; float x = (float)(int)(t == 0 ? layF(0x3f4) : layF(0x3f8)); drawImage(0x5f, (sc / 100) % 10, x, yd, 0, layF(0x3f0), 255); x = (float)(int)(x + layF(0x3fc)); drawImage(0x5f, (sc / 10) % 10, x, yd, 0, layF(0x3f0), 255); x = (float)(int)(x + layF(0x3fc)); drawImage(0x5f, sc % 10, x, yd, 0, layF(0x3f0), 255); }
        for (int t = 0; t < 2; t++) { float tx = (float)t * layF(0x3e8) + layF(0x3e4), iy = layF(0x404) + layF(0x408);
            int shown = wins[t]; if (!gameFlag && drawFlag != 1 && t == roundWinner) shown--; int lit = shown < 0 ? 0 : shown;
            for (int k = 0; k <= wp; k++) drawImage(0x5d, 4 + t, tx + layF(0x30c + wp * 0x14 + t * 0x64 + 4 * k), iy + layF(0x308), 0, 1.0f, k >= lit ? 0x22 : 0xff);
            if ((reach >> t) & 1) drawImage(0x91, 0, tx + (t == 0 ? layF(0x2fc) : layF(0x300)), iy + layF(0x304), 0, 1.0f, 255); } }
    void drawFrame5(int x, int y, int width) { const int t = 56; int n = width / t; int px = x - (t * n / 2 - t / 2); for (int i = 0; i < n; i++, px += t) blit(hdFrame78, i == 0 ? 0 : i == n - 1 ? 2 : 1, (float)px, (float)y); }
    void cursor(int cx, int cy, int player, int ticks, bool bracket) {
        int ang = (player << 14) + 0x1000 * ticks; float ax = (cx + 0.5f) * CELL, ay = (cy + 0.5f) * CELL;
        blit(cur, player & 3, ax, ay, 1.0f + 0.1f * (float)std::sin(ang * 6.283185307 / 65536.0));
        if (bracket) blit(cur, 4, ax, ay, 1.0f + 0.075f * (float)std::sin(2 * ang * 6.283185307 / 65536.0));
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
                const SDL_Rect& fr = sh.fr[frame]; const SDL_Point& of = sh.off[frame]; float sc = CELL / 64.0f; if (frame < (int)sh.fit.size()) sc *= sh.fit[frame];   // drawn at the original iPad (HD 1.0) frame size
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
        if (state == 0xC && blink <= 333333.0) { Sheet& pr = pad ? a.pprompt : a.tprompt; const SDL_Rect& pf = pr.fr[0];
#if defined(__ANDROID__)
            const bool dcPrompt = false;   // phones keep "TAP THE SCREEN!"
#else
            const bool dcPrompt = a.dpressOk;   // keyboard/pad platforms: the Dreamcast prompt "PRESS START BUTTON!" (ENGLISH/PRESSSTART), centred on the phone prompt's place
#endif
            if (dcPrompt) { SDL_Rect pd{px + pf.w / 2 - a.dpress.w / 2, py + pf.h / 2 - a.dpress.h / 2, a.dpress.w, a.dpress.h}; SDL_RenderCopy(a.ren, a.dpress.tex, nullptr, &pd); }
            else { SDL_Rect pd{px, py, pf.w, pf.h}; SDL_RenderCopy(a.ren, pr.tex, &pf, &pd); } }
        if (state != 0xC) { SDL_SetRenderDrawBlendMode(a.ren, SDL_BLENDMODE_BLEND); SDL_SetRenderDrawColor(a.ren, 0, 0, 0, (Uint8)std::max(0.0, std::min(255.0, timer / 500000.0 * 255.0))); SDL_Rect all{0, 0, LW, LH}; SDL_RenderFillRect(a.ren, &all); }
        SDL_RenderSetLogicalSize(a.ren, W, H);
    }
};

// ---------------------------------------------------------------- Credits (HD 1.0 CreditsScreen: parse 0x40748, process 0x40c50, render 0x40d68, handleInput 0x40d34)
struct CreditsMode : Screen {
    struct E { float h, y; int type; std::string text; };
    std::vector<E> ents; int phase = 0x17; double a14 = 0, a18 = 0, total = 0; bool leave = false;
    static constexpr float S0 = 1.25f, S2 = 0.9f;   // pad scales (+0xa34 / +0xa38 set in init for the device class > 10)
    static bool ok(App& a) { return a.hdFont1.tex && a.hdFont1.box.size() > 91 && a.hdString(0x17c); }
    CreditsMode(App& a) {   // parse(): text key 0x17c; "$s" = orange heading, "$i" + 2 chars = image (not drawn), "$x" skipped, blank line = one font line
        const std::string& s = *a.hdString(0x17c); const float lh = (float)a.hdFont1.box[91].y; float tot = 0.0f; int i = 0, len = (int)s.size();
        while (i < len) { int style = 0;
            for (;;) { if (i >= len) break; char c = s[i];
                if (c == 10) { ents.push_back({lh, tot, 1, ""}); i++; tot += lh + 4.0f; break; }
                if (c != '$') { int j = i; while (j < len && s[j] != 10) j++; float sc = style == 0 ? S0 : S2; ents.push_back({lh * sc, tot, style, s.substr(i, j - i)}); i = j + 1; tot += lh * sc + 4.0f; break; }
                char n = i + 1 < len ? s[i + 1] : 0;
                if (n == 'i') { ents.push_back({0.0f, tot, 3, ""}); i += 4; break; } else if (n == 's') { style = 2; i += 2; } else if (n == 'x') i += 2; else i += 1; } }
        total = tot; }
    int music() override { return -1; }
    void event(App& a, const SDL_Event& e) override { if (phase == 0x18 && e.type == SDL_MOUSEBUTTONDOWN && e.button.button == SDL_BUTTON_LEFT) { a.playSfx(2); a14 = 0; phase = 0x19; } }
    void tick(App& a) override {
        if (phase == 0x17) { a14 += 16384.0; if (a14 >= 500000.0) { a14 = 0; phase = 0x18; } }
        else if (phase == 0x18) { a14 += 16384.0; a18 += 16384.0 * 8e-5f; if (a18 > total) { a14 = 0; a18 = 0; phase = 0x19; } }   // scroll speed 8e-5 per microsecond
        else if (phase == 0x19) { a14 += 16384.0; if (a14 >= 1000000.0) { a14 = 1000000.0; leave = true; } } }
    const char* next() override { if (!leave) return nullptr; leave = false; return "OPTIONS"; }
    void draw(App& a, float) override {
        SDL_RenderSetLogicalSize(a.ren, GW, GH); SDL_RenderSetViewport(a.ren, nullptr); SDL_SetRenderDrawColor(a.ren, 0, 0, 0, 255); SDL_RenderClear(a.ren);
        for (auto& e : ents) { if (e.type != 0 && e.type != 2) continue; if (!(e.y < (float)a18 + 768.0f && (float)a18 < e.y + e.h)) continue;
            if (e.type == 0) a.printString(e.text, 512.0f, (float)(int)(e.y - (float)a18), 255, 255, 255, 255, S0, 0, false, 1); else a.printString(e.text, 512.0f, (float)(int)(e.y - (float)a18), 0xe0, 0x90, 0x10, 255, S2, 0, false, 1); }
        if (phase == 0x17 || phase == 0x19) { float f = phase == 0x17 ? (float)(a14 / 500000.0 * -255.0 + 255.0) : (float)(a14 / 1000000.0 * 255.0); SDL_SetRenderDrawBlendMode(a.ren, SDL_BLENDMODE_BLEND); SDL_SetRenderDrawColor(a.ren, 0, 0, 0, (Uint8)(int)std::max(0.0f, std::min(255.0f, f))); SDL_Rect all{0, 0, GW, GH}; SDL_RenderFillRect(a.ren, &all); }
    }
};

// ---------------------------------------------------------------- Options > How to Play (HD 1.0 HelpScreen: init 0x26218, process 0x24f00, handleInput 0x250c8, render 0x25314; draw calls checked with tools/oracle/hd_help_probe.py)
struct HelpMode : Screen {
    int phase = 0x14, a34 = -1, topic = -1, page = 0, sel = 0, mascot = 0, leaveTo = 0; bool a31 = false, a32 = false, leave = false; double a20 = 500000.0, t = 0;
    static constexpr int N = 6; static constexpr int key[N] = {0x169, 0x16a, 0x16b, 0x16c, 0x16d, 0x16e}; static constexpr int pagesN[N] = {6, 2, 2, 1, 1, 1}, firstKey[N] = {367, 373, 375, 377, 378, 379};   // DAT 0xe78ac: (page count, first text key)
    static constexpr int px[N] = {145, 225, 305, 385, 465, 545}, py[N] = {173, 263, 353, 433, 523, 613};
    static bool ok(App& a) { return a.opBg.tex && a.hlHdr.tex && a.hlTab.tex && a.hlFrm.tex && a.hlDia.tex && a.ssTab.tex && a.mnBars.tex && a.ssArrows.tex && a.hdFont.tex; }
    int music() override { return phase == 0x14 ? -1 : 5; }
    int hit(App& a, float lx, float ly) { for (int i = 0; i < N; i++) { int w = a.mnBars.box[0].x, h = a.mnBars.box[0].y; if (px[i] <= lx && lx <= px[i] + w && py[i] <= ly && ly <= py[i] + h) return i; } int bw = a.ssArrows.box[0].x, bh = a.ssArrows.box[0].y; if (0 <= lx && lx <= bw && 768 - bh <= ly && ly <= 768) return 6; return -1; }
    void event(App& a, const SDL_Event& e) override {
        if (phase != 0x15 || e.type != SDL_MOUSEBUTTONDOWN || e.button.button != SDL_BUTTON_LEFT) return;
        float lx, ly; SDL_RenderSetLogicalSize(a.ren, GW, GH); SDL_RenderWindowToLogical(a.ren, e.button.x, e.button.y, &lx, &ly); int x = (int)lx, y = (int)ly;
        if (a34 < 0) {   // topic list
            int h = hit(a, lx, ly); if (h < 0) return; int before = sel; if (h < 6) sel = h;
            if (before == h || h == 6) { a.playSfx(2); if (h == 6) { phase = 0x16; a20 = 0; leaveTo = 1; return; } topic = h; a20 = 0; a31 = true; a32 = false; a34 = 2; page = 0; }
            else a.playSfx(0); return; }
        if (a34 != 1) return;   // page view: left / right half = previous / next page, the bar's arrows, the back area
        const int cnt = pagesN[topic]; auto prev = [&] { if (page == 0) return; page--; a.playSfx(2); }; auto next = [&] { if (page >= cnt - 1) return; page++; a.playSfx(2); };
        if (!(512 < x || y >= 718)) prev(); else if (!(x <= 512 || y >= 718)) next();
        else if (357 <= x && x <= 404 && 724 <= y && y <= 768) prev(); else if (617 <= x && x <= 664 && 724 <= y && y <= 768) next();
        else if (x <= 0x31 && y > 718) { a20 = 0; a32 = true; a34 = 2; a.playSfx(3); } }
    void tick(App& a) override {
        if (phase == 0x14) { a20 -= 16384.0; if (a20 <= 0) { a20 = 0; phase = 0x15; } }
        else if (phase == 0x16) { a20 += 16384.0; if (a20 >= 500000.0) { a20 = 500000.0; leave = true; } }
        else if (phase == 0x15) {
            if (a34 == 2) { a20 += 16384.0; if (a20 >= 500000.0) { a20 = 500000.0; if (!a32) a34 = 0; else { a32 = false; topic = -1; a34 = -1; phase = 0x14; } a31 = false; } }
            else if (a34 == 0) { a20 -= 16384.0; if (a20 <= 0) { a20 = 0; a34 = 1; } }
            else if (a34 != 1) { t += 16384.0; if (t >= 166666.671875) { t -= 166666.671875; mascot = (mascot + 1) % 12; } } } }
    const char* next() override { if (!leave) return nullptr; leave = false; return "OPTIONS"; }
    // the frame of a page: filled panel, side edges and a top / bottom row of 8 px tiles (offsets of the pad layout)
    void panel(App& a) {
        a.fillRect(211, 90, 596, 223, 255, 255, 255, 255);
        a.rtexRaw(a.hlFrm, 0, 208, 87, 8, 229); a.rtexRaw(a.hlFrm, 2, 808, 87, 8, 229);
        for (int x = 216; x <= 800; x += 8) { a.rtexRaw(a.hlFrm, 1, (float)x, 87, 8, 8); a.rtexRaw(a.hlFrm, 3, (float)x, 309, 8, 7); }
        a.rtexRaw(a.hlFrm, 1, 800, 87, 8, 8); a.rtexRaw(a.hlFrm, 3, 800, 309, 8, 7); }
    void draw(App& a, float) override {
        SDL_RenderSetLogicalSize(a.ren, GW, GH); SDL_RenderSetViewport(a.ren, nullptr); SDL_SetRenderDrawColor(a.ren, 0, 0, 0, 255); SDL_RenderClear(a.ren);
        static const int tm[48] = {0,1,2,3,3,3,4,5,6,7,8,3,9,10,11,12,13,14,15,16,17,18,19,3,3,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,3,35,36,37,38,39,3,3};
        for (int r = 0; r < 6; r++) for (int c = 0; c < 8; c++) a.rtex(a.opBg, tm[r * 8 + c], (float)(c * 128), (float)(r * 128), 128, 128);
        if (a31 || a34 < 0) {
            a.rtexRaw(a.hlHdr, 0, 208, 50, 350, 34);
            for (int i = 0; i < N; i++) { int w = a.mnBars.box[0].x, h = a.mnBars.box[0].y; a.rtex(a.mnBars, i == sel ? 1 : 0, (float)px[i], (float)py[i], w, h);
                if (const std::string* s = a.hdString(key[i])) { const float sc = 0.6667f; const float lh = (float)a.hdFont1.box[91].y * sc; a.printString(*s, (float)(px[i] + a.mnBars.box[0].x / 2), (float)py[i] + ((float)a.mnBars.box[0].y - lh) * 0.5f, 255, 255, 255, 255, sc, 0, false, 1); }
                if (i == sel) { const SDL_Rect& m = a.mnMasc.fr[mascot]; a.rtex(a.mnMasc, mascot, (float)(px[i] + 36 - m.w), (float)(py[i] + (a.mnBars.box[0].y - m.h) / 2), m.w, m.h); } } }
        else {
            panel(a); a.rtexRaw(a.hlTab, 0, 208, 50, 263, 38);
            if (const std::string* s = a.hdString(key[topic])) a.printString(*s, 228, 55, 16, 16, 112, 255, 0.4f, 1, false, 1);
            if (const std::string* s = a.hdString(firstKey[topic] + page)) a.printString(*s, 216, 95, 16, 16, 112, 255, 0.4f, 1, false, 1);
            if (topic == 0 && page == 1) a.rtexRaw(a.hlDia, 0, 332, 146, 360, 163); else if (topic == 0 && page == 2) a.rtexRaw(a.hlDia, 1, 242, 121, 540, 188); else if (topic == 1 && page == 1) a.rtexRaw(a.hlDia, 2, 242, 177, 540, 132);
            a.rtex(a.ssTab, 0, 360, 727, 303, 41);
            if (const std::string* f = a.hdString(0x17f)) { char tx[128]; snprintf(tx, sizeof tx, f->c_str(), page + 1, pagesN[topic]); a.printString(tx, 512, 735, 16, 16, 112, 255, 0.4f, 0, false, 1); } }
        a.rtex(a.ssArrows, 0, 0, (float)(768 - a.ssArrows.box[0].y), a.ssArrows.box[0].x, a.ssArrows.box[0].y);
        if (!(phase == 0x15 && a34 == 1)) a.fillRect(0, 0, GW, GH, 0, 0, 0, (int)(a20 / 500000.0 * 255.0));
    }
};

// ---------------------------------------------------------------- battle setup, players pane (HD 1.0 PlayerSelectScreen::renderPlayersPane 0x33514). Verified draw calls: panels, slot labels, player and CPU level texts.
// Not ported yet (listed in docs/roadmap.md): the two bottom sheets, the Host / Join network buttons, the back button and the second corner button.
// PlayerSelectScreen::process state 0x23 (HD 1.0 0x34e16).
struct PlayersTextureLoad {
    struct Clock {
        float elapsed = 0;
        unsigned frame = 0, frameCount = 0;

        void step(float dt) {
            elapsed += dt;
            const float period = 1000000.0f / elapsed;
            if (elapsed >= period) {
                elapsed -= period;
                if (++frame == frameCount) frame = 0;
            }
        }
    };

    Clock preview, character;
    float pulse = 0, pulseRate = 0;
    std::vector<int> textures;
    size_t loaded = 0;

    // Returns true when the next screen state is 0x24. The original retires
    // the list on the tick after the last upload.
    template <class Put, class Release>
    bool step(float dt, int screenWidth, Put put, Release release) {
        if (loaded >= textures.size()) {
            for (auto it = textures.rbegin(); it != textures.rend(); ++it) release(*it);
            textures.clear();
            return true;
        }

        put(textures[loaded], 1);
        ++loaded;
        character.step(dt);
        pulseRate += 5.0f;
        pulse += 5.0f;
        if (pulse >= static_cast<float>(screenWidth) * 1.1f) {
            const float negativeWidth = -static_cast<float>(screenWidth);
            pulse = negativeWidth * 0.15f;
            pulseRate = negativeWidth * 0.05f;
        }
        preview.step(dt);
        return false;
    }
};

// PlayerSelectScreen::process, states 0x26 / 0x27 (HD 1.0 0x34de4; ground truth tools/oracle/players_state_probe.py, read in docs/roadmap.md 2026-11-14).
// 0x26: the fade timer +0xa38 grows by dt; at >= 500000 it clamps and, when +0xa3c is set, requests Menu (4).
// 0x27: acts only when (state timer & 7) > 4. Network flag: precalc(a40 == 1, 7) and screen 0x11.
// Local: split flag +0xa7d gives remove(0x63) / put(0x64, 1); a40 == 1 -> screen 0x13 (split 0x14), else 0xf (split 0x10); precalc(a40 == 1, 7).
// PlayerSelectScreen::handleInput routing in state 0x25 (HD 1.0 0x34fb8): +0xa44 == 0 -> processPlayersPane, == 1 -> processSettingsPane, else nothing.
static std::string playersRouteOps(int a44) { return a44 == 0 ? "ppane" : a44 == 1 ? "spane" : ""; }
static int playersFlowStep(int st, int tim, int a3c, int a40, int net, int split, float dt, float& fade, std::string& ops) {
    ops.clear(); char b[64];
    auto add = [&](const char* t) { if (!ops.empty()) ops += ';'; ops += t; };
    if (st == 0x26) { fade = fade + dt; if (!(fade >= 500000.0f)) return 0; fade = 500000.0f; return a3c == 0 ? 0 : 4; }
    if (st == 0x24) { fade = fade - dt; if (fade > 0.0f) return 0; fade = 0.0f; add("change(37)"); add("song(5)"); return 0; }   // fade-in ends: changeGameState(0x25) then playSong(5)
    if (st != 0x27 || (tim & 7) <= 4) return 0;
    snprintf(b, sizeof b, "precalc(%d,7)", a40 == 1 ? 1 : 0);
    if (net) { add(b); return 0x11; }
    if (split) { add("remove(99,0)"); add("put(100,1)"); }
    add(b);
    if (a40 == 1) return split ? 0x14 : 0x13;
    return split ? 0x10 : 0xf;
}
// iPad PlayerSelectScreen::render (HD 1.0 0x35154).
struct PlayersFrame {
    int state = 0x23, pane = 0, team = 0, costume = 0;
    int loaded = 0, textureCount = 0, catFrame = 0, mouseFrame = 0;
    float fade = 500000.0f, catX = -GW * 0.15f, mouseX = -GW * 0.05f;

    void draw(App& app, const std::function<void(int)>& drawPane) const {
        const auto texture = [&](int id, int frame, float x, float y, bool tile) {
            Sheet* sheet = app.imgSheet(id);
            if (!sheet || frame < 0 || frame >= static_cast<int>(sheet->fr.size())) return;
            if (!tile && state == 0x23) {
                x += sheet->off[frame].x;
                y += sheet->off[frame].y;
            }
            const int w = tile ? 128 : sheet->sz[frame].x - 2;
            const int h = tile ? 128 : sheet->sz[frame].y - 2;
            if (app.uiLog) {
                char line[128];
                snprintf(line, sizeof line, "RT %d %d %.4f %.4f %d %d", id, frame, x, y, w, h);
                app.uiLog->push_back(line);
            } else {
                const SDL_Rect& frameRect = sheet->fr[frame];
                const SDL_Rect src{frameRect.x + 1, frameRect.y + 1, w, h};
                const SDL_FRect dst{x, y, static_cast<float>(w), static_cast<float>(h)};
                SDL_RenderCopyF(app.ren, sheet->tex, &src, &dst);
            }
        };
        const auto overlay = [&](int alpha) {
            if (app.uiLog) app.uiLog->push_back("black " + std::to_string(alpha));
            else app.fillRect(0, 0, GW, GH, 0, 0, 0, alpha);
        };
        const auto message = [&](const std::string& text) {
            if (app.hdFont.box.size() <= 91) return;
            const float y = GH * 0.5f - app.hdFont.box[91].y;
            app.printString(text, GW * 0.5f, y, 255, 255, 255, 255, 1.0f, 0, false);
        };

        if (state == 0x23) {
            overlay(255);
            if (const auto* format = app.hdString(0x17d)) {
                char text[128];
                snprintf(text, sizeof text, format->c_str(), loaded, textureCount);
                message(text);
            }
            texture(40, catFrame, catX, GH * 0.75f, false);
            texture(costume == 1 ? 75 : costume == 2 ? 63 : 51, mouseFrame, mouseX, GH * 0.75f, false);
            return;
        }

        // The iPad tile map, resource key 0x126 (record 880).
        static constexpr int tiles[6][8] = {
            {0, 1, 2, 3, 4, 4, 4, 4}, {5, 6, 7, 8, 9, 10, 4, 4},
            {11, 12, 4, 4, 13, 14, 4, 15}, {16, 17, 18, 19, 20, 21, 22, 23},
            {24, 25, 26, 27, 28, 29, 30, 31}, {32, 4, 4, 4, 33, 34, 35, 36},
        };
        for (int row = 0; row < 6; ++row)
            for (int col = 0; col < 8; ++col)
                texture(28, tiles[row][col], 128.0f * col, 128.0f * row, true);
        texture(34, team == 1 ? 3 : 2, 208, 50, false);
        if (pane == 0 || pane == 1) drawPane(pane);
        if (state == 0x24 || state == 0x26) {
            overlay(static_cast<int>((fade / 500000.0f) * 255.0f));
        } else if (state == 0x27) {
            overlay(192);
            if (const auto* text = app.hdString(0x182)) message(*text);
        }
    }
};

struct PlayersPane {
    // HD 1.0 renderPlayersPane, iPad branch, local setup.
    static void drawPad(App& a, const int human[4], const int level[4], int slider, int pressed,
                        std::vector<std::string>* trace) {
        Sheet* labels = a.imgSheet(36);
        if (!labels || a.hdFont.box.size() <= 91 || a.hdFontW.empty()) return;
        const float lineHeight = static_cast<float>(a.hdFont.box[91].y);
        const auto texture = [&](int image, int frame, int x, int y) {
            Sheet* sheet = a.imgSheet(image);
            if (!sheet || frame >= static_cast<int>(sheet->sz.size())) return;
            const int w = sheet->sz[frame].x - 2, h = sheet->sz[frame].y - 2;
            if (trace) {
                char line[128];
                snprintf(line, sizeof line, "RT %d %d %d %d %d %d", image, frame, x, y, w, h);
                trace->push_back(line);
            } else a.rtex(*sheet, frame, x, y, w, h);
        };
        const auto label = [&](int key, int x, int y, int width, int height,
                               float scale, int color, bool shrink) {
            const auto* text = a.hdString(key);
            if (!text) return;
            const int center = x + width / 2;
            const float top = y + (height - lineHeight * scale) * 0.5f;
            if (shrink) {
                int textWidth;
                do {
                    textWidth = a.hdTextWidth(*text, 0, scale);
                    scale -= 0.05f;
                } while (textWidth > 103);
            }
            if (trace) {
                char line[256];
                snprintf(line, sizeof line, "PS %s %d %.1f %.3f %d", text->c_str(), center, top, scale, color);
                trace->push_back(line);
            } else a.printString(*text, static_cast<float>(center), top, color, color, color, 255, scale, 0, false);
        };

        for (int p = 0; p < 4; ++p) texture(35, p, 213 + 151 * p, 178);
        for (int p = 0; p < 4; ++p) {
            texture(36, human[p] ? 3 : 2, 234 + 151 * p, 219);
            texture(36, human[p] ? 2 : 3, 234 + 151 * p, 278);
        }
        texture(12, pressed == 8 ? 3 : 2, 84, 560);
        texture(12, pressed == 9 ? 3 : 2, 634, 560);
        for (int p = 0; p < 4; ++p) {
            label(0x1df, 234 + 151 * p, 219, 103, 31, 0.55f, 0, true);
            label(0x1e0, 234 + 151 * p, 278, 103, 31, 0.55f, 0, true);
        }
        label(0x1db, 84, 560, 306, 60, 1.0f, 255, true);
        label(0x1dc, 634, 560, 306, 60, 1.0f, 255, true);

        for (int p = 0; p < 4; ++p) {
            const int x = 244 + p * 151, y = 314;
            if (p != 0 && slider == p) {
                texture(36, 0, x, y);
                for (int row = 0; row < 6; ++row)
                    label(0x1e1 + row, x, y + 28 * row, 104, 28, 0.5f, 0, false);
                if (labels->off.size() > 4) {
                    const auto& offset = labels->off[4];
                    texture(36, 4, x + 52 + offset.x, y + 28 * level[p] + 14 + offset.y);
                }
            } else {
                texture(36, 1, x, y);
                label(0x1e1 + (p == 0 ? 0 : level[p]), x, y, 104, 29, 0.5f, 0, false);
            }
        }
        texture(17, 0, 0, 711);
        texture(17, 1, 967, 711);
    }

    // human[p] 1 = human, 0 = CPU; level[p] = CPU level index (0 Weak .. 3 Strong), shown as 'Weak' text in the level tag
    static void draw(App& a, const int human[4], const int level[4], std::vector<std::string>* log) {
        auto rt = [&](Sheet& sh, int sx, int sy, int sw, int sh_, float x, float y, int w, int h) {
            if (log) { char t[120]; snprintf(t, sizeof t, "RT %.1f %.1f %d %d %d %d %d %d", x, y, w, h, sx, sy, sw, sh_); log->push_back(t); return; }
            if (!sh.tex) return; SDL_Rect s{sx, sy, sw, sh_}; SDL_Rect d{(int)x, (int)y, w, h}; SDL_RenderCopy(a.ren, sh.tex, &s, &d); };
        auto txt = [&](const std::string& s, float x, float y, float sc) {
            if (log) { char t[200]; snprintf(t, sizeof t, "PS %s %.1f %.1f %.3f 0", s.c_str(), x, y, sc); log->push_back(t); return; }
            a.printString(s, x, y, 255, 255, 255, 255, sc, 0, false, 0); };
        for (int p = 0; p < 4; p++) rt(a.plPanels, 148 * p, 0, 148, 311, 15.0f + 153.0f * p, 50.0f, 148, 311);   // panels: sheet 35 frame strip, u = p / 4
        for (int p = 0; p < 4; p++) { float sx = 31.0f + 153.0f * p;   // slot labels (sheet 36): 'Human' row at y 81 (lit when human), 'Computer' row at y 125
            rt(a.plLabels, 107, human[p] ? 33 : 0, 105, 33, sx, 81.0f, 105, 33); rt(a.plLabels, 107, human[p] ? 0 : 33, 105, 33, sx, 125.0f, 105, 33); }
        rt(a.plBottom, 0, 128, 308, 62, 84.0f, 287.0f, 308, 62); rt(a.plBottom, 0, 128, 308, 62, 262.0f, 287.0f, 308, 62);   // bottom sheets: image 12 frame 2 (u 0, v .5, 308 x 62)
        for (int p = 0; p < 4; p++) { float sx = 31.0f + 153.0f * p; txt("Human", sx + 52.0f, 88.7f, 0.5f); txt("Computer", sx + 52.0f, 132.7f, 0.5f); }
        for (int p = 0; p < 4; p++) {   // level tags: 106 x 31 at y 151 (lit state not traced: drawn at the default frame)
            float sx = 37.0f + 153.0f * p; rt(a.plLabels, 107, 66, 106, 31, sx, 151.0f, 106, 31);
            if (const std::string* s = a.hdString(0x1e1 + (p == 0 ? 0 : level[p]))) txt(*s, sx + 53.0f, 158.5f, 0.5f); }   // player 0 uses the constant key 0x1e1; players 1..3 read their field (+0xd4c, +0xd50, +0xd54)   // level tag text = key 0x1e1 + the player's CPU type (0 Weak, 1 Hates Cats, 2 Loves Mice, 3 Tough, 4 Random, 5 None)
        rt(a.ssArrows, 0, 0, 59, 59, 0.0f, 709.0f, 59, 59); rt(a.ssArrows, 60, 0, 59, 59, 965.0f, 709.0f, 59, 59);   // back button (image 17 frame 0) and the corner button (frame 1), both 59 x 59
    }
};

// ---------------------------------------------------------------- battle setup, players pane input helpers (HD 1.0 PlayerSelectScreen::mutexPlayer 0x2f438, repositionSliderPanelItems 0x2f474); checked with tools/oracle/hd_players_helpers_probe.py
struct PlayersInputHelpers {
    // rows: 0..7 of the pane (stride 0x28 at +0x2e holds one byte per row: 1 = lit). mutexPlayer(a, b, v): v != 0 -> a cleared, b set; v == 0 -> a set, b cleared
    static void mutexPlayer(uint8_t lit[], int a, int b, int v) { lit[a] = v ? 0 : 1; lit[b] = v ? 1 : 0; }
    // repositionSliderPanelItems(x, y): the pane's origin is (x, y); the five further rows stack below it, each at the previous row's y + its height
    struct Row { int x, y, h; };
    static void reposition(int x, int y, Row rows[6]) { int yy = y; for (int i = 0; i < 6; i++) { rows[i].x = x; rows[i].y = yy; yy += rows[i].h; } }
};

// ---------------------------------------------------------------- players pane input, cases 0..13 (HD 1.0 PlayerSelectScreen::handlePlayersPaneInput 0x31d24); the field names are the screen offsets (+0xd3c etc.)
// checked with tools/players_input_diff.py against the original under Unicorn (tools/oracle/hd_players_input_probe.py), in the same item sequence
struct PlayersInputLogic {
    int d58 = -1, d3c = 0, d40 = 0, d44 = 0, a40 = 0, a3c = 0, a38 = 0, d20 = 0, a7c = 0, d18 = 0, g170 = 0; std::vector<int> sfx; bool gameState38 = false;
    bool networkReady = false, d34 = false;
    bool openSettings = false, settingsSyncRequested = false;
    void play(int id) { sfx.push_back(id); }
    void mutex(int a, int b, int v) { (void)a; (void)b; (void)v; }   // the lit flags of the two buttons (not in this dump)
    // one press on item it (press = 0); returns after the switch's own sound and state effects
    void press(int it) {
        a3c = 0;
        if (it == 8 || it == 9) { if (d18 == 0) return; }   // the early return of the pane (clears the item's flag, nothing else)
        switch (it) {
        case 0: case 1: play(3); return;
        case 2: if (d20 == 0 && a7c != 0) { play(2); d3c = 0; mutex(2, 3, 0); d58 = -1; return; } play(3); return;
        case 3: if (d20 == 0 || (g170 != 0)) { play(1); d3c = 1; mutex(2, 3, 1); if (d58 == 1) { d58 = -1; return; } d58 = 1; return; } play(3); return;   // the slider re-layout is in PlayersInputHelpers
        case 4: if (d20 == 0 && a7c != 0) { play(2); d40 = 0; d58 = -1; return; } play(3); return;
        case 5: if (d20 == 0 || (g170 != 0)) { play(1); d40 = 1; mutex(4, 5, 1); if (d58 == 2) { d58 = -1; return; } d58 = 2; return; } play(3); return;
        case 6: if (d20 == 0 && a7c != 0) { play(2); d44 = 0; d58 = -1; return; } play(3); return;
        case 7: if (d20 == 0 || (g170 != 0)) { play(1); d44 = 1; mutex(6, 7, 1); if (d58 == 3) { d58 = -1; return; } d58 = 3; return; } play(3); return;
        case 10: case 11: play(2); return;
        case 12: if (d20 == 0 || g170 != 0) { play(2); a40 = (a40 == 0) ? 1 : 0; return; } play(3); return;
        case 13: if (d20 == 0) { play(3); a3c = 1; a38 = 0; gameState38 = true; return; } return;
        case 14:
            if (d20 != 0) {
                if (g170 == 0 || !networkReady) { play(3); return; }
                play(2);
                if (d34) settingsSyncRequested = true;
            }
            play(2);
            openSettings = true;
            return;
        default: return;
        }
    }
};

// ---------------------------------------------------------------- battle setup, settings pane: menu item rectangles (HD 1.0 PlayerSelectScreen::initSettingsPaneMenuItems 0x31690, phone-style branch: +0xa7c = 0)
// items: 0 back (0, 711, 57 x 57), 1 corner (967, 711, 57 x 57), 2..9 buttons 30 x 30. Values read from the original under Unicorn (tools/players_settings_diff.py).
struct SettingsPaneItems {
    struct PaneRect { int x, y, w, h; };
    static int hit(const PaneRect* rects, int count, int x, int y) {
        for (int i = 0; i < count; ++i) {
            const auto& r = rects[i];
            if (r.x <= x && x <= r.x + r.w && r.y <= y && y <= r.y + r.h) return i;
        }
        return -1;
    }
    // updateMenuItemFromTouchEvent (press, 0): the first item (in order 0..9) whose rect contains the point, edges inclusive; -1 if none
    static int hit(int x, int y) { PaneRect r[10]; layout(r); return hit(r, 10, x, y); }
    static void layout(PaneRect out[10]) {
        out[0] = {0, 711, 57, 57}; out[1] = {967, 711, 57, 57};
        static const int bx[8] = {12, 207, 12, 207, 248, 443, 248, 443}, by[8] = {205, 205, 240, 240, 52, 52, 91, 91};
        for (int i = 0; i < 8; i++) out[2 + i] = {bx[i], by[i], 30, 30};
    }

    // HD initSettingsPaneMenuItems, iPad branch. Network mode omits both
    // launch buttons from the active menu items.
    static int layoutPad(PaneRect (&out)[37], bool network) {
        for (int i = 0; i < 25; ++i)
            out[i] = {228 + (i % 5) * 54, 258 + (i / 5) * 34, 46, 30};
        out[25] = {0, 711, 57, 57};
        out[26] = {967, 711, 57, 57};
        out[27] = {208, 444, 40, 40};
        out[28] = {468, 444, 40, 40};
        out[29] = {208, 500, 40, 40};
        out[30] = {468, 500, 40, 40};
        out[31] = {533, 250, 40, 40};
        out[32] = {793, 250, 40, 40};
        out[33] = {533, 312, 40, 40};
        out[34] = {793, 312, 40, 40};
        if (network) return 35;
        out[35] = {364, 610, 118, 93};
        out[36] = {542, 610, 118, 93};
        return 37;
    }

    static void drawPadTexture(App& app, std::vector<std::string>* trace, int image, int frame, int x, int y) {
        Sheet* sheet = app.imgSheet(image);
        if (!sheet || frame >= static_cast<int>(sheet->sz.size())) return;
        const int w = sheet->sz[frame].x - 2, h = sheet->sz[frame].y - 2;
        if (trace) {
            char line[96];
            snprintf(line, sizeof line, "RT %d %d %d %d %d %d", image, frame, x, y, w, h);
            trace->push_back(line);
        } else app.rtex(*sheet, frame, x, y, w, h);
    }

    // HD 1.0 renderSettingsPane: the three backgrounds and the 25 stage cells.
    static void drawPadStageGrid(App& app, int selected, std::vector<std::string>* trace) {
        drawPadTexture(app, trace, 38, 0, 208, 247);
        drawPadTexture(app, trace, 38, 1, 548, 361);
        drawPadTexture(app, trace, 38, 2, 508, 351);

        PaneRect items[37];
        layoutPad(items, false);
        for (int i = 0; i < 25; ++i) {
            const auto& cell = items[i];
            drawPadTexture(app, trace, 31, i == selected ? 1 : 0, cell.x, cell.y);
            const std::string text = i == 24 ? "?" : std::to_string(i + 1);
            const int x = cell.x + cell.w / 2, y = cell.y + 4;
            if (trace) {
                char line[96];
                snprintf(line, sizeof line, "PS %s %d %d", text.c_str(), x, y);
                trace->push_back(line);
            } else app.printString(text, x, y, 255, 255, 255, 255, 0.75f, 0, false);
        }
    }

    struct PadRules {
        int pointIndex, speedIndex, timeIndex;
        bool highMice, split;
    };

    // Local iPad path following the stage grid. The preview texture is generated
    // separately and drawn at this point, before the two corner buttons.
    static void drawPadRules(App& app, const PadRules& rules, const std::function<void(const SDL_Rect&)>& preview,
                             std::vector<std::string>* trace) {
        const auto label = [&](int x, int y, int key, auto... values) {
            const auto* format = app.hdString(key);
            if (!format) return;
            char text[128];
            snprintf(text, sizeof text, format->c_str(), values...);
            if (trace) {
                char line[180];
                snprintf(line, sizeof line, "PS %s %d %d", text, x, y);
                trace->push_back(line);
            } else app.printString(text, x, y, 0, 0, 0, 255, 0.55f, 0, false);
        };
        static constexpr int speeds[] = {0x185, 0x186, 0x1ab, 0x187, 0x188};
        const auto text = [&](int key) {
            const auto* value = app.hdString(key);
            return value ? value->c_str() : "";
        };
        drawPadTexture(app, trace, 33, 0, 208, 443);
        label(356, 455, 0x183, rules.pointIndex + 1);
        drawPadTexture(app, trace, 33, 0, 208, 500);
        label(356, 512, 0x184, text(speeds[rules.speedIndex]));
        drawPadTexture(app, trace, 33, 0, 532, 251);
        label(680, 263, 0x189, rules.timeIndex + 1, text(rules.timeIndex == 0 ? 0x18a : 0x18b));
        drawPadTexture(app, trace, 33, 0, 532, 313);
        label(680, 325, 0x18c, text(rules.highMice ? 0x18d : 0x1ab));

        PaneRect items[37];
        layoutPad(items, false);
        for (int i = 0; i < 2; ++i) {
            const auto& button = items[35 + i];
            drawPadTexture(app, trace, 39, i, button.x, button.y);
            if (i == static_cast<int>(rules.split)) {
                const PaneRect border[] = {
                    {button.x - 9, button.y - 10, button.w + 18, 3},
                    {button.x + button.w + 7, button.y - 9, 3, button.h + 18},
                    {button.x - 9, button.y + button.h + 7, button.w + 18, 3},
                    {button.x - 10, button.y - 9, 3, button.h + 18},
                };
                for (const auto& r : border) {
                    if (trace) {
                        char line[100];
                        snprintf(line, sizeof line, "FR %d %d %d %d 192 35 35 255", r.x, r.y, r.w, r.h);
                        trace->push_back(line);
                    } else app.fillRect(r.x, r.y, r.w, r.h, 192, 35, 35, 255);
                }
            }
        }
        if (preview) preview({564, 367, 234, 188});
        for (int i = 0; i < 2; ++i)
            drawPadTexture(app, trace, 17, i, items[25 + i].x, items[25 + i].y);
    }
};

// ---------------------------------------------------------------- settings pane: CPU level list rows (HD 1.0 renderSettingsPane 0x2fa70, default scroll 0 = pane +0xab0): 'Level 1'..'Level 24' then 'Random'; text x 61, scale 0.75, y = 115 + 24 k (+ the scroll offset); 'Random' at y 691
struct SettingsLevelList {
    struct Row { std::string text; float x, y, scale; };
    static void rows(float scroll, std::vector<Row>& out) {
        out.clear(); for (int k = 0; k < 24; k++) out.push_back({"Level " + std::to_string(k + 1), 61.0f, 115.0f + 24.0f * k + scroll, 0.75f});
        out.push_back({"Random", 61.0f, 691.0f + scroll, 0.75f});
    }
};

// ---------------------------------------------------------------- settings pane: list panels (HD 1.0 renderSettingsPane; sub-rects of image 28 in its 1024 x 1024 texture, drawn 1:1; measured with the oracle probe, see docs/roadmap.md)
struct SettingsListScroll {   // handleSettingsPaneInput (0x32d24): drag moves the offset by the pointer's change and clamps it to [-(rows-1) * row, 0]; release snaps to a whole row (index = trunc with the threshold) and stores it; checked with tools/scroll_diff.py
    float offset = 0, row = 40, threshold = 0.5f; int rows = 10, selected = 0, lastY = -1; bool dragging = false;
    void press(int y) { dragging = false; lastY = -1; (void)y; }   // (the hit test of the items is separate)
    void move(int y) { if (lastY == -1 && !dragging) { lastY = y; dragging = true; } float dy = (float)(y - lastY); offset += dy; float lo = -((float)rows - 1.0f) * row; if (offset < lo) offset = lo; else if (offset > 0.0f) offset = 0.0f; lastY = y; }
    void release() {
        if (!dragging) return; dragging = false;
        int off = (int)offset, r = (int)row; int q = off / r, rem = off % r; if (rem < 0) rem = -rem; int idx = q < 0 ? -q : q;
        selected = ((float)rem < threshold) ? idx : idx + 1; offset = (float)(-selected * r);
    }
};

struct SettingsListFill {   // renderSettingsPane's _BHLib_RenderFilledRect(19, 63, 211, 128, 255, 255, 255, 255): an opaque white box behind the level list (checked in tools/fill_diff.py)
    static constexpr int x = 19, y = 63, w = 211, h = 128;
    static constexpr int r = 255, g = 255, bl = 255, a = 255;
};
struct SettingsListPanels {
    struct Draw { int sx, sy, sw, sh, x, y, w, h; };
    static void draws(Draw out[4]) {
        // source rects in the 1024 x 1024 texture of image 28 (uv x 1024), drawn 1:1 at the destination
        out[0] = {1, 1, 300, 186, 12, 57, 300, 186};      // A
        out[1] = {303, 1, 268, 201, 267, 137, 268, 201};  // B
        out[2] = {573, 1, 40, 108, 237, 135, 40, 108};    // C
        out[3] = {1, 1, 301, 39, 12, 205, 301, 39};       // D
    }
};

// ---------------------------------------------------------------- Help & Options, main list (HD 1.0 HelpOptionsScreen: initMainMenuItems 0x23c1c, render 0x24bdc / renderGenericMenuItems 0x229a8, handleInput 0x246c8, process 0x245b4)
struct OptionsMode : Screen {
    int phase = 0x11, sel = 0, chosen = -1, mascot = 0, sub = 0; double fade = 500000.0, t = 0; bool leave = false;   // sub: 0 main list, 2 language list (a28)
    static constexpr int N = 7; static constexpr int key[N] = {0x15c, 0x15d, 0x15e, 0x15f, 0x160, 0x161, 0x1d8};   // How to Play, Sounds, Language, iPod Music, Costumes, Credits, Game Center
    static constexpr int px[N] = {145, 225, 305, 385, 465, 545, 625}, py[N] = {173, 263, 353, 433, 523, 613, 630};   // table at 0xe786c (initLanguageMenuItems uses its first six rows)
    static bool ok(App& a) { return a.opBg.tex && a.opHdr.tex && a.mnBars.tex && a.mnMasc.tex && a.ssArrows.tex && a.hdFont1.tex; }
    bool shown(int i) const { return sub == 2 ? i < 6 : (i != 3 && i != 6); }   // iPod Music is iOS-only and Game Center is absent (AppData[5] == 0): not shown
    int back() const { return sub == 2 ? 6 : sub == 1 ? 2 : 7; }   // sound list: 0 music, 1 sfx, 2 back (the vibration row exists only when AppData[0x685] is set)
    int drag = -1; static constexpr int SX = 303, SY0 = 245, SPITCH = 45, SW = 234;
    int sliderX(App& a) { int w = 0; for (int i = 0; i < 2; i++) if (const std::string* s = a.hdString(0x164 + i)) w = std::max(w, a.hdTextWidth(*s, 0, 1.0f)); return SX + w; }   // initSoundMenuItems: item x = 303 + the widest label
    int music() override { return phase == 0x11 ? -1 : 5; }
    int hitTest(App& a, float lx, float ly) { if (sub == 1) { int sx = sliderX(a); for (int i = 0; i < 2; i++) if (sx <= lx && lx <= sx + SW && SY0 + SPITCH * i <= ly && ly <= SY0 + SPITCH * i + 40) return i; int bw = a.ssArrows.box[0].x, bh = a.ssArrows.box[0].y; if (0 <= lx && lx <= bw && 768 - bh <= ly && ly <= 768) return 2; return -1; }
        for (int i = 0; i < N; i++) if (shown(i)) { int w = a.mnBars.box[0].x, h = a.mnBars.box[0].y; if (px[i] <= lx && lx <= px[i] + w && py[i] <= ly && ly <= py[i] + h) return i; }
        int bw = a.ssArrows.box[0].x, bh = a.ssArrows.box[0].y; if (0 <= lx && lx <= bw && 768 - bh <= ly && ly <= 768) return back(); return -1; }
    void setVol(App& a, int which, float lx) { int v = (int)((lx - (float)sliderX(a)) * (255.0f / (float)SW)); v = std::max(0, std::min(255, v)); if (which == 0) a.musicVol = v; else a.sfxVol = v; }
    void event(App& a, const SDL_Event& e) override {
        if (phase == 0x12 && sub == 1 && (e.type == SDL_MOUSEMOTION || e.type == SDL_MOUSEBUTTONUP) && drag >= 0) {   // handleInput param_3 == 1 (move) and 2 (release)
            float lx, ly; SDL_RenderSetLogicalSize(a.ren, GW, GH); SDL_RenderWindowToLogical(a.ren, e.type == SDL_MOUSEMOTION ? e.motion.x : e.button.x, e.type == SDL_MOUSEMOTION ? e.motion.y : e.button.y, &lx, &ly);
            if (e.type == SDL_MOUSEMOTION) setVol(a, drag, lx); else { if (drag == 1 && hitTest(a, lx, ly) == 1) a.playSfx(1); a.saveOptions(); drag = -1; } return; }
        if (phase != 0x12 || e.type != SDL_MOUSEBUTTONDOWN || e.button.button != SDL_BUTTON_LEFT) return;
        if (sub == 1) {   // handleInput, state 1 (sounds)
            float lx, ly; SDL_RenderSetLogicalSize(a.ren, GW, GH); SDL_RenderWindowToLogical(a.ren, e.button.x, e.button.y, &lx, &ly); int hit = hitTest(a, lx, ly);
            if (hit == 0 || hit == 1) { drag = hit; setVol(a, hit, lx); a.saveOptions(); } else if (hit == 2) { a.playSfx(2); sub = 0; sel = 0; } return; }
        float lx, ly; SDL_RenderSetLogicalSize(a.ren, GW, GH); SDL_RenderWindowToLogical(a.ren, e.button.x, e.button.y, &lx, &ly); int hit = hitTest(a, lx, ly); if (hit < 0) return;
        int before = sel; if (hit != back()) sel = hit;
        if (before != hit && hit != back()) { a.playSfx(0); return; }
        if (sub == 2) {   // HelpOptionsScreen::handleLanguageMenuItemSelection 0x2437c: items 0..5 -> AppData::setLocale + reload the language textures, 6 = back to the main list
            a.playSfx(2); if (hit == back()) { sub = 0; sel = 0; return; }
            if (a.langAvailable(hit)) a.setLanguage(hit); else a.playSfx(0x13);   // selected locale files missing (including Japanese with the HD 1.0 assets)
            return; }
        if (hit == back()) { a.playSfx(2); chosen = 7; fade = 0; phase = 0x13; return; }
        if (hit == 0 && HelpMode::ok(a)) { a.playSfx(2); chosen = 0; fade = 0; phase = 0x13; return; }   // How to Play
        if (hit == 5 && CreditsMode::ok(a)) { a.playSfx(2); chosen = 5; fade = 0; phase = 0x13; return; }   // Credits
        if (hit == 1) { a.playSfx(2); sub = 1; drag = -1; return; }   // Sounds
        if (hit == 2) { a.playSfx(2); sub = 2; sel = a.lang; return; }   // Language
        a.playSfx(0x13); }   // Costumes is unfinished. How to Play and Credits also land here if their required assets are unavailable.
    // renderSoundMenuItems 0x22dcc (checked against the original with tools/oracle/hd_options_probe.py, tools/options_diff.py); log != nullptr records the calls instead of drawing
    void drawSounds(App& a, int music, int sfx, int dragState, std::vector<std::string>* log) {
        auto rt = [&](Sheet& sh, int fr, float x, float y, int w, int h, int srcw) { if (log) { char t[120]; snprintf(t, sizeof t, "RT %.1f %.1f %d %d %.1f", x, y, w, h, fr == 1 && &sh == &a.opSld ? 0.5f : 0.0f); log->push_back(t); return; }
            SDL_Rect s = sh.fr[fr]; if (srcw >= 0) s.w = srcw; SDL_Rect d{(int)x, (int)y, w, h}; SDL_RenderCopy(a.ren, sh.tex, &s, &d); };
        const int sx = sliderX(a); int vol[2] = {music, sfx};
        for (int i = 0; i < 2; i++) rt(a.opSnd, 0, 283, (float)(SY0 + SPITCH * i), 460, 38, -1);
        for (int i = 0; i < 2; i++) if (const std::string* s = a.hdString(0x164 + i)) { float y = (float)(SY0 + SPITCH * i) + ((float)40 - (float)a.hdFont.box[91].y) * 0.5f;
            if (log) { char t[200]; snprintf(t, sizeof t, "PS %s %.1f %.1f %.1f %d", s->c_str(), (float)sx, y, 1.0f, 2); log->push_back(t); } else a.printString(*s, (float)sx, y, 255, 255, 255, 255, 1.0f, 2, false); }
        for (int i = 0; i < 2; i++) { float y = (float)(SY0 + SPITCH * i + 7); int fw = (int)((float)vol[i] / 255.0f * (float)SW); rt(a.opSld, 0, (float)sx, y, SW, 23, -1); rt(a.opSld, 1, (float)sx, y, fw, 23, fw);
            if (dragState == i) { char tx[16]; snprintf(tx, sizeof tx, "%d%%", (int)((float)vol[i] / 255.0f * 100.0f)); int tw = a.hdTextWidth(tx, 0, 0.5f); float kx = (float)(sx + fw); float rx = kx - (float)tw * 0.5f;
                if (log) { char t[200]; snprintf(t, sizeof t, "FR %.1f %.1f %.1f %d", rx, y - 16, (float)tw + 2, 16); log->push_back(t); snprintf(t, sizeof t, "PS %s %.1f %.1f %.1f %d", tx, kx + 1, y - 16, 0.5f, 0); log->push_back(t); }
                else { SDL_SetRenderDrawBlendMode(a.ren, SDL_BLENDMODE_BLEND); SDL_SetRenderDrawColor(a.ren, 0, 0, 0, 192); SDL_Rect r{(int)rx, (int)(y - 16), tw + 2, 16}; SDL_RenderFillRect(a.ren, &r); a.printString(tx, kx + 1, y - 16, 255, 255, 255, 255, 0.5f, 0, false); } } }
        rt(a.ssArrows, 0, 0, (float)(768 - a.ssArrows.box[0].y), a.ssArrows.box[0].x, a.ssArrows.box[0].y, -1); }
    void tick(App& a) override {
        if (phase == 0x11) { fade -= 16384.0; if (fade <= 0) { fade = 0; phase = 0x12; } }
        else if (phase == 0x12) { t += 16384.0; if (t >= 166666.671875) { t -= 166666.671875; mascot = (mascot + 1) % 12; } }
        else if (phase == 0x13) { fade += 16384.0; if (fade >= 500000.0) { fade = 500000.0; leave = true; } } }
    const char* next() override { if (!leave) return nullptr; leave = false; return chosen == 5 ? "CREDITS" : chosen == 0 ? "HELP" : "MENU"; }
    void draw(App& a, float) override {
        SDL_RenderSetLogicalSize(a.ren, GW, GH); SDL_RenderSetViewport(a.ren, nullptr); SDL_SetRenderDrawColor(a.ren, 0, 0, 0, 255); SDL_RenderClear(a.ren);
        static const int tm[48] = {0,1,2,3,3,3,4,5,6,7,8,3,9,10,11,12,13,14,15,16,17,18,19,3,3,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,3,35,36,37,38,39,3,3};   // tilemap resource 0x125 (HD ccrpad rec 879)
        for (int r = 0; r < 6; r++) for (int c = 0; c < 8; c++) a.rtex(a.opBg, tm[r * 8 + c], (float)(c * 128), (float)(r * 128), 128, 128);
        a.rtex(a.opHdr, 0, 208, 50, a.opHdr.fr[0].w, a.opHdr.fr[0].h);
        if (sub == 1) { drawSounds(a, a.musicVol, a.sfxVol, drag, nullptr); if (phase != 0x12) { SDL_SetRenderDrawBlendMode(a.ren, SDL_BLENDMODE_BLEND); SDL_SetRenderDrawColor(a.ren, 0, 0, 0, (Uint8)(int)(fade / 500000.0 * 255.0)); SDL_Rect all{0, 0, GW, GH}; SDL_RenderFillRect(a.ren, &all); } return; }
        for (int i = 0; i < N; i++) { if (!shown(i)) continue; int w = a.mnBars.box[0].x, h = a.mnBars.box[0].y; a.rtex(a.mnBars, i == sel ? 1 : 0, (float)px[i], (float)py[i], w, h);
            if (sub == 2 && i == 5 && a.langJa.tex) { const SDL_Rect& f = a.langJa.fr[0]; const SDL_Point& o = a.langJa.off[0]; a.rtex(a.langJa, 0, (float)(px[i] + w / 2 + o.x), (float)(py[i] + h / 2 + o.y), f.w, f.h); }   // the Japanese label is an image
            else if (const std::string* s = a.hdString(sub == 2 ? 0x1cd + i : key[i])) { const float sc = 0.6667f; const float lh = (float)a.hdFont1.box[91].y * sc; a.printString(*s, (float)(px[i] + a.mnBars.box[0].x / 2), (float)py[i] + ((float)a.mnBars.box[0].y - lh) * 0.5f, 255, 255, 255, 255, sc, 0, false, 1); }
            if (i == sel) { const SDL_Rect& m = a.mnMasc.fr[mascot]; a.rtex(a.mnMasc, mascot, (float)(px[i] + 36 - m.w), (float)(py[i] + (a.mnBars.box[0].y - m.h) / 2), m.w, m.h); } }
        a.rtex(a.ssArrows, 0, 0, (float)(768 - a.ssArrows.box[0].y), a.ssArrows.box[0].x, a.ssArrows.box[0].y);
        if (phase != 0x12) { SDL_SetRenderDrawBlendMode(a.ren, SDL_BLENDMODE_BLEND); SDL_SetRenderDrawColor(a.ren, 0, 0, 0, (Uint8)(int)(fade / 500000.0 * 255.0)); SDL_Rect all{0, 0, GW, GH}; SDL_RenderFillRect(a.ren, &all); }
    }
};

// ---------------------------------------------------------------- main menu, iPad layout (HD 1.0 MenuScreen: init 0xfcb0, handleInput 0xf584, process 0xf410, render 0xf640)
struct HdMenuMode : Screen {
    int phase = 0xe, sel = 0, chosen = -1; double fade = 500000.0, t1 = 0, t2 = 0; int bubbleFrame = 0, mascot = 0, descKey = -1; bool leave = false;
    static constexpr int N = 5; static constexpr int lab[N] = {0x14d, 0x14e, 0x14f, 0x150, 0x151}, desc[N] = {0x152, 0x153, 0x154, 0x155, 0x156};   // label / description text keys (hdTextMap)
    static constexpr int px[N] = {184, 264, 344, 424, 504}, py[N] = {173, 263, 353, 433, 523};                                                       // table at 0xe6cb4
    static bool ok(App& a) { return a.mnBg.tex && a.mnBars.tex && a.mnMasc.tex && a.mnDeco.tex && a.hdBub9.tex && a.hdFont1.tex && a.hdFont.tex; }
    int music() override { return phase == 0xe ? -1 : 0; }
    bool tutorialCleared() { return true; }   // VMU::isTutorialCleared: The Basics (the tutorial) is not ported, so the gate on Puzzle / Challenge / Battle is open (unlock-all)
    void event(App& a, const SDL_Event& e) override {
        if (phase != 0xf) return; int hit = -1;
        if (e.type == SDL_MOUSEBUTTONDOWN && e.button.button == SDL_BUTTON_LEFT) {
            float lx, ly; SDL_RenderSetLogicalSize(a.ren, GW, GH); SDL_RenderWindowToLogical(a.ren, e.button.x, e.button.y, &lx, &ly);
            for (int i = 0; i < N && hit < 0; i++) { int w = a.mnBars.box[0].x, h = a.mnBars.box[0].y; if (px[i] <= lx && lx <= px[i] + w && py[i] <= ly && ly <= py[i] + h) hit = i; }   // inclusive rects, first match
            if (hit < 0) return; int before = sel; sel = hit;
            if (before == hit) act(a, hit); else a.playSfx(0); }
        else if (e.type == SDL_KEYDOWN) { SDL_Keycode k = e.key.keysym.sym; if (k == SDLK_DOWN) { sel = (sel + 1) % N; a.playSfx(0); } else if (k == SDLK_UP) { sel = (sel + N - 1) % N; a.playSfx(0); } else if (k == SDLK_RETURN || k == SDLK_SPACE) act(a, sel); } }
    void act(App& a, int i) {
        if (!tutorialCleared() && i >= 1 && i <= 3) { a.playSfx(3); return; }
        if (i == 0 || i == 2 || (i == 4 && !OptionsMode::ok(a))) { a.playSfx(0x13); return; }   // The Basics and Stage Challenge are not ported yet (docs/roadmap.md)
        a.playSfx(2); chosen = i; fade = 0; phase = 0x10; }
    void tick(App& a) override {
        if (phase == 0xe) { fade -= 16384.0; if (fade <= 0) { fade = 0; phase = 0xf; } }
        else if (phase == 0xf) { t1 += 16384.0; if (t1 >= 500000.0) { t1 -= 500000.0; bubbleFrame = (bubbleFrame + 1) & 1; } t2 += 16384.0; if (t2 >= 166666.671875) { t2 -= 166666.671875; mascot = (mascot + 1) % 12; } }
        else if (phase == 0x10) { fade += 16384.0; if (fade >= 500000.0) { fade = 500000.0; leave = true; } } }
    const char* next() override { if (!leave) return nullptr; leave = false; static const char* to[N] = {nullptr, "STAGES", nullptr, "BATTLE", "OPTIONS"}; return to[chosen]; }
    void draw(App& a, float) override {
        SDL_RenderSetLogicalSize(a.ren, GW, GH); SDL_RenderSetViewport(a.ren, nullptr); SDL_SetRenderDrawColor(a.ren, 0, 0, 0, 255); SDL_RenderClear(a.ren);
        static const int tm[48] = {0,1,2,3,0,0,0,4,5,6,7,8,9,10,11,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,28,28,29,30,31,32,33,34,35,34,34,36,37,38,39};   // tilemap resource 0x124 (HD ccrpad rec 878)
        for (int r = 0; r < 6; r++) for (int c = 0; c < 8; c++) a.rtex(a.mnBg, tm[r * 8 + c], (float)(c * 128), (float)(r * 128), 128, 128);
        descKey = desc[sel];
        a.rtex(a.mnDeco, 0, 208, 50, a.mnDeco.fr[0].w, a.mnDeco.fr[0].h);
        if (descKey >= 0) if (const std::string* d = a.hdString(descKey)) a.drawBubble(792, 367, 350, *d, 1, bubbleFrame, 255);
        if (const std::string* d = a.hdString(0x15b)) a.drawBubble(156, 714, 240, *d, 4, 0, 255);   // "Enjoy ChuChu Rocket!"
        for (int i = 0; i < N; i++) { int w = a.mnBars.box[0].x, h = a.mnBars.box[0].y; int alpha = (!tutorialCleared() && i >= 1 && i <= 3) ? 0x80 : 0xff;
            SDL_SetTextureAlphaMod(a.mnBars.tex, (Uint8)alpha); a.rtex(a.mnBars, i == sel ? 1 : 0, (float)px[i], (float)py[i], w, h); SDL_SetTextureAlphaMod(a.mnBars.tex, 255);
            if (const std::string* t = a.hdString(lab[i])) { const float sc = 0.6667f; const float lh = (float)a.hdFont1.box[91].y * sc; a.printString(*t, (float)(px[i] + a.mnBars.box[0].x / 2), (float)py[i] + ((float)a.mnBars.box[0].y - lh) * 0.5f, 255, 255, 255, alpha, sc, 0, false, 1); }
            if (i == sel) { const SDL_Rect& m = a.mnMasc.fr[mascot]; a.rtex(a.mnMasc, mascot, (float)(px[i] + 36 - m.w), (float)(py[i] + (a.mnBars.box[0].y - m.h) / 2), m.w, m.h); descKey = desc[i]; } }
        if (phase == 0xe || phase == 0x10) { SDL_SetRenderDrawBlendMode(a.ren, SDL_BLENDMODE_BLEND); SDL_SetRenderDrawColor(a.ren, 0, 0, 0, (Uint8)(int)(fade / 500000.0 * 255.0)); SDL_Rect all{0, 0, GW, GH}; SDL_RenderFillRect(a.ren, &all); }
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
    void choose(App& a) { if (sel == 1) chosen = "STAGES"; else if (sel == 3) chosen = "BATTLE"; else a.playSfx(0x13); }
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

// Touch/mouse arrow gesture of the mobile versions (Android Input::setArrowOrigin / getArrowType, read 2026-11-13/14): press on a cell sets the origin, release decides the arrow from the drag vector:
// if the squared drag distance (touch pixels) exceeds 0.25 x the float at screen-struct +0x28 (a view scale, whose value was not read; >= 1 on any device, so the threshold is about one pixel),
// |dx| > |dy| -> east (release right of the origin) or west, otherwise south (release below) or north; no movement = no arrow (puzzle: the tap deletes an arrow already on the cell).
// The port measures the distance in window pixels and uses the scale 1.0 (unverified).
struct DragGesture {
    bool on = false; int cx = -1, cy = -1; float x0 = 0, y0 = 0; int wx0 = 0, wy0 = 0;
    bool begin(App& a, const SDL_Event& e) { float lx, ly; SDL_RenderSetLogicalSize(a.ren, GW, GH); SDL_RenderWindowToLogical(a.ren, e.button.x, e.button.y, &lx, &ly); lx -= OX; ly -= OY; int c = (int)std::floor(lx / CELL), r = (int)std::floor(ly / CELL); on = c >= 0 && c < 12 && r >= 0 && r < 9; cx = c; cy = r; x0 = lx; y0 = ly; wx0 = e.button.x; wy0 = e.button.y; return on; }
    // returns the direction (0 south, 1 west, 2 north, 3 east) or -1 for a tap
    int end(App& a, const SDL_Event& e) { on = false; float lx, ly; SDL_RenderSetLogicalSize(a.ren, GW, GH); SDL_RenderWindowToLogical(a.ren, e.button.x, e.button.y, &lx, &ly); lx -= OX; ly -= OY; float dx = lx - x0, dy = ly - y0; float wdx = (float)(e.button.x - wx0), wdy = (float)(e.button.y - wy0); if (wdx * wdx + wdy * wdy <= 0.25f) return -1; if (std::fabs(dy) < std::fabs(dx)) return dx > 0 ? 3 : 1; return dy > 0 ? 0 : 2; }
};

// ---------------------------------------------------------------- puzzle
struct PuzzleMode : Screen {
    Stages stages; int cur = 0; Sim sim; std::vector<std::pair<float, float>> prev; bool running = false; int state = 0;   // 0 planning, 1 running, 2 clear, 3 miss
    int stock[4] = {0, 0, 0, 0}; int totalMice = 0; bool back = false; DragGesture drag; int curX = 5, curY = 4; SDL_GameController* pad = nullptr;
    void putAt(int cx, int cy, int d) { sim.removeArrow(cx, cy); if (d >= 0 && used(d) < stock[d]) sim.placeArrow(cx, cy, d); }   // AR_PutArrowPzSp: an arrow already there is deleted first; a direction without stock places nothing
    int music() override { return 9; }   // PuzzleInit: BGM_Play(0xd) = song 9
    bool load(const std::string& root, int stage) { if (!loadStageSet(root, gApp ? gApp->stageSet : 0, stages)) return false; cur = stage % (int)stages.list.size(); reset(); return true; }
    bool dash = false; bool paused = false, pconf = false;   // PA_IsPaused and PuzzleGameScreen[0xa21] (the pause dialog's second state)
    void restartRun() { std::vector<Arrow> keep; for (auto& ar : sim.arrows) if (ar.live) keep.push_back(ar); reset(); for (auto& ar : keep) sim.placeArrow(ar.x, ar.y, ar.dir); }
    void reset() {
        sim.load(stages.list[cur].st); prev.clear(); dash = false; if (gApp) gApp->angs.clear(); running = false; state = 0; totalMice = 0;
        for (auto& e : sim.ents) if (e.mouse) totalMice++;
        for (int d = 0; d < 4; d++) stock[d] = 0;
        for (auto& s : stages.list[cur].sol) stock[s[2] & 3]++;       // arrow stock from the reference solution (stage struct counts not exported yet)
    }
    int used(int d) const { int n = 0; for (auto& a : sim.arrows) if (a.live && a.dir == d) n++; return n; }
    void event(App& a, const SDL_Event& e) override {
        if (e.type == SDL_KEYDOWN) { SDL_Keycode k = e.key.keysym.sym;
            if (k == SDLK_SPACE) { if (state == 0) { state = 1; running = true; } else if (state == 2) { cur = (cur + 1) % (int)stages.list.size(); reset(); }   /* a cleared stage leads to the next one */
                else if (state >= 3) reset(); }
            else if (k == SDLK_r) reset(); else if (k == SDLK_ESCAPE) back = true;
            else if (k == SDLK_RIGHTBRACKET) { cur = (cur + 1) % (int)stages.list.size(); reset(); } else if (k == SDLK_LEFTBRACKET) { cur = (cur + (int)stages.list.size() - 1) % (int)stages.list.size(); reset(); }
            else if (state == 0) { if (k == SDLK_UP) curY = std::max(0, curY - 1); else if (k == SDLK_DOWN) curY = std::min(8, curY + 1); else if (k == SDLK_LEFT) curX = std::max(0, curX - 1); else if (k == SDLK_RIGHT) curX = std::min(11, curX + 1);   // keyboard: arrows move the cursor, W/A/S/D place up/left/down/right (the pad's face buttons)
                else if (k == SDLK_w) putAt(curX, curY, 2); else if (k == SDLK_s) putAt(curX, curY, 0); else if (k == SDLK_a) putAt(curX, curY, 1); else if (k == SDLK_d) putAt(curX, curY, 3); } }
        else if (e.type == SDL_MOUSEBUTTONDOWN && e.button.button == SDL_BUTTON_LEFT && hudButton(a, e)) {}   // HD 1.0 PuzzleGameScreen::handleInput: rect 3 Start (flag 1), rect 4 Cancel (flag 2)
        else if (e.type == SDL_MOUSEBUTTONDOWN && state == 0 && e.button.button == SDL_BUTTON_LEFT) drag.begin(a, e);
        else if (e.type == SDL_MOUSEBUTTONUP && state == 0 && e.button.button == SDL_BUTTON_LEFT && drag.on) { int cx = drag.cx, cy = drag.cy; int d = drag.end(a, e); putAt(cx, cy, d); }   // a tap (d = -1) deletes the arrow on the cell
        else if (e.type == SDL_CONTROLLERDEVICEADDED && !pad) pad = SDL_GameControllerOpen(e.cdevice.which);
        else if (e.type == SDL_CONTROLLERBUTTONDOWN && state == 0) { int b = e.cbutton.button;   // Dreamcast-style pad: D-pad moves the cursor, Y/A/X/B place up/down/left/right, Start runs
            if (b == SDL_CONTROLLER_BUTTON_DPAD_UP) curY = std::max(0, curY - 1); else if (b == SDL_CONTROLLER_BUTTON_DPAD_DOWN) curY = std::min(8, curY + 1); else if (b == SDL_CONTROLLER_BUTTON_DPAD_LEFT) curX = std::max(0, curX - 1); else if (b == SDL_CONTROLLER_BUTTON_DPAD_RIGHT) curX = std::min(11, curX + 1);
            else if (b == SDL_CONTROLLER_BUTTON_Y) putAt(curX, curY, 2); else if (b == SDL_CONTROLLER_BUTTON_A) putAt(curX, curY, 0); else if (b == SDL_CONTROLLER_BUTTON_X) putAt(curX, curY, 1); else if (b == SDL_CONTROLLER_BUTTON_B) putAt(curX, curY, 3);
            else if (b == SDL_CONTROLLER_BUTTON_START) { state = 1; running = true; } }
    }
    // Touch rects of the puzzle screen (HD 1.0 PuzzleGameScreen::process 0x12994 -> Input::addRect(i, x0, y0, x1, y1) from layout +0x4d0 + 16 i): rect 3 (18, 88)-(160, 190) Start/Dash, rect 4 (21, 229)-(159, 275) Cancel.
    // In the placing mode, rect 3 sets input flag 1 (start) and rect 4 flag 2 (Cancel). Effects read from Android PuzzleLoop (0x33bbc): placing: flag 1 = start, flag 2 = delete all arrows; running: flag 1 = Dash, flag 2 = restart with the arrows kept.
    bool hudButton(App& a, const SDL_Event& e) {
        float lx, ly; SDL_RenderSetLogicalSize(a.ren, GW, GH); SDL_RenderWindowToLogical(a.ren, e.button.x, e.button.y, &lx, &ly);
        auto in = [&](float x0, float y0, float x1, float y1) { return lx >= x0 && lx < x1 && ly >= y0 && ly < y1; };
        if (paused) {   // PuzzleGameScreen::handleInput while PA_IsPaused (0x1299c..): rects 1 (128, 313)-(403, 413) and 2 (590, 314)-(881, 414), transcribed literally
            if (in(128, 313, 403, 413)) { if (!pconf) { pconf = true; a.playSfx(0); } else { a.playSfx(2); paused = false; } }
            if (in(590, 314, 881, 414)) { if (!pconf) { a.playSfx(2); paused = false; back = true; } else { pconf = false; a.playSfx(0); } }   // Input::setData(10, 1) = leave the screen; BGM_Release (not read yet) not reproduced
            return true; }
        if (in(10, 669, 173, 711)) { paused = true; a.playSfx(4); return true; }   // rect 0 = the pause button: Input::setData(0xb, 1) -> PA_PauseController, sound 4 (BGM_Pause not reproduced)
        if (in(18, 88, 160, 190)) { if (state == 0) { state = 1; running = true; dash = false; a.playSfx(2); } else if (running && !dash) { dash = true; a.playSfx(0xc); } return true; }   // PuzzleLoop: placing -> start (sound 2); running -> Dash (sound 0xc, two simulation steps per frame)
        if (in(21, 229, 159, 275)) { if (state == 0) { std::vector<std::pair<int,int>> cells; for (auto& ar : sim.arrows) if (ar.live) cells.push_back({ar.x, ar.y}); for (auto& c : cells) sim.removeArrow(c.first, c.second); }   // placing: AR_DeleteArrowPz (all arrows removed)
                                     else if (running) { a.playSfx(3); restartRun(); } return true; }   // running: sound 3, the stage restarts with the arrows kept (phase 1: AR_RestartArrowPzManager)
        return false;
    }
    int cticks = 0;
    void tick(App& a) override {
        if (paused) return; cticks++;
        for (size_t i = 0; i < sim.ents.size() && i < prev.size(); i++) prev[i] = {sim.ents[i].x, sim.ents[i].z};
        if (!running) return;
        sim.tick(); a.stepAngles(sim);
        if (dash) { sim.tick(); a.stepAngles(sim); }   // Dash: PuzzleLoop runs SmpColLoopInit/SmpTskExeServer/SmpColAnalyze twice per frame
        int alive = 0; for (auto& e : sim.ents) if (e.mouse && e.alive && !e.done) alive++;
        if (sim.killed > 0) { state = 3; running = false; } else if (alive == 0 && sim.saved == totalMice) { state = 2; running = false; if (gApp && gApp->stageSet == 0) gApp->setCleared(cur); }
    }
    const char* next() override { if (back) { back = false; if (gApp) gApp->nextStage = cur; return "STAGES"; } return nullptr; }
    void draw(App& a, float alpha) override {
        SDL_RenderSetLogicalSize(a.ren, GW, GH); SDL_RenderSetViewport(a.ren, nullptr); SDL_SetRenderDrawColor(a.ren, 24, 24, 40, 255); SDL_RenderClear(a.ren); { SDL_Rect vp{OX, OY, GW - OX, GH - OY}; SDL_RenderSetViewport(a.ren, &vp); }   // field coordinates start at (OX, OY)
        { const int set = gApp ? gApp->stageSet : 0; a.board(stages.list[cur].st, set == 1 ? 1 : (cur & 3) + 2, set == 1 ? 1 : 2); }   // puzzle colours (createPlayfieldPreview): floor (level & 3) + 2, wall 2; the extra levels (type 200) floor 1, wall 1
        a.rockets(sim, nullptr);
        for (auto& ar : sim.arrows) if (ar.live) a.arrow(ar.x, ar.y, ar.dir, 0, ar.hits);
        a.entities(sim, prev, running ? alpha : 1.0f);
        if (state == 0) a.cursor(curX, curY, 0, cticks, (sim.coll[curY][curX] & 0xF00) != 0);
        SDL_RenderSetViewport(a.ren, nullptr);   // puzzle HUD (HD 1.0 renderPuzzleHudiPad 0x137c4): image 0x5c frame 2 at (origin + 40, 690), frame 3 ten times every 64, frame 4;
        { int n = cur % 25 + 1; a.blit(a.hdPhud, 1, 90.0f, 520.0f, 1.3f); a.blit(a.hdStageNum, n / 10, 70.0f, 584.0f, 1.3f); a.blit(a.hdStageNum, n % 10, 120.0f, 584.0f, 1.3f); }   // renderPuzzleHudiPad: "stage" label (0x5c frame 1) at (90, 520) and the number (image 0x84, (stage mod 25) + 1, tens at (70, 584), ones at (120, 584)), all at scale 1.3; the stage-name frame and text are not drawn yet
        a.blit(a.hdPhud, 0, 85.0f, 190.0f);   // renderHudLeft (0x11e18): image 0x5c frame 0 (Start/Dash, Cancel panel) at layout (+0x64, +0x68) = (85, 190); its glow highlights (image 0x9d frames 4/5/6) and button hit rects are not done yet
        { float x = (float)OX + 40.0f; a.blit(a.hdPhud, 2, x, 690.0f); for (int k = 0; k < 10; k++) { x += 64.0f; a.blit(a.hdPhud, 3, x, 690.0f); } x += 64.0f; a.blit(a.hdPhud, 4, x, 690.0f); }
        // then the remaining arrows: AR_GetArrowdataPuzzle order east, west, north, south (rotations 4, 12, 0, 8 in 1/16 turns), image 0x54 frame 0 at scale 0.6, x from origin + 64 in steps of 60, y 706
        { static const int ord[4] = {3, 1, 2, 0}; static const int rot16[4] = {4, 12, 0, 8}; float x = (float)OX + 64.0f;
          for (int k = 0; k < 4; k++) { int d = ord[k]; for (int n = 0; n < stock[d] - used(d); n++) { a.blit(a.arw, 0, x, 706.0f, 0.6f, rot16[k] * 22.5); x += 60.0f; } } }
        a.drawFrame5(90, 410, 180); a.drawFrame5(720, 650, 440);   // name frames (renderPuzzleHudiPad: drawFrame(5, 90, 410, 180) for the level name, drawFrame(5, 720, 650, 440) for the stage name); the text itself (printString, original font) is not drawn yet
        if (!(gApp && gApp->stageSet != 0) && cur < 100) {   // printString(level name, 90, 410, black, scale 0.8, centred, v-centred) and printString(stage comment, 720, 650, scale 1.0); the y offset +10 applies only when AppData+0x664 == 5 (UTF-16 language branch). Texts T[0x1ab + (stage/25 <= 3 ? stage/25 : 0)] (getPuzzleType) and T[0x1e8 + stage] (FI_GetCommentStrP)
            const std::string* lv = a.hdString(0x1ab + (cur / 25 <= 3 ? cur / 25 : 0)); if (lv) a.printString(*lv, 90.0f, 410.0f, 0, 0, 0, 255, 0.8f, 0, true);
            const std::string* nm = a.hdString(0x1e8 + cur); if (nm) a.printString(*nm, 720.0f, 650.0f, 0, 0, 0, 255, 1.0f, 0, true); }
        a.blit(a.hdHud68, 5, 92.0f, 690.0f);   // end of renderPuzzleHudiPad: drawImage(0x68, 5, 92, 690) = the pause button (rect 0)
        if (paused) {   // PuzzleGameScreen::render pause branch (0x13620): black rect alpha getAlphaRect() = 0xc0, drawPauseBanner(512, 400, [0xa21]) (0x1b63c), name frame drawFrame(5, 512, 50, 320), name text at (512, 50) scale 0.8
            SDL_SetRenderDrawBlendMode(a.ren, SDL_BLENDMODE_BLEND); SDL_SetRenderDrawColor(a.ren, 0, 0, 0, 0xc0); SDL_Rect all{0, 0, GW, GH}; SDL_RenderFillRect(a.ren, &all);
            const float bx = 512.0f, by = 400.0f, sc = 2.0f;   // layout +0x520 = 400, +0x568 = 2.0
            a.blitFlip(a.hdPause, 0, bx, by, sc, false); a.blitFlip(a.hdPause, 1, bx - 10.0f, by - 2.0f, sc, pconf);
            if (pconf) { a.blitFlip(a.hdPause, 3, bx - 226.0f, by - 32.0f, sc, false); a.blitFlip(a.hdPause, 2, bx + 206.0f, by - 32.0f, sc, true); }
            else { a.blitFlip(a.hdPause, 2, bx - 226.0f, by - 32.0f, sc, false); a.blitFlip(a.hdPause, 3, bx + 206.0f, by - 32.0f, sc, true); }
            const std::string* t1 = a.hdString(0x1a9); const std::string* t2 = a.hdString(0x1aa);   // 'Resume', 'Quit'; y offset +10 because the device class is > 10 (CoreSettingsInit sets the global 0x172c10 = 1)
            if (t1) a.printString(*t1, bx - 252.0f, by - 40.0f + 10.0f, 255, 255, 255, 255, 1.6f, 0, true);
            if (t2) a.printString(*t2, bx + 238.0f, by - 40.0f + 10.0f, 255, 255, 255, 255, 1.6f, 0, true);
            a.drawFrame5(512, 50, 320);
            if (!(gApp && gApp->stageSet != 0) && cur < 100) { const std::string* nm = a.hdString(0x1e8 + cur); if (nm) a.printString(*nm, 512.0f, 50.0f, 0, 0, 0, 255, 0.8f, 0, true); } }
        SDL_RenderSetViewport(a.ren, nullptr);
    }
};

// ---------------------------------------------------------------- stage select (functional; the original's layout/art is not reproduced yet: docs/known_gaps.md)
struct StageSelectMode : Screen {
    Stages stages; int cur = 0, page = 0; bool go = false, back = false; static constexpr int COLS = 5, ROWS = 4, PER = COLS * ROWS;
    int music() override { return orig() ? (phase == 0x20 ? -1 : 5) : 0; }
    std::string rootDir; bool load(const std::string& root, int start) { rootDir = root; if (!loadStageSet(root, gApp ? gApp->stageSet : 0, stages)) return false; cur = start % (int)stages.list.size(); page = cur / PER; selPage = cur / 25; sel = cur % 25; lastItem = sel; return true; }
    // ---- the original iPad layout (HD 1.0 StageSelectScreen 0x10b54 grid branch, device class > 10), used for the 100 original puzzles; other stage sets keep the plain list below
    int phase = 0x20, selPage = 0, sel = 0, lastItem = 0, chosen = 0, prevKey = -1; double timer = 500000.0; bool leave = false, leaveBack = false;
    bool orig() { return gApp && gApp->stageSet == 0 && gApp->ssBg.tex && gApp->ssCells.tex && gApp->hdFont1.tex && gApp->ssArrows.tex && gApp->ssPanel.tex && gApp->ssTab.tex && gApp->ssHdr.tex && gApp->ssBubble.tex && stages.list.size() >= 100; }
    struct Item { int x, y, w, h; };
    Item item(App& a, int i) { if (i < 25) return {228 + 54 * (i % 5), 259 + 34 * (i / 5), 46, 30}; if (i == 25) return {208, 444, 40, 40}; if (i == 26) return {468, 444, 40, 40}; return {0, 768 - a.ssArrows.box[0].y, a.ssArrows.box[0].x, a.ssArrows.box[0].y}; }   // MenuItems 0..0x1b from StageSelectScreen::init
    void preview(App& a) {   // Render::createPlayfieldPreview(3, stage, 0x94): the field (floor colour (stage / 25 & 3) + 2, wall colour 2) at (32, 32) in an 832 x 640 texture
        int s = selPage * 25 + sel; if (s == prevKey && a.ssPrev) return; prevKey = s;
        if (!a.ssPrev) { a.ssPrev = SDL_CreateTexture(a.ren, SDL_PIXELFORMAT_ABGR8888, SDL_TEXTUREACCESS_TARGET, 832, 640); SDL_SetTextureBlendMode(a.ssPrev, SDL_BLENDMODE_BLEND); }
        SDL_SetRenderTarget(a.ren, a.ssPrev); SDL_SetRenderDrawColor(a.ren, 0, 0, 0, 0); SDL_RenderClear(a.ren); SDL_Rect vp{32, 32, 800, 608}; SDL_RenderSetViewport(a.ren, &vp);
        a.board(stages.list[s].st, ((s / 25) & 3) + 2, 2); SDL_RenderSetViewport(a.ren, nullptr); SDL_SetRenderTarget(a.ren, nullptr);
    }
    void origEvent(App& a, const SDL_Event& e) {
        if (e.type != SDL_MOUSEBUTTONDOWN || e.button.button != SDL_BUTTON_LEFT || phase != 0x21) return;   // handleInput works only in state 0x21
        float lx, ly; SDL_RenderSetLogicalSize(a.ren, GW, GH); SDL_RenderWindowToLogical(a.ren, e.button.x, e.button.y, &lx, &ly); int px = (int)lx, py = (int)ly;
        int hit = -1; for (int i = 0; i < 28 && hit < 0; i++) { Item t = item(a, i); if (t.x <= px && px <= t.x + t.w && t.y <= py && py <= t.y + t.h) hit = i; }   // AppScreen::updateMenuItemFromTouchEvent: inclusive rects, first match
        int before = lastItem; if (hit >= 0) lastItem = hit;
        auto startStage = [&](int it) { a.playSfx(2); chosen = it; timer = 0; phase = 0x22; leaveBack = false; };
        if (hit < 0) { if (px >= 564 && px <= 798 && py >= 367 && py <= 555) startStage(before); return; }   // the preview rect (this+0xa7c..0xa88)
        if (hit == 25) { selPage--; if (selPage < 0) { selPage = 0; a.playSfx(0x13); } else a.playSfx(1); preview(a); return; }
        if (hit == 26) { if (selPage < 3 && selPage + 1 <= a.maxStage()) { selPage++; preview(a); a.playSfx(1); } else a.playSfx(0x13); return; }
        if (hit == 27) { a.playSfx(3); chosen = 27; leaveBack = true; timer = 0; phase = 0x22; return; }
        if (before != hit) { a.playSfx(0); sel = hit; preview(a); } else startStage(hit);
    }
    void origTick(App& a) {
        if (phase == 0x20) { timer -= 16384.0; if (timer <= 0) { timer = 0; phase = 0x21; } }   // StageSelectScreen::process: fade in 0.5 s (the song 5 starts here)
        else if (phase == 0x22) { timer += 16384.0; if (timer >= 500000.0) { timer = 500000.0; leave = true; } }
    }
    void origDraw(App& a) {
        SDL_RenderSetLogicalSize(a.ren, GW, GH); SDL_RenderSetViewport(a.ren, nullptr); if (!a.uiLog) preview(a); SDL_SetRenderDrawColor(a.ren, 0, 0, 0, 255); SDL_RenderClear(a.ren);
        static const int tm[48] = {0,1,2,3,4,4,4,4,5,6,7,8,9,10,4,4,11,12,4,4,13,14,4,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,4,4,4,33,34,35,36};   // tilemap resource 0x126 (HD ccrpad rec 880): 8 x 6 tiles of 128 px
        for (int r = 0; r < 6; r++) for (int c = 0; c < 8; c++) a.rtex(a.ssBg, tm[r * 8 + c], (float)(c * 128), (float)(r * 128), 128, 128);
        a.rtexBox(a.ssHdr, 0, 208, 50);   // slot 0x454 frame a20 (0 = Puzzle)
        a.rtex(a.ssPanel, 0, 208, 247, a.ssPanel.sz[0].x, a.ssPanel.sz[0].y); a.rtex(a.ssPanel, 1, 548, 361, a.ssPanel.sz[1].x, a.ssPanel.sz[1].y); a.rtex(a.ssPanel, 2, 508, 351, a.ssPanel.sz[2].x, a.ssPanel.sz[2].y);
        for (int i = 0; i < 25; i++) { Item t = item(a, i); a.rtexBox(a.ssCells, i == sel ? 1 : 0, (float)t.x, (float)t.y);
            char nb[16]; snprintf(nb, sizeof nb, "%d", i + 1); a.printString(nb, (float)(t.x + (a.ssCells.box[0].x) / 2), (float)t.y + 1.0f, 255, 255, 255, 255, 0.45f, 0, false, 1);
            if (a.isCleared(selPage * 25 + i)) a.rtexBox(a.ssCells, 4, (float)(t.x + (a.ssCells.box[0].x - 2) / 2 - (a.ssCells.box[4].x - 2) / 2), (float)(t.y + (a.ssCells.box[0].y - 2) / 2 - (a.ssCells.box[4].y - 2) / 2)); }
        a.rtexBox(a.ssTab, 0, 208, 443); { int l = selPage + 1; a.rtexBox(a.ssTab, l, (float)(208 + (a.ssTab.box[0].x - 2) / 2 - (a.ssTab.box[l].x - 2) / 2), (float)(443 + (a.ssTab.box[0].y - 2) / 2 - (a.ssTab.box[l].y - 2) / 2)); }
        a.rtexBox(a.ssBubble, 0, 548, 292);
        if (const std::string* nm = a.hdString(0x1e8 + sel + selPage * 25)) a.printString(*nm, 682.0f, 299.0f, 0, 0, 0, 255, 0.45f, 0, false, 1);
        if (a.uiLog) a.logRT(564, 367, 234, 188); else if (a.ssPrev) { SDL_Rect d{564, 367, 234, 188}; SDL_RenderCopy(a.ren, a.ssPrev, nullptr, &d); }
        a.rtex(a.ssArrows, 0, 0, (float)(768 - a.ssArrows.box[0].y), a.ssArrows.box[0].x, a.ssArrows.box[0].y);
        if (timer > 0) a.fillRect(0, 0, GW, GH, 0, 0, 0, (int)(timer / 500000.0 * 255.0));
    }
    void event(App& a, const SDL_Event& e) override {
        if (orig()) { origEvent(a, e); return; }
        if (e.type != SDL_KEYDOWN) return; int n = (int)stages.list.size(); SDL_Keycode k = e.key.keysym.sym;
        if (k == SDLK_RIGHT) cur = (cur + 1) % n; else if (k == SDLK_LEFT) cur = (cur + n - 1) % n;
        else if (k == SDLK_DOWN) cur = std::min(n - 1, cur + COLS); else if (k == SDLK_UP) cur = std::max(0, cur - COLS);
        else if (k == SDLK_PAGEDOWN) cur = std::min(n - 1, cur + PER); else if (k == SDLK_PAGEUP) cur = std::max(0, cur - PER);
        else if (k == SDLK_TAB && gApp) { gApp->stageSet = (gApp->stageSet + 1) % kStageSets; stages = Stages(); load(rootDir, 0); }
        else if (k == SDLK_RETURN || k == SDLK_SPACE) go = true; else if (k == SDLK_ESCAPE) back = true;
        page = cur / PER;
    }
    void tick(App& a) override { if (orig()) origTick(a); }
    const char* next() override { if (orig()) { if (!leave) return nullptr; leave = false; if (leaveBack) return "MENU"; int s = std::max(0, std::min(99, chosen + selPage * 25)); if (gApp) gApp->nextStage = s; return "PUZZLE"; } if (back) { back = false; return "MENU"; } if (go) { go = false; if (gApp) gApp->nextStage = cur; return "PUZZLE"; } return nullptr; }
    void draw(App& a, float) override {
        if (orig()) { origDraw(a); return; }
        SDL_SetRenderDrawColor(a.ren, 24, 24, 40, 255); SDL_RenderClear(a.ren);
        a.text(gApp && gApp->stageSet == 2 ? "PUZZLE  DREAMCAST EXPRESS" : gApp && gApp->stageSet ? "PUZZLE  MORE STAGES" : "PUZZLE  STAGE SELECT", 24, 14, 34);
        const int cw = 140, ch = 78, x0 = (W - COLS * cw) / 2, y0 = 80;
        for (int i = 0; i < PER; i++) { int idx = page * PER + i; if (idx >= (int)stages.list.size()) break;
            SDL_Rect r{x0 + (i % COLS) * cw + 4, y0 + (i / COLS) * ch + 4, cw - 8, ch - 8}; bool sel = idx == cur;
            SDL_SetRenderDrawColor(a.ren, sel ? 250 : 40, sel ? 160 : 40, sel ? 30 : 90, 255); SDL_RenderFillRect(a.ren, &r);
            a.number(idx + 1, r.x + 14, r.y + 14, 40); }
        const auto& e = stages.list[cur]; std::string t = e.title; a.text(t, 24, y0 + ROWS * ch + 20, 30);
        std::string hint = "ARROWS CHOOSE  ENTER PLAY  TAB SET  ESC BACK"; a.text(hint, 24, H - 50, 22);
        std::string pg = std::to_string(page + 1) + "/" + std::to_string(((int)stages.list.size() + PER - 1) / PER); a.text(pg, W - a.textWidth(pg, 26) - 24, 14, 26);
    }
};

// ---------------------------------------------------------------- battle
struct BattleMode : Screen {
    Stages stages; int cur = 0; uint32_t seed = 1; int lv[4] = {-1, 3, 3, 3}; BattleGame game; std::vector<std::pair<float, float>> prev; bool paused = false, back = false;
    // 4-player local input: mouse = player 1; keyboard sets WASD+Q (P1), IJKL+U (P2), keypad 8456+0 (P3); gamepads in connection order (D-pad moves the cursor, DC buttons Y/A/X/B place up/down/left/right)
    // FourBattleLoop (HD 1.0 0x1c2b8) mode 1: a 120-tick intro (the round panel from tick 1 for 75 ticks, the Round START banner at tick 90 for 45 ticks), then play starts
    // FourBattleLoop modes 3..5 (0x1c3c2..): 3 round end (60 ticks), 4 between rounds (result screen, next round after 240 ticks and a touch), 5 match over
    int mode = 2, modeTick = 0, wins[4] = {0, 0, 0, 0}, winPoint = 2, roundWinner = 0, drawFlag = 0, gTime = 0, rank[4] = {0, 0, 0, 0}; bool tapped = false, matchOver = false, congra = false; int sub5 = 0, cnt5 = 0;   // winPoint: GetWinPoint (initial data value 2)
    // ResultRocket tasks (0x1fe24 Cons, 0x1ff58 Exec, 0x1fcf8 Draw; smoke 0x1fe10 / flash 0x1fdc8): the win icon rises from y = 620 (2 per tick) to 361, pulses (scale 1 -> 4 -> 1) and settles
    struct Rocket { int player, state; float x, y, tx, scale, dscale; }; std::vector<Rocket> rockets_; struct Smoke { float x, y; int n; }; std::vector<Smoke> smokes_; struct Flash { float x, y, scale, delta; }; std::vector<Flash> flashes_;
    int intro = 0, roundNo = 1; struct Banner { int kind, mode, tick, life; }; std::vector<Banner> banners; int lastLeftSec = -1;
    DragGesture drag; int lastCatSfx = -100; int curX[4] = {2, 9, 2, 9}, curY[4] = {2, 2, 6, 6}; SDL_GameController* pads[4] = {nullptr, nullptr, nullptr, nullptr};
    void place(int p, int cx, int cy, int d) { if (lv[p] >= 0 || p >= 4 || intro < 120) return; if (game.rollPending()) return;   /* Core::isRouletteActive -> Input::invalidateArrow: human arrow input is dropped while the wheel spins (Android 0x2bcc0, 0x4a9a8); the simulation keeps running */ if (d < 0) { d = 0; for (auto& ar : game.sim.arrows) if (ar.live && ar.x == cx && ar.y == cy && ar.owner == p) d = (ar.dir + 1) & 3; } game.placeArrow(p, cx, cy, d); }
    void moveCur(int p, int dx, int dy) { curX[p] = std::max(0, std::min(11, curX[p] + dx)); curY[p] = std::max(0, std::min(8, curY[p] + dy)); }
    bool keyPlayer(SDL_Keycode k) {   // keyboard = player 1: arrows move the cursor, W/A/S/D place up/left/down/right (the Dreamcast face buttons Y/X/A/B); the mouse is player 1 too (drag gesture)
        if (lv[0] >= 0) return false;
        if (k == SDLK_UP) moveCur(0, 0, -1); else if (k == SDLK_DOWN) moveCur(0, 0, 1); else if (k == SDLK_LEFT) moveCur(0, -1, 0); else if (k == SDLK_RIGHT) moveCur(0, 1, 0);
        else if (k == SDLK_w) place(0, curX[0], curY[0], 2); else if (k == SDLK_s) place(0, curX[0], curY[0], 0); else if (k == SDLK_a) place(0, curX[0], curY[0], 1); else if (k == SDLK_d) place(0, curX[0], curY[0], 3);
        else return false;
        return true;
    }
    void padButton(int p, int button) {
        if (p < 0 || p > 3 || lv[p] >= 0) return;
        switch (button) { case SDL_CONTROLLER_BUTTON_DPAD_UP: moveCur(p, 0, -1); break; case SDL_CONTROLLER_BUTTON_DPAD_DOWN: moveCur(p, 0, 1); break; case SDL_CONTROLLER_BUTTON_DPAD_LEFT: moveCur(p, -1, 0); break; case SDL_CONTROLLER_BUTTON_DPAD_RIGHT: moveCur(p, 1, 0); break;
            case SDL_CONTROLLER_BUTTON_Y: place(p, curX[p], curY[p], 2); break; case SDL_CONTROLLER_BUTTON_A: place(p, curX[p], curY[p], 0); break; case SDL_CONTROLLER_BUTTON_X: place(p, curX[p], curY[p], 1); break; case SDL_CONTROLLER_BUTTON_B: place(p, curX[p], curY[p], 3); break; default: break; }
    }
    bool load(const std::string& root, int stage, uint32_t sd) {
        if (!loadStages((root + "/battle_stages.bin").c_str(), stages, 2)) return false; cur = stage % (int)stages.list.size(); seed = sd;
        game.teamMode = getenv("CCR_TEAM") != nullptr; game.gbaCpu = getenv("CCR_CPU") && std::string(getenv("CCR_CPU")) == "gba"; game.rouletteManager = true; game.rotateOwn = true; game.baseScale = 1.0f; int minutes = getenv("CCR_MINUTES") ? atoi(getenv("CCR_MINUTES")) : 3; game.roundFrames = 60 * 60 * minutes;   // 1-3 minute rounds (NGI_SetGameTimer)
        if (const char* h = getenv("CCR_HUMANS")) { int n = std::max(1, std::min(4, atoi(h))); for (int p = 0; p < 4; p++) lv[p] = p < n ? -1 : (lv[p] < 0 ? 3 : lv[p]); }   // CCR_HUMANS=1..4 human players, the rest CPU
        for (int p = 0; p < 4; p++) game.setCpu(p, lv[p]);
        game.sfx = [this](int id) { if (id == 7) { if (game.frame - lastCatSfx < 3) return; lastCatSfx = game.frame; } if (gApp) gApp->playSfx(id); }; game.localPlayer = 0;   // ChuSECall(id) plays SFX index id (Android table at 0x63a00, ids 0..28 map to themselves); id 7 is dropped when it repeats within 3 ticks
        restart(); return true;
    }
    void restart() { sub5 = 0; cnt5 = 0; congra = false; rockets_.clear(); smokes_.clear(); flashes_.clear(); mode = 2; modeTick = 0; tapped = false; matchOver = false; intro = 0; banners.clear(); lastLeftSec = -1; game.start(stages.list[cur].st, seed); prev.clear(); if (gApp) gApp->angs.clear(); }
    // Original battle music (Android FUN_0003c56c / FUN_0003c534 / FUN_0003c828): while a roulette event runs the song depends on the outcome (table 0x63994: events 0..3 -> BGM ids 10, 9, 7, 8,
    // i.e. songs 6, 5, 3, 4); otherwise (and after the event) song 1 while more than 30 s are left (TI_CountDownBCDTimer > 0x2fff), song 2 in the last 30 s.
    int music() override { static const int evSong[4] = {6, 5, 3, 4}; int k = game.activeEventKind(); if (k >= 0 && k < 4) return evSong[k]; return game.clock > game.roundFrames - 60 * 30 ? 2 : 1; }
    void event(App& a, const SDL_Event& e) override {
        if (e.type == SDL_CONTROLLERDEVICEADDED) { for (int p = 0; p < 4; p++) if (!pads[p]) { pads[p] = SDL_GameControllerOpen(e.cdevice.which); break; } }
        else if (e.type == SDL_CONTROLLERBUTTONDOWN) { for (int p = 0; p < 4; p++) if (pads[p] && SDL_JoystickInstanceID(SDL_GameControllerGetJoystick(pads[p])) == e.cbutton.which) padButton(p, e.cbutton.button); }
        else if (e.type == SDL_KEYDOWN && keyPlayer(e.key.keysym.sym)) {}
        else if (e.type == SDL_KEYDOWN) { SDL_Keycode k = e.key.keysym.sym;
            if (k == SDLK_SPACE) paused = !paused; else if (k == SDLK_r) restart(); else if (k == SDLK_ESCAPE) back = true;
            else if (k == SDLK_RIGHTBRACKET) { cur = (cur + 1) % (int)stages.list.size(); restart(); } else if (k == SDLK_LEFTBRACKET) { cur = (cur + (int)stages.list.size() - 1) % (int)stages.list.size(); restart(); } }
        else if (e.type == SDL_MOUSEBUTTONDOWN && e.button.button == SDL_BUTTON_LEFT) { tapped = true; drag.begin(a, e); }
        else if (e.type == SDL_MOUSEBUTTONUP && e.button.button == SDL_BUTTON_LEFT && drag.on) { int cx = drag.cx, cy = drag.cy; int d = drag.end(a, e); if (d >= 0) place(0, cx, cy, d); }   // no drag = no arrow (Input::getArrowType returns 0)
    }
    void tick(App& a) override { if (paused) return;
        for (auto& bn : banners) bn.tick++; banners.erase(std::remove_if(banners.begin(), banners.end(), [](const Banner& bn) { return bn.tick >= bn.life; }), banners.end());   // SmpTskDelete when the counter reaches the lifetime
        if (intro < 120) { intro++; if (intro == 1) banners.push_back({1, roundNo, 0, 75}); if (intro == 90) banners.push_back({0, 6, 0, 45}); for (size_t i = 0; i < game.sim.ents.size() && i < prev.size(); i++) prev[i] = {game.sim.ents[i].x, game.sim.ents[i].z}; return; }
        { int left = game.roundFrames - game.clock; if (left >= 0 && left % 60 == 0 && left != lastLeftSec) { lastLeftSec = left; int sec = left / 60; int m = sec == 3 ? 2 : sec == 2 ? 1 : sec == 1 ? 0 : sec == 30 ? 3 : sec == 60 ? 4 : sec == 120 ? 5 : -1; if (m >= 0) banners.push_back({0, m, 0, App::countLife(m)}); } }   // FB_Exe_GAME: BCD 0x300 / 0x200 / 0x100, 0x3000, 0x10000, 0x20000
        if (gTime == 0 && getenv("CCR_WINPOINT")) winPoint = atoi(getenv("CCR_WINPOINT"));   // test override of GetWinPoint
        gTime++;
        for (auto& rk : rockets_) { if (rk.state == 0) { rk.y -= 2.0f; if (rk.y > rk.tx) { if ((gTime & 7) == 0) smokes_.push_back({rk.x, rk.y, 0}); } else { rk.state = 1; rk.scale = 1.0f; rk.dscale = 0.4f; flashes_.push_back({rk.x + 17.0f, rk.tx + 32.0f, 0.1f, 0.4f}); rk.y = rk.tx; if (gApp) { gApp->playSfx(0x14); } } }
            else if (rk.state == 1) { if (rk.scale >= 1.0f) { rk.scale += rk.dscale; if (rk.scale >= 4.0f) rk.dscale = -rk.dscale; } else { rk.scale = 1.0f; rk.state = 2; } } }
        for (auto& s : smokes_) s.n++; smokes_.erase(std::remove_if(smokes_.begin(), smokes_.end(), [](const Smoke& s) { return s.n > 8; }), smokes_.end());
        for (auto& f : flashes_) { if (f.scale < 0.1f) { f.scale = -1.0f; continue; } f.scale += f.delta; if (f.scale >= 1.4f) f.delta = -f.delta; } flashes_.erase(std::remove_if(flashes_.begin(), flashes_.end(), [](const Flash& f) { return f.scale < 0.0f; }), flashes_.end());
        if (mode == 2 && game.over) { mode = 3; modeTick = 0; }
        if (mode >= 4) { modeTick++;
            if (mode == 4 && modeTick > 0xf0 && tapped) { tapped = false; nextRound(); }
            else if (mode == 5) {   // FourBattleLoop mode 5 sub-states 0..3 (0x1c5c4): wait for the rocket, 30 ticks, 180 ticks (song 0x11), then the congratulations after 0xf0 ticks; a touch or 0x538 ticks ends
                if (tapped && sub5 >= 1) { if (gApp) gApp->playSfx(3); back = true; }
                else if (sub5 == 0) { if (game.teamMode) { sub5 = 1; cnt5 = 0x1e; } for (auto& rk : rockets_) if (rk.state >= 2) { sub5 = 1; cnt5 = 0x1e; } }
                else if (sub5 == 1) { if (--cnt5 < 0) { sub5 = 2; cnt5 = 0xb4; } }
                else if (sub5 == 2) { if (--cnt5 < 0) { sub5 = 3; cnt5 = 0; } }
                else { cnt5++; if (cnt5 == 0xf0) { congra = true; if (gApp) gApp->playSfx(0x14); } if (cnt5 <= 0x5f && (cnt5 & 0x1f) == 0 && gApp) gApp->playSfx(0x15); if (cnt5 > 0x538) { if (gApp) gApp->playSfx(3); back = true; } } }
            return; }   // mode 4: JudgeWin until 0xf0 ticks and a touch   // mode 4: JudgeWin until 0xf0 ticks and a touch; mode 5: until a touch (the original waits at most 0x538 ticks)
        if (mode == 3) { modeTick++; if (modeTick > 0x3b) endRound(); }
        for (size_t i = 0; i < game.sim.ents.size() && i < prev.size(); i++) prev[i] = {game.sim.ents[i].x, game.sim.ents[i].z}; for (int q = 0; q < 4; q++) { game.humanCell[q][0] = curX[q]; game.humanCell[q][1] = curY[q]; } if (mode == 2 || mode == 3) game.tick(); a.stepAngles(game.sim); }
    void endRound() {   // FourBattleLoop mode 3 after 60 ticks: the only player (team battle: team) with dense rank 0 wins the round
        if (game.teamMode) { int ts[2] = {game.score.team[0], game.score.team[1]}; int tr[2] = {ts[0] >= ts[1] ? 0 : 1, ts[1] >= ts[0] ? 0 : 1}; for (int p = 0; p < 4; p++) rank[p] = tr[p & 1]; modeTick = 0; rockets_.clear(); smokes_.clear(); flashes_.clear();
            if (tr[0] != tr[1]) { int w = tr[0] == 0 ? 0 : 1; roundWinner = w; drawFlag = 0; int old = wins[w]++; matchOver = old == winPoint; } else { drawFlag = 1; matchOver = false; } mode = matchOver ? 5 : 4; return; }   // the team result rocket (ResultRocketCons, team branch) is not ported
        int sc[4]; for (int p = 0; p < 4; p++) sc[p] = game.score.player[p]; int cnt = 0, w = 0; for (int p = 0; p < 4; p++) { int r = 0; for (int q = 0; q < 4; q++) if (sc[q] > sc[p]) { bool dup = false; for (int k = 0; k < q; k++) if (sc[k] == sc[q]) dup = true; if (!dup) r++; } rank[p] = r; if (r == 0) { cnt++; w = p; } }
        modeTick = 0; rockets_.clear(); smokes_.clear(); flashes_.clear(); if (cnt == 1) { roundWinner = w; drawFlag = 0; int old = wins[w]++; matchOver = old == winPoint; if (gApp) rockets_.push_back({w, 0, (float)w * gApp->layF(0x108) + gApp->layF(0x104) + gApp->layF(0x19c + winPoint * 0x14 + 4 * (wins[w] - 1)), 620.0f, 361.0f, 1.0f, 0.4f}); } else { drawFlag = 1; matchOver = false; }
        mode = matchOver ? 5 : 4; }
    void nextRound() { roundNo++; cur = (cur + 1) % (int)stages.list.size(); restart(); mode = 2; }   // GA_SetStageNumber(stage + 1, wrapping to 0)
    const char* next() override { if (back) { back = false; return "MENU"; } return nullptr; }
    void draw(App& a, float alpha) override {
        SDL_RenderSetLogicalSize(a.ren, GW, GH); SDL_RenderSetViewport(a.ren, nullptr); SDL_SetRenderDrawColor(a.ren, 24, 24, 40, 255); SDL_RenderClear(a.ren); { SDL_Rect vp{OX, OY, GW - OX, GH - OY}; SDL_RenderSetViewport(a.ren, &vp); }
        { static const int fc[4] = {1, 3, 4, 5}; a.board(stages.list[cur].st, fc[cur & 3], 0); }   // battle floor colour {1,3,4,5}[stage & 3], wall colour 0 (createPlayfieldPreview)
        a.rockets(game.sim, game.puku);
        for (auto& ar : game.sim.arrows) if (ar.live) a.arrow(ar.x, ar.y, ar.dir, ar.owner, ar.hits, ar.ttl);
        a.entities(game.sim, prev, paused ? 1.0f : alpha);
        for (int p = 0; p < 4; p++) if (lv[p] < 0) a.cursor(curX[p], curY[p], p, game.frame, (game.sim.coll[curY[p]][curX[p]] & 0xF00) != 0);
        { SDL_RenderSetViewport(a.ren, nullptr);   // battle HUD frame (HD 1.0 renderFourBattleHud 0x21038, free-for-all branch; layout struct values): image 0x68 frame 1 at (+0xb4, +0xb8) = (82, 62),
          // frame 2 at y + 0xbc (92) and 8 more times at + 0xc0 (0), frame 3 at + 0xc4 (0); frame 0 at (+0xc8, +0xcc) = (68, 88); player panels image 0x65 frame p at (280 + 192 p, 680) (+0x90..+0x9c),
          // separator 0x68 frame 4 at each panel 1..3 + (+0xa0, +0xa4) = (-1, -22); frame 5 at (+0xd0, +0xd4) = (82, 720). drawImage(id, frame, x, y, 0, 1.0, 255). The team branch (frames 6..13) is not drawn yet.
          int x0 = 82, y = 62; a.blit(a.hdHud68, 1, (float)x0, (float)y); y += 92; a.blit(a.hdHud68, 2, (float)x0, (float)y);
          for (int k = 1; k < 9; k++) { y += 0; a.blit(a.hdHud68, 2, (float)x0, (float)y); } y += 0; a.blit(a.hdHud68, 3, (float)x0, (float)(y + 0));
          a.blit(a.hdHud68, 0, 68.0f, 88.0f);
          for (int p = 0; p < 4; p++) { float px = 280.0f + 192.0f * p, py = 680.0f; a.blit(a.hdHud65, p, px, py); if (p > 0) a.blit(a.hdHud68, 4, px - 1.0f, py - 22.0f); }
          a.blit(a.hdHud68, 5, 82.0f, 720.0f); }
        SDL_RenderSetViewport(a.ren, nullptr);   // score digits (FUN_00030e18, iPad layout struct: x = 250 + 192 p + 30 k, y = 691; sprite r0729 frames 0..9 centred on their anchor); the player panels behind them (image 0x6d) are NOT drawn yet: their position field was not matched
        for (int p = 0; p < 4; p++) { int v = std::min(game.score.player[p], 999); int dg[3] = {v / 100 % 10, v / 10 % 10, v % 10};
            for (int k = 0; k < 3; k++) a.blit(a.digits, dg[k] == 1 ? 1 : dg[k] == 0 ? 0 : dg[k], 250.0f + 192 * p + 30 * k, 691.0f); }
        SDL_Rect vp2{OX, OY, GW - OX, GH - OY}; SDL_RenderSetViewport(a.ren, &vp2);
        { SDL_RenderSetViewport(a.ren, nullptr);   // rank crowns (HD 1.0 RankCrawnDrawPriority 0x209ac, free-for-all): shown while (task counter & 31) > 10 and the score total is non-zero;
          // image 0x5e frame = rank at (+0x6c + 192 p, +0x70) = (324 + 192 p, 644) (+0x74/+0x78 step). The task counter is taken as the battle frame count (the task starts with the battle).
          int tot = 0; for (int p = 0; p < 4; p++) tot += game.score.player[p];
          if ((game.frame & 31) > 10 && tot != 0) for (int p = 0; p < 4; p++) a.blit(a.crowns, game.rankOf(p), 324.0f + 192.0f * p, 644.0f);
          SDL_Rect vp4{OX, OY, GW - OX, GH - OY}; SDL_RenderSetViewport(a.ren, &vp4); }
        { SDL_RenderSetViewport(a.ren, nullptr);   // in-play timer (HD 1.0 clock2D 0x20e54): image 0x69 at scale 0.8; layout struct +0xf0 x = 78, +0xf8 step = 14, +0xf4 y = 84;
          // minutes at x, colon (frame 10) at x + step, tens at x + step + step / 2, ones at that + step; the value is TI_GetGameBCDTime = the BCD countdown rounded up to the next second
          int left = game.over ? 0 : std::max(0, game.roundFrames - game.clock); int secs = (left + 59) / 60; int mm = secs / 60, ss = secs % 60;
          const float y = 84.0f; float x = 78.0f; const float step = 14.0f;
          a.blit(a.hdTime, mm % 10, x, y, 0.8f); a.blit(a.hdTime, 10, x + step, y, 0.8f); float x2 = x + step + (float)((int)step / 2); a.blit(a.hdTime, ss / 10, x2, y, 0.8f); a.blit(a.hdTime, ss % 10, x2 + step, y, 0.8f);
          SDL_Rect vp3{OX, OY, GW - OX, GH - OY}; SDL_RenderSetViewport(a.ren, &vp3); }
        SDL_RenderSetViewport(a.ren, nullptr); for (auto& bn : banners) { if (bn.kind == 1) a.roundPanel(bn.mode, bn.tick); else a.battleCount(bn.mode, bn.tick); }   // banner tasks drawn over the HUD
        if (mode >= 4) { int sc[4]; for (int p = 0; p < 4; p++) sc[p] = game.score.player[p]; int reach = 0; if (!(gTime & 0x20) && !matchOver) for (int p = 0; p < 4; p++) if (wins[p] == winPoint) reach |= 1 << p;   // PM_DispReach: blinks with the global time, none when the match is over
            if (game.teamMode) { int ts[2] = {game.score.team[0], game.score.team[1]}, tr[2] = {rank[0], rank[1]}; a.judgeWinTeam(ts, tr, wins, roundWinner, drawFlag, winPoint, reach & 3, true); } else a.judgeWin(sc, rank, wins, roundWinner, drawFlag, winPoint, reach, true);
            for (auto& s : smokes_) a.drawImage(0x92, s.n, s.x, s.y - a.layF(0x230), 0, 1.0f, 255);
            for (auto& rk : rockets_) a.drawImage(0x5d, rk.player, rk.x, rk.y - a.layF(0x22c), 0, rk.scale, 255);
            if (congra) { a.drawImage(0x90, 0, a.layF(0x208), a.layF(0x20c), 0, 1.0f, 255); a.drawImage(0x62, roundWinner, a.layF(0x214), a.layF(0x218), 0, 2.0f, 255); }   // DispCongraDrawPriority 0x1f990 (the congratulation rockets, CongraRocketCons, are not ported)
            for (auto& f : flashes_) a.drawImage(0x87, 4, f.x, f.y - a.layF(0x22c), 0, f.scale, 0x40); }
        SDL_RenderSetViewport(a.ren, nullptr);
    }
};

static int saveFrame(SDL_Renderer* renderer, const char* path) {
    int width, height;
    if (SDL_GetRendererOutputSize(renderer, &width, &height) < 0) return 1;
    SDL_Surface* surface = SDL_CreateRGBSurfaceWithFormat(0, width, height, 32, SDL_PIXELFORMAT_ARGB8888);
    if (!surface) return 1;
    const bool saved = SDL_RenderReadPixels(renderer, nullptr, SDL_PIXELFORMAT_ARGB8888,
                                            surface->pixels, surface->pitch) == 0 &&
                       SDL_SaveBMP(surface, path) == 0;
    SDL_FreeSurface(surface);
    return saved ? 0 : 1;
}

int main(int argc, char** argv) {
    if (getenv("CCR_PSTEST23")) {
        PlayersTextureLoad load;
        int width, count;
        float dt;
        if (scanf("%d %d %f %f %f %f %u %u %f %u %u", &width, &count, &dt,
                  &load.pulse, &load.pulseRate,
                  &load.preview.elapsed, &load.preview.frame, &load.preview.frameCount,
                  &load.character.elapsed, &load.character.frame, &load.character.frameCount) != 11 ||
            count < 0) return 1;
        for (int i = 0; i < count; ++i) {
            int texture;
            if (scanf("%d", &texture) != 1) return 1;
            load.textures.push_back(texture);
        }
        while (true) {
            const bool finished = load.step(dt, width,
                [](int texture, int space) { printf("put:%d:%d ", texture, space); },
                [](int texture) { printf("destroy:%d ", texture); });
            printf("%d %zu %a %a %a %u %a %u\n", finished ? 0x24 : 0x23, load.loaded,
                   load.pulse, load.pulseRate, load.preview.elapsed, load.preview.frame,
                   load.character.elapsed, load.character.frame);
            if (finished) return 0;
        }
    }
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
        else if (name == "PUZZLE" || name == "puzzle") { auto m = std::make_unique<PuzzleMode>(); int sn = app.nextStage >= 0 ? app.nextStage : stageNo; app.nextStage = -1; if (!m->load(app.root, sn)) { printf("cannot load puzzle stages\n"); return false; } mode = std::move(m); }
        else if (name == "STAGES") { auto m = std::make_unique<StageSelectMode>(); if (!m->load(app.root, app.nextStage >= 0 ? app.nextStage : stageNo)) { printf("cannot load puzzle stages\n"); return false; } mode = std::move(m); }
        else if (name == "BATTLE" || name == "battle") { auto m = std::make_unique<BattleMode>(); memcpy(m->lv, lv, sizeof lv); if (!m->load(app.root, stageNo, seed)) { printf("cannot load battle stages\n"); return false; } mode = std::move(m); }
        else if (name == "HELP" && HelpMode::ok(app)) mode = std::make_unique<HelpMode>();
        else if (name == "CREDITS" && CreditsMode::ok(app)) mode = std::make_unique<CreditsMode>(app);
        else if (name == "OPTIONS" && OptionsMode::ok(app)) mode = std::make_unique<OptionsMode>();
        else if (HdMenuMode::ok(app)) mode = std::make_unique<HdMenuMode>();
        else mode = std::make_unique<MenuMode>();
        return true;
    };
    if (const char* bt = getenv("CCR_BUBBLE")) {   // development check: CCR_BUBBLE="x,y,w,flags,p6,alpha|text" prints the draw calls of Render::drawBubble (tools/bubble_diff.py compares them with the original)
        int x, y, w, fl, p6, al; int n = 0; if (sscanf(bt, "%d,%d,%d,%d,%d,%d|%n", &x, &y, &w, &fl, &p6, &al, &n) >= 6 && n > 0) { std::vector<std::string> lg; app.bubbleLog = &lg; app.drawBubble(x, y, w, bt + n, fl, p6, al); for (auto& s : lg) printf("%s\n", s.c_str()); } return 0; }
    if (const char* sst = getenv("CCR_SSTEST")) { int pg, sl; unsigned b0; if (sscanf(sst, "%d,%d,%u", &pg, &sl, &b0) == 3) { std::vector<std::string> lg; app.uiLog = &lg; app.loadProgress(); for (int i = 0; i < 4; i++) app.clr[i] = 0; app.clr[0] = b0; StageSelectMode ss; ss.selPage = pg; ss.sel = sl; ss.phase = 0x21; ss.timer = 0; ss.origDraw(app); for (auto& l : lg) printf("%s%c", l.c_str(), 10); } return 0; }
    if (const char* ht = getenv("CCR_HELPTEST")) { int tp, pg; if (sscanf(ht, "%d,%d", &tp, &pg) == 2) { std::vector<std::string> lg; app.uiLog = &lg; HelpMode hm; hm.phase = 0x15; hm.a20 = 0; if (tp < 0) hm.a34 = -1; else { hm.a34 = 1; hm.topic = tp; hm.page = pg; } hm.draw(app, 0); for (auto& l : lg) printf("%s%c", l.c_str(), 10); } return 0; }
    if (const char* jt = getenv("CCR_JUDGET")) { int s[2], r[2], wn[2], rw, df, wp, rc; if (sscanf(jt, "%d,%d;%d,%d;%d,%d;%d,%d,%d,%d", s, s + 1, r, r + 1, wn, wn + 1, &rw, &df, &wp, &rc) == 10) { std::vector<std::string> lg; app.imgLog = &lg; app.judgeWinTeam(s, r, wn, rw, df, wp, rc); for (auto& l : lg) printf("%s%c", l.c_str(), 10); } return 0; }
    if (const char* jw = getenv("CCR_JUDGE")) { int s[4], r[4], wn[4], rw, df, wp, rc; if (sscanf(jw, "%d,%d,%d,%d;%d,%d,%d,%d;%d,%d,%d,%d;%d,%d,%d,%d", s, s + 1, s + 2, s + 3, r, r + 1, r + 2, r + 3, wn, wn + 1, wn + 2, wn + 3, &rw, &df, &wp, &rc) == 16) { std::vector<std::string> lg; app.imgLog = &lg; app.judgeWin(s, r, wn, rw, df, wp, rc); for (auto& l : lg) printf("%s%c", l.c_str(), 10); } return 0; }
    if (const char* bn = getenv("CCR_BANNER")) { int kind, m, t; if (sscanf(bn, "%d,%d,%d", &kind, &m, &t) == 3) { std::vector<std::string> lg; app.imgLog = &lg; if (kind == 1) app.roundPanel(m, t); else app.battleCount(m, t); for (auto& l : lg) printf("%s%c", l.c_str(), 10); } return 0; }
    if (const char* sc = getenv("CCR_SCROLL")) { int off0, ly, y; if (sscanf(sc, "%d,%d,%d", &off0, &ly, &y) == 3) { SettingsListScroll s; s.offset = (float)off0; s.press(ly); s.move(ly); s.move(y); int d = (int)s.offset; s.release(); printf("%d %d %d\n", d, (int)s.offset, s.selected); } return 0; }
    if (const char* ht = getenv("CCR_HIT")) { int x, y; if (sscanf(ht, "%d,%d", &x, &y) == 2) printf("%d\n", SettingsPaneItems::hit(x, y)); return 0; }
    if (getenv("CCR_FILL")) { printf("%d %d %d %d %d %d %d %d\n", SettingsListFill::x, SettingsListFill::y, SettingsListFill::w, SettingsListFill::h, SettingsListFill::r, SettingsListFill::g, SettingsListFill::bl, SettingsListFill::a); return 0; }
    if (getenv("CCR_PANELS")) { SettingsListPanels::Draw d[4]; SettingsListPanels::draws(d); for (int i = 0; i < 4; i++) printf("%d %d %d %d %d %d %d %d\n", d[i].sx, d[i].sy, d[i].sw, d[i].sh, d[i].x, d[i].y, d[i].w, d[i].h); return 0; }
    if (getenv("CCR_LEVELROWS")) { std::vector<SettingsLevelList::Row> rw; SettingsLevelList::rows(0.0f, rw); for (auto& r : rw) printf("PS %s %.1f %.1f %.3f\n", r.text.c_str(), r.x, r.y, r.scale); return 0; }
    if (getenv("CCR_SETTINGSRECTS")) { SettingsPaneItems::PaneRect r[10]; SettingsPaneItems::layout(r); for (int i = 0; i < 10; i++) printf("%d %d %d %d %d\n", i, r[i].x, r[i].y, r[i].w, r[i].h); return 0; }
    if (const char* spec = getenv("CCR_PAD_RULES")) {
        int points, speed, time, high, split;
        if (sscanf(spec, "%d,%d,%d,%d,%d", &points, &speed, &time, &high, &split) != 5 ||
            speed < 0 || speed >= 5) return 1;
        const SettingsPaneItems::PadRules rules{points, speed, time, high != 0, split != 0};
        if (const char* shot = getenv("CCR_SHOT")) {
            SDL_RenderSetLogicalSize(app.ren, GW, GH);
            PlayersFrame frame;
            frame.state = 0x25;
            frame.pane = 1;
            frame.draw(app, [&](int) {
                SettingsPaneItems::drawPadStageGrid(app, 0, nullptr);
                SettingsPaneItems::drawPadRules(app, rules, {}, nullptr);
            });
            return saveFrame(app.ren, shot);
        }
        std::vector<std::string> trace;
        SettingsPaneItems::drawPadRules(app, rules, [&](const SDL_Rect& r) {
            char line[100];
            snprintf(line, sizeof line, "preview %d %d %d %d", r.x, r.y, r.w, r.h);
            trace.push_back(line);
        }, &trace);
        for (const auto& call : trace) puts(call.c_str());
        return 0;
    }
    if (const char* spec = getenv("CCR_PAD_SETTINGS_GRID")) {
        const int selected = atoi(spec);
        if (const char* shot = getenv("CCR_SHOT")) {
            SDL_RenderSetLogicalSize(app.ren, GW, GH);
            PlayersFrame frame;
            frame.state = 0x25;
            frame.pane = 1;
            frame.draw(app, [&](int) { SettingsPaneItems::drawPadStageGrid(app, selected, nullptr); });
            return saveFrame(app.ren, shot);
        }
        std::vector<std::string> trace;
        SettingsPaneItems::drawPadStageGrid(app, selected, &trace);
        for (const auto& call : trace) puts(call.c_str());
        return 0;
    }
    if (getenv("CCR_PAD_SETTINGS")) {
        for (bool network : {false, true}) {
            SettingsPaneItems::PaneRect rects[37];
            const int count = SettingsPaneItems::layoutPad(rects, network);
            printf("count %d\n", count);
            for (int i = 0; i < count; ++i) {
                const auto& r = rects[i];
                printf("%d %d %d %d\n", r.x, r.y, r.w, r.h);
            }
            int tests;
            if (scanf("%d", &tests) != 1 || tests < 0) return 1;
            for (int i = 0; i < tests; ++i) {
                int x, y;
                if (scanf("%d %d", &x, &y) != 2) return 1;
                printf("hit %d\n", SettingsPaneItems::hit(rects, count, x, y));
            }
        }
        return 0;
    }
    if (getenv("CCR_PSTEST24")) { for (float dt : {1.0f, 1.0f / 60.0f}) for (float f0 : {0.0f, 0.5f, 1.5f}) { std::string ops; float fade = f0; int req = playersFlowStep(0x24, 0, 0, 0, 0, 0, dt, fade, ops);
        printf("0x24 dt%.4f fade%.1f -> req=%d ops=[%s] fade=%.4f%c", dt, f0, req, ops.c_str(), fade, 10); }
        for (int a44 : {0, 1, 2}) printf("0x25 a44=%d -> req=%d ops=[%s]%c", a44, 0, playersRouteOps(a44).c_str(), 10); return 0; }
    if (getenv("CCR_PSTEST")) { int idx = 0; for (int st : {0x26, 0x27}) for (int tim : {3, 5}) for (int a3c : {0, 1}) for (int a40 : {0, 1, 2}) for (int net : {0, 1}) for (int split : {0, 1}) for (int k = 0; k < 2; k++) {
        float dt = k == 0 ? 1.0f : 1.0f / 60.0f, f0 = k == 0 ? (st == 0x26 ? 499999.5f : 0.0f) : 0.5f; std::string ops; float fade = f0; int req = playersFlowStep(st, tim, a3c, a40, net, split, dt, fade, ops);
        printf("%#x t%d a3c%d a40=%d net%d split%d dt%.4f fade%.1f -> req=%d ops=[%s] fade=%.4f%c", st, tim, a3c, a40, net, split, dt, f0, req, ops.c_str(), fade, 10); idx++; } return 0; }
    if (const char* pin = getenv("CCR_PLAYIN")) { PlayersInputLogic pil; for (int i = 0; i < 14; i++) { pil.sfx.clear(); pil.press(i); printf("%d d3c=%d d40=%d d44=%d d58=%d a40=%d a3c=%d a38=%d d20=%d\n", i, pil.d3c, pil.d40, pil.d44, pil.d58, pil.a40, pil.a3c, pil.a38, pil.d20); } return 0; }
    if (getenv("CCR_PLAY_SETTINGS")) {
        for (int connections : {0, 1})
            for (int host : {0, 1})
                for (bool ready : {false, true})
                    for (bool d34 : {false, true}) {
                        PlayersInputLogic input;
                        input.d20 = connections;
                        input.g170 = host;
                        input.networkReady = ready;
                        input.d34 = d34;
                        input.press(14);
                        printf("%d %d", input.openSettings, input.settingsSyncRequested);
                        for (int sound : input.sfx) printf(" %d", sound);
                        puts("");
                    }
        return 0;
    }
    if (const char* ph = getenv("CCR_PLAYHELP")) { int a, bb, v, x, y; int h[6] = {0,0,0,0,0,0}; if (sscanf(ph, "m:%d,%d,%d", &a, &bb, &v) == 3) { uint8_t lit[8] = {0,0,0,0,0,0,0,0}; if (a != 0 || bb != 1 || true) {} PlayersInputHelpers::mutexPlayer(lit, a, bb, v); printf("%d %d\n", lit[a], lit[bb]); return 0; } if (sscanf(ph, "r:%d,%d,%d,%d,%d,%d,%d", &x, &y, h, h + 1, h + 2, h + 3, h + 4) == 7) { PlayersInputHelpers::Row rows[6]; for (int i = 0; i < 5; i++) rows[i].h = h[i]; rows[5].h = 0; PlayersInputHelpers::reposition(x, y, rows); printf("%d %d\n", x, y); for (int i = 0; i < 5; i++) printf("%d %d\n", rows[i].x, rows[i].y); return 0; } return 0; }
    if (const char* spec = getenv("CCR_PSRENDER")) {
        PlayersFrame frame;
        if (sscanf(spec, "%d,%d,%d,%d,%d,%d,%d,%d,%f,%f,%f", &frame.state, &frame.pane,
                   &frame.team, &frame.costume, &frame.loaded, &frame.textureCount, &frame.catFrame,
                   &frame.mouseFrame, &frame.fade, &frame.catX, &frame.mouseX) != 11) return 1;
        if (const char* shot = getenv("CCR_SHOT")) {
            SDL_RenderSetLogicalSize(app.ren, GW, GH);
            frame.draw(app, [](int) {});
            return saveFrame(app.ren, shot);
        }
        std::vector<std::string> trace;
        app.uiLog = &trace;
        frame.draw(app, [&](int pane) { trace.push_back("pane " + std::to_string(pane)); });
        for (const auto& call : trace) puts(call.c_str());
        return 0;
    }
    if (const char* spec = getenv("CCR_PAD_PLAYERS")) {
        int human[4], level[4], slider, pressed;
        if (sscanf(spec, "%d,%d,%d,%d,%d,%d,%d,%d,%d,%d", &human[0], &human[1], &human[2],
                   &human[3], &level[0], &level[1], &level[2], &level[3], &slider, &pressed) != 10) return 1;
        if (const char* shot = getenv("CCR_SHOT")) {
            SDL_RenderSetLogicalSize(app.ren, GW, GH);
            PlayersFrame frame;
            frame.state = 0x25;
            frame.draw(app, [&](int) { PlayersPane::drawPad(app, human, level, slider, pressed, nullptr); });
            return saveFrame(app.ren, shot);
        }
        std::vector<std::string> trace;
        PlayersPane::drawPad(app, human, level, slider, pressed, &trace);
        for (const auto& call : trace) puts(call.c_str());
        return 0;
    }
    if (const char* pp = getenv("CCR_PLAYERSTEST")) { int h[4] = {0, 1, 0, 1}, l[4] = {0, 0, 0, 0}; if (sscanf(pp, "%d,%d,%d,%d;%d,%d,%d,%d", h, h + 1, h + 2, h + 3, l, l + 1, l + 2, l + 3) >= 4) { std::vector<std::string> lg; PlayersPane::draw(app, h, l, &lg); for (auto& s : lg) printf("%s%c", s.c_str(), 10); } return 0; }
    if (const char* st = getenv("CCR_SNDTEST")) { int m, s2, d; if (sscanf(st, "%d,%d,%d", &m, &s2, &d) == 3) { OptionsMode om; std::vector<std::string> lg; om.drawSounds(app, m, s2, d, &lg); for (auto& l : lg) printf("%s\n", l.c_str()); } return 0; }
    if (!enter(start)) return 2;
    const double dt = 1.0 / 60.0; double acc = 0;
    if (const char* shot = getenv("CCR_SHOT")) {
        int ticks = getenv("CCR_TICKS") ? atoi(getenv("CCR_TICKS")) : 600;
        if (const char* keys = getenv("CCR_KEYS")) for (const char* p = keys; *p; p++) { SDL_Event e{}; e.type = SDL_KEYDOWN; e.key.keysym.sym = (*p == ' ') ? SDLK_SPACE : (*p == 'D') ? SDLK_DOWN : (*p == 'E') ? SDLK_RETURN : *p; mode->event(app, e); if (const char* nx = mode->next()) enter(nx); }
        std::vector<std::array<int, 3>> clicks; if (const char* c = getenv("CCR_CLICKS")) { int t, x, y, n; const char* p = c; while (sscanf(p, "%d:%d,%d%n", &t, &x, &y, &n) == 3) { clicks.push_back({t, x, y}); p += n; if (*p == ';') p++; else break; } }   // headless test input: tick:x,y;... (window pixels)
        int lastSong = -2; for (int i = 0; i < ticks; i++) {
            for (auto& ck : clicks) if (ck[0] == i) for (int ty : {SDL_MOUSEBUTTONDOWN, SDL_MOUSEBUTTONUP}) { SDL_Event e{}; e.type = ty; e.button.button = SDL_BUTTON_LEFT; e.button.x = ck[1]; e.button.y = ck[2]; mode->event(app, e); if (const char* nx = mode->next()) enter(nx); } mode->tick(app); if (const char* nx = mode->next()) enter(nx); if (getenv("CCR_AUDIO_TEST") && mode->music() >= 0) { app.pumpMusic(mode->music()); if (app.curTrack != lastSong) { lastSong = app.curTrack; printf("tick %d: song %d (DC track %d), loop %zu..%zu of %zu samples\n", i, lastSong, lastSong + 4, app.songs[lastSong].loopStart, app.songs[lastSong].loopEnd, app.songs[lastSong].pcm.size()); } } }
        mode->draw(app, 1.0f);
        const int result = saveFrame(app.ren, shot);
        SDL_Quit();
        return result;
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
        while (acc >= dt) { mode->tick(app); if (const char* nx = mode->next()) { enter(nx); acc = 0; break; } acc -= dt; }   // screens that finish by themselves (fade-outs) are polled after every tick
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
