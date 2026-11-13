// Smoke/invariant test for BattleGame on every Dreamcast battle stage (scripted arrow placement, no other input).
#include "../core/battle.hpp"
#include <cstdio>
#include <cstring>
using namespace ccr;
int main(int argc, char** argv) {
    FILE* f = fopen(argc > 1 ? argv[1] : "../local/cache/assets/battle_stages.bin", "rb"); if (!f) { printf("cannot open stages\n"); return 2; }
    uint32_t n; if (fread(&n, 4, 1, f) != 1) return 2;
    int bad = 0, total = 0; long spawns = 0, roulettes = 0;
    for (uint32_t i = 0; i < n; i++) {
        uint8_t h[4]; Stage st; uint8_t walls[237], title[32];
        if (fread(h, 1, 4, f) != 4 || fread(st.tiles, 1, 108, f) != 108 || fread(walls, 1, 237, f) != 237 || fread(title, 1, 32, f) != 32) break;
        for (int r = 0; r < 10; r++) for (int c = 0; c < 12; c++) st.hw[r * 12 + c] = walls[25 * r + c];
        for (int r = 0; r < 9; r++) for (int c = 0; c < 13; c++) st.vw[r * 13 + c] = walls[25 * r + 12 + c];
        if (h[0] != 2) continue;
        BattleGame g; g.rouletteManager = false; g.roundFrames = 60 * 60; g.start(st, 1234 + i); total++;
        for (int t = 0; t < g.roundFrames; t++) {
            if (t % 90 == 0) g.placeArrow((t / 90) & 3, (t / 7) % 12, (t / 11) % 9, t & 3);
            g.tick();
        }
        for (int p = 0; p < 4; p++) if (g.score.player[p] < 0 || g.score.player[p] > 999) bad++;
        if (g.gen->mice < 0 || g.gen->cnt1 < 0 || g.gen->cnt2 < 0) { bad++; printf("stage %u: negative mouse counters %d %d %d\n", i, g.gen->mice, g.gen->cnt1, g.gen->cnt2); }
        spawns += (long)g.gen->spawns.size(); roulettes += (long)g.lastRoll.size();
        if (i < 3) printf("battle %u: gens %zu spawns %zu scores %d %d %d %d roulettes %zu\n", i, g.sim.gens.size(), g.gen->spawns.size(),
                          g.score.player[0], g.score.player[1], g.score.player[2], g.score.player[3], g.lastRoll.size());
    }
    printf("battle stages run: %d, spawns %ld, roulettes %ld, invariant failures: %d\n", total, spawns, roulettes, bad);
    return bad ? 1 : 0;
}
