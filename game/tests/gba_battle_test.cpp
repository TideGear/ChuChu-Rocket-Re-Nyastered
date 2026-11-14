// Whole-battle smoke test of the GBA CPU players on every Dreamcast battle stage: four GBA CPUs play a 3-minute round; counts the arrows each placed, the scores, and checks invariants.
// (The routines themselves are diff-tested against the ROM in cpu_gba_test; this checks that they drive the simulation sensibly.)
#include "../core/battle.hpp"
#include <cstdio>
using namespace ccr;
int main(int argc, char** argv) {
    FILE* f = fopen(argc > 1 ? argv[1] : "../local/cache/assets/battle_stages.bin", "rb"); if (!f) { printf("cannot open stages\n"); return 2; }
    uint32_t n; if (fread(&n, 4, 1, f) != 1) return 2; int bad = 0, total = 0; long placed = 0, scoreSum = 0, scoreSumOld = 0;
    for (uint32_t i = 0; i < n; i++) {
        uint8_t h[4]; Stage st; uint8_t walls[237], title[32];
        if (fread(h, 1, 4, f) != 4 || fread(st.tiles, 1, 108, f) != 108 || fread(walls, 1, 237, f) != 237 || fread(title, 1, 32, f) != 32) break;
        for (int r = 0; r < 10; r++) for (int c = 0; c < 12; c++) st.hw[r * 12 + c] = walls[25 * r + c];
        for (int r = 0; r < 9; r++) for (int c = 0; c < 13; c++) st.vw[r * 13 + c] = walls[25 * r + 12 + c];
        if (h[0] != 2) continue; total++;
        for (int variant = 0; variant < 2; variant++) {
            BattleGame g; g.rouletteManager = true; g.roundFrames = 60 * 180; g.gbaCpu = variant == 0; for (int p = 0; p < 4; p++) g.setCpu(p, 3);
            g.start(st, 77 + i); int live = 0;
            for (int t = 0; t < g.roundFrames * 2 && !g.over; t++) { g.tick(); if (t % 600 == 0) { live = 0; for (auto& a : g.sim.arrows) if (a.live) live++; if (live > 12) bad++; } }
            int sum = 0; for (int p = 0; p < 4; p++) { if (g.score.player[p] < 0 || g.score.player[p] > 999) bad++; sum += g.score.player[p]; }
            if (variant == 0) { scoreSum += sum; placed += (long)g.sim.arrows.size(); if (i < 3) printf("stage %u: GBA CPUs placed %zu arrows, scores %d %d %d %d\n", i, g.sim.arrows.size(), g.score.player[0], g.score.player[1], g.score.player[2], g.score.player[3]); }
            else scoreSumOld += sum;
        }
    }
    printf("gba cpu battles: %d stages, arrows placed %ld, mean total score %.1f (the port's earlier CPU: %.1f), invariant failures %d\n", total, placed, (double)scoreSum / total, (double)scoreSumOld / total, bad);
    return bad ? 1 : 0;
}
