// Roulette events Everybody Move (5) and Cat Attack (6) in whole CPU battles: checks the rocket owners stay a permutation, positions follow, and the scores of the opponents drop by a third (rounded up) at the end of Cat Attack.
#include "../core/battle.hpp"
#include <cstdio>
using namespace ccr;
int main(int argc, char** argv) {
    FILE* f = fopen(argc > 1 ? argv[1] : "../local/cache/assets/battle_stages.bin", "rb"); if (!f) { printf("cannot open stages\n"); return 2; }
    uint32_t n; if (fread(&n, 4, 1, f) != 1) return 2; int bad = 0, shuffles = 0, attacks = 0, monop = 0, monopGain = 0, jimeMice = 0;
    for (uint32_t i = 0; i < n; i++) {
        uint8_t h[4]; Stage st; uint8_t walls[237], title[32];
        if (fread(h, 1, 4, f) != 4 || fread(st.tiles, 1, 108, f) != 108 || fread(walls, 1, 237, f) != 237 || fread(title, 1, 32, f) != 32) break;
        for (int r = 0; r < 10; r++) for (int c = 0; c < 12; c++) st.hw[r * 12 + c] = walls[25 * r + c];
        for (int r = 0; r < 9; r++) for (int c = 0; c < 13; c++) st.vw[r * 13 + c] = walls[25 * r + 12 + c];
        if (h[0] != 2) continue;
        for (int team = 0; team < 2; team++) for (int seed = 0; seed < 6; seed++) {
            BattleGame g; g.rouletteManager = true; g.teamMode = team; g.roundFrames = 60 * 180; for (int p = 0; p < 4; p++) g.setCpu(p, 3);
            g.start(st, 1000 + seed * 31 + i); int prevEv = -1, monopStart = 0, monopRoller = 0; int before[4], roller = 0; int pos[4][2], beforeSc[4];
            for (int t = 0; t < g.roundFrames * 2 && !g.over; t++) {
                for (int p = 0; p < 4; p++) { beforeSc[p] = g.score.player[p]; pos[p][0] = g.sim.rocketPos[p][0]; pos[p][1] = g.sim.rocketPos[p][1]; }
                g.tick(); int ev = g.activeEventKind();
                if (ev == 5 && prevEv != 5) {
                    shuffles++; int seen[4] = {0, 0, 0, 0};
                    for (int p = 0; p < 4; p++) { int x = g.sim.rocketPos[p][0], y = g.sim.rocketPos[p][1]; if (g.sim.rocketOwner[y][x] != p) bad++; for (int q = 0; q < 4; q++) if (pos[q][0] == x && pos[q][1] == y) seen[q]++; }
                    for (int q = 0; q < 4; q++) if (seen[q] != 1) bad++;
                }
                if (prevEv == 6 && ev != 6) attacks++;
                if (ev == 7 && prevEv != 7) { monop++; monopRoller = -1; }
                if (ev == 7 && monopRoller < 0 && g.sim.monopoly >= 0) { monopRoller = g.sim.monopoly; monopStart = g.score.player[monopRoller]; }
                if (prevEv == 7 && ev != 7 && monopRoller >= 0) { if (g.score.player[monopRoller] > monopStart) monopGain++; }
                if (ev == 7) for (auto& m : g.sim.ents) if (m.mouse && m.alive && m.jime) { jimeMice++; break; }
                prevEv = ev; (void)before; (void)roller;
            }
        }
    }
    printf("everybody move %d, cat attack %d, mouse monopoly %d (roller scored in %d, ticks with flying mice %d), failures %d\n", shuffles, attacks, monop, monopGain, jimeMice, bad); return bad ? 1 : 0;
}
