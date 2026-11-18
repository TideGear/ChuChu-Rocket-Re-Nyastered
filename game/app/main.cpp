// Re-Nyastered game app (vertical slice, in progress): menu, puzzle mode and battle mode vs CPU players with extracted iOS art.
// usage: ccr <cache assets dir> [mode: menu|puzzle|battle] [stage] [seed] [cpu levels e.g. 3,3,3]
// Simulation: fixed 60 Hz (verified against the original); drawing is interpolated and resolution independent (logical 768x640 scaled to the window).
// Env: CCR_SIZE=3840x2160 CCR_FULLSCREEN=1 CCR_VSYNC=0 CCR_FILTER=nearest|linear CCR_MINUTES=1..3; CCR_SHOT=<bmp> CCR_TICKS=n renders headlessly (dummy video/audio, software renderer).
#define SDL_MAIN_HANDLED
#include <SDL.h>
#include "../core/battle.hpp"
#include "../core/angle.hpp"
#include "battle_preview.hpp"
#include "roulette_pose.hpp"
#include "roulette_draw.hpp"
#include "rocket_lid.hpp"
#include "../core/challenge.hpp"
#include "../core/challenge_battle.hpp"
#include "../core/userdata.hpp"
#include "../core/padmap.hpp"
#include "../core/vms.hpp"
#include "model3d.hpp"
#include <filesystem>
#include "rocket_launch.hpp"
#include "startup.hpp"
#include <array>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <memory>
#include <utility>
#include <string>
#include <functional>
#include <map>
#ifdef __EMSCRIPTEN__
#include <emscripten.h>
#endif
#include <vector>
#include <filesystem>
#include <algorithm>
// Sets an environment variable that getenv() sees on every platform (SDL_setenv does not update the C runtime's copy on Windows).
static void ccrSetEnv(const char* k, const char* v, int overwrite) {
#ifdef _WIN32
    if (!overwrite && getenv(k)) return; _putenv_s(k, v);
#else
    setenv(k, v, overwrite);
#endif
}
#ifdef _WIN32
#include "launcher_setup.hpp"
#elif !defined(__EMSCRIPTEN__)
#include "launcher_setup_posix.hpp"
#endif
extern "C" {
#include "stb_vorbis.c"
}
using namespace ccr;

static const int CELL = 64, W = 12 * CELL, H = 9 * CELL + 64;
// iPad-class layout (Core::settingsInit iOS 0x135cc + the static layout struct at 0x131028, read 2026-11-14): screen 1024 x 768, cell pitch 64 (= 4.2667 px per world unit), field origin (184, 32); other layouts: Android 800x480 (pitch 50, origin 160,18), 480x320 (pitch 35, origin 61,4).
static const int GW = 1024, GH = 768, OX = 184, OY = 32;
struct FieldLayout {
    float left = OX, top = OY, cell = CELL;
    float wallMagnification = 1.0f;

    float x(float cells) const { return left + cells * cell; }
    float y(float cells) const { return top + cells * cell; }
    float scale() const { return cell / CELL; }
    FieldLayout wallPlane() const {
        return {GW / 2.0f + (left - GW / 2.0f) * wallMagnification,
                GH / 2.0f + (top - GH / 2.0f) * wallMagnification,
                cell * wallMagnification};
    }
};

// Battle floor PowerVR quad in the 640x480 Dreamcast viewport, frame 3100.
static constexpr FieldLayout dcBattleField{
    136.92937f * 1.6f, 22.60363f * 1.6f, (457.67653f / 12) * 1.6f,
    218.0f / 215.0f
};
static const SDL_Color pcol[4] = {{60, 120, 255, 255}, {250, 170, 30, 255}, {240, 60, 60, 255}, {40, 190, 70, 255}};   // player order of the original art (arrow sheet r0645, cursor sheet r0732, rocket sheets r0651/r0663/r0675/r0687): blue, orange, red, green

// Built-in 5x7 bitmap font (uppercase, digits, basic punctuation) used when no mobile glyph sheet exists (a Dreamcast-only install has none; the disc's own fonts are not wired yet).
static const char kFontChars[] = "!%'()+,-./0123456789:<=>?ABCDEFGHIJKLMNOPQRSTUVWXYZ";
static const uint8_t kFont57[][7] = {{0x04,0x04,0x04,0x04,0x04,0x00,0x04},{0x19,0x1a,0x02,0x04,0x08,0x0b,0x13},{0x04,0x04,0x08,0x00,0x00,0x00,0x00},{0x02,0x04,0x08,0x08,0x08,0x04,0x02},{0x08,0x04,0x02,0x02,0x02,0x04,0x08},{0x00,0x04,0x04,0x1f,0x04,0x04,0x00},{0x00,0x00,0x00,0x00,0x06,0x04,0x08},{0x00,0x00,0x00,0x1f,0x00,0x00,0x00},{0x00,0x00,0x00,0x00,0x00,0x0c,0x0c},{0x01,0x02,0x02,0x04,0x08,0x08,0x10},{0x0e,0x11,0x13,0x15,0x19,0x11,0x0e},{0x04,0x0c,0x04,0x04,0x04,0x04,0x0e},{0x0e,0x11,0x01,0x02,0x04,0x08,0x1f},{0x1e,0x01,0x01,0x0e,0x01,0x01,0x1e},{0x02,0x06,0x0a,0x12,0x1f,0x02,0x02},{0x1f,0x10,0x1e,0x01,0x01,0x11,0x0e},{0x06,0x08,0x10,0x1e,0x11,0x11,0x0e},{0x1f,0x01,0x02,0x04,0x08,0x08,0x08},{0x0e,0x11,0x11,0x0e,0x11,0x11,0x0e},{0x0e,0x11,0x11,0x0f,0x01,0x02,0x0c},{0x00,0x0c,0x0c,0x00,0x0c,0x0c,0x00},{0x02,0x04,0x08,0x10,0x08,0x04,0x02},{0x00,0x00,0x1f,0x00,0x1f,0x00,0x00},{0x08,0x04,0x02,0x01,0x02,0x04,0x08},{0x0e,0x11,0x01,0x02,0x04,0x00,0x04},{0x0e,0x11,0x11,0x1f,0x11,0x11,0x11},{0x1e,0x11,0x11,0x1e,0x11,0x11,0x1e},{0x0e,0x11,0x10,0x10,0x10,0x11,0x0e},{0x1e,0x11,0x11,0x11,0x11,0x11,0x1e},{0x1f,0x10,0x10,0x1e,0x10,0x10,0x1f},{0x1f,0x10,0x10,0x1e,0x10,0x10,0x10},{0x0e,0x11,0x10,0x17,0x11,0x11,0x0f},{0x11,0x11,0x11,0x1f,0x11,0x11,0x11},{0x0e,0x04,0x04,0x04,0x04,0x04,0x0e},{0x07,0x02,0x02,0x02,0x02,0x12,0x0c},{0x11,0x12,0x14,0x18,0x14,0x12,0x11},{0x10,0x10,0x10,0x10,0x10,0x10,0x1f},{0x11,0x1b,0x15,0x15,0x11,0x11,0x11},{0x11,0x19,0x15,0x13,0x11,0x11,0x11},{0x0e,0x11,0x11,0x11,0x11,0x11,0x0e},{0x1e,0x11,0x11,0x1e,0x10,0x10,0x10},{0x0e,0x11,0x11,0x11,0x15,0x12,0x0d},{0x1e,0x11,0x11,0x1e,0x14,0x12,0x11},{0x0f,0x10,0x10,0x0e,0x01,0x01,0x1e},{0x1f,0x04,0x04,0x04,0x04,0x04,0x04},{0x11,0x11,0x11,0x11,0x11,0x11,0x0e},{0x11,0x11,0x11,0x11,0x11,0x0a,0x04},{0x11,0x11,0x11,0x15,0x15,0x1b,0x11},{0x11,0x11,0x0a,0x04,0x0a,0x11,0x11},{0x11,0x11,0x0a,0x04,0x04,0x04,0x04},{0x1f,0x01,0x02,0x04,0x08,0x10,0x1f}};
static const uint8_t* font57(unsigned char c) { if (c >= 'a' && c <= 'z') c = (unsigned char)(c - 32); for (size_t i = 0; i + 1 < sizeof kFontChars; i++) if ((unsigned char)kFontChars[i] == c) return kFont57[i]; return nullptr; }
struct Sheet { SDL_Texture* tex = nullptr; int w = 0, h = 0; std::vector<SDL_Rect> fr; std::vector<SDL_Point> off; std::vector<float> fit; std::vector<SDL_Point> box; std::vector<SDL_Point> sz; };   // sz = frame record shorts 0, 1 (the size the panel calls use), box = shorts 2, 3   // box = frame record shorts 2, 3 (the draw box BHLib_RenderTexture callers use, minus 2)   // fit: per-frame scale to the original iPad (HD 1.0) frame width   // off = the frame record's draw offset (xoff, yoff) from the anchor, in sheet pixels

static constexpr int kMobilePuzzleSource = 5;
struct Stages { struct E { Stage st; std::array<uint8_t, 4> stock{}; char title[33]; int src, idx; }; std::vector<E> list; };
static bool loadStages(const char* path, Stages& out, int onlySrc) {
    FILE* f = fopen(path, "rb"); if (!f) return false;
    uint32_t n; if (fread(&n, 4, 1, f) != 1) { fclose(f); return false; }
    for (uint32_t i = 0; i < n; i++) {
        uint8_t h[4], w[237]; Stages::E e;
        if (fread(h, 1, 4, f) != 4 || fread(e.st.tiles, 1, 108, f) != 108 || fread(w, 1, 237, f) != 237) break;
        bool bad = false;
        if (h[0] == kMobilePuzzleSource) {
            bad = fread(e.stock.data(), 1, e.stock.size(), f) != e.stock.size();
        } else {
            for (int i = 0; i < h[1]; ++i) {
                uint8_t arrow[3];
                if (fread(arrow, 1, sizeof arrow, f) != sizeof arrow) { bad = true; break; }
                ++e.stock[arrow[2] & 3];
            }
        }
        if (bad || fread(e.title, 1, 32, f) != 32) break;
        e.title[32] = 0; e.src = h[0]; e.idx = h[2] | (h[3] << 8);
        for (int r = 0; r < 10; r++) for (int c = 0; c < 12; c++) e.st.hw[r * 12 + c] = w[25 * r + c];
        for (int r = 0; r < 9; r++) for (int c = 0; c < 13; c++) e.st.vw[r * 13 + c] = w[25 * r + 12 + c];
        if (h[0] == onlySrc) out.list.push_back(e);
    }
    fclose(f); return !out.list.empty();
}

// Puzzle stage sets: 0 = the 100 main stages, 1 = the 2,466 further GBA stages, 2 = the Dreamcast Express DLC pack "DEPuzzle" (25 puzzles with the arrow stock decoded from the slot, docs/dlc.md; PuzzleP is left out until its stock is verified)
static const int kStageSets = 4;
static std::string gImportDir;   // <data folder>/imports: Dreamcast puzzle packs (.VMS) the player dropped there become stage set 3
static const int kImportedSource = 5;
static bool loadImportedPacks(Stages& out) {
    namespace fs = std::filesystem; std::error_code ec; if (gImportDir.empty() || !fs::is_directory(gImportDir, ec)) return false;
    std::vector<std::string> files;
    for (auto& de : fs::directory_iterator(gImportDir, ec)) { std::string ext = de.path().extension().string(); for (auto& c : ext) c = (char)tolower((unsigned char)c); if (ext == ".vms") files.push_back(de.path().string()); }
    std::sort(files.begin(), files.end());
    int idx = 0;
    for (const auto& path : files) {
        FILE* f = fopen(path.c_str(), "rb"); if (!f) continue;
        std::vector<uint8_t> data; uint8_t buf[4096]; size_t n; while ((n = fread(buf, 1, sizeof buf, f)) > 0) data.insert(data.end(), buf, buf + n);
        fclose(f);
        std::vector<VmsPuzzle> puzzles; if (vms::readPack(data, puzzles) <= 0) continue;   // not a puzzle pack (a character pack, or damaged): skipped
        for (const auto& p : puzzles) {
            Stages::E e; std::memset(&e.st, 0, sizeof e.st);
            std::memcpy(e.st.tiles, p.tiles, 108);
            for (int r = 0; r < 10; r++) for (int c = 0; c < 12; c++) e.st.hw[r * 12 + c] = p.walls[25 * r + c];
            for (int r = 0; r < 9; r++) for (int c = 0; c < 13; c++) e.st.vw[r * 13 + c] = p.walls[25 * r + 12 + c];
            for (const auto& ar : p.arrows) ++e.stock[ar.dir & 3];
            std::memset(e.title, 0, sizeof e.title); std::strncpy(e.title, p.title.c_str(), 32);
            bool plain = !p.title.empty(); for (unsigned char ch : p.title) if (ch < 0x20 || ch > 0x7e) plain = false;   // Shift-JIS titles cannot be drawn with the ASCII font: fall back to a number
            if (!plain) snprintf(e.title, sizeof e.title, "PUZZLE %d", idx + 1);
            e.src = kImportedSource; e.idx = idx++; out.list.push_back(e);
        }
    }
    return !out.list.empty();
}
static bool loadStageSet(const std::string& root, int set, Stages& out) {
    if (set == 3) return loadImportedPacks(out);
    if (set == 2) return loadStages((root + "/gba/dlc_stages.bin").c_str(), out, 3);
    if (loadStages((root + "/gba/gba_stages.bin").c_str(), out, set)) return true;
    if (set != 0) return false;
    return loadStages((root + "/mobile_puzzles.bin").c_str(), out, kMobilePuzzleSource) ||
           loadStages((root + "/dreamcast_puzzles.bin").c_str(), out, 4);
}

static bool challengeBoardsAvailable(const std::string& root) { Stages s; return loadStages((root + "/battle_stages.bin").c_str(), s, 3) && s.list.size() >= 25; }

struct App;
struct StarBackground {
    struct Star { float x, y, speed; int frame; };
    struct Twinkle { float x, y; int period, remaining; };
    std::array<Star, 322> stars;
    std::array<Twinkle, 161> twinkles;
    StarBackground() {
        // Use the original generator on a separate stream so visuals cannot affect play.
        Rng rng(1);
        for (auto& star : stars) {
            star.x = static_cast<float>(rng.u32() % GW);
            star.y = static_cast<float>(rng.u32() % GH);
            star.speed = (rng.u32() & 255) * (1.0f / 64) + 0.3f;
            star.frame = rng.u32() & 31;
        }
        for (auto& star : twinkles) {
            star.x = static_cast<float>(rng.u32() % GW);
            star.y = static_cast<float>(rng.u32() % GH);
            star.period = 3 + (rng.u32() & 63);
            star.remaining = rng.u32() % star.period;
        }
    }
    void tick(bool vertical) {
        for (auto& star : stars) {
            if (vertical) {
                star.y += 2.0f * star.speed;
                if (star.y > GH) star.y -= GH;
            } else {
                star.x = static_cast<float>(star.x - 1.5 * star.speed);
                if (star.x < 0.0f) star.x += GW;
            }
        }
        for (auto& star : twinkles) if (--star.remaining < 0) star.remaining = star.period;
    }
    void draw(App& a) const;
};

struct App {
    StarBackground stars;
    SDL_Window* win = nullptr; SDL_Renderer* ren = nullptr; std::string root, saveDir; RotatingLog log; PadMap padMap; QuitHold quitHold; Settings settings; ModelPack models3d; bool models3dTried = false, mobileSheetsMissing = false;
    bool useModels3d() { if (!models3dTried) { models3dTried = true; if (settings.models3d || getenv("CCR_MODELS")) models3d.load(ren, root + "/dreamcast/models.bin"); } return !models3d.models.empty(); }
    void saveSettings() { writeFile(saveDir + "/settings.ini", settingsText(settings)); }
    void savePadMap() { writeFile(saveDir + "/controls.ini", padMapText(padMap)); } bool headless = false, quit = false, vsync = true;
    int stageSet = 0;     // puzzle stage group: 0 = the 100 main stages, 1 = the 2,466 further GBA stages
    uint32_t clr[4] = {0, 0, 0, 0}; bool clrLoaded = false;   // VMU puzzle-cleared bits: word = stage / 25, bit = stage % 25 (VMU::isPuzzleCleared 0x37154); persisted in <assets>/progress.bin
    void loadProgress() { if (clrLoaded) return; clrLoaded = true; if (FILE* f = fopen((saveDir + "/progress.bin").c_str(), "rb")) { if (fread(clr, 4, 4, f) != 4) memset(clr, 0, sizeof clr); fclose(f); } if (getenv("CCR_CLEAR_ALL")) for (int i = 0; i < 4; i++) clr[i] = 0x1ffffff; }
    bool isCleared(int s) { loadProgress(); return s >= 0 && s < 100 && ((clr[s / 25] >> (s % 25)) & 1); }
    int maxStage() { if (settings.unlockAll) return 3; loadProgress(); for (int i = 0; i < 3; i++) if ((clr[i] & 0x1ffffff) != 0x1ffffff) return i; return 3; }   // VMU::getPuzzleMaxStage 0x372b4
    void setCleared(int s) { loadProgress(); if (s < 0 || s >= 100 || isCleared(s)) return; clr[s / 25] |= 1u << (s % 25); if (FILE* f = fopen((saveDir + "/progress.bin").c_str(), "wb")) { fwrite(clr, 4, 4, f); fclose(f); } }
    int nextStage = -1;   // stage chosen on the stage-select screen (consumed when the puzzle starts)
    Sheet atlas, cat, mouse, gold, digits, crowns, timefont, font;
    BattlePreviewAtlas battlePreviewAtlas;
    RouletteDraw rouletteDraw;
    Stages battlePreviewStages;
    bool battlePreviewLoaded = false;
    std::unique_ptr<SDL_Texture, decltype(&SDL_DestroyTexture)> battlePreviewTexture{nullptr, SDL_DestroyTexture};
    int battlePreviewKey = -1;

    std::vector<uint16_t> battlePreviewPixels(int stage, bool team) {
        if (!battlePreviewLoaded) {
            battlePreviewLoaded = true;
            loadStages((root + "/battle_stages.bin").c_str(), battlePreviewStages, 2);
            std::error_code error;
            for (const auto& entry : std::filesystem::directory_iterator(root + "/ios", error))
                if (battlePreviewAtlas.load(entry.path() / "ccrpad")) break;
        }
        if (stage < 0 || stage >= static_cast<int>(battlePreviewStages.list.size())) return {};
        return battlePreviewAtlas.compose(battlePreviewStages.list[stage].st, stage, team);
    }

    void drawBattlePreview(int stage, bool team, const SDL_Rect& dst) {
        int key = stage * 2 + team;
        if (battlePreviewKey != key) {
            battlePreviewKey = key;
            battlePreviewTexture.reset();
            const auto pixels = battlePreviewPixels(stage, team);
            if (pixels.empty()) return;
            battlePreviewTexture.reset(SDL_CreateTexture(ren, SDL_PIXELFORMAT_RGBA4444, SDL_TEXTUREACCESS_STATIC,
                                                         BattlePreviewAtlas::width, BattlePreviewAtlas::height));
            if (!battlePreviewTexture) return;
            if (SDL_UpdateTexture(battlePreviewTexture.get(), nullptr, pixels.data(),
                                  BattlePreviewAtlas::width * sizeof(uint16_t)) != 0) {
                battlePreviewTexture.reset();
                return;
            }
            SDL_SetTextureBlendMode(battlePreviewTexture.get(), SDL_BLENDMODE_BLEND);
        }
        if (battlePreviewTexture) SDL_RenderCopy(ren, battlePreviewTexture.get(), nullptr, &dst);
    }
    Sheet arw, cur, rk[4], hdTime, hdHud65, hdHud68, hdPhud, hdStageNum, hdFrame78, hdFont, hdFont1, hdPause, ssBg, ssBubble, ssCells, ssTab, ssPanel, ssArrows, ssHdr, hdBub9, hdBubTail, mnBg, mnBars, mnMasc, mnDeco, opBg, opHdr, langJa, opSnd, opSld, hlHdr, hlTab, hlFrm, hlDia, plPanels, plLabels, plBottom, plTiles; std::vector<std::string>* bubbleLog = nullptr; SDL_Texture* ssPrev = nullptr; int ssPrevKey = -1; std::vector<uint8_t> hdFontW, hdFontW1; std::map<int, std::string> hdText; std::map<int, int> hdTextMap; bool gameArtOk = false;   // original in-play art: arrows (r0645, frame = owner), cursors (r0732: frames 0..3 = players, 4 = square bracket), closed rocket sphere = frame 0 of r0651/r0663/r0675/r0687
    Sheet catV[3], mouseV[3], goldV[3]; bool walkOk = false;   // walk cycles per view (0 side, 1 back, 2 front): cat r0420/r0429/r0438 (20 frames), mouse r0491/r0495/r0499 and gold mouse r0472/r0476/r0480 (11 frames)
    Sheet tbg, tprompt, trocket, tlogo, mbg, mbtn, mdeco, dlogo, dpress; bool dlogoOk = false, dpressOk = false;
    Sheet dcArrows, dcPuzzleStart, dcPuzzleCancel, dcPuzzlePanel, dcPuzzleStage, dcPuzzleDigits, dcPuzzlePlate, dcPuzzleLabels, dcPause, dcPauseBoxes, dcPauseTeam, dcPauseMarks, dcCursors, dcCursorTrail, dcBattleHud;
    Sheet pbg, pprompt, procket, pdeco, pbtn, pmbg; bool padOk = false; bool titleOk = false, menuOk = false;   // iPad HD layout: the highest-resolution mobile art (tools/export_tilemaps.py, tools/export_pad_ui.py)
    Sheet phonePuzzleHud, phonePauseButton, phonePauseTitle, phonePausePanel;
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
    std::array<std::vector<int16_t>, 8> rouletteVoice, rouletteVoiceJapanese;

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
        if (headless) { if (!gpu) ccrSetEnv("SDL_VIDEODRIVER", "dummy", 1); ccrSetEnv("SDL_AUDIODRIVER", "dummy", 1); if (!gpu) SDL_SetHint(SDL_HINT_RENDER_DRIVER, "software"); }   // never take the user's screen/audio
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
        const bool mobileSheets = loadSheet(ret + "r0930", atlas) && loadSheet(ret + "r0447", cat) && loadSheet(ret + "r0503", mouse) && loadSheet(ret + "r0484", gold) && loadSheet(ret + "r0729", digits) &&
              loadSheet(ret + "r0726", crowns) && loadSheet(ret + "r0749", timefont) && loadSheet(ret + "r0023", font);
        if (!mobileSheets) {   // a Dreamcast-only install: the 3D model pack (cats, mice, rockets, floor, walls) carries the field and labels use the built-in bitmap font
            FILE* mp = fopen((root + "/dreamcast/models.bin").c_str(), "rb");
            if (!mp) { printf("missing sprite sheets in %s (tools/export_sprites.py <ccrret> <dir> all) and no Dreamcast model pack\n", ret.c_str()); return false; }
            fclose(mp); mobileSheetsMissing = true; printf("mobile sprite sheets not found: using the Dreamcast model pack and the built-in font\n");
        }
        titleOk = loadSheet(ret + "a0090", tbg) && loadSheet(ret + "a0097", tprompt) &&
                  loadSheet(ret + "a0100", trocket) && loadSheet(ret + "a0042", tlogo);
        menuOk = loadSheet(ret + "a0134", mbg) && loadSheet(ret + "a0113", mbtn) && loadSheet(ret + "a0110", mdeco);
        dlogoOk = loadSheet(ret + "dlogo", dlogo);
        dpressOk = loadSheet(ret + "dpress", dpress);
        loadSheet(ret + "dc_arrows", dcArrows);
        loadSheet(ret + "dc_puzzle_start", dcPuzzleStart);
        loadSheet(ret + "dc_puzzle_cancel", dcPuzzleCancel);
        loadSheet(ret + "dc_puzzle_panel", dcPuzzlePanel);
        loadSheet(ret + "dc_puzzle_stage", dcPuzzleStage);
        loadSheet(ret + "dc_puzzle_digits", dcPuzzleDigits);
        loadSheet(ret + "dc_puzzle_plate", dcPuzzlePlate);
        loadSheet(ret + "dc_puzzle_labels", dcPuzzleLabels);
        loadSheet(ret + "dc_pause", dcPause);
        loadSheet(ret + "dc_pause_boxes", dcPauseBoxes);
        loadSheet(ret + "dc_pause_team", dcPauseTeam);
        loadSheet(ret + "dc_pause_marks", dcPauseMarks);
        loadSheet(ret + "dc_cursors", dcCursors);
        loadSheet(ret + "dc_cursor_trail", dcCursorTrail);
        loadSheet(ret + "dc_battle_hud", dcBattleHud);
        padOk = (dlogoOk || imgSheet(7)) && loadSheet(ret + "bg0877", pbg) &&
                loadSheet(ret + "pprompt", pprompt) && loadSheet(ret + "procket", procket) &&
                loadSheet(ret + "pdeco", pdeco) && loadSheet(ret + "pbtn", pbtn) && loadSheet(ret + "bg0879", pmbg);
        titleOk = titleOk || padOk;
        loadStrings();
        const char* phoneLocale = getenv("CCR_LANG");
        const std::string phoneArt = ret + "phone_" + (phoneLocale ? phoneLocale : "en") + "/";
        loadSheet(phoneArt + "puzzle_hud", phonePuzzleHud);
        loadSheet(phoneArt + "pause_button", phonePauseButton);
        loadSheet(phoneArt + "pause_title", phonePauseTitle);
        loadSheet(ret + "phone_pause_panel", phonePausePanel);
        { static const char* cv[3] = {"r0420", "r0429", "r0438"}, *mv[3] = {"r0491", "r0495", "r0499"}, *gv[3] = {"r0472", "r0476", "r0480"}; walkOk = true;
          for (int k = 0; k < 3; k++) { walkOk = loadSheet(ret + cv[k], catV[k]) && loadSheet(ret + mv[k], mouseV[k]) && loadSheet(ret + gv[k], goldV[k]) && walkOk;
            loadFit(ret + "hd_cat" + std::to_string(k) + ".frames.bin", catV[k]); loadFit(ret + "hd_mouse" + std::to_string(k) + ".frames.bin", mouseV[k]); loadFit(ret + "hd_gold" + std::to_string(k) + ".frames.bin", goldV[k]); } }
        if (atlas.fr.size() >= 35 && atlas.fr[8].w == 37) {
            // Phone boards use 37px tiles, including the edge pixels the field builder crops.
            atlas.fit.assign(atlas.fr.size(), (CELL + 2.0f) / 37.0f);
            if (arw.fit.empty()) arw.fit.assign(arw.fr.size(), 66.0f / 37.0f);
            for (auto& rocket : rk) rocket.fit.assign(rocket.fr.size(), 1.8f);
            for (auto* views : {catV, mouseV, goldV})
                for (int view = 0; view < 3; ++view)
                    if (views[view].fit.empty()) views[view].fit.assign(views[view].fr.size(), 1.8f);
        }
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
        if (sfxDir.empty())
            for (auto& e : fs::directory_iterator(root + "/android", ec))
                if (fs::exists(e.path() / "audio_sfx" / "000.ogg")) { sfxDir = (e.path() / "audio_sfx").string(); break; }
        sfx.resize(29);
        if (!sfxDir.empty()) {
            const auto loadClip = [&](int id, const char* prefix, std::vector<int16_t>& clip) {
                char name[16];
                snprintf(name, sizeof name, "%s%03d.ogg", prefix, id);
                int ch, rate;
                short* pcm;
                const int frames = stb_vorbis_decode_filename((sfxDir + "/" + name).c_str(), &ch, &rate, &pcm);
                if (frames > 0) { toStereo44k(pcm, frames, ch, rate, clip); free(pcm); }
            };
            for (int i = 0; i < static_cast<int>(sfx.size()); ++i) loadClip(i, "", sfx[i]);
            for (int i = 0; i < static_cast<int>(rouletteVoice.size()); ++i) {
                loadClip(117 + i, "", rouletteVoice[i]);
                loadClip(117 + i, "J", rouletteVoiceJapanese[i]);
            }
        }
        if (headless && !getenv("CCR_AUDIO_TEST")) return;   // CCR_AUDIO_TEST=1: open the (dummy) audio device in headless runs to exercise the music code
        SDL_AudioSpec want{}; want.freq = 44100; want.format = AUDIO_S16SYS; want.channels = 2; want.samples = 1024; want.callback = audioCb; want.userdata = this; SDL_AudioSpec have;
        adev = SDL_OpenAudioDevice(nullptr, 0, &want, &have, 0); if (adev) SDL_PauseAudioDevice(adev, 0);
    }
    void playSfx(int id) {
        if (!adev) return;
        const std::vector<int16_t>* clip = nullptr;
        if (id >= 0 && id < static_cast<int>(sfx.size())) clip = &sfx[id];
        if (id >= 117 && id < 117 + static_cast<int>(rouletteVoice.size()))
            clip = lang == 5 ? &rouletteVoiceJapanese[id - 117] : &rouletteVoice[id - 117];
        if (!clip || clip->empty()) return;
        if (headless && id == 7 && getenv("CCR_CAT_AUDIO_TRACE"))
            printf("cat rocket clip 007.ogg %zu samples\n", clip->size());
        if (headless && id == 27 && getenv("CCR_CAT_AUDIO_TRACE"))
            printf("cat cue clip 027.ogg %zu samples\n", clip->size());
        if (headless && id >= 117 && getenv("CCR_ROULETTE_AUDIO_TRACE"))
            printf("roulette clip %s%03d.ogg %zu samples\n", lang == 5 ? "J" : "", id, clip->size());
        SDL_LockAudioDevice(adev);
        voices.push_back({clip, 0});
        SDL_UnlockAudioDevice(adev);
    }
    void loadSong(int n) {
        Song& sg = songs[n]; if (sg.tried) return; sg.tried = true; namespace fs = std::filesystem; std::error_code ec;
        char nm[16]; snprintf(nm, sizeof nm, "M%02d.ogg", n); std::vector<int16_t> mobile; int mobileFrames = 0;
        for (const char* platform : {"ios", "android"}) {
            for (auto& e : fs::directory_iterator(root + "/" + platform, ec)) {
                const auto path = (e.path() / "audio_song" / nm).string();
                if (!fs::exists(path)) continue;
                int ch, rate;
                short* pcm;
                int frames = stb_vorbis_decode_filename(path.c_str(), &ch, &rate, &pcm);
                if (frames <= 0) continue;
                toStereo44k(pcm, frames, ch, rate, mobile);
                free(pcm);
                mobileFrames = frames;
                break;
            }
            if (mobileFrames > 0) break;
        }
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
        if (!digits.tex || digits.fr.size() < 10) { text(std::to_string(v), x, y, hgt); return; }
        std::string s = std::to_string(v); int cx = x;
        for (char c : s) { const SDL_Rect& fr = digits.fr[c - '0']; int w = fr.w * hgt / fr.h; SDL_Rect d{cx, y, w, hgt}; SDL_RenderCopy(ren, digits.tex, &fr, &d); cx += w + 2; }
    }
    // Glyph sheet r0023 (frame = character code). Per-glyph record (36 bytes): u0 v0 u1 v1 floats, then int16 w, h, 64, 64, xoff, yoff (drawn at pen + offset, line top at y): the pen advances by xoff + w.
    // hgt is the cap height in pixels (cap glyphs are 39 sheet pixels tall).
    struct GlyphMet { int w = 0, h = 0, xo = 0, yo = 0; }; GlyphMet gm[256];
    void loadFontMetrics() { FILE* f = fopen((root + "/ret_all/r0023.frames.bin").c_str(), "rb"); if (!f) return; uint32_t n = 0; if (fread(&n, 4, 1, f) != 1) { fclose(f); return; }
        for (uint32_t i = 0; i < n && i < 256; i++) { uint8_t rec[36]; if (fread(rec, 1, 36, f) != 36) break; int16_t v[10]; memcpy(v, rec + 16, 20); gm[i] = {v[0], v[1], v[4], v[5]}; } fclose(f); }
    int textWidth(const std::string& s, int hgt) { if (!font.tex) { const int px = std::max(1, hgt / 7); return (int)s.size() * 6 * px; } float sc = hgt / 39.0f, w = 0; for (unsigned char c : s) w += gm[c].h ? (gm[c].xo + gm[c].w) * sc : 20 * sc; return (int)w; }
    void text(const std::string& s, int x, int y, int hgt) {
        if (!font.tex) {   // built-in bitmap font: one 5x7 glyph per character, white
            const int px = std::max(1, hgt / 7); int pen = x; SDL_SetRenderDrawColor(ren, 255, 255, 255, 255);
            for (unsigned char c : s) { if (const uint8_t* g = font57(c)) for (int row = 0; row < 7; row++) for (int col = 0; col < 5; col++) if (g[row] >> (4 - col) & 1) { SDL_Rect d{pen + col * px, y + row * px, px, px}; SDL_RenderFillRect(ren, &d); } pen += 6 * px; }
            return; }
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
    // Dreamcast board (models_3d): the floor is the game's single 180 x 135 quad textured with yuka01-06 (floor colour N = yuka N+1), each wall edge a kabetx01-03 piece (wall colour N = kabetx N+1),
    // both seen from straight above like the mobile board; holes, spawn markers and rocket rings still use the mobile atlas on top of the 3D floor (their Dreamcast models are not identified).
    bool board3d(int floorColor, int wallColor, FieldLayout field) {
        if (!useModels3d()) return false;
        const Model3D* floorM = models3d.find("floor"); const Model3D* wallM = models3d.find("wall"); if (!floorM || !wallM) return false;
        const int dcFloor = wallColor == 0 ? 0 : floorColor;   // Dreamcast Battle and Team Battle boards all use yuka01 (purple and tan), read from the 25 stage-select previews of the real game; other modes keep the mobile rule until their Dreamcast frames are checked
        const int mat = 29 + std::max(0, std::min(5, getenv("CCR_FLOOR3D") ? atoi(getenv("CCR_FLOOR3D")) : dcFloor)); if (mat >= (int)floorM->matTex.size()) return false;
        SDL_Texture* tex = models3d.textures[floorM->matTex[mat]];
        std::vector<SDL_Vertex> verts; verts.reserve(12 * 9 * 6);
        // Neutral floor modulation measured from the Dreamcast Normal Puzzle 01 capture.
        const SDL_Color floorLight{202, 202, 202, 255};
        for (int r = 0; r < 9; r++) for (int c = 0; c < 12; c++) {
            const float x0 = field.x(c), y0 = field.y(r);
            const float x1 = field.x(c + 1), y1 = field.y(r + 1);
            // The Dreamcast starts the checkerboard in the right-hand texture quarter.
            const float u0 = ((c + 1) & 1) * 0.5f, v0 = (r & 1) * 0.5f;
            const float u1 = u0 + 0.5f, v1 = v0 + 0.5f;
            SDL_Vertex a{{x0, y0}, floorLight, {u0, v0}}, b{{x1, y0}, floorLight, {u1, v0}}, d{{x1, y1}, floorLight, {u1, v1}}, e{{x0, y1}, floorLight, {u0, v1}};
            verts.push_back(a); verts.push_back(b); verts.push_back(d); verts.push_back(a); verts.push_back(d); verts.push_back(e);
        }
        SDL_RenderGeometry(ren, tex, verts.data(), (int)verts.size(), nullptr, 0);
        return true;
    }
    void walls3d(const Stage& st, int wallColor, FieldLayout field) {
        const Model3D* wallM = models3d.find("wall"); if (!wallM) return; const float k = field.cell / kCell; const int mat = 35 + std::max(0, std::min(2, wallColor));
        for (int r = 0; r <= kRows; ++r) {
            for (int c = 0; c < kCols; ++c) if (st.hw[r * kCols + c] || r == 0 || r == kRows) models3d.draw(ren, *wallM, field.x(c + 0.5f), field.y(r), k, 0.0f, 90.0f, 0.6f, -1, mat);
            if (r == kRows) break;
            for (int c = 0; c <= kCols; ++c) if (st.vw[r * (kCols + 1) + c] || c == 0 || c == kCols) models3d.draw(ren, *wallM, field.x(c), field.y(r + 0.5f), k, 90.0f, 90.0f, 0.6f, -1, mat);
        }
    }
    void board(const Stage& st, int floorColor, int wallColor, FieldLayout field = {}) {
        const bool three = board3d(floorColor, wallColor, field);
        static const int ring[9] = {0x1b, 0x1c, 0x1d, 0x22, 0x1a, 0x1e, 0x21, 0x20, 0x1f};
        for (int r = 0; r < 9; r++) for (int c = 0; c < 12; c++) {
            float ax = field.x(c + 0.5f), ay = field.y(r + 0.5f); uint8_t t = st.tiles[r * 12 + c];
            if (t == 0x11) { blit(atlas, 7, ax, ay, field.scale()); continue; }
            if (!three) blit(atlas, 8 + floorColor * 2 + ((c ^ r) & 1), ax, ay, 1.0f, 0.0, 1);
            if (t >= 1 && t <= 4) blit(atlas, 6, ax, ay, field.scale());
            else if (t >= 5 && t <= 8) {
                const Model3D* po = three ? models3d.find("hole_out") : nullptr; const Model3D* pi = three ? models3d.find("hole_in") : nullptr; const float k = field.cell / kCell;
                if (po && pi) { models3d.draw(ren, *po, ax, ay, k, 0.0f, 90.0f); models3d.draw(ren, *pi, ax, ay, k, 0.0f, 90.0f); }
                else blit(atlas, ring[(c >> 2) + 3 * (r / 3)], ax, ay, field.scale());
            }
        }
        if (three) { walls3d(st, wallColor, field.wallPlane()); return; }
        // HD 1.0 createPlayfield draws horizontal and vertical edge rows in
        // alternation. Keep its wall footprint and use the higher-resolution art.
        auto wall = [&](int frame, int x, int y, int w, int h) {
            SDL_Rect src = atlas.fr[frame];
            ++src.x;
            --src.w;
            SDL_Rect dst{static_cast<int>(field.x(x / float(CELL))), static_cast<int>(field.y(y / float(CELL))),
                         static_cast<int>(w * field.scale()), static_cast<int>(h * field.scale())};
            SDL_RenderCopy(ren, atlas.tex, &src, &dst);
        };
        for (int r = 0; r <= kRows; ++r) {
            for (int c = 0; c < kCols; ++c)
                if (st.hw[r * kCols + c]) wall(wallColor, c * CELL - 8, r * CELL - 11, 83, 24);
            if (r == kRows) break;
            for (int c = 0; c <= kCols; ++c)
                if (st.vw[r * (kCols + 1) + c]) wall(wallColor + 3, c * CELL - 9, r * CELL - 10, 23, 84);
        }
    }
    // Arrow sprite (image 0x5f, frame = owner; the art points up, rotated clockwise by the heading); a struck arrow is drawn at 0.7 (AR_ArrowDrawPriority).
    void arrow(int x, int y, int dir, int owner, int hits = 0, int ttl = -1, FieldLayout field = {}) {
        if (ttl >= 0 && !(ttl > 60 || (ttl > 0 && (ttl & 1)))) return;   // in the last 60 ticks the arrow flickers (drawn only on odd ticks)
        arrowIcon(field.x(x + 0.5f), field.y(y + 0.5f), dir, owner, (hits ? 0.7f : 1.0f) * field.scale());
    }
    void arrowIcon(float cx, float cy, int dir, int owner, float sc) {
        static const double rot[4] = {180.0, 270.0, 0.0, 90.0};
        if (settings.models3d && dcArrows.tex && dcArrows.fr.size() == 4) {
            // The Dreamcast texture points west and covers one cell.
            const SDL_Rect& src = dcArrows.fr[owner & 3];
            const float w = src.w * sc, h = src.h * sc;
            const SDL_FRect dst{cx - w / 2, cy - h / 2, w, h};
            SDL_RenderCopyExF(ren, dcArrows.tex, &src, &dst, rot[dir & 3] + 90.0,
                              nullptr, SDL_FLIP_NONE);
        } else {
            blit(arw, owner & 3, cx, cy, sc, rot[dir & 3]);
        }
    }
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
        if (FILE* f = fopen((saveDir + "/options.bin").c_str(), "rb")) { unsigned char c = 0; if (fread(&c, 1, 1, f) == 1 && c < 6 && !getenv("CCR_LANG")) lang = c; unsigned char v[2]; if (fread(v, 1, 2, f) == 2) { musicVol = v[0]; sfxVol = v[1]; } fclose(f); }
        if (!langAvailable(lang)) lang = 0; applyLocale(); }
    void saveOptions() { if (FILE* f = fopen((saveDir + "/options.bin").c_str(), "wb")) { unsigned char c[3] = {(unsigned char)lang, (unsigned char)std::max(0, std::min(255, musicVol)), (unsigned char)std::max(0, std::min(255, sfxVol))}; fwrite(c, 1, 3, f); fclose(f); } }
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

    bool useDcBattleHud() {
        return dcBattleHud.tex && dcBattleHud.fr.size() >= 31 &&
               (mobileSheetsMissing || useModels3d());
    }

    void dcBattleSprite(int frame, float x, float y, float width, float height) {
        constexpr float scale = GW / 640.0f;
        const SDL_FRect dst{x * scale, y * scale, width * scale, height * scale};
        SDL_RenderCopyF(ren, dcBattleHud.tex, &dcBattleHud.fr[frame], &dst);
    }

    // The Battle task (0x8c0272a0) submits these sprites at fixed screen
    // coordinates. SDL draws them from far to near instead of sorting by 1/w.
    // The left column shared by the Dreamcast Battle and Challenge screens (Flycast frames 3100 and Challenge A1): purple strip, planet clock, and the nine-rocket time gauge.
    void drawDcTimerColumn(int remainingFrames, int roundFrames) {
        auto sprite = [&](int frame, float x, float y, float width, float height) {
            dcBattleSprite(frame, x, y, width, height);
        };
        sprite(5, 32, 0, 128, 256);
        sprite(6, 32, 256, 128, 256);
        sprite(4, -16, 16, 256, 128);
        const int seconds = (remainingFrames + 59) / 60;
        const int timer[] = {seconds / 60 % 10, 10, seconds / 10 % 6, seconds % 10};
        for (int i = 0; i < 4; ++i) sprite(9 + timer[i], 36 + 16 * i, 55, 16, 32);
        const int lit = std::min(9, 10 * remainingFrames / std::max(1, roundFrames));
        // The rocket vertices use source-alpha additive blending.
        SDL_SetTextureBlendMode(dcBattleHud.tex, SDL_BLENDMODE_ADD);
        for (int i = 0; i < 9; ++i) {
            const bool on = i < lit;
            const int brightness = on ? 255 : 128;
            SDL_SetTextureColorMod(dcBattleHud.tex, i < 3 ? brightness : 0,
                                   i < 3 ? 113 * brightness / 255 : brightness,
                                   (i < 3 ? 57 : 227) * brightness / 255);
            SDL_SetTextureAlphaMod(dcBattleHud.tex, brightness);
            sprite(on ? 7 : 8, 55, 395 - 30 * i, 32, 32);
        }
        SDL_SetTextureColorMod(dcBattleHud.tex, 255, 255, 255);
        SDL_SetTextureAlphaMod(dcBattleHud.tex, 255);
        SDL_SetTextureBlendMode(dcBattleHud.tex, SDL_BLENDMODE_BLEND);
    }

    void drawDcBattleHud(const Scoreboard& score, const int (&cpuLevel)[4],
                         int remainingFrames, int roundFrames) {
        auto sprite = [&](int frame, float x, float y, float width, float height) {
            dcBattleSprite(frame, x, y, width, height);
        };
        drawDcTimerColumn(remainingFrames, roundFrames);
        for (int p = 0; p < 4; ++p) sprite(p, 127 + 120 * p, 368, 128, 88);
        for (int p = 0; p < 4; ++p) {
            const int value = std::max(0, score.player[p]);
            const int digits[] = {(value / 100) % 10, (value / 10) % 10, value % 10};
            for (int i = 0; i < 3; ++i)
                sprite(20 + digits[i], 139 + 120 * p + 32 * i, 403, 32, 32);
        }
        // CPU name plates (0x8c029a20) sit between the digits and the frame.
        for (int p = 0; p < 4; ++p)
            if (cpuLevel[p] >= 0) sprite(30, 132 + 120 * p, 370, 128, 32);
    }

    // The Dreamcast pause overlay (Flycast Puzzle pause frame and Battle pause frame): no dimming, nine quads on the 640 x 480 screen drawn here at 1.6 times that, far to near:
    // the PAUSED board, the bubbles with the cat, then the labels. Battle's is the same shifted up 60 pixels (dy = -60).
    void drawDcPause(float dy, float playerPlateY = -1.0f) {
        if (!dcPause.tex) return;
        struct Part { SDL_Rect src; float x, y, w, h; bool flip; };
        static const Part parts[] = {
            {{0, 0, 256, 256}, 132, 144, 256, 256, false}, {{256, 0, 128, 256}, 388, 144, 128, 256, false},
            {{0, 256, 128, 64}, 133, 199, 128, 64, false}, {{384, 128, 32, 64}, 255, 199, 32, 64, false},
            {{128, 256, 128, 64}, 379, 199, 128, 64, false}, {{416, 128, 32, 64}, 353, 199, 32, 64, true},
            {{384, 0, 64, 128}, 285, 196, 64, 128, true},
            {{256, 256, 128, 32}, 144, 205, 128, 32, false}, {{384, 256, 128, 32}, 400, 205, 128, 32, false}};
        for (const Part& pt : parts) {
            const SDL_Rect dst{(int)std::lround(pt.x * 1.6f), (int)std::lround((pt.y + dy) * 1.6f), (int)std::lround(pt.w * 1.6f), (int)std::lround(pt.h * 1.6f)};
            SDL_RenderCopyEx(ren, dcPause.tex, &pt.src, &dst, 0.0, nullptr, pt.flip ? SDL_FLIP_HORIZONTAL : SDL_FLIP_NONE);
        }
        if (playerPlateY >= 0) {   // "Player 1" plate, 256 x 64 at x 230 (Battle y 270, Challenge y 400 in Flycast frames)
            const SDL_Rect src{0, 320, 256, 64}, dst{368, (int)std::lround(playerPlateY * 1.6f), 410, 102};
            SDL_RenderCopy(ren, dcPause.tex, &src, &dst);
        }
    }

    // Dreamcast Team Battle HUD (Flycast Team Battle frame 3600): the shared left column, two 256 x 88 team panels (blue and red, orange and green), one three-digit team score
    // in each, and the 128 x 32 Computer plates of the CPU players. Frames 39 and 40 are the panels.
    void drawDcTeamHud(const Scoreboard& score, const int (&cpuLevel)[4], int remainingFrames, int roundFrames) {
        drawDcTimerColumn(remainingFrames, roundFrames);
        dcBattleSprite(39, 124, 384, 256, 88);
        dcBattleSprite(40, 368, 383, 256, 88);
        for (int t = 0; t < 2; ++t) {
            const int value = std::max(0, score.team[t]);
            const int digits[] = {(value / 100) % 10, (value / 10) % 10, value % 10};
            for (int i = 0; i < 3; ++i) dcBattleSprite(20 + digits[i], (t == 0 ? 254 : 382) + 32 * i, 402, 32, 32);
        }
        static const float plate[4][2] = {{135, 387}, {485, 387}, {135, 417}, {485, 417}};
        for (int p = 0; p < 4; ++p)
            if (cpuLevel[p] >= 0) dcBattleSprite(30, plate[p][0], plate[p][1], 128, 32);
    }

    void drawDcTeamCrowns(int tick, const Scoreboard& score) {
        if ((tick & 31) <= 10 || (score.team[0] == 0 && score.team[1] == 0)) return;
        for (int t = 0; t < 2; ++t) {
            const int rank = score.team[t] < score.team[1 - t] ? 1 : 0;
            const int radius = rank == 0 ? 31 : 23, size = (radius + 1) * 2;
            dcBattleSprite(31 + rank, (t == 0 ? 304 : 424) - radius - 1, 371 - radius - 1, size, size);
        }
    }

    void drawDcScoreCrowns(int tick, const Scoreboard& score, const int (&ranks)[4]) {
        if ((tick & 31) <= 10 || std::all_of(score.player, score.player + 4,
                                             [](int value) { return value == 0; })) return;
        for (int p = 0; p < 4; ++p) {
            const int rank = ranks[p];
            const int radius = rank == 0 ? 31 : 23;
            const int size = (radius + 1) * 2;
            dcBattleSprite(31 + rank, 218 + 120 * p - radius, 360 - radius, size, size);
        }
    }

    // Tag update at 0x8c013e5e. A full 16-tick bob sums to zero.
    void drawDcPlayerTag(int player, int tick, SDL_FPoint start) {
        constexpr int release = 180;
        constexpr float step = 6.283185307f / 16.0f;
        for (int i = 0; i < std::min(tick, release) % 16; ++i)
            start.y -= 2.5f * std::sin(i * step);
        const int fall = std::max(0, tick - release);
        const float angle = (1 - 4 * player) * step;
        start.x += fall * std::cos(angle);
        start.y += fall * (std::sin(angle) + 0.1f * (fall + 1));
        if (start.y < 480) dcBattleSprite(35 + player, start.x, start.y, 208, 52);
    }

    // HD 1.0 iPad renderFourBattleHud and renderTeamBattleHud (-788),
    // followed by score4pb2D or scoreteam2D (-784) before the field (-780).
    void drawBattleHud(bool team, bool showScores, const Scoreboard& score) {
        auto panel = [&](int id, int frame, float x, float y, int alpha = 255) {
            if (imgLog || (id != 0x65 && id != 0x68)) {
                drawImage(id, frame, x, y, 0, 1.0f, alpha);
            } else {
                Sheet& sheet = id == 0x65 ? hdHud65 : hdHud68;
                if (!sheet.tex) return;
                SDL_SetTextureAlphaMod(sheet.tex, static_cast<Uint8>(alpha));
                blit(sheet, frame, x, y);
                SDL_SetTextureAlphaMod(sheet.tex, 255);
            }
        };
        for (int frame = 6; frame <= 13; ++frame) panel(0x68, frame, 82, 62 + 92 * (frame - 6));
        panel(0x68, 0, 68, 88);
        if (team) {
            panel(0x6a, 8, 374, 685);
            panel(0x68, 4, 319, 703, 222);
            panel(0x6a, 9, 759, 685);
            panel(0x68, 4, 815, 704, 222);
            panel(0x68, 4, 814, 667, 222);
        } else {
            for (int p = 0; p < 4; ++p) {
                float x = 280 + 192 * p;
                panel(0x65, p, x, 680);
                if (p != 0) panel(0x68, 4, x - 1, 658);
            }
        }
        panel(0x68, 5, 82, 720);
        if (!showScores) return;

        for (int p = 0; p < (team ? 2 : 4); ++p) {
            const int value = team ? score.team[p] : score.player[p];
            const int glyphs[] = {(value / 100) % 10, (value / 10) % 10, value % 10};
            const float x = team ? 404 + 268 * p : 250 + 192 * p;
            const float y = team ? 685 : 691;
            for (int k = 0; k < 3; ++k) {
                if (imgLog || imgSheet(0x5f)) panel(0x5f, glyphs[k], x + k * 30, y);
                else blit(digits, glyphs[k], x + k * 30, y);
            }
        }
    }
    // RankCrawnDrawPriority (0x28f) runs after field objects and before the cursor ring.
    void drawBattleRankOverlay(bool team, bool paused, int tick, const Scoreboard& score,
                               const int (&ranks)[4], const int (&wins)[4], const int (&rockets)[4][2],
                               bool dcScoreCrowns = false, FieldLayout field = {}) {
        if ((tick & 31) <= 10) return;
        const int* scores = team ? score.team : score.player;
        const int count = team ? 2 : 4;
        int total = 0;
        for (int p = 0; p < count; ++p) total += scores[p];
        auto crown = [&](int rank, float x, float y, float scale) {
            if (imgLog || imgSheet(0x5e)) drawImage(0x5e, rank, x, y, 0, scale, 255);
            else blit(crowns, rank, x, y, scale);
        };
        auto rocketCrown = [&](int slot) {
            const double worldX = 14.5 * rockets[slot][0] + 19.5;
            const float worldY = 14.5f * rockets[slot][1] + 3.0f;
            crown(0, field.x(static_cast<float>(worldX / kCell)), field.y(worldY / kCell), field.scale());
        };
        for (int p = 0; p < count; ++p) {
            // GameWinRocketDraw uses the accumulated wins, even at zero score.
            if (!team || !paused) {
                const float start = team ? 298 + 496 * p : 234 + 192 * p;
                const float step = team ? 14 : 12;
                for (int w = 0; w < wins[p]; ++w)
                    drawImage(0x67, team ? p + 4 : p, start + step * w, team ? 644 : 640, 0, 1.0f, 255);
            }
            if (total == 0) continue;
            const int rank = team ? scores[p] < scores[1 - p] : ranks[p];
            const float x = team ? 430 + 270 * p : 324 + 192 * p;
            const float y = team ? 640 : 644;
            if (!dcScoreCrowns) crown(rank, x, y, rank == 0 ? 1.3f : 1.0f);
            if (rank == 0) {
                rocketCrown(p);
                if (team) rocketCrown(p + 2);
            }
        }
    }
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
    bool useDcCursors() {
        return dcCursors.tex && dcCursors.fr.size() == 4 && (!cur.tex || useModels3d());
    }
    void dcCursorAt(Sheet& sheet, float x, float y, int player, float size) {
        const SDL_FRect dst{x - size / 2, y - size / 2, size, size};
        SDL_RenderCopyF(ren, sheet.tex, &sheet.fr[player], &dst);
    }
    void drawDcBattlePadCursor(float x, float y, int player, int ticks) {
        if (!useDcCursors()) {
            cursorAt(x, y, player, ticks, false, dcBattleField.scale());
            return;
        }
        const float phase = (player * 4 + ticks % 16) * (6.283185307f / 16.0f);
        const float half = 32.0f * (1.0f + 0.1f * std::sin(phase));
        dcCursorAt(dcCursors, x + half, y + half, player, 2 * half);
    }
    void cursorAt(float x, float y, int player, int ticks, bool bracket = false, float fieldScale = 1.0f) {
        int ang = (player << 14) + 0x1000 * ticks;
        float phase = (bracket ? 2.0f : 1.0f) * ang * 6.283185307f / 65536.0f;
        const float scale = fieldScale * (1.0f + (bracket ? 0.075f : 0.1f) * std::sin(phase));
        if (!bracket && useDcCursors()) dcCursorAt(dcCursors, x, y, player, CELL * scale);
        else blit(cur, bracket ? 4 : player & 3, x, y, scale);
    }
    void cursor(int cx, int cy, int player, int ticks, bool bracket = false, FieldLayout field = {}) {
        cursorAt(field.x(cx + 0.5f), field.y(cy + 0.5f), player, ticks, bracket, field.scale());
    }
    void cursorGhost(float x, float y, int player, Uint8 opacity, float cell) {
        SDL_SetTextureAlphaMod(dcCursorTrail.tex, opacity);
        dcCursorAt(dcCursorTrail, x, y, player, cell);
        SDL_SetTextureAlphaMod(dcCursorTrail.tex, 255);
    }
    // Turn animation exactly as the original (Core::adjustAngle/diffAngle, entity fields +0x20 current angle, +0x24 target = heading << 14, +0x28 step = int(speed * 32768 / 12)):
    // the sprite sheets are 32-angle turntables, frame = angle >> 11. Called once per simulation tick.
    std::vector<int> angs; std::vector<float> cphase; int gtime = 0;   // cat walk phase (+0.45 per tick, wraps at 20.0: FUN_00028ffc), global tick for the mouse walk frame (TI_GetGlobalTime mod 11: FUN_000353e0)
    void stepAngles(const Sim& sim, bool effectsOnly = false) {
        if (!effectsOnly) {
            gtime++; while (cphase.size() < sim.ents.size()) cphase.push_back(0.0f);
            for (size_t i = 0; i < sim.ents.size(); i++) {
                const Entity& e = sim.ents[i];
                if (e.mouse || !e.alive || e.rocketIn || e.catRespawned || (e.catWalkScale >= 0.0f && !e.reg)) continue;
                cphase[i] += 0.45f;
                if (cphase[i] >= 20.0f) cphase[i] -= 20.0f;
            }
        }
        while (angs.size() < sim.ents.size()) angs.push_back(sim.ents[angs.size()].heading << 14);
        for (size_t i = 0; i < sim.ents.size(); i++) {
            const Entity& e = sim.ents[i];
            if (e.fallingInHole()) {
                if (e.drawsHoleFall() && sim.now > e.catHoleFallTick) angs[i] = (angs[i] + 0x1000) & 0xffff;
            } else if (e.rocketIn) {
                const float entryScale = e.catWalkScale < 0.0f ? 1.0f : e.catWalkScale;
                if (e.rocketCounter > 0.0f && e.rocketCounter < entryScale) angs[i] += 0x1000;
            } else if (!effectsOnly) {
                if (e.catRespawned) angs[i] = ((e.heading << 14) + 0x1000) & 0xffff;
                else angs[i] = stepAngle(angs[i], e.heading, e.mouse ? sim.mouseSpeed : sim.catSpeed);
            }
        }
    }
    struct FieldObject {
        int depth;
        float x, z;
        size_t index;
        bool rocket;
        bool ghost = false;
    };
    std::vector<FieldObject> fieldObjects;
    // Dreamcast 3D characters (docs/dreamcast_models.md): the basic mouse plays its eight keyframes by the low three bits of the shared clock (0x8c019b0c writes them, 0x8c019e26 draws the frame
    // directly); the cat plays its 24-frame walk cycle from the walk phase (provisional mapping). Orientation: the heading angle (heading << 14) turns the model about the vertical axis.
    bool draw3dCharacter(const Entity& en, size_t i, int ang, float x, float z,
                         int mouseFrame, float cell) {
        const Model3D* m = en.mouse ? models3d.find("mouse" + std::to_string(mouseFrame)) : models3d.find("cat");
        if (!m) return false;
        const float turn = (float)(ang & 0xffff) * (360.0f / 65536.0f);
        // Matched against Flycast Normal Puzzle 01 and 02 (docs/dreamcast_models.md): the mouse turns by -angle; the cat keeps the earlier 180 - angle until a real frame checks it.
        static const int catYawMode = getenv("CCR_CAT_YAW") ? atoi(getenv("CCR_CAT_YAW")) : 1;   // the field cat callback 0x8c011060 applies njRotateY(-angle) like the mouse: 1 = -a is the default; comparison values 0 = 180 - a, 2 = a, 3 = 180 + a, 4 = 0, 5 = 180
        const float yaw = en.mouse ? -turn : catYawMode == 1 ? -turn : catYawMode == 2 ? turn : catYawMode == 3 ? 180.0f + turn : catYawMode == 4 ? 0.0f : catYawMode == 5 ? 180.0f : 180.0f - turn;
        const float scale = cell * (en.mouse ? 0.072f : 0.075f);   // 0.075 against Flycast Normal 25 once the yaw was fixed (0.066 was too small, 0.085 a little large)
        const int catFrame = (i < cphase.size() ? (int)(cphase[i] * 1.2f) : 0) % 24;   // the walk phase (0.45 per tick, wraps at 20) stretched over the 24 frames: provisional, the Dreamcast phase rule is not decoded
        // The original tilts both characters by -8192 (45 degrees) before drawing (0x8c0193e0, 0x8c0117c0); CCR_CHAR_PITCH overrides for comparisons.
        static const float pitchOverride = getenv("CCR_CHAR_PITCH") ? static_cast<float>(atof(getenv("CCR_CHAR_PITCH"))) : 45.0f;
        static const float catPitch = getenv("CCR_CAT_PITCH") ? static_cast<float>(atof(getenv("CCR_CAT_PITCH"))) : -999.0f;   // comparison only
        const float pitch = (!en.mouse && catPitch > -900.0f) ? catPitch : pitchOverride;
        static const uint64_t catSkip = getenv("CCR_CAT_SKIP") ? (uint64_t)strtoull(getenv("CCR_CAT_SKIP"), nullptr, 0) : 0;   // comparison only: bit n skips material n of the cat
        models3d.draw(ren, *m, x, z + cell * 0.22f, scale, yaw, pitch, 1.0f, en.mouse ? -1 : catFrame, -1, en.mouse ? 0 : catSkip);
        (void)i; return true;
    }
    void drawFieldObjects(const Sim& sim, std::vector<std::pair<float, float>>& prev,
                          float alpha, const float* puku = nullptr, FieldLayout field = {},
                          bool dcProjection = false, int soloRocket = 0) {
        // The Dreamcast resets the clock on stage load and samples it before advancing the task loop.
        const int mouseFrame = std::max(0, sim.now - 1) & 7;
        fieldObjects.clear();
        auto rocket = [&](int x, int y, int player) {
            float z = (y + 0.5f) * kCell;
            fieldObjects.push_back({static_cast<int>(z), (x + 0.5f) * kCell, z,
                                    static_cast<size_t>(player), true});
        };
        if (puku) {
            for (int p = 0; p < 4; ++p) rocket(sim.rocketPos[p][0], sim.rocketPos[p][1], p);
        } else {
            for (int y = 0; y < kRows; ++y)
                for (int x = 0; x < kCols; ++x)
                    if (sim.coll[y][x] & kRocket) rocket(x, y, dcProjection ? soloRocket : 0);   // Dreamcast domes: Puzzle's single rocket is the blue lid, Challenge A1's is red (Flycast frames)
        }

        while (prev.size() < sim.ents.size()) prev.push_back({sim.ents[prev.size()].x, sim.ents[prev.size()].z});
        size_t ghostIndex = 0;
        for (size_t i = 0; i <= sim.ents.size(); ++i) {
            while (ghostIndex < sim.effects.size() && sim.effects[ghostIndex].submission == i) {
                const auto& ghost = sim.effects[ghostIndex];
                if (ghost.age > 0)
                    fieldObjects.push_back({std::max(-64, static_cast<int>(ghost.z)), ghost.x, ghost.z,
                                            ghostIndex, false, true});
                ++ghostIndex;
            }
            if (i == sim.ents.size()) break;
            const Entity& en = sim.ents[i];
            if (en.drawsHoleFall() || en.drawsRocketEntry()) {
                fieldObjects.push_back({std::max(-64, static_cast<int>(en.z)), en.x, en.z, i, false});
                continue;
            }
            if (!en.alive || en.done || en.rocketIn) continue;
            float x = prev[i].first + (en.x - prev[i].first) * alpha;
            float z = prev[i].second + (en.z - prev[i].second) * alpha;
            if (en.catRespawned || std::fabs(en.x - prev[i].first) > 100 || std::fabs(en.z - prev[i].second) > 100) { x = en.x; z = en.z; }
            fieldObjects.push_back({static_cast<int>(en.z), x, z, i, false});
        }

        // HD 1.0 adds these sprites to the same render list using truncated
        // world Z. Equal-depth sprites keep their submission order.
        std::stable_sort(fieldObjects.begin(), fieldObjects.end(),
                         [](const FieldObject& a, const FieldObject& b) { return a.depth < b.depth; });
        for (const FieldObject& object : fieldObjects) {
            const float x = field.x(object.x / kCell), z = field.y(object.z / kCell);
            size_t i = object.index;
            if (object.ghost) {
                const auto& ghost = sim.effects[i];
                drawImage(ghost.image(), ghost.age & 7, x, z, ghost.flags(), ghost.scale() * field.scale(), 255);
                if (headless && getenv("CCR_MOUSE_GHOST_LIVE_TRACE"))
                    printf("mouse ghost %d %.3f %.3f\n", ghost.age, x, z);
                continue;
            }
            if (object.rocket) {
                if (dcProjection) {
                    static constexpr const char* lids[] = {"lid1", "lid2", "lid3", "lid4"};
                    if (const auto* lid = models3d.find(lids[i])) {
                        models3d.drawDcRocketDome(ren, *lid, {x, z}, {GW / 2.0f, GH / 2.0f},
                                                 field.cell / kCell, puku ? puku[i] : 1.0f);
                        continue;
                    }
                }
                blit(rk[i], 0, x, z, (puku ? puku[i] : 1.0f) * 0.8f * field.scale());
                continue;
            }
            const Entity& en = sim.ents[i];
            int ang = (i < angs.size() ? angs[i] : en.heading << 14);
            if (useModels3d() && !en.drawsHoleFall() && !en.rocketIn && en.catWalkScale < 0.0f && draw3dCharacter(en, i, ang, x, z, mouseFrame, field.cell)) continue;
            if (en.drawsHoleFall()) {
                drawImage(0x2b, (ang & 0xffff) >> 11, x, z, 0, en.rocketCounter * field.scale(), 255);
                if (headless && getenv("CCR_CAT_HOLE_TRACE"))
                    printf("cat hole %d %.3f %.3f %.6f\n", (ang & 0xffff) >> 11, x, z, en.rocketCounter);
                continue;
            }
            const float walkScale = en.rocketIn ? en.rocketCounter : (en.catWalkScale < 0.0f ? 1.0f : en.catWalkScale);
            if (en.rocketIn || en.catWalkScale >= 0.0f) {
                const unsigned angle = static_cast<unsigned>(ang);
                const int image = angle >= 0x6001 && angle <= 0xa000 ? 41 :
                                  angle >= 0x2001 && angle <= 0xe000 ? 40 : 42;
                if (imgSheet(image)) {
                    const int frame = i < cphase.size() ? static_cast<int>(cphase[i]) : 0;
                    const int flags = image == 40 && angle < 0x8000 ? 2 : 0;
                    if (walkScale > 0.0f) drawImage(image, frame, x, z, flags, walkScale * field.scale(), 255);
                    if (headless && getenv("CCR_CAT_HOLE_TRACE") && (en.rocketIn || walkScale < 1.0f))
                        printf("cat %s %d %d %.3f %.3f %.6f\n", en.rocketIn ? "rocket" : "return", image, frame, x, z, walkScale);
                    continue;
                }
            }
            if (walkScale == 0.0f) continue;
            if (walkOk) {   // original view choice (CA_CatDrawSTPriority / FUN_0003582c, literals from the code): back view for angles in [0x6001, 0xA000], front outside [0x2001, 0xE000], side otherwise
                unsigned a = (unsigned)ang & 0xffff; int view = (a >= 0x6001 && a <= 0xA000) ? 1 : ((a < 0x2001 || a > 0xE000) ? 2 : 0);
                Sheet& sh = !en.mouse ? catV[view] : (en.type == 1 ? goldV[view] : mouseV[view]);
                int frame = !en.mouse ? (i < cphase.size() ? (int)cphase[i] : 0) : gtime % 11; frame = std::min(frame, (int)sh.fr.size() - 1);
                const SDL_Rect& fr = sh.fr[frame]; const SDL_Point& of = sh.off[frame]; float sc = walkScale * (field.cell / 64.0f); if (frame < (int)sh.fit.size()) sc *= sh.fit[frame];   // drawn at the original iPad (HD 1.0) frame size
                SDL_Rect dst{(int)std::lround(x + of.x * sc), (int)std::lround(z + of.y * sc), (int)std::lround(fr.w * sc), (int)std::lround(fr.h * sc)};
                bool flip = view == 0 && a > 0x2000 && a < 0x8000;   // the side art faces east; west-facing is mirrored (unverified: the flag the original passes to drawImage is not in the decompile)
                SDL_RenderCopyEx(ren, sh.tex, &fr, &dst, 0.0, nullptr, flip ? SDL_FLIP_HORIZONTAL : SDL_FLIP_NONE); continue;
            }
            Sheet& sh = !en.mouse ? cat : (en.type == 1 ? gold : mouse);
            const SDL_Rect& fr = sh.fr[(ang >> 11) & 31]; float sc = walkScale * field.cell * 0.95f / fr.w; int dw = (int)(fr.w * sc), dh = (int)(fr.h * sc);
            SDL_Rect dst{(int)(x) - dw / 2, (int)(z) - dh * 2 / 3, dw, dh}; SDL_RenderCopy(ren, sh.tex, &fr, &dst);
        }
    }
};

void StarBackground::draw(App& a) const {
    if (!a.imgSheet(154)) return;
    for (const auto& star : stars) a.drawImage(154, star.frame, star.x, star.y, 0, 1.0f, 128);
    for (const auto& star : twinkles)
        if (star.remaining * 2 < star.period) a.drawImage(154, 11, star.x, star.y, 0, 1.0f, 128);
}

static App* gApp = nullptr;   // for sound hooks
struct Screen { virtual ~Screen() {} virtual void event(App&, const SDL_Event&) {} virtual void tick(App&) {} virtual void draw(App&, float) {} virtual int music() { return -1; } virtual const char* next() { return nullptr; } };

// Developer/preview screen: the Dreamcast 3D character models drawn live (cat, and the basic mouse's eight walk keyframes played as an animation). Start with: ccr <assets> models
struct ModelViewerMode : Screen {
    ModelPack pack; bool loaded = false; int tickCount = 0; bool leave = false;
    bool load(App& a) { loaded = pack.load(a.ren, a.root + "/dreamcast/models.bin"); return loaded; }
    void event(App&, const SDL_Event& e) override { if (e.type == SDL_KEYDOWN && e.key.keysym.sym == SDLK_ESCAPE) leave = true; }
    void tick(App&) override { tickCount++; }
    const char* next() override { if (!leave) return nullptr; leave = false; return "MENU"; }
    void draw(App& a, float) override {
        SDL_RenderSetLogicalSize(a.ren, GW, GH); SDL_RenderSetViewport(a.ren, nullptr); SDL_SetRenderDrawColor(a.ren, 70, 80, 110, 255); SDL_RenderClear(a.ren);
        const float yaw = (float)(tickCount % 360);
        if (const Model3D* cat = pack.find("cat")) pack.draw(a.ren, *cat, 280.0f, 560.0f, 12.0f, yaw, 10.0f, 1.0f, (tickCount / 3) % 24);   // the head morphs through its 24 frames
        const int frame = (tickCount / 3) % 8;   // the walk cycle: eight keyframe meshes
        if (const Model3D* mouse = pack.find("mouse" + std::to_string(frame))) pack.draw(a.ren, *mouse, 740.0f, 520.0f, 20.0f, yaw, 10.0f);
        if (getenv("CCR_CANDS")) { int n = 0; for (int i = 0; i < 64; i++) { char nm[16]; snprintf(nm, sizeof nm, "h_%x", 0); (void)nm; } static const unsigned offs[21] = {0xaa370, 0xaa46c, 0xaa760, 0xaaa54, 0xab03c, 0xab180, 0xab290, 0xab674, 0xabe04, 0xac3e4, 0xade98, 0xb0c7c, 0xb0db4, 0xb0eec, 0xb1024, 0xb1178, 0xb1274, 0xb1370, 0xb146c, 0xb15c0, 0xb16bc}; for (unsigned o : offs) { char nm[24]; snprintf(nm, sizeof nm, "h_%x", o); if (const Model3D* m = pack.find(nm)) { float mx = 1.0f; for (const auto& t : m->tris) for (int k = 0; k < 3; k++) mx = std::max(mx, std::max(std::fabs(t.v[k].x), std::max(std::fabs(t.v[k].y), std::fabs(t.v[k].z)))); const float sc = 60.0f / mx; const float cx = 90.0f + 170.0f * (n % 6), cy = 120.0f + 150.0f * (n / 6); pack.draw(a.ren, *m, cx, cy, sc, 0.0f, 90.0f); a.text(nm + 2, 18, (int)cx - 30, (int)cy + 62); n++; } } return; }
        if (getenv("CCR_CAMFIT")) {   // pitch comparison against the Dreamcast frame: cat and mouse at pitches 30..80 (columns), cat yaw 180 and mouse yaw 0 (their fronts)
            const Model3D* cat = pack.find("cat"); const Model3D* mo = pack.find("mouse0");
            for (int i = 0; i < 6; i++) { const float pitch = 20.0f + 10.0f * i; if (cat) { pack.draw(a.ren, *cat, 90.0f + 160.0f * i, 130.0f, 5.2f, 180.0f, pitch, 1.0f, 17); pack.draw(a.ren, *cat, 90.0f + 160.0f * i, 330.0f, 5.2f, 0.0f, pitch, 1.0f, 17); } if (mo) { pack.draw(a.ren, *mo, 90.0f + 160.0f * i, 500.0f, 7.0f, 180.0f, pitch); } }
            a.text("PITCH 30 40 50 60 70 80", 24, 14, 24); return; }
        if (getenv("CCR_LIGHTFIT")) { if (const Model3D* cat = pack.find("cat")) for (int i = 0; i < 4; i++) pack.draw(a.ren, *cat, 130.0f + 250.0f * i, 400.0f, 18.0f, 180.0f - 90.0f * i, 10.0f, 1.0f, 17); return; }
        if (getenv("CCR_MOUSEFIT")) { if (const Model3D* mo = pack.find("mouse0")) for (int i = 0; i < 4; i++) pack.draw(a.ren, *mo, 140.0f + 240.0f * i, 330.0f, 22.0f, 90.0f * i, 12.0f, 1.0f); a.text("MOUSE YAW 0 90 180 270", 24, 14, 24); return; }
        if (getenv("CCR_PITCHFIT")) { if (const Model3D* cat = pack.find("cat")) for (int i = 0; i < 4; i++) { pack.draw(a.ren, *cat, 140.0f + 240.0f * i, 330.0f, 9.0f, 180.0f, 10.0f + 10.0f * i, 1.0f, 0); pack.draw(a.ren, *cat, 140.0f + 240.0f * i, 640.0f, 9.0f, 0.0f, 10.0f + 10.0f * i, 1.0f, 0); } a.text("PITCH 10 20 30 40  FRONT / BACK", 24, 14, 24); return; }
        static const char* rk[4] = {"rocket_blue", "rocket_orange", "rocket_red", "rocket_green"};
        for (int i = 0; i < 4; i++) if (const Model3D* m = pack.find(rk[i])) pack.draw(a.ren, *m, 120.0f + 230.0f * i, 690.0f, 7.0f, yaw * 0.5f + 40.0f * i, 25.0f);
        if (const Model3D* m = pack.find("lid1")) pack.draw(a.ren, *m, 120.0f, 250.0f, 12.0f, yaw, 25.0f);
        if (const Model3D* m = pack.find("wall")) pack.draw(a.ren, *m, 940.0f, 250.0f, 6.0f, yaw, 25.0f);
        a.text("DREAMCAST MODELS  CAT (24 FRAME HEAD MORPH)  MOUSE (8 FRAME WALK)  ESC BACK", 24, 14, 24);
    }
};

struct StartupMode : Screen {
    Startup splash;
    static bool available(App& app) {
        for (int i = 3; i <= 5; ++i) {
            const auto* sheet = app.imgSheet(i);
            if (!sheet || sheet->fr.empty()) return false;
        }
        return true;
    }
    void tick(App& app) override {
        if (splash.tick(1000000.0f / 60.0f)) app.playSong(14);
    }
    void event(App&, const SDL_Event& event) override {
        if ((event.type == SDL_KEYDOWN && !event.key.repeat) || event.type == SDL_MOUSEBUTTONDOWN ||
            event.type == SDL_FINGERDOWN || event.type == SDL_CONTROLLERBUTTONDOWN) splash.press();
    }
    const char* next() override { return splash.phase == Startup::Title ? "TITLE" : nullptr; }
    void draw(App& app, float) override {
        SDL_RenderSetLogicalSize(app.ren, GW, GH);
        const bool sonic = splash.image() == 5;
        SDL_SetRenderDrawColor(app.ren, sonic ? 112 : 255, sonic ? 192 : 255, sonic ? 240 : 255, 255);
        SDL_RenderClear(app.ren);
        const auto* sheet = app.imgSheet(splash.image());
        const auto& frame = sheet->fr[0];
        const int w = sheet->sz[0].x - 2, h = sheet->sz[0].y - 2;
        const int trimTop = sonic ? 0 : 1;
        const SDL_Rect source{frame.x + 1, frame.y + 1 + trimTop, w, h - trimTop};
        const SDL_Rect destination{(GW - w) / 2, (GH - h) / 2 + trimTop, w, h - trimTop};
        SDL_SetTextureAlphaMod(sheet->tex, static_cast<Uint8>(splash.opacity()));
        SDL_RenderCopy(app.ren, sheet->tex, &source, &destination);
        SDL_SetTextureAlphaMod(sheet->tex, 255);
        if (const int alpha = splash.blackout()) {
            SDL_SetRenderDrawBlendMode(app.ren, SDL_BLENDMODE_BLEND);
            SDL_SetRenderDrawColor(app.ren, 0, 0, 0, static_cast<Uint8>(alpha));
            SDL_RenderFillRect(app.ren, nullptr);
        }
    }
};

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
        else if (pad) {
            if (const Sheet* logo = a.imgSheet(7)) {
                const SDL_Rect& frame = logo->fr[0];
                SDL_Rect dst{208, 208, frame.w, frame.h};
                SDL_RenderCopy(a.ren, logo->tex, &frame, &dst);
            }
        } else { const SDL_Rect& lf = a.tlogo.fr[0]; SDL_Rect ld{12, 28, lf.w, lf.h}; SDL_RenderCopy(a.ren, a.tlogo.tex, &lf, &ld); }
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

    // PlayerSelectScreen::handleSettingsPaneInput (HD 1.0, 0x32d24).
    struct LocalPadInput {
        enum class Action { None, Preview, Players, Launch };
        struct Result { Action action = Action::None; int sound = -1; };

        PadRules rules{2, 2, 2, false, false};
        int stage = 0;
        bool launching = false;

        Result touch(int x, int y, int phase) {
            if (launching || phase != 0) return {};
            PaneRect items[37];
            const int count = layoutPad(items, false);
            const int item = hit(items, count, x, y);
            if (item >= 0 && item < 25) {
                stage = item;
                return {Action::Preview, 0};
            }
            if (item == 25) return {Action::Players, 2};
            if (item == 26 || (item == -1 && x >= 564 && x <= 798 && y >= 367 && y <= 555)) {
                launching = true;
                return {Action::Launch, 2};
            }
            if (item >= 27 && item <= 34) {
                const int delta = (item & 1) ? -1 : 1;
                if (item <= 28) rules.pointIndex = std::clamp(rules.pointIndex + delta, 0, 4);
                else if (item <= 30) rules.speedIndex = std::clamp(rules.speedIndex + delta, 0, 4);
                else if (item <= 32) rules.timeIndex = std::clamp(rules.timeIndex + delta, 0, 2);
                else rules.highMice = std::clamp(static_cast<int>(rules.highMice) + delta, 0, 1) != 0;
                return {Action::None, 1};
            }
            if (item == 35 || item == 36) {
                rules.split = item == 36;
                return {Action::None, 0};
            }
            return {};
        }
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
struct LocalPlayersPaneInput {
    PlayersInputLogic controls;
    std::array<int, 4> levels{};

    LocalPlayersPaneInput() {
        controls.a7c = 1;
        controls.d3c = controls.d40 = controls.d44 = 1;
    }

    void touch(int x, int y, int phase) {
        controls.sfx.clear();
        controls.openSettings = false;
        controls.gameState38 = false;
        if (phase != 0) return;
        controls.a3c = 0;
        using Rect = SettingsPaneItems::PaneRect;
        if (controls.d58 != -1) {
            Rect rows[6];
            for (int row = 0; row < 6; ++row)
                rows[row] = {244 + 151 * controls.d58, 314 + 28 * row, 104, 28};
            int row = SettingsPaneItems::hit(rows, 6, x, y);
            if (row >= 0) {
                levels[controls.d58] = row;
                controls.d58 = -1;
                controls.play(1);
                return;
            }
        }
        // HD 1.0 initPlayersPaneMenuItems. The two connection overlays
        // (items 10 and 11) are disabled in the local pane.
        constexpr Rect items[] = {
            {234, 219, 103, 31}, {234, 278, 103, 31}, {385, 219, 103, 31}, {385, 278, 103, 31},
            {536, 219, 103, 31}, {536, 278, 103, 31}, {687, 219, 103, 31}, {687, 278, 103, 31},
            {84, 560, 306, 60}, {634, 560, 306, 60}, {0, 0, -1, -1}, {0, 0, -1, -1},
            {208, 50, 608, 56}, {0, 711, 57, 57}, {967, 711, 57, 57},
        };
        controls.press(SettingsPaneItems::hit(items, 15, x, y));
    }
};

struct BattleSetupMode : Screen {
    PlayersFrame frame;
    LocalPlayersPaneInput players;
    SettingsPaneItems::LocalPadInput settings;
    int stateTicks = 0;
    const char* destination = nullptr;

    BattleSetupMode() { frame.state = 0x24; }  // SDL loads the required sheets before the fade.

    static bool available(App& app) {
        for (int image : {12, 17, 28, 31, 33, 34, 35, 36, 38, 39})
            if (!app.imgSheet(image)) return false;
        return app.hdFont.tex && !app.battlePreviewPixels(0, false).empty();
    }

    void event(App& app, const SDL_Event& event) override {
        if (frame.state != 0x25 || event.type != SDL_MOUSEBUTTONDOWN ||
            event.button.button != SDL_BUTTON_LEFT) return;
        SDL_RenderSetLogicalSize(app.ren, GW, GH);
        float x, y;
        SDL_RenderWindowToLogical(app.ren, event.button.x, event.button.y, &x, &y);
        if (x < 0 || x > GW || y < 0 || y > GH) return;
        if (frame.pane == 0) {
            players.touch(static_cast<int>(x), static_cast<int>(y), 0);
            const auto& input = players.controls;
            for (int sound : input.sfx) app.playSfx(sound);
            frame.team = input.a40;
            if (input.openSettings) frame.pane = 1;
            if (input.gameState38) {
                frame.state = 0x26;
                frame.fade = 0.0f;
            }
            return;
        }

        using Action = SettingsPaneItems::LocalPadInput::Action;
        const auto result = settings.touch(static_cast<int>(x), static_cast<int>(y), 0);
        if (result.action == Action::Launch) {
            // Split-screen rendering is still open.
            if (settings.rules.split) {
                settings.launching = false;
                app.playSfx(3);
                return;
            }
            frame.state = 0x27;
            stateTicks = 0;
        } else if (result.action == Action::Players) {
            frame.pane = 0;
            players.controls.d58 = -1;
        }
        if (result.sound >= 0) app.playSfx(result.sound);
    }

    void tick(App&) override {
        if (frame.state == 0x25 || destination) return;
        std::string ops;
        int request = playersFlowStep(frame.state, ++stateTicks, players.controls.a3c,
                                      frame.team, 0, settings.rules.split, 16384.0f, frame.fade, ops);
        if (frame.state == 0x24 && frame.fade == 0.0f) frame.state = 0x25;
        if (request == 4) destination = "MENU";
        if (request == 0xf || request == 0x13) destination = "BATTLE_MATCH";
    }

    int music() override { return frame.state == 0x24 ? -1 : 5; }
    const char* next() override { return std::exchange(destination, nullptr); }

    void draw(App& app, float) override {
        SDL_RenderSetLogicalSize(app.ren, GW, GH);
        SDL_RenderSetViewport(app.ren, nullptr);
        frame.draw(app, [&](int pane) {
            if (pane == 0) {
                const auto& p = players.controls;
                const int human[] = {1, !p.d3c, !p.d40, !p.d44};
                PlayersPane::drawPad(app, human, players.levels.data(), p.d58, -1, nullptr);
            } else {
                SettingsPaneItems::drawPadStageGrid(app, settings.stage, nullptr);
                SettingsPaneItems::drawPadRules(app, settings.rules, [&](const SDL_Rect& rect) {
                    app.drawBattlePreview(settings.stage, frame.team != 0, rect);
                }, nullptr);
            }
        });
    }
};

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
    bool shown(int i) const { return sub == 2 ? i < 6 : i != 6; }   // slot 3 (iPod Music, iOS-only) carries this port's own settings page   // iPod Music is iOS-only and Game Center is absent (AppData[5] == 0): not shown
    int capture = -1;   // sub 3: -1 list, 0..3 waiting for the controller button of arrow dir 0..3
    std::array<int, 4> pendingArrowButtons{};
    int back() const { return sub == 2 ? 6 : sub == 1 ? 2 : 7; }
    static constexpr int PR = 8, PX = 225, PY0 = 173, PPITCH = 70;   // port settings rows
    static const char* dirName(int d) { static const char* n[4] = {"down", "left", "up", "right"}; return n[d]; }
    std::string portLabel(App& a, int i) {
        const Settings& st = a.settings; char b[96];
        switch (i) { case 0: return std::string("Fullscreen: ") + (st.fullscreen ? "On" : "Off"); case 1: return std::string("VSync: ") + (st.vsync ? "On" : "Off"); case 2: return "Scaling: " + st.filter;
            case 3: snprintf(b, sizeof b, "Log detail: %d", st.logLevel); return b;
            case 7: return std::string("3D characters: ") + (st.models3d ? "On" : "Off");
            case 6: return std::string("Unlock all: ") + (st.unlockAll ? "On" : "Off");
            case 5: return "Battle CPU: " + std::string(st.cpuStyle == "gba" ? "GBA" : "Dreamcast");
            default: if (capture >= 0) { snprintf(b, sizeof b, "Press pad button for arrow %s", dirName(capture)); return b; } return "Remap arrow buttons"; } }
    int portHit(float lx, float ly, App& a) { for (int i = 0; i < PR; i++) { int w = a.mnBars.box[0].x, h = a.mnBars.box[0].y; if (PX <= lx && lx <= PX + w && PY0 + PPITCH * i <= ly && ly <= PY0 + PPITCH * i + h) return i; } int bw = a.ssArrows.box[0].x, bh = a.ssArrows.box[0].y; if (0 <= lx && lx <= bw && 768 - bh <= ly && ly <= 768) return 99; return -1; }
    void portAct(App& a, int i) {
        Settings& st = a.settings;
        if (i == 0) { st.fullscreen = !st.fullscreen; SDL_SetWindowFullscreen(a.win, st.fullscreen ? SDL_WINDOW_FULLSCREEN_DESKTOP : 0); }
        else if (i == 1) { st.vsync = !st.vsync; a.vsync = st.vsync; SDL_RenderSetVSync(a.ren, a.vsync); }
        else if (i == 2) st.filter = st.filter == "linear" ? "nearest" : "linear";
        else if (i == 3) st.logLevel = (st.logLevel + 1) % 3;
        else if (i == 4) { capture = 0; return; }
        else if (i == 7) { st.models3d = !st.models3d; a.models3d.clear(); a.models3dTried = false; }
        else if (i == 6) st.unlockAll = !st.unlockAll;
        else if (i == 5) st.cpuStyle = st.cpuStyle == "gba" ? "dreamcast" : "gba";
        a.saveSettings(); a.log.write(1, ("setting changed: " + portLabel(a, i)).c_str()); }   // sound list: 0 music, 1 sfx, 2 back (the vibration row exists only when AppData[0x685] is set)
    int drag = -1; static constexpr int SX = 303, SY0 = 245, SPITCH = 45, SW = 234;
    int sliderX(App& a) { int w = 0; for (int i = 0; i < 2; i++) if (const std::string* s = a.hdString(0x164 + i)) w = std::max(w, a.hdTextWidth(*s, 0, 1.0f)); return SX + w; }   // initSoundMenuItems: item x = 303 + the widest label
    int music() override { return phase == 0x11 ? -1 : 5; }
    int hitTest(App& a, float lx, float ly) { if (sub == 1) { int sx = sliderX(a); for (int i = 0; i < 2; i++) if (sx <= lx && lx <= sx + SW && SY0 + SPITCH * i <= ly && ly <= SY0 + SPITCH * i + 40) return i; int bw = a.ssArrows.box[0].x, bh = a.ssArrows.box[0].y; if (0 <= lx && lx <= bw && 768 - bh <= ly && ly <= 768) return 2; return -1; }
        for (int i = 0; i < N; i++) if (shown(i)) { int w = a.mnBars.box[0].x, h = a.mnBars.box[0].y; if (px[i] <= lx && lx <= px[i] + w && py[i] <= ly && ly <= py[i] + h) return i; }
        int bw = a.ssArrows.box[0].x, bh = a.ssArrows.box[0].y; if (0 <= lx && lx <= bw && 768 - bh <= ly && ly <= 768) return back(); return -1; }
    void setVol(App& a, int which, float lx) { int v = (int)((lx - (float)sliderX(a)) * (255.0f / (float)SW)); v = std::max(0, std::min(255, v)); if (which == 0) a.musicVol = v; else a.sfxVol = v; }
    void event(App& a, const SDL_Event& e) override {
        if (phase == 0x12 && sub == 3) {
            if (capture >= 0 && e.type == SDL_CONTROLLERBUTTONDOWN) {
                const int button = e.cbutton.button;
                if (button < SDL_CONTROLLER_BUTTON_DPAD_UP) {
                    pendingArrowButtons[capture++] = button;
                    a.playSfx(2);
                    if (capture == static_cast<int>(pendingArrowButtons.size())) {
                        std::copy(pendingArrowButtons.begin(), pendingArrowButtons.end(), a.padMap.arrow);
                        capture = -1;
                        a.savePadMap();
                        a.log.write(1, "controller arrow buttons remapped");
                    }
                }
                return;
            }
            if (capture >= 0 && e.type == SDL_KEYDOWN && e.key.keysym.sym == SDLK_ESCAPE) { capture = -1; return; }
            if (e.type == SDL_KEYDOWN) { SDL_Keycode k = e.key.keysym.sym; if (k == SDLK_ESCAPE) { a.playSfx(2); sub = 0; sel = 3; } else if (k == SDLK_DOWN) { sel = (sel + 1) % PR; a.playSfx(0); } else if (k == SDLK_UP) { sel = (sel + PR - 1) % PR; a.playSfx(0); } else if (k == SDLK_RETURN && capture < 0) { a.playSfx(2); portAct(a, sel); } return; }
            if (e.type == SDL_CONTROLLERBUTTONDOWN && capture < 0) { int b = e.cbutton.button; if (b == SDL_CONTROLLER_BUTTON_DPAD_DOWN) { sel = (sel + 1) % PR; a.playSfx(0); } else if (b == SDL_CONTROLLER_BUTTON_DPAD_UP) { sel = (sel + PR - 1) % PR; a.playSfx(0); } else if (b == SDL_CONTROLLER_BUTTON_A) { a.playSfx(2); portAct(a, sel); } else if (b == SDL_CONTROLLER_BUTTON_B) { a.playSfx(2); sub = 0; sel = 3; } return; }
            if (e.type == SDL_MOUSEBUTTONDOWN && e.button.button == SDL_BUTTON_LEFT && capture < 0) { float lx, ly; SDL_RenderSetLogicalSize(a.ren, GW, GH); SDL_RenderWindowToLogical(a.ren, e.button.x, e.button.y, &lx, &ly); int h = portHit(lx, ly, a); if (h == 99) { a.playSfx(2); sub = 0; sel = 3; } else if (h >= 0) { if (sel != h) { sel = h; a.playSfx(0); } else { a.playSfx(2); portAct(a, h); } } }
            return; }
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
        if (hit == 3) { a.playSfx(2); sub = 3; sel = 0; capture = -1; return; }   // this port's settings
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
        if (sub == 3) {
            for (int i = 0; i < PR; i++) { int w = a.mnBars.box[0].x, h = a.mnBars.box[0].y; a.rtex(a.mnBars, i == sel ? 1 : 0, (float)PX, (float)(PY0 + PPITCH * i), w, h);
                const float sc = 0.6667f; const float lh = (float)a.hdFont1.box[91].y * sc; a.printString(portLabel(a, i), (float)(PX + w / 2), (float)(PY0 + PPITCH * i) + ((float)h - lh) * 0.5f, 255, 255, 255, 255, sc, 0, false, 1);
                if (i == sel) { const SDL_Rect& m = a.mnMasc.fr[mascot]; a.rtex(a.mnMasc, mascot, (float)(PX + 36 - m.w), (float)(PY0 + PPITCH * i + (h - m.h) / 2), m.w, m.h); } }
            a.rtex(a.ssArrows, 0, 0, (float)(768 - a.ssArrows.box[0].y), a.ssArrows.box[0].x, a.ssArrows.box[0].y); return; }
        if (sub == 1) { drawSounds(a, a.musicVol, a.sfxVol, drag, nullptr); if (phase != 0x12) { SDL_SetRenderDrawBlendMode(a.ren, SDL_BLENDMODE_BLEND); SDL_SetRenderDrawColor(a.ren, 0, 0, 0, (Uint8)(int)(fade / 500000.0 * 255.0)); SDL_Rect all{0, 0, GW, GH}; SDL_RenderFillRect(a.ren, &all); } return; }
        for (int i = 0; i < N; i++) { if (!shown(i)) continue; int w = a.mnBars.box[0].x, h = a.mnBars.box[0].y; a.rtex(a.mnBars, i == sel ? 1 : 0, (float)px[i], (float)py[i], w, h);
            if (sub == 2 && i == 5 && a.langJa.tex) { const SDL_Rect& f = a.langJa.fr[0]; const SDL_Point& o = a.langJa.off[0]; a.rtex(a.langJa, 0, (float)(px[i] + w / 2 + o.x), (float)(py[i] + h / 2 + o.y), f.w, f.h); }   // the Japanese label is an image
            else if (sub == 0 && i == 3) { const float sc = 0.6667f; const float lh = (float)a.hdFont1.box[91].y * sc; a.printString("Settings", (float)(px[i] + a.mnBars.box[0].x / 2), (float)py[i] + ((float)a.mnBars.box[0].y - lh) * 0.5f, 255, 255, 255, 255, sc, 0, false, 1); }
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
        if (i == 0 || (i == 2 && !challengeBoardsAvailable(a.root)) || (i == 4 && !OptionsMode::ok(a))) { a.playSfx(0x13); return; }   // The Basics is not ported yet; Stage Challenge needs the Challenge boards (docs/roadmap.md)
        a.playSfx(2); chosen = i; fade = 0; phase = 0x10; }
    void tick(App& a) override {
        if (phase == 0xe) { fade -= 16384.0; if (fade <= 0) { fade = 0; phase = 0xf; } }
        else if (phase == 0xf) { t1 += 16384.0; if (t1 >= 500000.0) { t1 -= 500000.0; bubbleFrame = (bubbleFrame + 1) & 1; } t2 += 16384.0; if (t2 >= 166666.671875) { t2 -= 166666.671875; mascot = (mascot + 1) % 12; } }
        else if (phase == 0x10) { fade += 16384.0; if (fade >= 500000.0) { fade = 500000.0; leave = true; } } }
    const char* next() override { if (!leave) return nullptr; leave = false; static const char* to[N] = {nullptr, "STAGES", "CHALLENGE", "BATTLE", "OPTIONS"}; return to[chosen]; }
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
    bool bare(const App& a) const { return !a.menuOk && !a.padOk; }
    void geom(App& a, int i, int& x, int& y, int& w, int& h) { if (a.padOk) { const SDL_Rect& f = a.pbtn.fr[0]; x = ibx[i]; y = iby[i]; w = f.w; h = f.h; } else { const SDL_Rect& f = a.mbtn.fr[0]; x = pbx[i]; y = pby[i]; w = f.w; h = f.h; } }
    void event(App& a, const SDL_Event& e) override {
        if (bare(a)) {
            if (e.type == SDL_KEYDOWN) {
                const auto key = e.key.keysym.sym;
                if (key == SDLK_DOWN || key == SDLK_UP) sel = sel == 1 ? 3 : 1;
                else if (key == SDLK_RETURN || key == SDLK_SPACE) choose(a);
            } else if (e.type == SDL_MOUSEBUTTONDOWN && e.button.button == SDL_BUTTON_LEFT) {
                SDL_RenderSetLogicalSize(a.ren, GW, GH);
                float x, y;
                SDL_RenderWindowToLogical(a.ren, e.button.x, e.button.y, &x, &y);
                if (x >= 340 && x < 684 && y >= 290 && y < 450) {
                    sel = y < 370 ? 1 : 3;
                    choose(a);
                }
            }
            return;
        }
        if (e.type == SDL_KEYDOWN) { SDL_Keycode k = e.key.keysym.sym;
            if (k == SDLK_DOWN) sel = (sel + 1) % N; else if (k == SDLK_UP) sel = (sel + N - 1) % N; else if (k == SDLK_RETURN || k == SDLK_SPACE) choose(a); else if (k == SDLK_ESCAPE) back = true; }
        else if (e.type == SDL_MOUSEMOTION || (e.type == SDL_MOUSEBUTTONDOWN && e.button.button == SDL_BUTTON_LEFT)) {
            int mx = e.type == SDL_MOUSEMOTION ? e.motion.x : e.button.x, my = e.type == SDL_MOUSEMOTION ? e.motion.y : e.button.y;
            SDL_RenderSetLogicalSize(a.ren, a.padOk ? 1024 : 480, a.padOk ? 768 : 320); float lx, ly; SDL_RenderWindowToLogical(a.ren, mx, my, &lx, &ly); SDL_RenderSetLogicalSize(a.ren, W, H);
            for (int i = 0; i < N; i++) { int x, y, w, h; geom(a, i, x, y, w, h); if (lx >= x && lx < x + w && ly >= y && ly < y + h) { sel = i; if (e.type == SDL_MOUSEBUTTONDOWN) choose(a); } } }
    }
    void choose(App& a) { if (sel == 1) chosen = "STAGES"; else if (sel == 2 && challengeBoardsAvailable(a.root)) chosen = "CHALLENGE"; else if (sel == 3) chosen = "BATTLE"; else a.playSfx(0x13); }
    const char* next() override { if (back) { back = false; return "TITLE"; } const char* c = chosen; chosen = nullptr; return c; }
    void draw(App& a, float) override {
        if (bare(a)) {
            SDL_RenderSetLogicalSize(a.ren, GW, GH);
            SDL_SetRenderDrawColor(a.ren, 24, 24, 60, 255);
            SDL_RenderClear(a.ren);
            SDL_SetRenderDrawColor(a.ren, 66, 58, 130, 255);
            SDL_Rect selection{340, sel == 1 ? 290 : 370, 344, 80};
            SDL_RenderFillRect(a.ren, &selection);
            a.text("PUZZLE", 370, 310, 36);
            a.text("BATTLE", 370, 390, 36);
            return;
        }
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
    bool begin(App& a, const SDL_Event& e, FieldLayout field = {}) {
        SDL_RenderSetLogicalSize(a.ren, GW, GH);
        SDL_RenderWindowToLogical(a.ren, e.button.x, e.button.y, &x0, &y0);
        cx = static_cast<int>(std::floor((x0 - field.left) / field.cell));
        cy = static_cast<int>(std::floor((y0 - field.top) / field.cell));
        on = cx >= 0 && cx < kCols && cy >= 0 && cy < kRows;
        wx0 = e.button.x; wy0 = e.button.y;
        return on;
    }
    // returns the direction (0 south, 1 west, 2 north, 3 east) or -1 for a tap
    int end(App& a, const SDL_Event& e) { on = false; float lx, ly; SDL_RenderSetLogicalSize(a.ren, GW, GH); SDL_RenderWindowToLogical(a.ren, e.button.x, e.button.y, &lx, &ly); float dx = lx - x0, dy = ly - y0; float wdx = (float)(e.button.x - wx0), wdy = (float)(e.button.y - wy0); if (wdx * wdx + wdy * wdy <= 0.25f) return -1; if (std::fabs(dy) < std::fabs(dx)) return dx > 0 ? 3 : 1; return dy > 0 ? 0 : 2; }
};

static int arrowKey(SDL_Keycode key) {
    switch (key) {
    case SDLK_s: case SDLK_DOWN: return 0;
    case SDLK_a: case SDLK_LEFT: return 1;
    case SDLK_w: case SDLK_UP: return 2;
    case SDLK_d: case SDLK_RIGHT: return 3;
    default: return -1;
    }
}

struct MouseAim {
    float x = 0, y = 0;
    bool inside = false;
    FieldLayout field;
    void update(App& app, int windowX, int windowY, FieldLayout layout = {}) {
        field = layout;
        if (!app.headless) SDL_GetMouseState(&windowX, &windowY);
        SDL_RenderSetLogicalSize(app.ren, GW, GH);
        SDL_RenderWindowToLogical(app.ren, windowX, windowY, &x, &y);
        inside = x >= field.left && y >= field.top && x < field.x(kCols) && y < field.y(kRows);
    }
    int cellX() const { return static_cast<int>((x - field.left) / field.cell); }
    int cellY() const { return static_cast<int>((y - field.top) / field.cell); }
};

struct CursorTrail {
    static constexpr int lifetime = 24;
    struct Sample {
        float x = 0, y = 0;
        bool visible = false;
        bool mouse = false;
    };
    std::array<Sample, lifetime> history{};
    Sample previous;
    int next = 0;

    // One ghost at the old position per moving tick (Dreamcast 0x8c0145ee).
    void tick(float x, float y, bool visible, bool mouse) {
        history[next] = previous;
        history[next].visible = previous.visible && visible && mouse == previous.mouse &&
                                (x != previous.x || y != previous.y);
        next = (next + 1) % lifetime;
        previous = {x, y, visible, mouse};
    }

    void draw(App& app, int player, float cell = CELL, bool dcBattle = false) const {
        if (!app.dcCursorTrail.tex || app.dcCursorTrail.fr.size() != 4 || !app.useDcCursors()) return;
        // The original submits the oldest task first and truncates the fade to a byte.
        for (int i = 0; i < lifetime; ++i) {
            const auto& sample = history[(next + i) % lifetime];
            if (!sample.visible) continue;
            if (dcBattle && !sample.mouse) {
                // The trail is a board-plane quad at depth 212, anchored by
                // its top left. The floor position is at depth 218.
                constexpr float scale = 218.0f / 212.0f;
                const float size = cell * scale;
                const float x = GW / 2.0f + (sample.x - GW / 2.0f) * scale;
                const float y = GH / 2.0f + (sample.y - GH / 2.0f) * scale;
                app.cursorGhost(x + size / 2, y + size / 2, player, (i + 1) * 64 / lifetime, size);
            } else {
                app.cursorGhost(sample.x, sample.y, player, (i + 1) * 64 / lifetime, cell);
            }
        }
    }
};

struct PadAim {
    float x, y, previousX = x, previousY = y;
    int targetX = -1, targetY = -1;
    float logicalX(float fraction = 1.0f, FieldLayout field = {}) const {
        return field.x((previousX + (x - previousX) * fraction) / kCell);
    }
    float logicalY(float fraction = 1.0f, FieldLayout field = {}) const {
        return field.y((previousY + (y - previousY) * fraction) / kCell);
    }

    // Dreamcast 1ST_READ.BIN at 0x8c014220.
    void tick(SDL_GameController* pad) {
        previousX = x;
        previousY = y;
        const auto axis = [&](SDL_GameControllerAxis which) {
            const int value = SDL_GameControllerGetAxis(pad, which);
            const float delta = (value >> 8) * 256 * 0.00009f;
            return std::fabs(delta) < 0.09f ? 0.0f : delta;
        };
        const float dx = axis(SDL_CONTROLLER_AXIS_LEFTX), dy = axis(SDL_CONTROLLER_AXIS_LEFTY);
        if (dx != 0 || dy != 0) {
            x = std::clamp(x + dx, 0.0f, kCols * kCell - 0.01f);
            y = std::clamp(y + dy, 0.0f, kRows * kCell - 0.01f);
            targetX = targetY = -1;
            return;
        }
        const auto step = [&](float& position, int& target, int cells,
                              SDL_GameControllerButton negative, SDL_GameControllerButton positive) {
            if (target < 0) {
                const int direction = SDL_GameControllerGetButton(pad, positive) -
                                      SDL_GameControllerGetButton(pad, negative);
                if (!direction) return;
                const int next = static_cast<int>(position / kCell) + direction;
                if (next < 0 || next >= cells) return;
                target = next;
            }
            const float center = (target + 0.5f) * kCell;
            if (std::fabs(center - position) <= 1.8f) target = -1;
            else position += center > position ? 1.8f : -1.8f;
        };
        step(x, targetX, kCols, SDL_CONTROLLER_BUTTON_DPAD_LEFT, SDL_CONTROLLER_BUTTON_DPAD_RIGHT);
        step(y, targetY, kRows, SDL_CONTROLLER_BUTTON_DPAD_UP, SDL_CONTROLLER_BUTTON_DPAD_DOWN);
    }

    void draw(App& app, int player, int ticks, float alpha, FieldLayout field = {}) const {
        app.cursorAt(logicalX(alpha, field), logicalY(alpha, field), player, ticks, false, field.scale());
    }
};

// ---------------------------------------------------------------- puzzle
struct PuzzleMode : Screen {
    static constexpr int kFailureHoldFrames = 120;
    MouseAim aim;
    CursorTrail cursorTrail;
    bool mouseCursor = false;
    int failureFrames = 0;
    PadAim padAim{97.5f, 67.5f};   // Flycast Normal Puzzle 01 and 02: the pad cursor starts on cell (6, 4), its pointer at the cell centre
    Stages stages; int cur = 0; Sim sim; std::vector<std::pair<float, float>> prev; bool running = false; int state = 0;   // 0 planning, 1 running, 2 clear, 3 miss
    int stock[4] = {0, 0, 0, 0}; int totalMice = 0; bool back = false; DragGesture drag; int curX = 6, curY = 4; SDL_GameController* pad = nullptr;
    void putAt(int cx, int cy, int d) { sim.removeArrow(cx, cy); if (d >= 0 && used(d) < stock[d]) sim.placeArrow(cx, cy, d); }   // AR_PutArrowPzSp: an arrow already there is deleted first; a direction without stock places nothing
    int music() override { return 9; }   // PuzzleInit: BGM_Play(0xd) = song 9
    bool load(const std::string& root, int stage) { if (!loadStageSet(root, gApp ? gApp->stageSet : 0, stages)) return false; cur = stage % (int)stages.list.size(); reset(); return true; }
    bool dcPanelDrawn = false;   // the Dreamcast bottom panel replaces the iPad arrow strip
    bool dash = false; bool paused = false, pconf = false;   // PA_IsPaused and PuzzleGameScreen[0xa21] (the pause dialog's second state)
    void restartRun() { std::vector<Arrow> keep; for (auto& ar : sim.arrows) if (ar.live) keep.push_back(ar); reset(); for (auto& ar : keep) sim.placeArrow(ar.x, ar.y, ar.dir); }
    void reset() {
        cursorTrail = {};
        sim.load(stages.list[cur].st); prev.clear(); dash = false; failureFrames = 0; if (gApp) gApp->angs.clear(); running = false; state = 0; totalMice = 0;
        for (auto& e : sim.ents) if (e.mouse) totalMice++;
        for (int d = 0; d < 4; d++) stock[d] = stages.list[cur].stock[d];
    }
    // Dreamcast Puzzle uses the same measured floor plane as Battle (Flycast Normal Puzzle 01/02: floor quad x 136.929-594.606, y 22.604-365.861 of 640 x 480).
    FieldLayout pf(const App& a) const { return dreamcastPuzzleControls(a) ? dcBattleField : FieldLayout{}; }
    int used(int d) const { int n = 0; for (auto& a : sim.arrows) if (a.live && a.dir == d) n++; return n; }
    ~PuzzleMode() override { if (pad) SDL_GameControllerClose(pad); }
    void event(App& a, const SDL_Event& e) override {
        if (e.type == SDL_MOUSEMOTION || e.type == SDL_MOUSEBUTTONDOWN || e.type == SDL_MOUSEBUTTONUP) {
            aim.update(a, e.type == SDL_MOUSEMOTION ? e.motion.x : e.button.x,
                          e.type == SDL_MOUSEMOTION ? e.motion.y : e.button.y, pf(a));
            mouseCursor = true;
        } else if (e.type == SDL_WINDOWEVENT && e.window.event == SDL_WINDOWEVENT_LEAVE) aim.inside = false;
        if (e.type == SDL_KEYDOWN) { SDL_Keycode k = e.key.keysym.sym;
            if (paused && k != SDLK_ESCAPE) return;
            if (!a.headless && arrowKey(k) >= 0) aim.update(a, 0, 0, pf(a));
            if (k == SDLK_SPACE) { if (state == 0) { state = 1; running = true; } else if (state == 2) { cur = (cur + 1) % (int)stages.list.size(); reset(); } }   /* a cleared stage leads to the next one */
            else if (k == SDLK_r) reset(); else if (k == SDLK_ESCAPE) back = true;
            else if (k == SDLK_RIGHTBRACKET) { cur = (cur + 1) % (int)stages.list.size(); reset(); } else if (k == SDLK_LEFTBRACKET) { cur = (cur + (int)stages.list.size() - 1) % (int)stages.list.size(); reset(); }
            else if (state == 0 && !paused && !e.key.repeat && aim.inside && arrowKey(k) >= 0) {
                mouseCursor = true;
                putAt(aim.cellX(), aim.cellY(), arrowKey(k));
            } }
        else if (e.type == SDL_MOUSEBUTTONDOWN && e.button.button == SDL_BUTTON_LEFT && hudButton(a, e)) {}   // HD 1.0 PuzzleGameScreen::handleInput: rect 3 Start (flag 1), rect 4 Cancel (flag 2)
        else if (e.type == SDL_MOUSEBUTTONDOWN && state == 0 && e.button.button == SDL_BUTTON_LEFT) drag.begin(a, e, pf(a));
        else if (e.type == SDL_MOUSEBUTTONUP && state == 0 && e.button.button == SDL_BUTTON_LEFT && drag.on) { int cx = drag.cx, cy = drag.cy; int d = drag.end(a, e); putAt(cx, cy, d); }   // a tap (d = -1) deletes the arrow on the cell
        else if (e.type == SDL_CONTROLLERDEVICEADDED && !pad) pad = SDL_GameControllerOpen(e.cdevice.which);
        else if (e.type == SDL_CONTROLLERDEVICEREMOVED && pad &&
                 SDL_JoystickInstanceID(SDL_GameControllerGetJoystick(pad)) == e.cdevice.which) {
            SDL_GameControllerClose(pad);
            pad = nullptr;
        }
        else if (e.type == SDL_CONTROLLERBUTTONDOWN && pad && state == 0 && !paused &&
                 SDL_JoystickInstanceID(SDL_GameControllerGetJoystick(pad)) == e.cbutton.which) { int b = e.cbutton.button;
            mouseCursor = false;
            { const PadMap& pm = gApp->padMap; int d = -1; for (int k = 0; k < 4; k++) if (b == pm.arrow[k]) d = k; if (d >= 0) putAt(curX, curY, d);
            else if (b == pm.pause) { state = 1; running = true; } } }
    }
    // Touch rects of the puzzle screen (HD 1.0 PuzzleGameScreen::process 0x12994 -> Input::addRect(i, x0, y0, x1, y1) from layout +0x4d0 + 16 i): rect 3 (18, 88)-(160, 190) Start/Dash, rect 4 (21, 229)-(159, 275) Cancel.
    // In the placing mode, rect 3 sets input flag 1 (start) and rect 4 flag 2 (Cancel). Effects read from Android PuzzleLoop (0x33bbc): placing: flag 1 = start, flag 2 = delete all arrows; running: flag 1 = Dash, flag 2 = restart with the arrows kept.
    bool ipadPauseAvailable(const App& a) const {
        return a.hdHud68.fr.size() > 5 && a.hdPause.fr.size() > 3 && a.hdFont.tex;
    }
    bool phonePauseAvailable(App& a) const {
        return !ipadPauseAvailable(a) && a.phonePauseButton.fr.size() > 5 &&
               !a.phonePauseTitle.fr.empty() && a.phonePausePanel.fr.size() > 2 &&
               !a.str(217).empty() && !a.str(218).empty();
    }
    bool phonePuzzleHudAvailable(const App& a) const {
        return a.hdPhud.fr.empty() && !a.phonePuzzleHud.fr.empty();
    }
    // Fit the 480 × 320 handset UI at integer scale on the shared gameplay canvas.
    static constexpr int phoneX = (GW - 960) / 2, phoneY = (GH - 640) / 2;
    // Real draw list (Flycast frame 2390, 640 x 480): the R panel is a 128 x 128 quad at (5, 32), the L panel one at (5, 160); the exported sheets are cropped to 126 x 128 and 126 x 73, drawn here at 1.6 times that screen.
    static constexpr SDL_Rect dcStartRect{8, 51, 202, 205};
    static constexpr SDL_Rect dcCancelRect{8, 256, 202, 117};
    bool dreamcastPuzzleControls(const App& a) const {
        return a.settings.models3d && a.dcPuzzleStart.tex && a.dcPuzzleCancel.tex && !phonePuzzleHudAvailable(a);
    }
    void drawPhonePause(App& a) const {
        auto art = [&](Sheet& sheet, int frame, int x, int y, bool mirror = false) {
            a.blitFlip(sheet, frame, phoneX + 2 * x, phoneY + 2 * y, 2.0f, mirror);
        };
        art(a.phonePauseTitle, 0, 240, 200);
        art(a.phonePausePanel, 0, 235, 199, pconf);
        art(a.phonePausePanel, pconf ? 2 : 1, 129, 183);
        art(a.phonePausePanel, pconf ? 1 : 2, 341, 183, true);
        const int height = 28;
        for (int i = 0; i < 2; ++i) {
            const std::string& text = a.str(217 + i);
            const int x = phoneX + 2 * (i == 0 ? 114 : 359);
            a.text(text, x - a.textWidth(text, height) / 2, phoneY + 2 * 183 - height / 2, height);
        }
    }
    bool hudButton(App& a, const SDL_Event& e) {
        float lx, ly; SDL_RenderSetLogicalSize(a.ren, GW, GH); SDL_RenderWindowToLogical(a.ren, e.button.x, e.button.y, &lx, &ly);
        auto in = [&](float x0, float y0, float x1, float y1) { return lx >= x0 && lx < x1 && ly >= y0 && ly < y1; };
        const bool phone = phonePauseAvailable(a);
        auto handset = [&](int x0, int y0, int x1, int y1) {
            const float x = (lx - phoneX) / 2, y = (ly - phoneY) / 2;
            return x >= x0 && x <= x1 && y >= y0 && y <= y1;
        };
        if (paused) {
            if (phone ? handset(33, 148, 204, 215) : in(128, 313, 403, 413)) { if (!pconf) { pconf = true; a.playSfx(0); } else { a.playSfx(2); paused = false; } }
            if (phone ? handset(265, 148, 440, 215) : in(590, 314, 881, 414)) { if (!pconf) { a.playSfx(2); paused = false; back = true; } else { pconf = false; a.playSfx(0); } }
            return true; }
        if (state == 3) return true;   // PuzzleLoop disables pause and ignores HUD input during the failure phase.
        if (phone ? handset(0, 295, 60, 320) : ipadPauseAvailable(a) && in(10, 669, 173, 711)) {
            paused = true;
            drag.on = false;
            if (phone) pconf = false;
            a.playSfx(4);
            return true;
        }
        const bool phoneHud = phonePuzzleHudAvailable(a);
        const bool dcControls = dreamcastPuzzleControls(a);
        auto inRect = [&](const SDL_Rect& r) { return in(r.x, r.y, r.x + r.w, r.y + r.h); };
        if (dcControls ? inRect(dcStartRect) : phoneHud ? handset(0, 0, 56, 40) : in(18, 88, 160, 190)) { if (state == 0) { state = 1; running = true; dash = false; a.playSfx(2); } else if (running && !dash) { dash = true; a.playSfx(0xc); } return true; }   // PuzzleLoop: placing -> start (sound 2); running -> Dash (sound 0xc, two simulation steps per frame)
        if (dcControls ? inRect(dcCancelRect) : phoneHud ? handset(0, 39, 56, 84) : in(21, 229, 159, 275)) { if (state == 0) { std::vector<std::pair<int,int>> cells; for (auto& ar : sim.arrows) if (ar.live) cells.push_back({ar.x, ar.y}); for (auto& c : cells) sim.removeArrow(c.first, c.second); }   // placing: AR_DeleteArrowPz (all arrows removed)
                                     else if (running) { a.playSfx(3); restartRun(); } return true; }   // running: sound 3, the stage restarts with the arrows kept (phase 1: AR_RestartArrowPzManager)
        return false;
    }
    int cticks = 0;
    void tick(App& a) override {
        a.stars.tick(false);
        if (paused) return; cticks++;
        if (pad && state == 0) {
            padAim.tick(pad);
            if (padAim.x != padAim.previousX || padAim.y != padAim.previousY) mouseCursor = false;
            curX = static_cast<int>(padAim.x / kCell);
            curY = static_cast<int>(padAim.y / kCell);
        }
        cursorTrail.tick(mouseCursor ? aim.x : padAim.logicalX(1.0f, pf(a)), mouseCursor ? aim.y : padAim.logicalY(1.0f, pf(a)),
                         state == 0 && (!mouseCursor || aim.inside), mouseCursor);
        for (size_t i = 0; i < sim.ents.size() && i < prev.size(); i++) prev[i] = {sim.ents[i].x, sim.ents[i].z};
        if (state == 3) {
            if (failureFrames == 0) a.playSfx(27);
            if (failureFrames > kFailureHoldFrames) {
                restartRun();
                return;
            }
            if (failureFrames++ == kFailureHoldFrames) return;   // clear the task pass before rebuilding
        }
        if (state == 2 || state == 3) {
            // Keep character effects ticking while the result holds the board.
            ++sim.now;
            sim.tickEffects();
            a.stepAngles(sim, true);
            if (dash) { ++sim.now; sim.tickEffects(); a.stepAngles(sim, true); }
            return;
        }
        if (!running) return;
        sim.tick(); a.stepAngles(sim);
        if (dash) { sim.tick(); a.stepAngles(sim); }   // Dash: PuzzleLoop runs SmpColLoopInit/SmpTskExeServer/SmpColAnalyze twice per frame
        int alive = 0; for (auto& e : sim.ents) if (e.mouse && e.alive && !e.done) alive++;
        if (sim.killed > 0 || sim.catsInRocket > 0) { state = 3; running = false; } else if (alive == 0 && sim.saved == totalMice) { state = 2; running = false; if (gApp && gApp->stageSet == 0) gApp->setCleared(cur); }
    }
    const char* next() override { if (back) { back = false; if (gApp) gApp->nextStage = cur; return "STAGES"; } return nullptr; }
    void drawFailureFocus(App& a) const {
        if (failureFrames <= 0 || failureFrames > kFailureHoldFrames) return;
        const int passes = dash ? 2 : 1;
        if (failureFrames * passes >= 180) return;   // FocusControll retires the task at age 180.
        const int target = sim.lastKilledMouse >= 0 ? sim.lastKilledMouse : sim.lastCatInRocket;
        if (target < 0) return;
        const auto& entity = sim.ents[target];
        const float x = OX + entity.x * (CELL / kCell), y = OY + entity.z * (CELL / kCell);
        const int opacity[] = {200, 120, 60};
        float previous = 0.0f;
        for (int age = 0; age < 3 && age < failureFrames; ++age) {
            const int updates = (failureFrames - age) * passes;
            const float scale = updates < 30 ? (16.0f - 0.5f * updates) * 0.8f * 0.8f : 0.8f;
            if (scale == previous) continue;
            a.drawImage(149, 0, x, y, 0, scale, opacity[age]);
            if (a.headless && getenv("CCR_PUZZLE_FOCUS_TRACE"))
                printf("puzzle focus %a %a %a %d\n", x, y, scale, opacity[age]);
            previous = scale;
        }
    }
    void draw(App& a, float alpha) override {
        dcPanelDrawn = false;
        const bool hasBoardTasks = failureFrames <= kFailureHoldFrames;
        SDL_RenderSetLogicalSize(a.ren, GW, GH); SDL_RenderSetViewport(a.ren, nullptr);
        SDL_SetRenderDrawColor(a.ren, 0, 0, 26, 255);   // iPad Puzzle clear colour (blue 0.1)
        SDL_RenderClear(a.ren);
        a.stars.draw(a);
        if (hasBoardTasks) {
            const int set = gApp ? gApp->stageSet : 0;
            a.board(stages.list[cur].st, set == 1 ? 1 : a.useModels3d() ? ((cur / 25) & 3) + 2 : (cur & 3) + 2, set == 1 ? 1 : 2, pf(a));   // Dreamcast 3D board: the real Normal 01 and 02 both show yuka03 (tan and pink), so the floor follows the group of 25, not the stage number (other groups unverified)
            for (auto& ar : sim.arrows) if (ar.live) a.arrow(ar.x, ar.y, ar.dir, 0, ar.hits, -1, pf(a));
        }
        const int aimX = mouseCursor ? aim.cellX() : curX, aimY = mouseCursor ? aim.cellY() : curY;
        const bool showCursor = state == 0 && (!mouseCursor || aim.inside);
        if (showCursor && ((dreamcastPuzzleControls(a) && !mouseCursor) || (sim.coll[aimY][aimX] & 0xF00))) a.cursor(aimX, aimY, 0, cticks, true, pf(a));   // Flycast Puzzle 01 and 02: the pad cursor's corner bracket sits on cell (6, 4) even over a mouse, so the Dreamcast pad cursor always shows it
        if (hasBoardTasks) a.drawFieldObjects(sim, prev, running ? alpha : 1.0f, nullptr, pf(a), dreamcastPuzzleControls(a));
        if (showCursor) {
            cursorTrail.draw(a, 0);
            if (mouseCursor) a.cursorAt(aim.x, aim.y, 0, cticks, false, pf(a).scale());
            else if (dreamcastPuzzleControls(a)) { const float fraction = paused ? 1.0f : alpha; a.drawDcBattlePadCursor(padAim.logicalX(fraction, pf(a)), padAim.logicalY(fraction, pf(a)), 0, cticks); }   // same corner-anchored pad cursor as Battle (Flycast Puzzle frames show it that way)
            else padAim.draw(a, 0, cticks, paused ? 1.0f : alpha, pf(a));
        }
        SDL_RenderSetViewport(a.ren, nullptr);   // puzzle HUD (HD 1.0 renderPuzzleHudiPad 0x137c4): image 0x5c frame 2 at (origin + 40, 690), frame 3 ten times every 64, frame 4;
        const bool dcLeft = dreamcastPuzzleControls(a) && a.dcPuzzleStage.tex;   // real draw list: the 128 x 64 "stage" quad at (5, 325) of 640 x 480, drawn here at 1.6 times that
        if (dcLeft) { const SDL_Rect dst{8, 520, 205, 102}; SDL_RenderCopy(a.ren, a.dcPuzzleStage.tex, nullptr, &dst); int n = cur % 25 + 1;
            if (a.dcPuzzleDigits.tex) {   // real draw list: 51 x 51 quads at x 38.2 and 68.2, y 375.2 of 640 x 480 (the glyphs are PUZZLECLEAR_new0..9)
                const SDL_Rect src0{(n / 10) * 64, 0, 64, 64}, src1{(n % 10) * 64, 0, 64, 64}, dst0{61, 600, 82, 82}, dst1{109, 600, 82, 82};
                SDL_RenderCopy(a.ren, a.dcPuzzleDigits.tex, &src0, &dst0); SDL_RenderCopy(a.ren, a.dcPuzzleDigits.tex, &src1, &dst1);
            } else { a.blit(a.hdStageNum, n / 10, 102.0f, 641.0f, 1.3f); a.blit(a.hdStageNum, n % 10, 150.0f, 641.0f, 1.3f); } }
        else
        { int n = cur % 25 + 1; a.blit(a.hdPhud, 1, 90.0f, 520.0f, 1.3f); a.blit(a.hdStageNum, n / 10, 70.0f, 584.0f, 1.3f); a.blit(a.hdStageNum, n % 10, 120.0f, 584.0f, 1.3f); }   // renderPuzzleHudiPad: "stage" label (0x5c frame 1) at (90, 520) and the number (image 0x84, (stage mod 25) + 1, tens at (70, 584), ones at (120, 584)), all at scale 1.3; the stage-name frame and text are not drawn yet
        if (phonePuzzleHudAvailable(a)) {
            // Android renderPuzzleHudLeft subtracts the caller's 4px inset from (30, 40).
            a.blit(a.phonePuzzleHud, 0, phoneX + 2 * 26, phoneY + 2 * 40, 2.0f);
            // renderPuzzleHudiPhone (Android 0x5f95c): arrow slot panel frames 2, 3 (three times, 32 apart) and 4 at x 29 from y 101, then each
            // remaining arrow direction in AR_GetArrowdataPuzzle order east, west, north, south: image 0x5f frame 0 at (24, y) scale 0.8 rotated
            // 4/12/0/8 sixteenths, count text at (48, y) scale 0.6, y from 112 in steps of 36. tools/oracle/android_puzzle_hud_calls.py records these calls.
            // Not drawn yet: the name frame (0x73 frame 5 at 29,308) and the "stage" label and number shown while puzzlestage_endflag is 1.
            auto phoneHudAt = [&](int frame, float y) { a.blit(a.phonePuzzleHud, frame, phoneX + 2 * 29.0f, phoneY + 2 * y, 2.0f); };
            phoneHudAt(2, 101.0f);
            for (int k = 0; k < 3; k++) phoneHudAt(3, 133.0f + 32.0f * k);
            phoneHudAt(4, 229.0f);
            { static const int ord[4] = {3, 1, 2, 0}; float y = 112.0f;
              for (int k = 0; k < 4; k++) { const int d = ord[k], left = stock[d] - used(d); if (left <= 0) continue;
                  a.arrowIcon(phoneX + 2 * 24.0f, phoneY + 2 * y, d, 0, 0.8f);
                  { const int h = 47; const std::string t = std::to_string(left); SDL_SetTextureColorMod(a.font.tex, 0, 0, 0); a.text(t, (int)(phoneX + 2 * 48.0f) - a.textWidth(t, h) / 2, (int)(phoneY + 2 * y) - h / 2, h); SDL_SetTextureColorMod(a.font.tex, 255, 255, 255); } y += 36.0f; } }
        } else if (dreamcastPuzzleControls(a)) {
            SDL_RenderCopy(a.ren, a.dcPuzzleStart.tex, nullptr, &dcStartRect);
            SDL_RenderCopy(a.ren, a.dcPuzzleCancel.tex, nullptr, &dcCancelRect);
            // The real Puzzle screen (Flycast frame 2390, docs/dreamcast_models.md) draws the bottom panel as two 256 x 96 quads of one texture at x 130 and 386, y 372 on a 640 x 480 screen; this view is 1.6 times that.
            if (a.dcPuzzlePanel.tex) {
                const SDL_Rect src0{0, 0, 256, 96}, src1{0, 96, 256, 96};
                const SDL_Rect dst0{208, 595, 410, 154}, dst1{618, 595, 410, 154};
                SDL_RenderCopy(a.ren, a.dcPuzzlePanel.tex, &src0, &dst0);
                SDL_RenderCopy(a.ren, a.dcPuzzlePanel.tex, &src1, &dst1);
                dcPanelDrawn = true;
            }
        } else {
            a.blit(a.hdPhud, 0, 85.0f, 190.0f);
        }
        if (!phonePuzzleHudAvailable(a)) {
        if (!dcPanelDrawn) { float x = (float)OX + 40.0f; a.blit(a.hdPhud, 2, x, 690.0f); for (int k = 0; k < 10; k++) { x += 64.0f; a.blit(a.hdPhud, 3, x, 690.0f); } x += 64.0f; a.blit(a.hdPhud, 4, x, 690.0f); }
        // then the remaining arrows: AR_GetArrowdataPuzzle order east, west, north, south (rotations 4, 12, 0, 8 in 1/16 turns), image 0x54 frame 0 at scale 0.6, x from origin + 64 in steps of 60, y 706
        { static const int ordIpad[4] = {3, 1, 2, 0}, ordDc[4] = {2, 3, 0, 1};   // Flycast Normal 25: the panel shows up, then right (order beyond those two unverified)
          const int* ord = dcPanelDrawn ? ordDc : ordIpad; float x = dcPanelDrawn ? 253.0f : (float)OX + 64.0f; const float iy = dcPanelDrawn ? 667.0f : 706.0f; const float isc = dcPanelDrawn ? 0.8f : 0.6f;   // Dreamcast: first icon quad x 142-174, y 401-433 of 640 x 480 (x1.6); the slot pitch for further arrows is not measured yet
          for (int k = 0; k < 4; k++) { int d = ord[k]; for (int n = 0; n < stock[d] - used(d); n++) { a.arrowIcon(x, iy, d, 0, isc); x += dcPanelDrawn ? 54.4f : 60.0f; } } }   // Dreamcast: icons 34 px apart on the 640 x 480 screen (x 142-174 and 176-208)
        }
        const std::string* levelName = !(gApp && gApp->stageSet != 0) && cur < 100 ? a.hdString(0x1ab + (cur / 25 <= 3 ? cur / 25 : 0)) : nullptr;
        int labelRow = -1;
        if (dcLeft && levelName && a.dcPuzzlePlate.tex && a.dcPuzzleLabels.tex) {   // the real list: the 512 x 64 plate texture squeezed into 230 x 45 at (3.1, 278.3) and the 256 x 32 label into 179 x 22 at (15.4, 283.5) of 640 x 480; shown at 1.6 times that
            static const char* const kinds[] = {"normal", "hard", "mania", "original", "special"};
            std::string lower = *levelName; for (char& c : lower) c = static_cast<char>(tolower(static_cast<unsigned char>(c)));
            for (int k = 0; k < 5; ++k) if (lower.find(kinds[k]) != std::string::npos) labelRow = k;
            if (labelRow >= 0) {
                const SDL_Rect plateDst{5, 445, 369, 50}, labelSrc{0, labelRow * 32, 256, 32}, labelDst{25, 454, 287, 36};
                SDL_RenderCopy(a.ren, a.dcPuzzlePlate.tex, nullptr, &plateDst); SDL_RenderCopy(a.ren, a.dcPuzzleLabels.tex, &labelSrc, &labelDst);
            }
        }
        if (labelRow < 0) a.drawFrame5(90, 410, 180);
        const bool dcBubble = dcLeft && a.dcPuzzlePlate.tex;   // the hint bubble reuses the plate texture at x 316-828, y 365.2-416.4 of 640 x 480 (the full 512 x 64 texture, so rows 0-43 span 35 px); the text is a separate 512 x 256 sprite at (336, 370)
        if (dcBubble) { const SDL_Rect bubble{506, 584, 819, 56}; SDL_RenderCopy(a.ren, a.dcPuzzlePlate.tex, nullptr, &bubble); }
        else a.drawFrame5(720, 650, 440);   // name frames (renderPuzzleHudiPad: drawFrame(5, 90, 410, 180) for the level name, drawFrame(5, 720, 650, 440) for the stage name); the text itself (printString, original font) is not drawn yet
        if (!(gApp && gApp->stageSet != 0) && cur < 100) {   // printString(level name, 90, 410, black, scale 0.8, centred, v-centred) and printString(stage comment, 720, 650, scale 1.0); the y offset +10 applies only when AppData+0x664 == 5 (UTF-16 language branch). Texts T[0x1ab + (stage/25 <= 3 ? stage/25 : 0)] (getPuzzleType) and T[0x1e8 + stage] (FI_GetCommentStrP)
            const std::string* lv = a.hdString(0x1ab + (cur / 25 <= 3 ? cur / 25 : 0)); if (lv && labelRow < 0) a.printString(*lv, 90.0f, 410.0f, 0, 0, 0, 255, 0.8f, 0, true);
            const std::string* nm = a.hdString(0x1e8 + cur); if (nm) a.printString(*nm, dcBubble ? 727.0f : 720.0f, dcBubble ? 613.0f : 650.0f, 0, 0, 0, 255, 1.0f, 0, true); }   // Dreamcast: centred in the bubble with the port's font (the original renders the string left-aligned in its own bitmap font)
        const bool phonePause = phonePauseAvailable(a);
        if (phonePause) a.blit(a.phonePauseButton, 5, phoneX + 58, phoneY + 616, 2.0f);
        else if (ipadPauseAvailable(a) && !dcPanelDrawn) a.blit(a.hdHud68, 5, 92.0f, 690.0f);   // the real Dreamcast Puzzle screen has no Pause plate
        drawFailureFocus(a);
        if (paused && dreamcastPuzzleControls(a) && a.dcPause.tex) {   // Flycast Puzzle pause frame (docs/dreamcast_models.md)
            a.drawDcPause(0.0f);
            return;
        }
        if (paused) {   // PuzzleGameScreen::render pause branch (0x13620): black rect alpha getAlphaRect() = 0xc0, drawPauseBanner(512, 400, [0xa21]) (0x1b63c), name frame drawFrame(5, 512, 50, 320), name text at (512, 50) scale 0.8
            SDL_SetRenderDrawBlendMode(a.ren, SDL_BLENDMODE_BLEND); SDL_SetRenderDrawColor(a.ren, 0, 0, 0, 0xc0); SDL_Rect all{0, 0, GW, GH}; SDL_RenderFillRect(a.ren, &all);
            if (phonePause) {
                drawPhonePause(a);
                return;
            }
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
// ---------------------------------------------------------------- Stage Challenge (puzzle-based types 0 to 2; core/challenge.hpp, verified against the original's ChallengeLoop)
struct ChallengeMode : Screen {
    Stages stages; int cur = 0; ChallengeGame game; ChallengeBattleGame bgame; bool battle = false; MouseAim aim; bool mouseCursor = false, back = false, nextStageRequested = false; int lastDir = 0, cticks = 0; bool saved_ = false, newBest = false; int bestSeconds = 0;
    std::vector<std::pair<float, float>> prev;
    // Dreamcast layout (Flycast Challenge A1): the same measured floor plane as Battle and Puzzle, and the Battle task's left column (strip, clock, nine-rocket time gauge).
    bool paused = false;   // P key (the original's START) or CCR_PAUSE_TICK in headless tests
    bool dcLayout(App& a) { return a.useModels3d() && a.useDcBattleHud(); }
    FieldLayout pf(App& a) { return dcLayout(a) ? dcBattleField : FieldLayout{}; }
    // progress file: u32 cleared mask (Data +8), then 25 u32 best times in seconds (0 = none), like Data::clearChallenge
    struct Save { uint32_t mask = 0, best[25] = {}; };
    static Save loadSave(const std::string& root) { Save s; if (FILE* f = fopen((root + "/challenge.bin").c_str(), "rb")) { if (fread(&s, sizeof s, 1, f) != 1) s = Save(); fclose(f); } return s; }
    void logResult(App& a) { char b[160]; snprintf(b, sizeof b, "challenge stage %d: cleared in %d s", cur + 1, battle ? bgame.clearSeconds() : game.clearSeconds()); a.log.write(1, b); }
    void saveResult(App& a) { logResult(a);   // Data::clearChallenge: mark the stage cleared, keep the smaller non-zero time
        Save s = loadSave(a.saveDir); const int t = battle ? bgame.clearSeconds() : game.clearSeconds(); newBest = s.best[cur] == 0 || (uint32_t)t < s.best[cur];
        s.mask |= 1u << cur; if (newBest) s.best[cur] = (uint32_t)t; bestSeconds = (int)s.best[cur];
        if (FILE* f = fopen((a.saveDir + "/challenge.bin").c_str(), "wb")) { fwrite(&s, sizeof s, 1, f); fclose(f); }
    }
    static bool available(const std::string& root) { return challengeBoardsAvailable(root); }
    bool load(const std::string& root, int stage) { if (!loadStages((root + "/battle_stages.bin").c_str(), stages, 3) || stages.list.empty()) return false; begin(stage); return true; }
    void begin(int stage) { saved_ = false; cur = ((stage % (int)stages.list.size()) + (int)stages.list.size()) % (int)stages.list.size(); battle = ChallengeBattleGame::supports(cur);
        if (battle) bgame.start(stages.list[cur].st, cur, (uint32_t)SDL_GetTicks() * 2654435761u + (uint32_t)cur); else game.start(stages.list[cur].st, cur);   // types 3 and 4 run on the battle engine (core/challenge_battle.hpp)
        prev.clear(); }
    int phase() const { return battle ? bgame.phase : game.phase; }
    bool supportedNow() const { return battle || game.supported(); }
    Sim& simRef() { return battle ? bgame.game.sim : game.sim; }
    void skipIntro() { if (battle) bgame.skipIntro(); else game.skipIntro(); }
    int music() override { return 9; }
    void place(App& a, int dir) { if (phase() != ChallengeGame::Play || !aim.inside) return; lastDir = dir; if ((battle ? bgame.placeArrow(aim.cellX(), aim.cellY(), dir) : game.placeArrow(aim.cellX(), aim.cellY(), dir))) a.playSfx(1); else a.playSfx(0x13); }
    void event(App& a, const SDL_Event& e) override {
        if (e.type == SDL_MOUSEMOTION || e.type == SDL_MOUSEBUTTONDOWN) { aim.update(a, e.type == SDL_MOUSEMOTION ? e.motion.x : e.button.x, e.type == SDL_MOUSEMOTION ? e.motion.y : e.button.y, pf(a)); mouseCursor = true; }
        if (e.type == SDL_MOUSEBUTTONDOWN && e.button.button == SDL_BUTTON_LEFT) {
            if (phase() == ChallengeGame::Intro) skipIntro();                                   // flag 1: a tap skips the intro
            else if (game.phase == ChallengeGame::Failure) { begin(cur); a.playSfx(2); }              // flag 8: restart the stage
            else if (game.phase == ChallengeGame::Result) nextStageRequested = true;
            else if (!supportedNow()) back = true;
            else place(a, lastDir);
        }
        if (e.type == SDL_KEYDOWN && !e.key.repeat) {
            const SDL_Keycode k = e.key.keysym.sym;
            if (k == SDLK_p && supportedNow() && phase() == ChallengeGame::Play) { paused = !paused; return; }
            if (paused) return;
            if (k == SDLK_ESCAPE) { back = true; return; }                                             // flag 2: quit
            if (phase() == ChallengeGame::Intro && (k == SDLK_RETURN || k == SDLK_SPACE)) skipIntro();
            else if (game.phase == ChallengeGame::Failure && (k == SDLK_RETURN || k == SDLK_r)) { begin(cur); a.playSfx(2); }
            else if (game.phase == ChallengeGame::Result && (k == SDLK_RETURN || k == SDLK_SPACE)) nextStageRequested = true;
            else if (arrowKey(k) >= 0) { if (!a.headless) aim.update(a, 0, 0, pf(a)); place(a, arrowKey(k)); }
        }
    }
    void tick(App& a) override {
        if (nextStageRequested) { nextStageRequested = false; begin(cur + 1); return; }
        if (!supportedNow()) return;
        static const int pauseAt = getenv("CCR_PAUSE_TICK") ? atoi(getenv("CCR_PAUSE_TICK")) : -1;
        if (pauseAt >= 0 && cticks == pauseAt) paused = true;
        if (paused) return;
        ++cticks;
        Sim& sm = simRef();
        prev.resize(sm.ents.size());
        for (size_t i = 0; i < sm.ents.size(); i++) prev[i] = {sm.ents[i].x, sm.ents[i].z};
        const int before = phase();
        if (battle) bgame.tick(); else game.tick();
        if (phase() == ChallengeGame::Result && !saved_) { saved_ = true; saveResult(a); }
        if (phase() != before) { if (phase() == ChallengeGame::Success || phase() == ChallengeGame::Result) a.playSfx(0x15); else if (phase() == ChallengeGame::Failure) { a.playSfx(0x1b); char lb[200]; snprintf(lb, sizeof lb, "challenge stage %d: failed (%s)", cur + 1, (battle ? bgame.failReason : game.failReason) ? (battle ? bgame.failReason : game.failReason) : ""); a.log.write(1, lb); } }
    }
    const char* next() override { if (!back) return nullptr; back = false; return "MENU"; }
    void draw(App& a, float alpha) override {
        SDL_RenderSetLogicalSize(a.ren, GW, GH); SDL_RenderSetViewport(a.ren, nullptr);
        SDL_SetRenderDrawColor(a.ren, 0, 0, 26, 255); SDL_RenderClear(a.ren);
        a.stars.draw(a);
        const bool dc = dcLayout(a); const FieldLayout field = pf(a);
        a.board(stages.list[cur].st, 1, 1, field);                                                   // Challenge: floor 1, wall 1 (Render::createPlayfieldPreview)
        for (auto& ar : simRef().arrows) if (ar.live) a.arrow(ar.x, ar.y, ar.dir, 0, ar.hits, -1, field);
        a.drawFieldObjects(simRef(), prev, phase() == ChallengeGame::Play ? alpha : 1.0f, nullptr, field, dc, 2);
        if (supportedNow() && phase() == ChallengeGame::Play && mouseCursor && aim.inside) a.cursorAt(aim.x, aim.y, 0, cticks, false, field.scale());
        SDL_RenderSetViewport(a.ren, nullptr);
        std::string line;
        const int ph = phase(), pf = battle ? bgame.phaseFrame : game.phaseFrame, pt = battle ? bgame.playTick : game.playTick;
        const char* why = battle ? bgame.failReason : game.failReason;
        const int clearSec = battle ? bgame.clearSeconds() : game.clearSeconds();
        if (dc && supportedNow()) {
            const bool longRound = battle && bgame.type == 5;
            const int total = longRound ? 3600 : 1800;
            const int remaining = !battle ? ChallengeGame::kLimitTicks - game.playTick : longRound ? 3600 - bgame.game.clock : ChallengeBattleGame::kLimitTicks - bgame.playTick;
            a.drawDcTimerColumn(std::max(0, remaining), total);
        }
        if (!supportedNow()) line = "THIS CHALLENGE STAGE IS NOT PORTED YET  ESC BACK";
        else if (ph == ChallengeGame::Intro) line = "STAGE CHALLENGE " + std::to_string(cur + 1) + "  CLICK TO START";
        else if (ph == ChallengeGame::Countdown) line = std::to_string(1 + (ChallengeGame::kCountdownFrames - pf) / 36) + "...";
        else if (ph == ChallengeGame::Play) {
            const std::string time = "   TIME " + std::to_string(std::max(0, battle ? bgame.secondsLeft() + 1 : (ChallengeGame::kLimitTicks - pt) / 60 + 1));
            if (!battle) line = std::string(game.type == 2 ? "EATEN " : "SAVED ") + std::to_string(game.counter()) + " OF " + std::to_string(game.target) + time;
            else if (bgame.type == 3) line = "SCORE " + std::to_string(bgame.playerScore()) + " OF 100" + time;
            else if (bgame.type == 5) line = "YOUR TEAM " + std::to_string(bgame.teamScore(0)) + "  OTHERS " + std::to_string(bgame.teamScore(1)) + time;
            else line = "YOUR TEAM " + std::to_string(bgame.ownTeam()) + "  OTHERS " + std::to_string(bgame.enemyTeam()) + time;
        }
        else if (ph == ChallengeGame::Success || ph == ChallengeGame::Result) line = ph == ChallengeGame::Result ? "CLEAR!  " + std::to_string(clearSec) + " SEC  BEST " + std::to_string(bestSeconds) + (newBest ? " NEW" : "") + "  CLICK FOR NEXT" : "CLEAR!";
        else line = std::string("MISS: ") + (why ? why : "") + "   CLICK RETRY  ESC QUIT";
        if (paused && dc && a.dcPause.tex) {   // Flycast Challenge A1 pause frame: the Puzzle overlay 32 pixels lower, a "Player 1" plate at y 400 and the stage type's title on the plate sheet at (184, 104)
            a.drawDcPause(32.0f, 400.0f);
            static const int titleOfType[6] = {1, 2, 0, 3, 4, 5};   // type 0 Get mice (verified on A1); the rest follow the rules: 2 cats eat mice = Lunch time, 3 = 100 mice, 4 = Cat soccer, 5 = Final battle, 1 = Run away (by elimination)
            const int title = titleOfType[std::clamp(battle ? bgame.type : game.type, 0, 5)];
            if (title >= 0 && a.dcPuzzlePlate.tex) {
                const SDL_Rect plateDst{294, 166, 819, 70}, textSrc{256, 320 + 32 * title, 256, 32}, textDst{328, 173, 410, 51};
                SDL_RenderCopy(a.ren, a.dcPuzzlePlate.tex, nullptr, &plateDst); SDL_RenderCopy(a.ren, a.dcPause.tex, &textSrc, &textDst);
            }
            return;
        }
        if (!dc || (ph != ChallengeGame::Intro && ph != ChallengeGame::Countdown)) a.text(line, dc ? 210 : 24, dc ? 660 : 14, 30);   // the real Dreamcast Challenge screen shows no text line; the port keeps one for score and results
    }
};

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
        SDL_SetRenderTarget(a.ren, a.ssPrev); SDL_SetRenderDrawColor(a.ren, 0, 0, 0, 0); SDL_RenderClear(a.ren);
        a.board(stages.list[s].st, ((s / 25) & 3) + 2, 2, {32, 32}); SDL_RenderSetViewport(a.ren, nullptr); SDL_SetRenderTarget(a.ren, nullptr);
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
        if (e.type == SDL_KEYDOWN && e.key.keysym.sym == SDLK_TAB && gApp) {
            if (orig() && phase != 0x21) return;
            for (int offset = 1; offset < kStageSets; ++offset) {
                const int set = (gApp->stageSet + offset) % kStageSets;
                Stages candidate;
                if (!loadStageSet(rootDir, set, candidate)) continue;
                gApp->stageSet = set;
                stages = std::move(candidate);
                page = cur = sel = selPage = lastItem = 0;
                prevKey = -1;
                phase = 0x21;
                timer = 0;
                break;
            }
            return;
        }
        if (orig()) { origEvent(a, e); return; }
        if (e.type != SDL_KEYDOWN) return; int n = (int)stages.list.size(); SDL_Keycode k = e.key.keysym.sym;
        if (k == SDLK_RIGHT) cur = (cur + 1) % n; else if (k == SDLK_LEFT) cur = (cur + n - 1) % n;
        else if (k == SDLK_DOWN) cur = std::min(n - 1, cur + COLS); else if (k == SDLK_UP) cur = std::max(0, cur - COLS);
        else if (k == SDLK_PAGEDOWN) cur = std::min(n - 1, cur + PER); else if (k == SDLK_PAGEUP) cur = std::max(0, cur - PER);
        else if (k == SDLK_RETURN || k == SDLK_SPACE) go = true; else if (k == SDLK_ESCAPE) back = true;
        page = cur / PER;
    }
    void tick(App& a) override { if (orig()) origTick(a); }
    const char* next() override { if (orig()) { if (!leave) return nullptr; leave = false; if (leaveBack) return "MENU"; int s = std::max(0, std::min(99, chosen + selPage * 25)); if (gApp) gApp->nextStage = s; return "PUZZLE"; } if (back) { back = false; return "MENU"; } if (go) { go = false; if (gApp) gApp->nextStage = cur; return "PUZZLE"; } return nullptr; }
    void draw(App& a, float) override {
        if (orig()) { origDraw(a); return; }
        SDL_RenderSetLogicalSize(a.ren, W, H);
        SDL_SetRenderDrawColor(a.ren, 24, 24, 40, 255); SDL_RenderClear(a.ren);
        a.text(gApp && gApp->stageSet == 3 ? "PUZZLE  IMPORTED PACKS" : gApp && gApp->stageSet == 2 ? "PUZZLE  DREAMCAST EXPRESS" : gApp && gApp->stageSet ? "PUZZLE  MORE STAGES" : "PUZZLE  STAGE SELECT", 24, 14, 34);
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
    MouseAim aim;
    bool mouseCursor = false;
    PadAim padAim[4]{{37.5f, 37.5f}, {142.5f, 37.5f}, {37.5f, 97.5f}, {142.5f, 97.5f}};
    std::array<CursorTrail, 4> cursorTrails;
    std::array<SDL_FPoint, 4> playerTagStart;
    FieldLayout field;
    bool dcProjection = false;
    Stages stages; int cur = 0; uint32_t seed = 1; int lv[4] = {-1, 3, 3, 3}; BattleGame game; std::vector<std::pair<float, float>> prev; bool paused = false, back = false;
    // Mouse and keyboard control player 1. Controller face buttons place arrows.
    // FourBattleLoop (HD 1.0 0x1c2b8) mode 1: a 120-tick intro (the round panel from tick 1 for 75 ticks, the Round START banner at tick 90 for 45 ticks), then play starts
    // FourBattleLoop modes 3..5 (0x1c3c2..): 3 round end (60 ticks), 4 between rounds (result screen, next round after 240 ticks and a touch), 5 match over
    int mode = 2, modeTick = 0, wins[4] = {0, 0, 0, 0}, winPoint = 2, roundWinner = 0, drawFlag = 0, gTime = 0, rank[4] = {0, 0, 0, 0}; bool tapped = false, matchOver = false, congra = false; int sub5 = 0, cnt5 = 0;   // winPoint: GetWinPoint (initial data value 2)
    // ResultRocket tasks (0x1fe24 Cons, 0x1ff58 Exec, 0x1fcf8 Draw; smoke 0x1fe10 / flash 0x1fdc8): the win icon rises from y = 620 (2 per tick) to 361, pulses (scale 1 -> 4 -> 1) and settles
    struct Rocket { int player, state; float x, y, tx, scale, dscale; }; std::vector<Rocket> rockets_; struct Smoke { float x, y; int n; }; std::vector<Smoke> smokes_; struct Flash { float x, y, scale, delta; }; std::vector<Flash> flashes_;
    int intro = 0, roundNo = 1; struct Banner { int kind, mode, tick, life; }; std::vector<Banner> banners;
    DragGesture drag; int lastCatSfx = -100; int curX[4] = {2, 9, 2, 9}, curY[4] = {2, 2, 6, 6}; SDL_GameController* pads[4] = {nullptr, nullptr, nullptr, nullptr};
    std::vector<SDL_GameController*> unassignedPads;
    ~BattleMode() override {
        for (auto* pad : pads) if (pad) SDL_GameControllerClose(pad);
        for (auto* pad : unassignedPads) SDL_GameControllerClose(pad);
    }
    static bool padMatches(SDL_GameController* pad, SDL_JoystickID id) {
        return pad && SDL_JoystickInstanceID(SDL_GameControllerGetJoystick(pad)) == id;
    }
    auto findUnassignedPad(SDL_JoystickID id) {
        return std::find_if(unassignedPads.begin(), unassignedPads.end(),
                            [id](SDL_GameController* pad) { return padMatches(pad, id); });
    }
    void place(int p, int cx, int cy, int d) { if (lv[p] >= 0 || p >= 4 || intro < 120) return; if (game.rollPending()) return;   /* Core::isRouletteActive -> Input::invalidateArrow: human arrow input is dropped while the wheel spins (Android 0x2bcc0, 0x4a9a8); the simulation keeps running */ if (d < 0) { d = 0; for (auto& ar : game.sim.arrows) if (ar.live && ar.x == cx && ar.y == cy && ar.owner == p) d = (ar.dir + 1) & 3; } game.placeArrow(p, cx, cy, d); }
    bool keyPlayer(const SDL_KeyboardEvent& key) {
        const int direction = arrowKey(key.keysym.sym);
        if (lv[0] >= 0 || direction < 0) return false;
        if (!paused && !key.repeat && aim.inside) {
            mouseCursor = true;
            place(0, aim.cellX(), aim.cellY(), direction);
        }
        return true;
    }
    void padButton(int p, int button) {
        if (p < 0 || p > 3 || lv[p] >= 0) return;
        if (p == 0) mouseCursor = false;
        for (int d = 0; d < 4; d++) if (button == gApp->padMap.arrow[d]) { place(p, curX[p], curY[p], d); break; }
    }
    bool load(const std::string& root, int stage, uint32_t sd,
              const SettingsPaneItems::PadRules* rules = nullptr, int localTeam = -1) {
        if (!loadStages((root + "/battle_stages.bin").c_str(), stages, 2)) return false; cur = stage % (int)stages.list.size(); seed = sd;
        game.teamMode = localTeam < 0 ? getenv("CCR_TEAM") != nullptr : localTeam != 0;
        dcProjection = gApp && gApp->useModels3d();
        field = dcProjection ? dcBattleField : FieldLayout{};
        game.rocketPulseDecay = dcProjection ? 0.05f : 0.0f;
        game.gbaCpu = getenv("CCR_CPU") ? std::string(getenv("CCR_CPU")) == "gba" : (gApp && gApp->settings.cpuStyle == "gba");
        game.rouletteManager = true;
        game.rotateOwn = true;
        game.generatorParams = GenParams{};
        if (rules) {
            // HD 1.0 GA_OnGameFlag and GE_StartGenerator4Manager.
            constexpr float speeds[] = {0.25f, 0.75f, 1.0f, 1.25f, 2.0f};
            game.baseScale = speeds[rules->speedIndex];
            game.roundFrames = (rules->timeIndex + 1) * 60 * 60;
            game.generatorParams.pSpecial2 *= rules->highMice ? 5.0f : 1.0f;
            winPoint = rules->pointIndex;
        } else {
            game.baseScale = 1.0f;
            int minutes = getenv("CCR_MINUTES") ? atoi(getenv("CCR_MINUTES")) : 3;
            game.roundFrames = minutes * 60 * 60;
            winPoint = getenv("CCR_WINPOINT") ? atoi(getenv("CCR_WINPOINT")) : 2;
        }
        if (localTeam < 0) if (const char* h = getenv("CCR_HUMANS")) { int n = std::max(1, std::min(4, atoi(h))); for (int p = 0; p < 4; p++) lv[p] = p < n ? -1 : (lv[p] < 0 ? 3 : lv[p]); }   // CCR_HUMANS=1..4 human players, the rest CPU
        for (int p = 0; p < 4; p++) game.setCpu(p, lv[p]);
        game.sfx = [this](int id) {
            if (id == 7) {
                const int elapsed = gTime - lastCatSfx;
                lastCatSfx = gTime;  // ChuSECall updates the timer even for a suppressed request.
                if (elapsed < 3) return;
            }
            if (!gApp) return;
            if (gApp->headless && (id == 10 || id == 11 || id == 13 || id >= 117) &&
                getenv("CCR_ROULETTE_AUDIO_TRACE"))
                printf("roulette cue %d %d\n", game.frame, id);
            gApp->playSfx(id);
        };
        game.localPlayer = 0;
        restart(); return true;
    }
    void restart() {
        sub5 = 0; cnt5 = 0; congra = false; rockets_.clear(); smokes_.clear(); flashes_.clear();
        mode = 2; modeTick = 0; tapped = false; matchOver = false; intro = 0; banners.clear();
        cursorTrails = {};
        // FourBattleLoop masks the task server by RL_GetRoulette4Status.
        game.freezeOnRoll = game.cpuRunsOnFreeze = true;
        game.start(stages.list[cur].st, seed);
        if (dcProjection) {
            // The Dreamcast cursor constructor (0x8c0148c0) starts at the
            // centre of the player's rocket cell (0x8c01c65c).
            for (int p = 0; p < 4; ++p) {
                curX[p] = game.sim.rocketPos[p][0];
                curY[p] = game.sim.rocketPos[p][1];
                padAim[p] = {(curX[p] + 0.5f) * kCell, (curY[p] + 0.5f) * kCell};
            }
        }
        constexpr float toNative = 640.0f / GW;
        const float cursorInset = dcProjection ? 0.0f : field.cell / 2.0f;
        for (int p = 0; p < 4; ++p) {
            playerTagStart[p] = {(padAim[p].logicalX(1.0f, field) - cursorInset) * toNative - 130,
                                 (padAim[p].logicalY(1.0f, field) - cursorInset) * toNative -
                                     (dcProjection ? 20.0f : 35.0f)};
        }
        prev.clear();
        if (gApp) gApp->angs.clear();
    }
    // Original battle music (Android FUN_0003c56c / FUN_0003c534 / FUN_0003c828): while a roulette event runs the song depends on the outcome (table 0x63994: events 0..3 -> BGM ids 10, 9, 7, 8,
    // i.e. songs 6, 5, 3, 4); otherwise (and after the event) song 1 while more than 30 s are left (TI_CountDownBCDTimer > 0x2fff), song 2 in the last 30 s.
    int music() override { static const int evSong[4] = {6, 5, 3, 4}; int k = game.activeEventKind(); if (k >= 0 && k < 4) return evSong[k]; return game.clock > game.roundFrames - 60 * 30 ? 2 : 1; }
    void event(App& a, const SDL_Event& e) override {
        if (e.type == SDL_MOUSEMOTION || e.type == SDL_MOUSEBUTTONDOWN || e.type == SDL_MOUSEBUTTONUP) {
            aim.update(a, e.type == SDL_MOUSEMOTION ? e.motion.x : e.button.x,
                          e.type == SDL_MOUSEMOTION ? e.motion.y : e.button.y, field);
            mouseCursor = true;
        } else if (e.type == SDL_WINDOWEVENT && e.window.event == SDL_WINDOWEVENT_LEAVE) aim.inside = false;
        if (e.type == SDL_CONTROLLERDEVICEADDED) {
            const auto id = SDL_JoystickGetDeviceInstanceID(e.cdevice.which);
            if (id < 0 || findUnassignedPad(id) != unassignedPads.end()) return;
            for (auto* pad : pads) if (padMatches(pad, id)) return;
            if (auto* pad = SDL_GameControllerOpen(e.cdevice.which)) unassignedPads.push_back(pad);
        }
        else if (e.type == SDL_CONTROLLERDEVICEREMOVED) {
            for (auto& pad : pads) if (padMatches(pad, e.cdevice.which)) {
                SDL_GameControllerClose(pad);
                pad = nullptr;
            }
            const auto unassigned = findUnassignedPad(e.cdevice.which);
            if (unassigned != unassignedPads.end()) {
                SDL_GameControllerClose(*unassigned);
                unassignedPads.erase(unassigned);
            }
        }
        else if (e.type == SDL_CONTROLLERBUTTONDOWN) {
            for (int p = 0; p < 4; ++p) {
                if (padMatches(pads[p], e.cbutton.which)) {
                    padButton(p, e.cbutton.button);
                    return;
                }
            }
            const auto unassigned = findUnassignedPad(e.cbutton.which);
            if (unassigned == unassignedPads.end()) return;
            for (int p = 0; p < 4; ++p) {
                if (!pads[p] && lv[p] < 0) {
                    pads[p] = *unassigned;
                    unassignedPads.erase(unassigned);
                    if (p == 0) mouseCursor = false;
                    return;
                }
            }
        }
        else if (e.type == SDL_KEYDOWN && arrowKey(e.key.keysym.sym) >= 0) {
            if (!a.headless) aim.update(a, 0, 0, field);
            keyPlayer(e.key);
        }
        else if (e.type == SDL_KEYDOWN) { SDL_Keycode k = e.key.keysym.sym;
            if (k == SDLK_SPACE) paused = !paused; else if (k == SDLK_r) restart(); else if (k == SDLK_ESCAPE) back = true;
            else if (k == SDLK_RIGHTBRACKET) { cur = (cur + 1) % (int)stages.list.size(); restart(); } else if (k == SDLK_LEFTBRACKET) { cur = (cur + (int)stages.list.size() - 1) % (int)stages.list.size(); restart(); } }
        else if (e.type == SDL_MOUSEBUTTONDOWN && e.button.button == SDL_BUTTON_LEFT) { tapped = true; drag.begin(a, e, field); }
        else if (e.type == SDL_MOUSEBUTTONUP && e.button.button == SDL_BUTTON_LEFT && drag.on) { int cx = drag.cx, cy = drag.cy; int d = drag.end(a, e); if (d >= 0) place(0, cx, cy, d); }   // no drag = no arrow (Input::getArrowType returns 0)
    }
    void tick(App& a) override {
        if (back) return;
        tickBattle(a);
        // The iPad camera task switches StarsExec when the final win starts its rocket parade.
        a.stars.tick(mode == 5 && sub5 == 3);
    }
    int loggedMode_ = 0;
    void logRound(App& a) {   // match results for the rotating log
        char b[200]; snprintf(b, sizeof b, "battle %s: stage %d, round winner player %d%s, wins %d-%d-%d-%d, scores %d %d %d %d", matchOver ? "match over" : "round over", cur, roundWinner + 1, drawFlag ? " (draw)" : "", wins[0], wins[1], wins[2], wins[3], game.score.player[0], game.score.player[1], game.score.player[2], game.score.player[3]);
        a.log.write(1, b);
    }
    void tickBattle(App& a) { static const int pauseAt = getenv("CCR_PAUSE_TICK") ? atoi(getenv("CCR_PAUSE_TICK")) : -1; if (pauseAt >= 0 && game.frame == pauseAt) paused = true;   // headless test hook: pause at a Battle frame
        if (paused) return;
        if (mode >= 4 && loggedMode_ != mode) { loggedMode_ = mode; logRound(a); } else if (mode < 4) loggedMode_ = 0;
        if (intro >= 120 && mode == 2 && !game.rollPending()) {
            for (int p = 0; p < 4; ++p) {
                if (!pads[p] || lv[p] >= 0) continue;
                auto& pointer = padAim[p];
                pointer.tick(pads[p]);
                if (p == 0 && (pointer.x != pointer.previousX || pointer.y != pointer.previousY)) mouseCursor = false;
                curX[p] = static_cast<int>(pointer.x / kCell);
                curY[p] = static_cast<int>(pointer.y / kCell);
            }
        } else {
            for (auto& pointer : padAim) { pointer.previousX = pointer.x; pointer.previousY = pointer.y; }
        }
        for (int p = 0; p < 4; ++p) {
            const bool mouse = p == 0 && mouseCursor;
            cursorTrails[p].tick(mouse ? aim.x : padAim[p].logicalX(1.0f, field),
                                 mouse ? aim.y : padAim[p].logicalY(1.0f, field),
                                 lv[p] < 0 && (!mouse || aim.inside), mouse);
        }
        for (auto& bn : banners) bn.tick++; banners.erase(std::remove_if(banners.begin(), banners.end(), [](const Banner& bn) { return bn.tick >= bn.life; }), banners.end());   // SmpTskDelete when the counter reaches the lifetime
        if (intro < 120) { intro++; if (intro == 1) banners.push_back({1, roundNo, 0, 75}); if (intro == 90) banners.push_back({0, 6, 0, 45}); for (size_t i = 0; i < game.sim.ents.size() && i < prev.size(); i++) prev[i] = {game.sim.ents[i].x, game.sim.ents[i].z}; return; }
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
        for (size_t i = 0; i < game.sim.ents.size() && i < prev.size(); i++) prev[i] = {game.sim.ents[i].x, game.sim.ents[i].z}; for (int q = 0; q < 4; q++) { game.humanCell[q][0] = curX[q]; game.humanCell[q][1] = curY[q]; }
        if (mouseCursor && aim.inside) { game.humanCell[0][0] = aim.cellX(); game.humanCell[0][1] = aim.cellY(); }
        const int previousClock = game.clock;
        if (mode == 2 || mode == 3) game.tick();
        // FB_Exe_GAME checks the BCD time after decrementing it.
        const int left = game.roundFrames - game.clock;
        if (mode == 2 && game.clock != previousClock && left >= 0 && left % 60 == 0) {
            const int seconds = left / 60;
            const int banner = seconds == 3 ? 2 : seconds == 2 ? 1 : seconds == 1 ? 0 :
                               seconds == 30 ? 3 : seconds == 60 ? 4 : seconds == 120 ? 5 : -1;
            if (banner >= 0) banners.push_back({0, banner, 0, App::countLife(banner)});
        }
        a.stepAngles(game.sim);
    }
    void endRound() {   // FourBattleLoop mode 3 after 60 ticks: the only player (team battle: team) with dense rank 0 wins the round
        if (game.teamMode) { int ts[2] = {game.score.team[0], game.score.team[1]}; int tr[2] = {ts[0] >= ts[1] ? 0 : 1, ts[1] >= ts[0] ? 0 : 1}; for (int p = 0; p < 4; p++) rank[p] = tr[p & 1]; modeTick = 0; rockets_.clear(); smokes_.clear(); flashes_.clear();
            if (tr[0] != tr[1]) { int w = tr[0] == 0 ? 0 : 1; roundWinner = w; drawFlag = 0; int old = wins[w]++; matchOver = old == winPoint; } else { drawFlag = 1; matchOver = false; } mode = matchOver ? 5 : 4; return; }   // the team result rocket (ResultRocketCons, team branch) is not ported
        int sc[4]; for (int p = 0; p < 4; p++) sc[p] = game.score.player[p]; int cnt = 0, w = 0; for (int p = 0; p < 4; p++) { int r = 0; for (int q = 0; q < 4; q++) if (sc[q] > sc[p]) { bool dup = false; for (int k = 0; k < q; k++) if (sc[k] == sc[q]) dup = true; if (!dup) r++; } rank[p] = r; if (r == 0) { cnt++; w = p; } }
        modeTick = 0; rockets_.clear(); smokes_.clear(); flashes_.clear(); if (cnt == 1) { roundWinner = w; drawFlag = 0; int old = wins[w]++; matchOver = old == winPoint; if (gApp) rockets_.push_back({w, 0, (float)w * gApp->layF(0x108) + gApp->layF(0x104) + gApp->layF(0x19c + winPoint * 0x14 + 4 * (wins[w] - 1)), 620.0f, 361.0f, 1.0f, 0.4f}); } else { drawFlag = 1; matchOver = false; }
        mode = matchOver ? 5 : 4; }
    void nextRound() { roundNo++; cur = (cur + 1) % (int)stages.list.size(); restart(); mode = 2; }   // GA_SetStageNumber(stage + 1, wrapping to 0)
    const char* next() override { if (back) { back = false; return "MENU"; } return nullptr; }
    void draw(App& a, float alpha) override {
        SDL_RenderSetLogicalSize(a.ren, GW, GH); SDL_RenderSetViewport(a.ren, nullptr); SDL_SetRenderDrawColor(a.ren, 0, 0, 0, 255); SDL_RenderClear(a.ren);
        a.stars.draw(a);
        const bool dcHud = mode < 4 && a.useDcBattleHud() && (!game.teamMode || a.dcBattleHud.fr.size() >= 41);
        const bool dcPlayerOverlays = dcHud && a.dcBattleHud.fr.size() >= 39;
        const int left = game.over ? 0 : std::max(0, game.roundFrames - game.clock);
        const int seconds = (left + 59) / 60;
        if (!dcHud) a.drawBattleHud(game.teamMode, intro > 0 && !game.over, game.score);
        { static const int fc[4] = {1, 3, 4, 5}; a.board(stages.list[cur].st, fc[cur & 3], 0, field); }   // battle floor colour {1,3,4,5}[stage & 3], wall colour 0 (createPlayfieldPreview)
        for (auto& ar : game.sim.arrows) if (ar.live) a.arrow(ar.x, ar.y, ar.dir, ar.owner, ar.hits, ar.ttl, field);
        for (int p = 0; p < 4; ++p) {
            const bool mouse = p == 0 && mouseCursor;
            if (lv[p] >= 0 || (mouse && !aim.inside)) continue;
            const int x = mouse ? aim.cellX() : curX[p], y = mouse ? aim.cellY() : curY[p];
            if (game.sim.coll[y][x] & 0xF00) a.cursor(x, y, p, game.frame, true, field);
        }
        a.drawFieldObjects(game.sim, prev, paused ? 1.0f : alpha, game.puku, field, dcProjection);
        if (dcHud) { if (game.teamMode) a.drawDcTeamHud(game.score, lv, left, game.roundFrames); else a.drawDcBattleHud(game.score, lv, left, game.roundFrames); }
        const int ranks[] = {game.rankOf(0), game.rankOf(1), game.rankOf(2), game.rankOf(3)};
        const int taskAge = intro + game.frame;
        if (intro > 0 && !game.over)
            a.drawBattleRankOverlay(game.teamMode, paused, taskAge, game.score, ranks,
                                    wins, game.sim.rocketPos, dcPlayerOverlays, field);
        if (dcPlayerOverlays) { if (game.teamMode) a.drawDcTeamCrowns(taskAge, game.score); else a.drawDcScoreCrowns(taskAge, game.score, ranks); }
        for (int p = 0; p < 4; ++p)
            if (lv[p] < 0) cursorTrails[p].draw(a, p, field.cell, dcProjection);
        const float cursorAlpha = paused ? 1.0f : alpha;
        for (int p = 0; p < 4; ++p) {
            if (lv[p] >= 0) continue;
            if (p == 0 && mouseCursor) {
                if (aim.inside) a.cursorAt(aim.x, aim.y, p, game.frame, false, field.scale());
            } else if (dcProjection) {
                a.drawDcBattlePadCursor(padAim[p].logicalX(cursorAlpha, field),
                                        padAim[p].logicalY(cursorAlpha, field), p, taskAge);
            } else padAim[p].draw(a, p, game.frame, cursorAlpha, field);
        }
        if (dcPlayerOverlays) {
            for (int p = 0; p < 4; ++p)
                if (lv[p] < 0) a.drawDcPlayerTag(p, taskAge, playerTagStart[p]);
        }
        if (!dcHud) { SDL_RenderSetViewport(a.ren, nullptr);   // in-play timer (HD 1.0 clock2D 0x20e54): image 0x69 at scale 0.8; layout struct +0xf0 x = 78, +0xf8 step = 14, +0xf4 y = 84;
          // minutes at x, colon (frame 10) at x + step, tens at x + step + step / 2, ones at that + step; the value is TI_GetGameBCDTime = the BCD countdown rounded up to the next second
          int mm = seconds / 60, ss = seconds % 60;
          const float y = 84.0f; float x = 78.0f; const float step = 14.0f;
          if (a.hdTime.tex) {
              a.blit(a.hdTime, mm % 10, x, y, 0.8f);
              a.blit(a.hdTime, 10, x + step, y, 0.8f);
              const float x2 = x + step + static_cast<int>(step) / 2;
              a.blit(a.hdTime, ss / 10, x2, y, 0.8f);
              a.blit(a.hdTime, ss % 10, x2 + step, y, 0.8f);
          } else if (a.timefont.fr.size() > 10 && a.timefont.fr[0].w > 0) {
              const float scale = 14.0f / a.timefont.fr[0].w;
              const int frames[] = {mm % 10, 10, ss / 10, ss % 10};
              for (int i = 0; i < 4; ++i) a.blit(a.timefont, frames[i], 65.0f + i * 19.0f, y, scale);
          } }
        SDL_RenderSetViewport(a.ren, nullptr); for (auto& bn : banners) { if (bn.kind == 1) a.roundPanel(bn.mode, bn.tick); else a.battleCount(bn.mode, bn.tick); }   // banner tasks drawn over the HUD
        int rollTick, roller, outcome;
        if (game.rouletteDrawState(rollTick, roller, outcome)) {
            const auto& cell = game.sim.rocketPos[roller];
            const auto pose = battleRoulettePose(rollTick, cell[0], cell[1], outcome, field.left, field.top, field.cell / kCell);
            // Slot 99 is byte-identical across the five exported iPad language packs.
            a.rouletteDraw.draw(a.ren, a.root + "/ret_all/loc_en/img_99", pose, GW, GH);
            if (a.headless && getenv("CCR_ROULETTE_DRAW_TRACE"))
                printf("roulette %d %d %d %d %d %a %a %a %a\n", game.frame, rollTick, roller,
                       cell[0], cell[1], pose.x, pose.y, pose.degrees, pose.scale);
        }
        if (mode >= 4) { int sc[4]; for (int p = 0; p < 4; p++) sc[p] = game.score.player[p]; int reach = 0; if (!(gTime & 0x20) && !matchOver) for (int p = 0; p < 4; p++) if (wins[p] == winPoint) reach |= 1 << p;   // PM_DispReach: blinks with the global time, none when the match is over
            if (game.teamMode) { int ts[2] = {game.score.team[0], game.score.team[1]}, tr[2] = {rank[0], rank[1]}; a.judgeWinTeam(ts, tr, wins, roundWinner, drawFlag, winPoint, reach & 3, true); } else a.judgeWin(sc, rank, wins, roundWinner, drawFlag, winPoint, reach, true);
            for (auto& s : smokes_) a.drawImage(0x92, s.n, s.x, s.y - a.layF(0x230), 0, 1.0f, 255);
            for (auto& rk : rockets_) a.drawImage(0x5d, rk.player, rk.x, rk.y - a.layF(0x22c), 0, rk.scale, 255);
            if (congra) { a.drawImage(0x90, 0, a.layF(0x208), a.layF(0x20c), 0, 1.0f, 255); a.drawImage(0x62, roundWinner, a.layF(0x214), a.layF(0x218), 0, 2.0f, 255); }   // DispCongraDrawPriority 0x1f990 (the congratulation rockets, CongraRocketCons, are not ported)
            for (auto& f : flashes_) a.drawImage(0x87, 4, f.x, f.y - a.layF(0x22c), 0, f.scale, 0x40); }
        SDL_RenderSetViewport(a.ren, nullptr);
        if (paused && dcProjection && a.dcPause.tex) {
            if (game.teamMode && a.dcPauseTeam.tex) {   // Team Battle: four quads at y 352 (Flycast team pause frame): 256 x 128 at x 16 and 320, 64 x 128 at x 272 and 576
                static const int srcX[4] = {0, 256, 320, 576}, srcW[4] = {256, 64, 256, 64}, dstX[4] = {16, 272, 320, 576};
                for (int i = 0; i < 4; ++i) {
                    const SDL_Rect src{srcX[i], 0, srcW[i], 128}, dst{(int)std::lround(dstX[i] * 1.6f), 563, (int)std::lround(srcW[i] * 1.6f), 205};
                    SDL_RenderCopy(a.ren, a.dcPauseTeam.tex, &src, &dst);
                }
            } else if (a.dcPauseBoxes.tex) for (int p = 0; p < 4; ++p) {   // the score panels become the four win boxes (Flycast Battle pause frame, 640 x 480): 128 x 128 at x 16 + 152p, y 320, with a 32 x 128 end piece (their grey rocket icons are not drawn yet)
                const SDL_Rect big{160 * p, 0, 128, 128}, end{160 * p + 128, 0, 32, 128};
                const SDL_Rect bigDst{(int)std::lround((16 + 152 * p) * 1.6f), 512, 205, 205}, endDst{(int)std::lround((144 + 152 * p) * 1.6f), 512, 51, 205};
                SDL_RenderCopy(a.ren, a.dcPauseBoxes.tex, &big, &bigDst); SDL_RenderCopy(a.ren, a.dcPauseBoxes.tex, &end, &endDst);
            }
            if (a.dcPauseMarks.tex) {   // three 64 x 64 rockets per box (Flycast pause frames): the sheet's grey rocket for rounds not won, the player's colour for each win (marks: white, blue, yellow, red, green, rebl, yegr)
                const int count = game.teamMode ? 2 : 4;
                for (int p = 0; p < count; ++p) for (int k = 0; k < 3; ++k) {
                    const bool won = k < wins[p];
                    const int tile = won ? (game.teamMode ? 5 + p : 1 + p) : 0;
                    const float x = game.teamMode ? 191.0f + 150.0f * p + 40.0f * k : 38.0f + 152.0f * p + 40.0f * k, y = game.teamMode ? 395.0f : 361.0f;
                    const SDL_Rect src{64 * tile, 0, 64, 64}, dst{(int)std::lround(x * 1.6f), (int)std::lround(y * 1.6f), 102, 102};
                    SDL_RenderCopy(a.ren, a.dcPauseMarks.tex, &src, &dst);
                }
            }
            a.drawDcPause(-60.0f, 270.0f);
        }   // Flycast Battle pause frame: the Puzzle overlay 60 pixels higher (the "Player 1" plate and the win boxes are not drawn yet)
    }
};

static int saveFrame(SDL_Renderer* renderer, const char* path) {
    int width, height;
    if (SDL_GetRendererOutputSize(renderer, &width, &height) < 0) return 1;
    // SDL2 reads back the current viewport. Capture the full output even if
    // the screen changed its logical size after drawing, as TitleMode does.
    if (SDL_RenderSetLogicalSize(renderer, 0, 0) < 0) return 1;
    SDL_Surface* surface = SDL_CreateRGBSurfaceWithFormat(0, width, height, 32, SDL_PIXELFORMAT_ARGB8888);
    if (!surface) return 1;
    const bool saved = SDL_RenderReadPixels(renderer, nullptr, SDL_PIXELFORMAT_ARGB8888,
                                            surface->pixels, surface->pitch) == 0 &&
                       SDL_SaveBMP(surface, path) == 0;
    SDL_FreeSurface(surface);
    return saved ? 0 : 1;
}

int main(int argc, char** argv) {
#ifdef _WIN32
    if (argc > 1 && !strcmp(argv[1], "--prepare")) return prepareLauncherAssets();
#elif !defined(__EMSCRIPTEN__)
    if (argc > 1 && !strcmp(argv[1], "--prepare")) return prepareLauncherAssets(argc, argv);
#endif
    if (getenv("CCR_STARTUP_FLOW_TRACE")) {
        Startup splash;
        float elapsed;
        int press;
        while (scanf("%f %d", &elapsed, &press) == 2) {
            if (press) splash.press();
            const bool jingle = splash.tick(elapsed);
            printf("%d %a %d %d %d\n", static_cast<int>(splash.phase), splash.timer,
                   jingle ? 1 : 0, splash.opacity(), splash.blackout());
            if (splash.phase == Startup::Title) splash = Startup{};
        }
        return 0;
    }
    if (getenv("CCR_MOUSE_GHOST_TRACE")) {
        MouseGhost ghost{};
        while (scanf("%f %f %d", &ghost.x, &ghost.z, &ghost.angle) == 3) {
            ghost.age = 0;
            for (int i = 1; i < 48; ++i) {
                ghost.tick();
                printf("%d %d %d %a %a %a\n", ghost.image(), ghost.age & 7, ghost.flags(),
                       ghost.x * (CELL / kCell) + OX, ghost.z * (CELL / kCell) + OY, ghost.scale());
            }
        }
        return 0;
    }
    if (getenv("CCR_ROCKET_LAUNCH_TRACE")) {
        int player, team, x, y;
        unsigned globalTime;
        while (scanf("%d %d %d %d %u", &player, &team, &x, &y, &globalTime) == 5) {
            if (player < 0 || player >= 4 || x < 0 || x >= kCols || y < 0 || y >= kRows) return 1;
            const float worldX = (x + 0.5f) * kCell, worldZ = (y + 0.5f) * kCell;
            RocketLaunch launch;
            RocketLid lid;
            std::vector<std::pair<RocketLaunchImage, int>> images;
            for (int tick = 0; tick < 240; ++tick) {
                images.clear();
                lid.tick(x, y, globalTime + tick);
                launch.tick(globalTime + tick);
                if (launch.visible())
                    images.emplace_back(rocketLaunchImage(player, team != 0, worldX, worldZ, launch.height,
                                                          CELL / kCell, OX, OY), 0);
                const auto lidImage = rocketLidImage(player, team != 0, x, y, lid.openness,
                                                     worldX, worldZ, CELL / kCell, OX, OY);
                images.emplace_back(RocketLaunchImage{static_cast<int>(worldZ), lidImage.image, lidImage.frame,
                    255, lidImage.x, lidImage.y, 0.8f}, lidImage.flags);
                for (const auto& puff : launch.smoke)
                    if (puff.visible())
                        images.emplace_back(rocketSmokeImage(worldX, worldZ, puff, CELL / kCell, OX, OY), 0);
                std::stable_sort(images.begin(), images.end(),
                                 [](const auto& a, const auto& b) { return a.first.depth < b.first.depth; });
                for (const auto& [image, flags] : images)
                    printf("%d %d %d %d %d %d %a %a %a\n", tick, image.depth, image.image, image.frame,
                           image.alpha, flags, image.x, image.y, image.scale);
            }
            puts("");
        }
        return 0;
    }
    if (getenv("CCR_ROCKET_LID_TRACE")) {
        int player, team, x, y;
        unsigned globalTime;
        while (scanf("%d %d %d %d %u", &player, &team, &x, &y, &globalTime) == 5) {
            if (player < 0 || player >= 4 || x < 0 || x >= kCols || y < 0 || y >= kRows) return 1;
            RocketLid lid;
            for (int i = 0; i < 640; ++i) {
                lid.tick(x, y, globalTime + i);
                const auto image = rocketLidImage(player, team != 0, x, y, lid.openness,
                    (x + 0.5f) * kCell, (y + 0.5f) * kCell, CELL / kCell, OX, OY);
                printf("%d %d %d %a %d %d %d %a %a\n", lid.phase, lid.count, lid.angle,
                       lid.openness, image.image, image.frame, image.flags, image.x, image.y);
            }
        }
        return 0;
    }
    if (getenv("CCR_ROULETTE_MESH_TRACE")) {
        RoulettePose pose;
        float u0, v0, u1, v1;
        while (scanf("%f %f %f %f %f %f %f %f", &pose.x, &pose.y, &pose.degrees,
                     &pose.scale, &u0, &v0, &u1, &v1) == 8) {
            const auto mesh = makeRouletteMesh(u0, v0, u1, v1);
            for (const auto index : mesh.indices) printf("%u ", static_cast<unsigned>(index));
            puts("");
            for (const auto& v : mesh.vertices) {
                const auto p = projectRouletteVertex(v, pose);
                printf("%a %a %a %a %a %a %a %a %a %a %a\n",
                       v.nx, v.ny, v.nz, v.x, v.y, v.z, v.u, v.v, p.x, p.y, p.inverseDepth);
            }
        }
        return 0;
    }
    if (getenv("CCR_ROULETTE_POSE_TRACE")) {
        int rocketX, rocketY, outcome;
        while (scanf("%d %d %d", &rocketX, &rocketY, &outcome) == 3) {
            if (rocketX < 0 || rocketX >= kCols || rocketY < 0 || rocketY >= kRows ||
                outcome < 0 || outcome >= 8) return 1;
            for (int tick = 0; tick < 120; ++tick) {
                const auto pose = battleRoulettePose(tick, rocketX, rocketY, outcome, OX, OY, CELL / kCell);
                printf("%a %a %a %a\n", pose.x, pose.y, pose.degrees, pose.scale);
            }
        }
        return 0;
    }
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
    bool portableFlag = false;   // --portable anywhere on the command line: saves, settings and logs go to <program folder>/data
    for (int i = 1; i < argc; ) { if (!strcmp(argv[i], "--portable")) { portableFlag = true; for (int j = i; j < argc; j++) argv[j] = argv[j + 1]; --argc; } else ++i; }
    // Asset folder: first argument, else CCR_ASSETS, else the usual places (next to the exe, the repo's local cache, %APPDATA%/ChuChuRocketReNyastered/assets, then the older %APPDATA%/ReNyastered/assets).
    std::string root; int shift = 0;
    auto hasAssets = [](const std::string& d) { FILE* f = fopen((d + "/ret_all/r0930.tex.bin").c_str(), "rb"); if (f) { fclose(f); return true; } return false; };
    if (argc >= 2 && std::string(argv[1]) != "menu" && std::string(argv[1]) != "models" && std::string(argv[1]) != "puzzle" && std::string(argv[1]) != "battle" && std::string(argv[1]) != "title") { root = argv[1]; shift = 1; }
    else {
        std::vector<std::string> cand; if (const char* e = getenv("CCR_ASSETS")) cand.push_back(e);
        char* bp = SDL_GetBasePath(); std::string base = bp ? bp : ""; if (bp) SDL_free(bp);
        cand.push_back(base + "assets"); cand.push_back(base + "../../local/cache/assets"); cand.push_back(base + "../../../local/cache/assets"); cand.push_back("local/cache/assets");
#ifndef _WIN32
        if (const char* xdg = getenv("XDG_CONFIG_HOME")) cand.push_back(std::string(xdg) + "/ChuChuRocketReNyastered/assets");   // where RecompLauncher's {config} points on Linux
        if (const char* home = getenv("HOME")) { cand.push_back(std::string(home) + "/.config/ChuChuRocketReNyastered/assets"); cand.push_back(std::string(home) + "/Library/Application Support/ChuChuRocketReNyastered/assets"); }
#endif
        if (const char* ap = getenv("APPDATA")) { cand.push_back(std::string(ap) + "/ChuChuRocketReNyastered/assets"); cand.push_back(std::string(ap) + "/ReNyastered/assets"); }   // the second is the folder name used before 2026-11-17
        for (auto& c : cand) if (hasAssets(c)) { root = c; break; }
        if (root.empty()) {
#ifdef _WIN32
            const char* msg = "Game assets not found.\n\nIn RecompLauncher run Easy Setup first and pick the folder with your original game files. Without the launcher, run setup.cmd from a source checkout, or start ccr with the asset folder as its first argument (or set CCR_ASSETS).";
#else
            const char* msg = "Game assets not found.\n\nThey are extracted once from your own copies of the game. In RecompLauncher run Easy Setup first and pick the folder with your original files. Without the launcher, run this once in a terminal:\n    ./ccr --prepare \"/folder/with/your/game/files\"\n(needs Python 3.10+ with Pillow; add --download-python to let setup install Pillow into a private environment), then start ccr again. The assets go to ~/.config/ChuChuRocketReNyastered/assets and setup.log there lists problems.";
#endif
            printf("%s\n", msg); if (!getenv("CCR_SHOT") && !getenv("CCR_HEADLESS") && !getenv("CCR_BENCH") && SDL_Init(SDL_INIT_VIDEO) == 0) { SDL_ShowSimpleMessageBox(SDL_MESSAGEBOX_ERROR, "ChuChu Rocket! Re-Nyastered", msg, nullptr); SDL_Quit(); } return 2;
        }
    }
    if (argc > 1 + shift && !strcmp(argv[1 + shift], "--launcher")) {
        if (!hasAssets(root)) {   // launched by RecompLauncher before setup finished (or setup failed): say so instead of exiting silently
            const std::string m = "The extracted game assets were not found in:\n" + root + "\n\nIn RecompLauncher run Easy Setup (pick the folder with your original game files) and wait for it to finish; its log is setup.log in the same data folder.";
            printf("%s\n", m.c_str()); if (!getenv("CCR_SHOT") && !getenv("CCR_HEADLESS") && !getenv("CCR_BENCH") && SDL_Init(SDL_INIT_VIDEO) == 0) { SDL_ShowSimpleMessageBox(SDL_MESSAGEBOX_ERROR, "ChuChu Rocket! Re-Nyastered", m.c_str(), nullptr); SDL_Quit(); }
            return 2;
        }
        ++shift;
        if (!getenv("CCR_FULLSCREEN")) {
            const char* mode = getenv("RECOMPLAUNCHER_MODE");
            if (mode && !strcmp(mode, "bigpicture")) ccrSetEnv("CCR_FULLSCREEN", "1", 1);
        }
        while (argc > 1 + shift) {
            const char* arg = argv[1 + shift];
            if (!strcmp(arg, "--fullscreen")) ccrSetEnv("CCR_FULLSCREEN", "1", 1);
            else if (!strcmp(arg, "--windowed")) ccrSetEnv("CCR_FULLSCREEN", "", 1);
            else if (!strcmp(arg, "--vsync")) ccrSetEnv("CCR_VSYNC", "1", 1);
            else if (!strcmp(arg, "--no-vsync")) ccrSetEnv("CCR_VSYNC", "0", 1);
            else if (!strcmp(arg, "--filter=nearest")) ccrSetEnv("CCR_FILTER", "nearest", 1);
            else if (!strcmp(arg, "--filter=linear")) ccrSetEnv("CCR_FILTER", "linear", 1);
            else break;
            ++shift;
        }
    }

    App app; app.root = root;
    {   // data folder, readable settings and the rotating log (core/userdata.hpp)
        char* bp2 = SDL_GetBasePath(); const std::string programDir = bp2 ? bp2 : "."; if (bp2) SDL_free(bp2);
        const bool quiet = (getenv("CCR_SHOT") || getenv("CCR_HEADLESS") || getenv("CCR_BENCH")) && !getenv("CCR_USERDATA_TEST");   // test runs never create settings or logs (CCR_USERDATA_TEST=1 exercises them headlessly)
        app.saveDir = quiet ? root : resolveDataDir(programDir, root, portableFlag);
        if (!quiet) {
            const Settings st = loadOrCreateSettings(app.saveDir); app.settings = st;
            if (st.fullscreen) ccrSetEnv("CCR_FULLSCREEN", "1", 0);
            if (!st.vsync) ccrSetEnv("CCR_VSYNC", "0", 0);
            ccrSetEnv("CCR_FILTER", st.filter.c_str(), 0);
            if (st.width > 0 && st.height > 0) { char sz[40]; snprintf(sz, sizeof sz, "%dx%d", st.width, st.height); ccrSetEnv("CCR_SIZE", sz, 0); }
            app.padMap = loadOrCreatePadMap(app.saveDir);
            app.log.open(app.saveDir, st.logLevel, st.logMaxKb, st.logKeepFiles);
            gImportDir = app.saveDir + "/imports"; std::error_code iec; std::filesystem::create_directories(gImportDir, iec);
            app.log.write(1, ("session start; data folder " + app.saveDir + "; assets " + root).c_str());
        }
    }
    if (!app.init()) return 2; gApp = &app;
    std::string start = argc > 1 + shift ? argv[1 + shift] : "STARTUP"; int stageNo = argc > 2 + shift ? atoi(argv[2 + shift]) : 0; uint32_t seed = argc > 3 + shift ? (uint32_t)atoi(argv[3 + shift]) : 1;
    int lv[4] = {-1, 3, 3, 3}; if (argc > 4 + shift) { int k = 1; for (const char* p = argv[4 + shift]; *p && k < 4; ) { lv[k++] = atoi(p); while (*p && *p != ',') p++; if (*p == ',') p++; } }
    std::unique_ptr<Screen> mode;
    auto enter = [&](const std::string& name) -> bool {
        app.log.write(2, ("screen " + name).c_str());
        if (name == "STARTUP" && app.titleOk && StartupMode::available(app)) mode = std::make_unique<StartupMode>();
        else if ((name == "STARTUP" || name == "TITLE" || name == "title") && app.titleOk) mode = std::make_unique<TitleMode>();
        else if (name == "PUZZLE" || name == "puzzle") { auto m = std::make_unique<PuzzleMode>(); int sn = app.nextStage >= 0 ? app.nextStage : stageNo; app.nextStage = -1; if (!m->load(app.root, sn)) { printf("cannot load puzzle stages\n"); return false; } mode = std::move(m); }
        else if (name == "CHALLENGE" || name == "challenge") { auto m = std::make_unique<ChallengeMode>(); if (!m->load(app.root, app.nextStage >= 0 ? app.nextStage : stageNo)) { printf("cannot load challenge stages\n"); return false; } app.nextStage = -1; mode = std::move(m); }
        else if (name == "STAGES") { auto m = std::make_unique<StageSelectMode>(); if (!m->load(app.root, app.nextStage >= 0 ? app.nextStage : stageNo)) { printf("cannot load puzzle stages\n"); return false; } mode = std::move(m); }
        else if (name == "BATTLE" && BattleSetupMode::available(app)) mode = std::make_unique<BattleSetupMode>();
        else if (name == "BATTLE" || name == "battle" || name == "BATTLE_MATCH") {
            auto battle = std::make_unique<BattleMode>();
            if (name == "BATTLE_MATCH") {
                const auto& setup = static_cast<const BattleSetupMode&>(*mode);
                const auto& p = setup.players.controls;
                const int cpu[] = {0, p.d3c, p.d40, p.d44};
                for (int i = 0; i < 4; ++i) battle->lv[i] = cpu[i] ? setup.players.levels[i] : -1;
                if (!battle->load(app.root, setup.settings.stage, seed, &setup.settings.rules, setup.frame.team)) return false;
                if (app.headless && getenv("CCR_BATTLE_SETUP_TRACE")) {
                    printf("battle %d %d %d %d %a %a %d %d %d %d\n", battle->cur, battle->game.teamMode,
                           battle->winPoint, battle->game.roundFrames, battle->game.baseScale,
                           battle->game.generatorParams.pSpecial2, battle->lv[0], battle->lv[1], battle->lv[2], battle->lv[3]);
                }
            } else {
                memcpy(battle->lv, lv, sizeof lv);
                if (!battle->load(app.root, stageNo, seed)) { puts("cannot load battle stages"); return false; }
            }
            for (int i = 0; i < SDL_NumJoysticks(); ++i) if (SDL_IsGameController(i)) {
                SDL_Event event{};
                event.type = SDL_CONTROLLERDEVICEADDED;
                event.cdevice.which = i;
                battle->event(app, event);
            }
            mode = std::move(battle);
        }
        else if (name == "HELP" && HelpMode::ok(app)) mode = std::make_unique<HelpMode>();
        else if (name == "CREDITS" && CreditsMode::ok(app)) mode = std::make_unique<CreditsMode>(app);
        else if (name == "MODELS" || name == "models") { auto m = std::make_unique<ModelViewerMode>(); if (!m->load(app)) { printf("cannot load dreamcast/models.bin (run tools/export_dc_models.py)\n"); return false; } mode = std::move(m); }
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
            int stage = 0, team = 0;
            if (const char* selection = getenv("CCR_PAD_PREVIEW")) {
                if (sscanf(selection, "%d,%d", &stage, &team) != 2 || stage < 0 || stage >= 25 ||
                    (team != 0 && team != 1)) return 1;
            }
            SDL_RenderSetLogicalSize(app.ren, GW, GH);
            PlayersFrame frame;
            frame.state = 0x25;
            frame.pane = 1;
            frame.team = team;
            frame.draw(app, [&](int) {
                SettingsPaneItems::drawPadStageGrid(app, stage, nullptr);
                SettingsPaneItems::drawPadRules(app, rules, [&](const SDL_Rect& rect) {
                    app.drawBattlePreview(stage, team != 0, rect);
                }, nullptr);
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
    if (const char* path = getenv("CCR_PAD_PREVIEW_DUMP")) {
        std::ofstream output(path, std::ios::binary);
        for (bool team : {false, true}) {
            for (int stage = 0; stage < 25; ++stage) {
                const auto pixels = app.battlePreviewPixels(stage, team);
                if (pixels.empty() || !output.write(reinterpret_cast<const char*>(pixels.data()),
                                                    pixels.size() * sizeof(uint16_t))) return 1;
            }
        }
        output.close();
        return output.fail() ? 1 : 0;
    }
    if (getenv("CCR_BATTLE_HUD_TRACE")) {
        int team, showScores, tick, paused, ranks[4], wins[4], rockets[4][2];
        Scoreboard score;
        while (scanf("%d %d %d %d %d %d %d %d %d %d %d %d %d", &team, &showScores, &tick,
                     &score.player[0], &score.player[1], &score.player[2], &score.player[3],
                     &score.team[0], &score.team[1], &ranks[0], &ranks[1], &ranks[2], &ranks[3]) == 13) {
            if (scanf("%d %d %d %d %d", &paused, &wins[0], &wins[1], &wins[2], &wins[3]) != 5) return 1;
            for (auto& rocket : rockets)
                if (scanf("%d %d", &rocket[0], &rocket[1]) != 2) return 1;
            std::vector<std::string> trace;
            app.imgLog = &trace;
            app.drawBattleHud(team != 0, showScores != 0, score);
            app.drawBattleRankOverlay(team != 0, paused != 0, tick, score, ranks, wins, rockets);
            app.imgLog = nullptr;
            for (const auto& call : trace) puts(call.c_str());
            puts("end");
        }
        return 0;
    }
    if (getenv("CCR_PAD_MATCH_RULES")) {
        int points, speed, time, high;
        while (scanf("%d %d %d %d", &points, &speed, &time, &high) == 4) {
            if (points < 0 || points > 4 || speed < 0 || speed > 4 || time < 0 || time > 2 ||
                high < 0 || high > 1) return 1;
            const SettingsPaneItems::PadRules rules{points, speed, time, high != 0, false};
            BattleMode battle;
            if (!battle.load(app.root, 0, 1, &rules)) return 1;
            for (int round = 0; round < 2; ++round) {
                printf("%d %d %a %a %a\n", battle.winPoint, battle.game.roundFrames,
                       battle.game.sim.catSpeed, battle.game.sim.mouseSpeed, battle.game.gen->params().pSpecial2);
                if (round == 0) battle.restart();
            }
        }
        return 0;
    }
    if (getenv("CCR_PAD_SETTINGS_INPUT")) {
        SettingsPaneItems::LocalPadInput input;
        int x, y, phase, high, split, locked;
        while (scanf("%d %d %d %d %d %d %d %d %d %d", &x, &y, &phase, &input.stage,
                     &input.rules.pointIndex, &input.rules.speedIndex, &input.rules.timeIndex,
                     &high, &split, &locked) == 10) {
            input.rules.highMice = high != 0;
            input.rules.split = split != 0;
            input.launching = locked != 0;
            const auto result = input.touch(x, y, phase);
            printf("%d %d %d %d %d %d %d %d %d\n", static_cast<int>(result.action), result.sound,
                   input.stage, input.rules.pointIndex, input.rules.speedIndex, input.rules.timeIndex,
                   input.rules.highMice, input.rules.split, input.launching);
        }
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
    if (getenv("CCR_PAD_PLAYERS_INPUT")) {
        LocalPlayersPaneInput input;
        int x, y, phase;
        while (scanf("%d %d %d", &x, &y, &phase) == 3) {
            input.touch(x, y, phase);
            const auto& p = input.controls;
            printf("%d %d %d %d %d %d %d %d %d %d", p.d3c, p.d40, p.d44, p.d58, p.a40,
                   input.levels[1], input.levels[2], input.levels[3], p.openSettings, p.gameState38);
            for (int sound : p.sfx) printf(" %d", sound);
            puts("");
        }
        return 0;
    }
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
        if (const char* aim = getenv("CCR_AIM")) {
            SDL_Event e{};
            e.type = SDL_MOUSEMOTION;
            if (sscanf(aim, "%d,%d", &e.motion.x, &e.motion.y) == 2) mode->event(app, e);
        }
        auto sendKeys = [&]() {
            const char* keys = getenv("CCR_KEYS");
            if (!keys) return;
            for (const char* p = keys; *p; p++) {
                SDL_Event e{};
                e.type = SDL_KEYDOWN;
                switch (*p) {
                case 'D': e.key.keysym.sym = SDLK_DOWN; break;
                case 'U': e.key.keysym.sym = SDLK_UP; break;
                case 'L': e.key.keysym.sym = SDLK_LEFT; break;
                case 'R': e.key.keysym.sym = SDLK_RIGHT; break;
                case 'E': e.key.keysym.sym = SDLK_RETURN; break;
                default: e.key.keysym.sym = *p; break;
                }
                mode->event(app, e);
                if (const char* nx = mode->next()) enter(nx);
            }
        };
        const char* keyTickOption = getenv("CCR_KEY_TICK");
        const int keyTick = keyTickOption ? atoi(keyTickOption) : -1;
        if (keyTick < 0) sendKeys();
        std::vector<std::array<int, 3>> clicks; if (const char* c = getenv("CCR_CLICKS")) { int t, x, y, n; const char* p = c; while (sscanf(p, "%d:%d,%d%n", &t, &x, &y, &n) == 3) { clicks.push_back({t, x, y}); p += n; if (*p == ';') p++; else break; } }   // headless test input: tick:x,y;... (window pixels)
        int lastSong = -2; for (int i = 0; i < ticks; i++) {
            if (i == keyTick) sendKeys();
            for (auto& ck : clicks) if (ck[0] == i) for (int ty : {SDL_MOUSEBUTTONDOWN, SDL_MOUSEBUTTONUP}) { SDL_Event e{}; e.type = ty; e.button.button = SDL_BUTTON_LEFT; e.button.x = ck[1]; e.button.y = ck[2]; mode->event(app, e); if (const char* nx = mode->next()) enter(nx); } mode->tick(app); if (const char* nx = mode->next()) enter(nx); if (getenv("CCR_AUDIO_TEST") && mode->music() >= 0) { app.pumpMusic(mode->music()); if (app.curTrack != lastSong) { lastSong = app.curTrack; printf("tick %d: song %d (DC track %d), loop %zu..%zu of %zu samples\n", i, lastSong, lastSong + 4, app.songs[lastSong].loopStart, app.songs[lastSong].loopEnd, app.songs[lastSong].pcm.size()); } } }
        mode->draw(app, 1.0f);
        const int result = saveFrame(app.ren, shot);
        mode.reset(); app.battlePreviewTexture.reset(); app.rouletteDraw.reset(); app.models3d.clear(); SDL_Quit();
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
        (void)sec; mode.reset(); app.battlePreviewTexture.reset(); app.rouletteDraw.reset(); app.models3d.clear(); SDL_Quit(); return 0;
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
        while (acc >= dt) { bool a1 = false, a2 = false;   // controller-only quit: hold the two quit buttons on any pad
            for (int i = 0; i < SDL_NumJoysticks(); i++) if (SDL_IsGameController(i)) if (SDL_GameController* c = SDL_GameControllerFromInstanceID(SDL_JoystickGetDeviceInstanceID(i))) { if (SDL_GameControllerGetButton(c, (SDL_GameControllerButton)app.padMap.quitA) && SDL_GameControllerGetButton(c, (SDL_GameControllerButton)app.padMap.quitB)) a1 = a2 = true; }
            if (app.quitHold.tick(a1, a2, app.padMap.quitHoldTicks)) { app.log.write(1, "quit: controller quit combo held"); app.quit = true; break; }
            mode->tick(app); if (const char* nx = mode->next()) { enter(nx); acc = 0; break; } acc -= dt; }   // screens that finish by themselves (fade-outs) are polled after every tick
        if (mode->music() >= 0) app.pumpMusic(mode->music());
        mode->draw(app, (float)(acc / dt)); SDL_RenderPresent(app.ren);
    };
#ifdef __EMSCRIPTEN__
    emscripten_set_main_loop_arg([](void* f) { (*(std::function<void()>*)f)(); }, &frame, 0, 1);   // browser drives the frames (requestAnimationFrame); never returns
#else
    while (!app.quit) frame();
#endif
    app.log.write(1, "session end"); mode.reset(); app.battlePreviewTexture.reset(); app.rouletteDraw.reset(); app.models3d.clear(); SDL_Quit(); return 0;
}
