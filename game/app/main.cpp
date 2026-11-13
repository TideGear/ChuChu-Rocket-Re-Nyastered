// Re-Nyastered game app (vertical slice, in progress): menu, puzzle mode and battle mode vs CPU players with extracted iOS art.
// usage: ccr <cache assets dir> [mode: menu|puzzle|battle] [stage] [seed] [cpu levels e.g. 3,3,3]
// Simulation: fixed 60 Hz (verified against the original); drawing is interpolated and resolution independent (logical 768x640 scaled to the window).
// Env: CCR_SIZE=3840x2160 CCR_FULLSCREEN=1 CCR_VSYNC=0 CCR_FILTER=nearest|linear CCR_MINUTES=1..3; CCR_SHOT=<bmp> CCR_TICKS=n renders headlessly (dummy video/audio, software renderer).
#define SDL_MAIN_HANDLED
#include <SDL.h>
#include "../core/battle.hpp"
#include <array>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <memory>
#include <string>
#include <vector>
using namespace ccr;

static const int CELL = 64, W = 12 * CELL, H = 9 * CELL + 64;
static const SDL_Color pcol[4] = {{60, 120, 255, 255}, {40, 190, 70, 255}, {240, 60, 60, 255}, {250, 170, 30, 255}};

struct Sheet { SDL_Texture* tex = nullptr; int w = 0, h = 0; std::vector<SDL_Rect> fr; };

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
    SDL_AudioDeviceID adev = 0; Uint8* mus[2] = {nullptr, nullptr}; Uint32 mlen[2] = {0, 0}; SDL_AudioSpec mspec{}; int curTrack = -1; size_t musPos = 0;

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
            s.fr.push_back({(int)std::lround(e[0] * s.w), (int)std::lround(e[1] * s.h), (int)std::lround((e[2] - e[0]) * s.w), (int)std::lround((e[3] - e[1]) * s.h)}); }
        return true;
    }
    bool init() {
        headless = getenv("CCR_SHOT") || getenv("CCR_HEADLESS");
        if (headless) { SDL_setenv("SDL_VIDEODRIVER", "dummy", 1); SDL_setenv("SDL_AUDIODRIVER", "dummy", 1); SDL_SetHint(SDL_HINT_RENDER_DRIVER, "software"); }   // never take the user's screen/audio
        if (SDL_Init(SDL_INIT_VIDEO | SDL_INIT_AUDIO) != 0) { printf("SDL: %s\n", SDL_GetError()); return false; }
        int winW = W, winH = H; if (const char* sz = getenv("CCR_SIZE")) { int a = 0, b = 0; if (sscanf(sz, "%dx%d", &a, &b) == 2 && a > 0 && b > 0) { winW = a; winH = b; } }
        SDL_SetHint(SDL_HINT_RENDER_SCALE_QUALITY, getenv("CCR_FILTER") ? getenv("CCR_FILTER") : "linear");
        Uint32 wf = SDL_WINDOW_RESIZABLE | SDL_WINDOW_ALLOW_HIGHDPI | (getenv("CCR_FULLSCREEN") ? SDL_WINDOW_FULLSCREEN_DESKTOP : 0);
        win = SDL_CreateWindow("ChuChu Rocket! Re-Nyastered", SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED, winW, winH, wf);
        vsync = !(getenv("CCR_VSYNC") && atoi(getenv("CCR_VSYNC")) == 0);
        ren = SDL_CreateRenderer(win, -1, headless ? SDL_RENDERER_SOFTWARE : (SDL_RENDERER_ACCELERATED | (vsync ? SDL_RENDERER_PRESENTVSYNC : 0)));
        SDL_RenderSetLogicalSize(ren, W, H);
        std::string ret = root + "/ret_all/";
        if (!(loadSheet(ret + "r0930", atlas) && loadSheet(ret + "r0447", cat) && loadSheet(ret + "r0503", mouse) && loadSheet(ret + "r0484", gold) && loadSheet(ret + "r0729", digits) &&
              loadSheet(ret + "r0726", crowns) && loadSheet(ret + "r0749", timefont) && loadSheet(ret + "r0023", font))) { printf("missing sprite sheets in %s (tools/export_sprites.py <ccrret> <dir> all)\n", ret.c_str()); return false; }
        for (int i = 0; i < 2; i++) { std::string wp = root + "/dreamcast/audio/track" + (i ? "10" : "09") + ".wav"; SDL_AudioSpec sp; if (SDL_LoadWAV(wp.c_str(), &sp, &mus[i], &mlen[i])) mspec = sp; else mus[i] = nullptr; }
        if (mus[0] && !headless) { SDL_AudioSpec want = mspec, have; adev = SDL_OpenAudioDevice(nullptr, 0, &want, &have, 0); if (adev) SDL_PauseAudioDevice(adev, 0); }
        return true;
    }
    void pumpMusic(int track) {                          // Dreamcast CD audio (best source, docs/audio.md): songs 5/6 for battle, looped; the disc has a 2 s lead-in
        if (!adev || !mus[track]) return;
        if (curTrack != track) { SDL_ClearQueuedAudio(adev); curTrack = track; musPos = (size_t)(2.0 * mspec.freq) * 4; }
        while (SDL_GetQueuedAudioSize(adev) < (Uint32)(mspec.freq * 4 / 2)) {
            Uint32 chunk = (Uint32)(mspec.freq * 4 / 10); if (musPos + chunk > mlen[track]) musPos = (size_t)(2.0 * mspec.freq) * 4;
            SDL_QueueAudio(adev, mus[track] + musPos, chunk); musPos += chunk; }
    }
    // --- drawing helpers ---
    void number(int v, int x, int y, int hgt) {
        std::string s = std::to_string(v); int cx = x;
        for (char c : s) { const SDL_Rect& fr = digits.fr[c - '0']; int w = fr.w * hgt / fr.h; SDL_Rect d{cx, y, w, hgt}; SDL_RenderCopy(ren, digits.tex, &fr, &d); cx += w + 2; }
    }
    int textWidth(const std::string& s, int hgt) { int w = 0; for (unsigned char c : s) { const SDL_Rect& fr = font.fr[c]; w += fr.h ? fr.w * hgt / fr.h : hgt / 2; w += 1; } return w; }
    void text(const std::string& s, int x, int y, int hgt) {              // glyph sheet r0023: frame = character code
        for (unsigned char c : s) { const SDL_Rect& fr = font.fr[c]; if (!fr.h) { x += hgt / 2; continue; } int w = fr.w * hgt / fr.h; SDL_Rect d{x, y, w, hgt}; SDL_RenderCopy(ren, font.tex, &fr, &d); x += w + 1; }
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
    void entities(const Sim& sim, std::vector<std::pair<float, float>>& prev, float alpha) {
        while (prev.size() < sim.ents.size()) prev.push_back({sim.ents[prev.size()].x, sim.ents[prev.size()].z});
        for (size_t i = 0; i < sim.ents.size(); i++) {
            const Entity& en = sim.ents[i]; if (!en.alive || en.done || en.rocketIn) continue;
            float x = prev[i].first + (en.x - prev[i].first) * alpha, z = prev[i].second + (en.z - prev[i].second) * alpha;
            if (std::fabs(en.x - prev[i].first) > 100 || std::fabs(en.z - prev[i].second) > 100) { x = en.x; z = en.z; }
            Sheet& sh = !en.mouse ? cat : (en.type == 1 ? gold : mouse);
            const SDL_Rect& fr = sh.fr[(en.heading * 8) & 31]; float sc = CELL * 0.95f / fr.w; int dw = (int)(fr.w * sc), dh = (int)(fr.h * sc);
            SDL_Rect dst{(int)(x * (CELL / 15.0f)) - dw / 2, (int)(z * (CELL / 15.0f)) - dh * 2 / 3, dw, dh}; SDL_RenderCopy(ren, sh.tex, &fr, &dst);
        }
    }
};

struct Mode { virtual ~Mode() {} virtual void event(App&, const SDL_Event&) {} virtual void tick(App&) {} virtual void draw(App&, float) {} virtual int music() { return -1; } virtual const char* next() { return nullptr; } };

// ---------------------------------------------------------------- menu
struct MenuMode : Mode {
    int sel = 0; const char* chosen = nullptr; static constexpr int N = 3; const char* items[N] = {"PUZZLE", "BATTLE", "QUIT"};
    void event(App& a, const SDL_Event& e) override {
        if (e.type == SDL_KEYDOWN) { SDL_Keycode k = e.key.keysym.sym;
            if (k == SDLK_DOWN) sel = (sel + 1) % N; else if (k == SDLK_UP) sel = (sel + N - 1) % N; else if (k == SDLK_RETURN || k == SDLK_SPACE) choose(a); }
        else if (e.type == SDL_MOUSEBUTTONDOWN && e.button.button == SDL_BUTTON_LEFT) { float lx, ly; SDL_RenderWindowToLogical(a.ren, e.button.x, e.button.y, &lx, &ly);
            for (int i = 0; i < N; i++) if (ly > 250 + i * 90 && ly < 250 + i * 90 + 70) { sel = i; choose(a); } }
    }
    void choose(App& a) { if (sel == 2) a.quit = true; else chosen = items[sel]; }
    const char* next() override { const char* c = chosen; chosen = nullptr; return c; }
    void draw(App& a, float) override {
        SDL_SetRenderDrawColor(a.ren, 24, 24, 60, 255); SDL_RenderClear(a.ren);
        std::string title = "CHUCHU ROCKET!"; a.text(title, (W - a.textWidth(title, 64)) / 2, 90, 64);
        for (int i = 0; i < N; i++) { std::string s = items[i]; int h = i == sel ? 56 : 44; a.text(s, (W - a.textWidth(s, h)) / 2, 260 + i * 90, h); }
    }
};

// ---------------------------------------------------------------- puzzle
struct PuzzleMode : Mode {
    Stages stages; int cur = 0; Sim sim; std::vector<std::pair<float, float>> prev; bool running = false; int state = 0;   // 0 planning, 1 running, 2 clear, 3 miss
    int stock[4] = {0, 0, 0, 0}; int totalMice = 0; bool back = false;
    bool load(const std::string& root, int stage) { if (!loadStages((root + "/gba/gba_stages.bin").c_str(), stages, 0)) return false; cur = stage % (int)stages.list.size(); reset(); return true; }
    void reset() {
        sim.load(stages.list[cur].st); prev.clear(); running = false; state = 0; totalMice = 0;
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
    void tick(App&) override {
        for (size_t i = 0; i < sim.ents.size() && i < prev.size(); i++) prev[i] = {sim.ents[i].x, sim.ents[i].z};
        if (!running) return;
        sim.tick();
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
struct BattleMode : Mode {
    Stages stages; int cur = 0; uint32_t seed = 1; int lv[4] = {-1, 3, 3, 3}; BattleGame game; std::vector<std::pair<float, float>> prev; bool paused = false, back = false;
    bool load(const std::string& root, int stage, uint32_t sd) {
        if (!loadStages((root + "/battle_stages.bin").c_str(), stages, 2)) return false; cur = stage % (int)stages.list.size(); seed = sd;
        game.rouletteManager = true; game.baseScale = 1.0f; int minutes = getenv("CCR_MINUTES") ? atoi(getenv("CCR_MINUTES")) : 3; game.roundFrames = 60 * 60 * minutes;   // 1-3 minute rounds (NGI_SetGameTimer)
        for (int p = 0; p < 4; p++) game.setCpu(p, lv[p]);
        restart(); return true;
    }
    void restart() { game.start(stages.list[cur].st, seed); prev.clear(); }
    int music() override { return game.frame > game.roundFrames - 60 * 30 ? 1 : 0; }
    void event(App& a, const SDL_Event& e) override {
        if (e.type == SDL_KEYDOWN) { SDL_Keycode k = e.key.keysym.sym;
            if (k == SDLK_SPACE) paused = !paused; else if (k == SDLK_r) restart(); else if (k == SDLK_ESCAPE) back = true;
            else if (k == SDLK_RIGHT) { cur = (cur + 1) % (int)stages.list.size(); restart(); } else if (k == SDLK_LEFT) { cur = (cur + (int)stages.list.size() - 1) % (int)stages.list.size(); restart(); } }
        else if (e.type == SDL_MOUSEBUTTONDOWN && e.button.button == SDL_BUTTON_LEFT) {
            float lx, ly; SDL_RenderWindowToLogical(a.ren, e.button.x, e.button.y, &lx, &ly); int cx = (int)(lx / CELL), cy = (int)(ly / CELL);
            if (cx >= 0 && cx < 12 && cy >= 0 && cy < 9) { int d = 0; for (auto& ar : game.sim.arrows) if (ar.live && ar.x == cx && ar.y == cy && ar.owner == 0) d = (ar.dir + 1) & 3; game.placeArrow(0, cx, cy, d); }
        }
    }
    void tick(App&) override { if (paused) return; for (size_t i = 0; i < game.sim.ents.size() && i < prev.size(); i++) prev[i] = {game.sim.ents[i].x, game.sim.ents[i].z}; game.tick(); }
    const char* next() override { if (back) { back = false; return "MENU"; } return nullptr; }
    void draw(App& a, float alpha) override {
        SDL_SetRenderDrawColor(a.ren, 24, 24, 40, 255); SDL_RenderClear(a.ren);
        a.board(stages.list[cur].st);
        for (auto& ar : game.sim.arrows) if (ar.live) a.arrow(ar.x, ar.y, ar.dir, pcol[ar.owner & 3]);
        a.entities(game.sim, prev, paused ? 1.0f : alpha);
        for (int p = 0; p < 4; p++) { SDL_Rect b{p * (W / 4) + 6, 9 * CELL + 6, W / 4 - 12, 52}; SDL_SetRenderDrawColor(a.ren, pcol[p].r, pcol[p].g, pcol[p].b, 255); SDL_RenderFillRect(a.ren, &b);
            a.number(game.score.player[p], b.x + 12, b.y + 8, 36);
            if (game.over) { int rk = game.rankOf(p); const SDL_Rect& fr = a.crowns.fr[rk < 4 ? rk : 3]; int ch = 44, cw = fr.w * ch / fr.h; SDL_Rect d{b.x + b.w - cw - 8, b.y + 4, cw, ch}; SDL_RenderCopy(a.ren, a.crowns.tex, &fr, &d); } }
        int rem = game.over ? 0 : (game.roundFrames - game.frame) / 60; int m = rem / 60, sec = rem % 60; int x = W / 2 - 60; const int hgt = 28;
        auto glyph = [&](int idx) { const SDL_Rect& fr = a.timefont.fr[idx]; int w = fr.w * hgt / fr.h; SDL_Rect d{x, 6, w, hgt}; SDL_RenderCopy(a.ren, a.timefont.tex, &fr, &d); x += w + 1; };
        glyph(m % 10); glyph(10); glyph(sec / 10); glyph(sec % 10);
    }
};

int main(int argc, char** argv) {
    if (argc < 2) { printf("usage: ccr <cache assets dir> [menu|puzzle|battle] [stage] [seed] [cpu levels]\n"); return 2; }
    App app; app.root = argv[1]; if (!app.init()) return 2;
    std::string start = argc > 2 ? argv[2] : "menu"; int stageNo = argc > 3 ? atoi(argv[3]) : 0; uint32_t seed = argc > 4 ? (uint32_t)atoi(argv[4]) : 1;
    int lv[4] = {-1, 3, 3, 3}; if (argc > 5) { int k = 1; for (const char* p = argv[5]; *p && k < 4; ) { lv[k++] = atoi(p); while (*p && *p != ',') p++; if (*p == ',') p++; } }
    std::unique_ptr<Mode> mode;
    auto enter = [&](const std::string& name) -> bool {
        if (name == "PUZZLE" || name == "puzzle") { auto m = std::make_unique<PuzzleMode>(); if (!m->load(app.root, stageNo)) { printf("cannot load puzzle stages\n"); return false; } mode = std::move(m); }
        else if (name == "BATTLE" || name == "battle") { auto m = std::make_unique<BattleMode>(); memcpy(m->lv, lv, sizeof lv); if (!m->load(app.root, stageNo, seed)) { printf("cannot load battle stages\n"); return false; } mode = std::move(m); }
        else mode = std::make_unique<MenuMode>();
        return true;
    };
    if (!enter(start)) return 2;
    const double dt = 1.0 / 60.0; double acc = 0;
    if (const char* shot = getenv("CCR_SHOT")) {
        int ticks = getenv("CCR_TICKS") ? atoi(getenv("CCR_TICKS")) : 600;
        if (const char* keys = getenv("CCR_KEYS")) for (const char* p = keys; *p; p++) { SDL_Event e{}; e.type = SDL_KEYDOWN; e.key.keysym.sym = (*p == ' ') ? SDLK_SPACE : (*p == 'D') ? SDLK_DOWN : (*p == 'E') ? SDLK_RETURN : *p; mode->event(app, e); if (const char* nx = mode->next()) enter(nx); }
        for (int i = 0; i < ticks; i++) mode->tick(app);
        mode->draw(app, 1.0f); SDL_Surface* s = SDL_CreateRGBSurfaceWithFormat(0, W, H, 32, SDL_PIXELFORMAT_ARGB8888);
        SDL_RenderReadPixels(app.ren, nullptr, SDL_PIXELFORMAT_ARGB8888, s->pixels, s->pitch); SDL_SaveBMP(s, shot); SDL_FreeSurface(s); SDL_Quit(); return 0;
    }
    Uint64 last = SDL_GetPerformanceCounter();
    while (!app.quit) {
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
    }
    SDL_Quit(); return 0;
}
