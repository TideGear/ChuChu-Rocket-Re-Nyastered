// Re-Nyastered development viewer: renders a puzzle stage with the extracted tile atlas and runs the verified simulation
// on a fixed 60 Hz step; drawing is interpolated so the display rate does not change game speed.
// usage: viewer <gba_stages.bin> <atlas dir with 0930.bin/0931.bin> [stage index]
// Keys: SPACE pause, R restart, LEFT/RIGHT previous/next stage, click a cell: place/rotate an arrow, right click: remove.
// NOTE: mice and cats are drawn as plain discs for now; their sprite sheets are not mapped yet.
#define SDL_MAIN_HANDLED
#include <SDL.h>
#include "../core/sim.hpp"
#include <cmath>
#include <cstdlib>
#include <cstdio>
#include <string>
#include <vector>
using namespace ccr;

struct StageData { Stage st; std::vector<uint8_t> sol; int src, idx; char title[33]; };

static bool loadStages(const char* path, std::vector<StageData>& out) {
    FILE* f = fopen(path, "rb"); if (!f) return false;
    uint32_t n; if (fread(&n, 4, 1, f) != 1) return false;
    for (uint32_t i = 0; i < n; i++) {
        uint8_t hdr[4]; if (fread(hdr, 1, 4, f) != 4) break;
        StageData d; d.src = hdr[0]; d.idx = hdr[2] | (hdr[3] << 8);
        uint8_t walls[237];
        if (fread(d.st.tiles, 1, 108, f) != 108 || fread(walls, 1, 237, f) != 237) break;
        d.sol.resize(hdr[1] * 3);
        if (hdr[1] && fread(d.sol.data(), 1, d.sol.size(), f) != d.sol.size()) break;
        if (fread(d.title, 1, 32, f) != 32) break;
        d.title[32] = 0;
        for (int r = 0; r < 10; r++) for (int c = 0; c < 12; c++) d.st.hw[r * 12 + c] = walls[25 * r + c];
        for (int r = 0; r < 9; r++) for (int c = 0; c < 13; c++) d.st.vw[r * 13 + c] = walls[25 * r + 12 + c];
        out.push_back(d);
    }
    fclose(f);
    return !out.empty();
}

struct Atlas { SDL_Texture* tex = nullptr; int w = 0, h = 0; std::vector<SDL_Rect> frames; };

static bool loadSheet(SDL_Renderer* r, const std::string& texPath, const std::string& framePath, Atlas& a, size_t minFrames) {
    FILE* f = fopen(texPath.c_str(), "rb"); if (!f) return false;
    uint32_t wh[2]; if (fread(wh, 4, 2, f) != 2) return false;
    a.w = (int)wh[0]; a.h = (int)wh[1];
    std::vector<uint8_t> px((size_t)a.w * a.h * 4);
    if (fread(px.data(), 1, px.size(), f) != px.size()) return false;
    fclose(f);
    a.tex = SDL_CreateTexture(r, SDL_PIXELFORMAT_ABGR8888, SDL_TEXTUREACCESS_STATIC, a.w, a.h);
    SDL_UpdateTexture(a.tex, nullptr, px.data(), a.w * 4);
    SDL_SetTextureBlendMode(a.tex, SDL_BLENDMODE_BLEND);
    f = fopen(framePath.c_str(), "rb"); if (!f) return false;
    uint32_t n; if (fread(&n, 4, 1, f) != 1) return false;
    std::vector<float> fl(n * 9);
    if (fread(fl.data(), 4, fl.size(), f) != fl.size()) return false;
    fclose(f);
    for (uint32_t i = 0; i < n; i++) {
        const float* e = &fl[i * 9];
        a.frames.push_back({(int)std::lround(e[0] * a.w), (int)std::lround(e[1] * a.h),
                            (int)std::lround((e[2] - e[0]) * a.w), (int)std::lround((e[3] - e[1]) * a.h)});
    }
    return a.frames.size() >= minFrames;
}

static bool loadAtlas(SDL_Renderer* r, const std::string& dir, Atlas& a) { return loadSheet(r, dir + "/0930.bin", dir + "/0931.bin", a, 35); }

static void disc(SDL_Renderer* r, float cx, float cy, float rad, SDL_Color c) {
    std::vector<SDL_Vertex> v; std::vector<int> idx;
    v.push_back({{cx, cy}, c, {0, 0}});
    for (int i = 0; i <= 24; i++) {
        float a = i * 3.14159265f * 2 / 24;
        v.push_back({{cx + std::cos(a) * rad, cy + std::sin(a) * rad}, c, {0, 0}});
        if (i) { idx.push_back(0); idx.push_back(i); idx.push_back(i + 1); }
    }
    SDL_RenderGeometry(r, nullptr, v.data(), (int)v.size(), idx.data(), (int)idx.size());
}

int main(int argc, char** argv) {
    if (argc < 3) { printf("usage: viewer <gba_stages.bin> <atlas dir> [stage]\n"); return 2; }
    std::vector<StageData> stages;
    if (!loadStages(argv[1], stages)) { printf("cannot read stages from %s\n", argv[1]); return 2; }
    int cur = argc > 3 ? atoi(argv[3]) : 0;
    if (cur < 0 || cur >= (int)stages.size()) cur = 0;
    if (SDL_Init(SDL_INIT_VIDEO) != 0) { printf("SDL: %s\n", SDL_GetError()); return 2; }
    const int CELL = 72, W = 12 * CELL, H = 9 * CELL;
    SDL_Window* win = SDL_CreateWindow("ChuChu Rocket! Re-Nyastered (dev viewer)", SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED, W, H, SDL_WINDOW_RESIZABLE);
    SDL_Renderer* ren = SDL_CreateRenderer(win, -1, SDL_RENDERER_ACCELERATED | SDL_RENDERER_PRESENTVSYNC);
    SDL_RenderSetLogicalSize(ren, W, H);
    Atlas atlas;
    if (!loadAtlas(ren, argv[2], atlas)) { printf("cannot read atlas from %s\n", argv[2]); return 2; }
    Atlas catSheet, mouseSheet;   // optional sheets written by tools/export_sprites.py (default dir: local/cache/assets/sprites)
    {
        std::string sd = argc > 4 ? argv[4] : std::string(argv[2]) + "/../../../../sprites";
        loadSheet(ren, sd + "/cat.tex.bin", sd + "/cat.frames.bin", catSheet, 32);
        loadSheet(ren, sd + "/mouse.tex.bin", sd + "/mouse.frames.bin", mouseSheet, 32);
    }
    Sim sim; bool paused = false;
    struct Snap { float x, z; };
    std::vector<Snap> prev;
    auto restart = [&]() {
        sim.load(stages[cur].st);
        prev.clear();
        for (auto& e : sim.ents) prev.push_back({e.x, e.z});
        char t[160];
        snprintf(t, sizeof t, "Re-Nyastered dev viewer - %s stage %d %s", stages[cur].src ? "GBA user" : "main", stages[cur].idx, stages[cur].title);
        SDL_SetWindowTitle(win, t);
    };
    restart();
    auto draw = [&](float alpha) {
        SDL_SetRenderDrawColor(ren, 24, 24, 40, 255); SDL_RenderClear(ren);
        const Stage& st = stages[cur].st;
        for (int r = 0; r < 9; r++) for (int c = 0; c < 12; c++) {
            SDL_Rect dst{c * CELL, r * CELL, CELL, CELL}; uint8_t t = st.tiles[r * 12 + c];
            SDL_RenderCopy(ren, atlas.tex, &atlas.frames[8 + ((r + c) & 1)], &dst);
            if (t == T_Hole) SDL_RenderCopy(ren, atlas.tex, &atlas.frames[7], &dst);
            if (t == T_Rocket) { SDL_RenderCopy(ren, atlas.tex, &atlas.frames[6], &dst); SDL_RenderCopy(ren, atlas.tex, &atlas.frames[26], &dst); }
        }
        SDL_SetRenderDrawColor(ren, 20, 20, 90, 255);
        for (int r = 0; r < 10; r++) for (int c = 0; c < 12; c++) if (st.hw[r * 12 + c]) { SDL_Rect q{c * CELL - 1, r * CELL - 3, CELL + 2, 6}; SDL_RenderFillRect(ren, &q); }
        for (int r = 0; r < 9; r++) for (int c = 0; c < 13; c++) if (st.vw[r * 13 + c]) { SDL_Rect q{c * CELL - 3, r * CELL - 1, 6, CELL + 2}; SDL_RenderFillRect(ren, &q); }
        for (auto& a : sim.arrows) if (a.live) {
            static const float dx[4] = {0, -1, 0, 1}, dy[4] = {1, 0, -1, 0};
            float cx = (a.x + 0.5f) * CELL, cy = (a.y + 0.5f) * CELL, ux = dx[a.dir], uy = dy[a.dir], px = -uy, py = ux;
            SDL_Color col{230, 200, 40, 255};
            SDL_Vertex v[3] = {{{cx + ux * 26, cy + uy * 26}, col, {0, 0}},
                               {{cx - ux * 14 + px * 22, cy - uy * 14 + py * 22}, col, {0, 0}},
                               {{cx - ux * 14 - px * 22, cy - uy * 14 - py * 22}, col, {0, 0}}};
            SDL_RenderGeometry(ren, nullptr, v, 3, nullptr, 0);
        }
        for (size_t i = 0; i < sim.ents.size(); i++) {
            const Entity& en = sim.ents[i]; if (!en.alive || en.done) continue;
            float x = prev[i].x + (en.x - prev[i].x) * alpha, z = prev[i].z + (en.z - prev[i].z) * alpha;
            if (std::fabs(en.x - prev[i].x) > 100 || std::fabs(en.z - prev[i].z) > 100) { x = en.x; z = en.z; }   // wrapped over the edge: no interpolation
            Atlas& sh = en.mouse ? mouseSheet : catSheet;
            if (sh.tex) {                                    // pre-rendered 32-view turntable: frame 0 faces the camera, 8 frames per quarter turn
                const SDL_Rect& fr = sh.frames[(en.heading * 8) & 31];
                float sc = CELL * 0.95f / fr.w; int dw = (int)(fr.w * sc), dh = (int)(fr.h * sc);
                SDL_Rect dst{(int)(x * (CELL / 15.0f)) - dw / 2, (int)(z * (CELL / 15.0f)) - dh * 2 / 3, dw, dh};
                SDL_RenderCopy(ren, sh.tex, &fr, &dst);
            } else disc(ren, x * (CELL / 15.0f), z * (CELL / 15.0f), CELL * 0.22f, en.mouse ? SDL_Color{240, 240, 250, 255} : SDL_Color{250, 140, 30, 255});
        }
    };
    const double dt = 1.0 / 60.0; double acc = 0;
    if (const char* shotPath = getenv("VIEWER_SHOT")) {          // headless check: run N ticks, render once, save a BMP
        int ticks = getenv("VIEWER_TICKS") ? atoi(getenv("VIEWER_TICKS")) : 60;
        for (int i = 0; i < ticks; i++) { for (size_t k = 0; k < sim.ents.size(); k++) prev[k] = {sim.ents[k].x, sim.ents[k].z}; sim.tick(); }
        draw(1.0f);
        SDL_Surface* surf = SDL_CreateRGBSurfaceWithFormat(0, W, H, 32, SDL_PIXELFORMAT_ARGB8888);
        SDL_RenderReadPixels(ren, nullptr, SDL_PIXELFORMAT_ARGB8888, surf->pixels, surf->pitch);
        SDL_SaveBMP(surf, shotPath); SDL_FreeSurface(surf); SDL_Quit(); return 0;
    }
    Uint64 last = SDL_GetPerformanceCounter(); bool run = true;
    while (run) {
        SDL_Event e;
        while (SDL_PollEvent(&e)) {
            if (e.type == SDL_QUIT) run = false;
            else if (e.type == SDL_KEYDOWN) {
                SDL_Keycode k = e.key.keysym.sym;
                if (k == SDLK_ESCAPE) run = false;
                else if (k == SDLK_SPACE) paused = !paused;
                else if (k == SDLK_r) restart();
                else if (k == SDLK_RIGHT) { cur = (cur + 1) % (int)stages.size(); restart(); }
                else if (k == SDLK_LEFT) { cur = (cur + (int)stages.size() - 1) % (int)stages.size(); restart(); }
            } else if (e.type == SDL_MOUSEBUTTONDOWN) {
                float lx, ly; SDL_RenderWindowToLogical(ren, e.button.x, e.button.y, &lx, &ly);
                int cx = (int)(lx / CELL), cy = (int)(ly / CELL);
                if (cx >= 0 && cx < 12 && cy >= 0 && cy < 9) {
                    int existing = -1;
                    for (auto& a : sim.arrows) if (a.live && a.x == cx && a.y == cy) existing = a.dir;
                    if (e.button.button == SDL_BUTTON_LEFT) sim.placeArrow(cx, cy, existing < 0 ? 0 : (existing + 1) & 3);
                    else if (existing >= 0) sim.removeArrow(cx, cy);
                }
            }
        }
        Uint64 now = SDL_GetPerformanceCounter();
        acc += (double)(now - last) / (double)SDL_GetPerformanceFrequency(); last = now;
        if (acc > 0.25) acc = 0.25;
        while (!paused && acc >= dt) {
            for (size_t i = 0; i < sim.ents.size(); i++) prev[i] = {sim.ents[i].x, sim.ents[i].z};
            sim.tick(); acc -= dt;
        }
        draw(paused ? 1.0f : (float)(acc / dt));
        SDL_RenderPresent(ren);
    }
    SDL_Quit();
    return 0;
}
