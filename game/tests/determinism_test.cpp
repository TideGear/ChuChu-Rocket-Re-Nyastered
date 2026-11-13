// Determinism / replay test: every Dreamcast battle stage is played (CPU opponents + scripted human arrows) while an input log is recorded; the log is then replayed on a fresh game
// and a third run interleaves unrelated work between ticks (as a renderer would). A 64-bit hash of all entity positions and scores after EVERY tick must be identical in the three runs.
#include "../core/battle.hpp"
#include <cstdio>
#include <cstring>
#include <vector>
using namespace ccr;
static uint64_t mix(uint64_t h, uint64_t v) { h ^= v + 0x9e3779b97f4a7c15ull + (h << 6) + (h >> 2); return h; }
static uint64_t hashState(const BattleGame& g) {
    uint64_t h = 1469598103934665603ull;
    for (auto& e : g.sim.ents) { uint32_t a, b; memcpy(&a, &e.x, 4); memcpy(&b, &e.z, 4); h = mix(h, a); h = mix(h, b); }
    for (int p = 0; p < 4; p++) h = mix(h, (uint64_t)g.score.player[p]);
    h = mix(h, (uint64_t)g.sim.ents.size()); return h;
}
struct In { int t, p, x, y, d; };
static void setup(BattleGame& g, const Stage& st, uint32_t seed) {
    for (int p = 1; p < 4; p++) g.setCpu(p, 3);
    g.rouletteManager = true; g.roundFrames = 60 * 60; g.start(st, seed);
}
int main(int argc, char** argv) {
    FILE* f = fopen(argc > 1 ? argv[1] : "../local/cache/assets/battle_stages.bin", "rb"); if (!f) { printf("cannot open stages\n"); return 2; }
    uint32_t n; if (fread(&n, 4, 1, f) != 1) return 2;
    int stages = 0, bad = 0; long ticks = 0;
    for (uint32_t i = 0; i < n; i++) {
        uint8_t h[4]; Stage st; uint8_t walls[237], title[32];
        if (fread(h, 1, 4, f) != 4 || fread(st.tiles, 1, 108, f) != 108 || fread(walls, 1, 237, f) != 237 || fread(title, 1, 32, f) != 32) break;
        for (int r = 0; r < 10; r++) for (int c = 0; c < 12; c++) st.hw[r * 12 + c] = walls[25 * r + c];
        for (int r = 0; r < 9; r++) for (int c = 0; c < 13; c++) st.vw[r * 13 + c] = walls[25 * r + 12 + c];
        if (h[0] != 2) continue;
        stages++; uint32_t seed = 777 + i; std::vector<In> log; std::vector<uint64_t> ref;
        { BattleGame g; setup(g, st, seed);
          for (int t = 0; t < g.roundFrames; t++) { if (t % 75 == 0) { In in{t, 0, (t / 5) % 12, (t / 9) % 9, t & 3}; log.push_back(in); g.placeArrow(in.p, in.x, in.y, in.d); } g.tick(); ref.push_back(hashState(g)); } }
        for (int variant = 0; variant < 2; variant++) {
            BattleGame g; setup(g, st, seed); size_t k = 0; volatile double sink = 0;
            for (int t = 0; t < (int)ref.size(); t++) {
                while (k < log.size() && log[k].t == t) { g.placeArrow(log[k].p, log[k].x, log[k].y, log[k].d); k++; }
                if (variant == 1) for (int j = 0; j < 1000; j++) sink += j * 0.5;      // unrelated per-frame work (rendering stand-in)
                g.tick(); ticks++;
                if (hashState(g) != ref[t]) { printf("stage %u variant %d: first difference at tick %d\n", i, variant, t); bad++; break; }
            }
        }
    }
    printf("determinism: %d stages x 3 runs, %ld replayed ticks, %d diverging runs\n", stages, ticks, bad);
    return bad ? 1 : 0;
}
