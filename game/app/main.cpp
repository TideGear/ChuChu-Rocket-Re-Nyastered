// Re-Nyastered game app (vertical slice, in progress): battle mode vs CPU players with extracted iOS art.
// usage: ccr <cache assets dir> [stage 0..24] [seed] [cpu levels e.g. 3,3,3 for players 1..3]
// Controls: click a cell = place/rotate your (player 1) arrow, right click = nothing, SPACE pause, R restart, ESC quit.
// Simulation: fixed 60 Hz BattleGame (verified against the original); drawing is interpolated.
#define SDL_MAIN_HANDLED
#include <SDL.h>
#include "../core/battle.hpp"
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>
using namespace ccr;

struct Sheet { SDL_Texture* tex = nullptr; int w = 0, h = 0; std::vector<SDL_Rect> fr; };

static bool loadSheet(SDL_Renderer* r, const std::string& base, Sheet& s) {
    FILE* f = fopen((base + ".tex.bin").c_str(), "rb"); if (!f) return false;
    uint32_t wh[2]; if (fread(wh, 4, 2, f) != 2) { fclose(f); return false; }
    s.w = (int)wh[0]; s.h = (int)wh[1];
    std::vector<uint8_t> px((size_t)s.w * s.h * 4);
    if (fread(px.data(), 1, px.size(), f) != px.size()) { fclose(f); return false; }
    fclose(f);
    s.tex = SDL_CreateTexture(r, SDL_PIXELFORMAT_ABGR8888, SDL_TEXTUREACCESS_STATIC, s.w, s.h);
    SDL_UpdateTexture(s.tex, nullptr, px.data(), s.w * 4); SDL_SetTextureBlendMode(s.tex, SDL_BLENDMODE_BLEND);
    f = fopen((base + ".frames.bin").c_str(), "rb"); if (!f) return false;
    uint32_t n; if (fread(&n, 4, 1, f) != 1) { fclose(f); return false; }
    std::vector<float> fl(n * 9); if (fread(fl.data(), 4, fl.size(), f) != fl.size()) { fclose(f); return false; }
    fclose(f);
    for (uint32_t i = 0; i < n; i++) { const float* e = &fl[i * 9];
        s.fr.push_back({(int)std::lround(e[0] * s.w), (int)std::lround(e[1] * s.h), (int)std::lround((e[2] - e[0]) * s.w), (int)std::lround((e[3] - e[1]) * s.h)}); }
    return true;
}

struct Stages { std::vector<Stage> st; };
static bool loadStages(const char* path, Stages& out) {
    FILE* f = fopen(path, "rb"); if (!f) return false;
    uint32_t n; if (fread(&n, 4, 1, f) != 1) return false;
    for (uint32_t i = 0; i < n; i++) {
        uint8_t h[4], w[237], t[32]; Stage s;
        if (fread(h, 1, 4, f) != 4 || fread(s.tiles, 1, 108, f) != 108 || fread(w, 1, 237, f) != 237) break;
        if (h[1]) fseek(f, h[1] * 3, SEEK_CUR);
        if (fread(t, 1, 32, f) != 32) break;
        for (int r = 0; r < 10; r++) for (int c = 0; c < 12; c++) s.hw[r * 12 + c] = w[25 * r + c];
        for (int r = 0; r < 9; r++) for (int c = 0; c < 13; c++) s.vw[r * 13 + c] = w[25 * r + 12 + c];
        if (h[0] == 2) out.st.push_back(s);          // battle stages only
    }
    fclose(f); return !out.st.empty();
}

int main(int argc, char** argv) {
    if (argc < 2) { printf("usage: ccr <cache assets dir> [stage] [seed] [cpu levels]\n"); return 2; }
    std::string root = argv[1];
    Stages stages; if (!loadStages((root + "/battle_stages.bin").c_str(), stages)) { printf("cannot load battle stages from %s\n", root.c_str()); return 2; }
    int stageNo = argc > 2 ? atoi(argv[2]) % (int)stages.st.size() : 0; uint32_t seed = argc > 3 ? (uint32_t)atoi(argv[3]) : 1;
    int lv[4] = {-1, 3, 3, 3};
    if (argc > 4) { int k = 1; for (const char* p = argv[4]; *p && k < 4; ) { lv[k++] = atoi(p); while (*p && *p != ',') p++; if (*p == ',') p++; } }
    if (getenv("CCR_SHOT") || getenv("CCR_HEADLESS")) {                     // automated runs must never take the user's screen or audio
        SDL_setenv("SDL_VIDEODRIVER", "dummy", 1); SDL_setenv("SDL_AUDIODRIVER", "dummy", 1); SDL_SetHint(SDL_HINT_RENDER_DRIVER, "software");
    }
    if (SDL_Init(SDL_INIT_VIDEO | SDL_INIT_AUDIO) != 0) { printf("SDL: %s\n", SDL_GetError()); return 2; }
    const int CELL = 64, W = 12 * CELL, H = 9 * CELL + 64;
    // Resolution/frame-rate independence: logic is a fixed 60 Hz tick, drawing is interpolated, and everything is drawn in a fixed logical space
    // scaled to the window (any size up to and beyond 4K; env CCR_SIZE=3840x2160, CCR_FULLSCREEN=1, CCR_VSYNC=0 for uncapped frame rate, F11 / V at runtime).
    int winW = W, winH = H; if (const char* sz = getenv("CCR_SIZE")) { int a = 0, b = 0; if (sscanf(sz, "%dx%d", &a, &b) == 2 && a > 0 && b > 0) { winW = a; winH = b; } }
    SDL_SetHint(SDL_HINT_RENDER_SCALE_QUALITY, getenv("CCR_FILTER") ? getenv("CCR_FILTER") : "linear");
    Uint32 wflags = SDL_WINDOW_RESIZABLE | SDL_WINDOW_ALLOW_HIGHDPI | (getenv("CCR_FULLSCREEN") ? SDL_WINDOW_FULLSCREEN_DESKTOP : 0);
    SDL_Window* win = SDL_CreateWindow("ChuChu Rocket! Re-Nyastered", SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED, winW, winH, wflags);
    bool vsync = !(getenv("CCR_VSYNC") && atoi(getenv("CCR_VSYNC")) == 0);
    SDL_Renderer* ren = SDL_CreateRenderer(win, -1, (getenv("CCR_SHOT") || getenv("CCR_HEADLESS")) ? SDL_RENDERER_SOFTWARE : (SDL_RENDERER_ACCELERATED | (vsync ? SDL_RENDERER_PRESENTVSYNC : 0)));
    SDL_RenderSetLogicalSize(ren, W, H);
    std::string ret = root + "/ret_all/";
    Sheet atlas, cat, mouse, gold, digits, crowns, timefont;
    bool ok = loadSheet(ren, ret + "r0930", atlas) && loadSheet(ren, ret + "r0447", cat) && loadSheet(ren, ret + "r0503", mouse) && loadSheet(ren, ret + "r0484", gold)
           && loadSheet(ren, ret + "r0729", digits) && loadSheet(ren, ret + "r0726", crowns) && loadSheet(ren, ret + "r0749", timefont);
    if (!ok) { printf("missing sprite sheets in %s (run tools/export_sprites.py <ccrret> <dir> all)\n", ret.c_str()); return 2; }

    // Music: Dreamcast CD track (best source, see docs/audio.md) streamed from a WAV, looped. Battle uses songs 5 (long time left) and 6 (late), = tracks 09 and 10.
    SDL_AudioDeviceID adev = 0; Uint8* mus[2] = {nullptr, nullptr}; Uint32 mlen[2] = {0, 0}; SDL_AudioSpec mspec{};
    for (int i = 0; i < 2; i++) { std::string wp = root + "/dreamcast/audio/track" + (i ? "10" : "09") + ".wav"; SDL_AudioSpec sp; if (!SDL_LoadWAV(wp.c_str(), &sp, &mus[i], &mlen[i])) { mus[i] = nullptr; } else mspec = sp; }
    int curTrack = -1; size_t musPos = 0;
    if (mus[0] && !getenv("CCR_SHOT")) { SDL_AudioSpec want = mspec, have; adev = SDL_OpenAudioDevice(nullptr, 0, &want, &have, 0); if (adev) SDL_PauseAudioDevice(adev, 0); }
    auto pumpMusic = [&](int track) {
        if (!adev || !mus[track]) return;
        if (curTrack != track) { SDL_ClearQueuedAudio(adev); curTrack = track; musPos = (size_t)(2.0 * mspec.freq) * 4; }   // skip the disc's 2 s lead-in
        while (SDL_GetQueuedAudioSize(adev) < (Uint32)(mspec.freq * 4 / 2)) {                                              // keep ~0.5 s queued
            Uint32 chunk = (Uint32)(mspec.freq * 4 / 10); if (musPos + chunk > mlen[track]) { musPos = (size_t)(2.0 * mspec.freq) * 4; }
            SDL_QueueAudio(adev, mus[track] + musPos, chunk); musPos += chunk; }
    };
    BattleGame game; game.rouletteManager = true; game.baseScale = 1.0f;
    { int minutes = getenv("CCR_MINUTES") ? atoi(getenv("CCR_MINUTES")) : 3; game.roundFrames = 60 * 60 * minutes; }   // Android NGI_SetGameTimer: 1-3 minute rounds (setting-dependent)
    for (int p = 0; p < 4; p++) game.setCpu(p, lv[p]);
    struct Snap { float x, z; }; std::vector<Snap> prev;
    auto restart = [&]() { game.start(stages.st[stageNo], seed); prev.clear(); };
    restart(); bool paused = false;
    static const SDL_Color pcol[4] = {{60, 120, 255, 255}, {40, 190, 70, 255}, {240, 60, 60, 255}, {250, 170, 30, 255}};
    auto drawNumber = [&](int v, int x, int y, int hgt) {
        std::string s = std::to_string(v); int cx = x;
        for (char c : s) { const SDL_Rect& fr = digits.fr[c - '0']; int w = fr.w * hgt / fr.h; SDL_Rect d{cx, y, w, hgt}; SDL_RenderCopy(ren, digits.tex, &fr, &d); cx += w + 2; }
    };
    auto draw = [&](float alpha) {
        SDL_SetRenderDrawColor(ren, 24, 24, 40, 255); SDL_RenderClear(ren);
        const Stage& st = stages.st[stageNo];
        for (int r = 0; r < 9; r++) for (int c = 0; c < 12; c++) {
            SDL_Rect dst{c * CELL, r * CELL, CELL, CELL}; SDL_RenderCopy(ren, atlas.tex, &atlas.fr[8 + ((r + c) & 1)], &dst);
            uint8_t t = st.tiles[r * 12 + c];
            if (t >= 1 && t <= 4) { static const int sph[4] = {20, 21, 22, 23}; SDL_RenderCopy(ren, atlas.tex, &atlas.fr[sph[t - 1]], &dst); }
            if (t >= 5 && t <= 8) SDL_RenderCopy(ren, atlas.tex, &atlas.fr[7], &dst);
        }
        SDL_SetRenderDrawColor(ren, 20, 20, 90, 255);
        for (int r = 0; r < 10; r++) for (int c = 0; c < 12; c++) if (st.hw[r * 12 + c]) { SDL_Rect q{c * CELL - 1, r * CELL - 3, CELL + 2, 6}; SDL_RenderFillRect(ren, &q); }
        for (int r = 0; r < 9; r++) for (int c = 0; c < 13; c++) if (st.vw[r * 13 + c]) { SDL_Rect q{c * CELL - 3, r * CELL - 1, 6, CELL + 2}; SDL_RenderFillRect(ren, &q); }
        for (auto& a : game.sim.arrows) if (a.live) {
            static const float dx[4] = {0, -1, 0, 1}, dy[4] = {1, 0, -1, 0};
            float cx = (a.x + 0.5f) * CELL, cy = (a.y + 0.5f) * CELL, ux = dx[a.dir], uy = dy[a.dir], px = -uy, py = ux; SDL_Color col = pcol[a.owner & 3];
            SDL_Vertex v[3] = {{{cx + ux * 24, cy + uy * 24}, col, {0, 0}}, {{cx - ux * 12 + px * 20, cy - uy * 12 + py * 20}, col, {0, 0}}, {{cx - ux * 12 - px * 20, cy - uy * 12 - py * 20}, col, {0, 0}}};
            SDL_RenderGeometry(ren, nullptr, v, 3, nullptr, 0);
        }
        if (prev.size() < game.sim.ents.size()) for (size_t i = prev.size(); i < game.sim.ents.size(); i++) prev.push_back({game.sim.ents[i].x, game.sim.ents[i].z});
        for (size_t i = 0; i < game.sim.ents.size(); i++) {
            const Entity& en = game.sim.ents[i]; if (!en.alive || en.done || en.rocketIn) continue;
            float x = prev[i].x + (en.x - prev[i].x) * alpha, z = prev[i].z + (en.z - prev[i].z) * alpha;
            if (std::fabs(en.x - prev[i].x) > 100 || std::fabs(en.z - prev[i].z) > 100) { x = en.x; z = en.z; }
            Sheet& sh = !en.mouse ? cat : (en.type == 1 ? gold : mouse);
            const SDL_Rect& fr = sh.fr[(en.heading * 8) & 31]; float sc = CELL * 0.95f / fr.w; int dw = (int)(fr.w * sc), dh = (int)(fr.h * sc);
            SDL_Rect dst{(int)(x * (CELL / 15.0f)) - dw / 2, (int)(z * (CELL / 15.0f)) - dh * 2 / 3, dw, dh}; SDL_RenderCopy(ren, sh.tex, &fr, &dst);
        }
        // HUD: scores per player (digit font) and remaining time
        for (int p = 0; p < 4; p++) { SDL_Rect b{p * (W / 4) + 6, 9 * CELL + 6, W / 4 - 12, 52}; SDL_SetRenderDrawColor(ren, pcol[p].r, pcol[p].g, pcol[p].b, 255); SDL_RenderFillRect(ren, &b);
            drawNumber(game.score.player[p], b.x + 12, b.y + 8, 36);
            if (game.over) { int rk = game.rankOf(p); const SDL_Rect& fr = crowns.fr[rk < 4 ? rk : 3]; int ch = 44, cw = fr.w * ch / fr.h; SDL_Rect d{b.x + b.w - cw - 8, b.y + 4, cw, ch}; SDL_RenderCopy(ren, crowns.tex, &fr, &d); } }
        { int rem = game.over ? 0 : (game.roundFrames - game.frame) / 60; int m = rem / 60, sec = rem % 60; int x = W / 2 - 60, y = 6; const int hgt = 28;
          auto glyph = [&](int idx) { const SDL_Rect& fr = timefont.fr[idx]; int w = fr.w * hgt / fr.h; SDL_Rect d{x, y, w, hgt}; SDL_RenderCopy(ren, timefont.tex, &fr, &d); x += w + 1; };
          glyph(m % 10); glyph(10); glyph(sec / 10); glyph(sec % 10); }
    };
    const double dt = 1.0 / 60.0; double acc = 0;
    if (const char* shot = getenv("CCR_SHOT")) {
        int ticks = getenv("CCR_TICKS") ? atoi(getenv("CCR_TICKS")) : 600;
        for (int i = 0; i < ticks; i++) { for (size_t k = 0; k < game.sim.ents.size() && k < prev.size(); k++) prev[k] = {game.sim.ents[k].x, game.sim.ents[k].z}; game.tick(); }
        draw(1.0f); SDL_Surface* s = SDL_CreateRGBSurfaceWithFormat(0, W, H, 32, SDL_PIXELFORMAT_ARGB8888);
        SDL_RenderReadPixels(ren, nullptr, SDL_PIXELFORMAT_ARGB8888, s->pixels, s->pitch); SDL_SaveBMP(s, shot); SDL_FreeSurface(s); SDL_Quit(); return 0;
    }
    Uint64 last = SDL_GetPerformanceCounter(); bool run = true;
    while (run) {
        SDL_Event e;
        while (SDL_PollEvent(&e)) {
            if (e.type == SDL_QUIT) run = false;
            else if (e.type == SDL_KEYDOWN) { SDL_Keycode k = e.key.keysym.sym; if (k == SDLK_ESCAPE) run = false; else if (k == SDLK_F11) { Uint32 f = SDL_GetWindowFlags(win); SDL_SetWindowFullscreen(win, (f & SDL_WINDOW_FULLSCREEN_DESKTOP) ? 0 : SDL_WINDOW_FULLSCREEN_DESKTOP); }
                else if (k == SDLK_v) { vsync = !vsync; SDL_RenderSetVSync(ren, vsync); }
                else if (k == SDLK_SPACE) paused = !paused; else if (k == SDLK_r) restart();
                else if (k == SDLK_RIGHT) { stageNo = (stageNo + 1) % (int)stages.st.size(); restart(); } else if (k == SDLK_LEFT) { stageNo = (stageNo + (int)stages.st.size() - 1) % (int)stages.st.size(); restart(); } }
            else if (e.type == SDL_MOUSEBUTTONDOWN && e.button.button == SDL_BUTTON_LEFT) {
                float lx, ly; SDL_RenderWindowToLogical(ren, e.button.x, e.button.y, &lx, &ly); int cx = (int)(lx / CELL), cy = (int)(ly / CELL);
                if (cx >= 0 && cx < 12 && cy >= 0 && cy < 9) { int d = 0; for (auto& a : game.sim.arrows) if (a.live && a.x == cx && a.y == cy && a.owner == 0) d = (a.dir + 1) & 3; game.placeArrow(0, cx, cy, d); }
            }
        }
        Uint64 now = SDL_GetPerformanceCounter(); acc += (double)(now - last) / (double)SDL_GetPerformanceFrequency(); last = now; if (acc > 0.25) acc = 0.25;
        while (!paused && acc >= dt) { for (size_t k = 0; k < game.sim.ents.size() && k < prev.size(); k++) prev[k] = {game.sim.ents[k].x, game.sim.ents[k].z}; game.tick(); acc -= dt; }
        pumpMusic(game.frame > game.roundFrames - 60 * 30 ? 1 : 0);
        draw(paused ? 1.0f : (float)(acc / dt)); SDL_RenderPresent(ren);
    }
    SDL_Quit(); return 0;
}
