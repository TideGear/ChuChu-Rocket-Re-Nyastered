// How often does a character's drawn angle differ from its heading (the "walks backwards" look)? Plays full battles and histograms |angle - heading| per entity per tick.
// usage: turn_stats <battle_stages.bin>
#include "../core/battle.hpp"
#include "../core/angle.hpp"
#include <cstdio>
using namespace ccr;
int main(int argc, char** argv) {
    FILE* f = fopen(argc > 1 ? argv[1] : "../local/cache/assets/battle_stages.bin", "rb"); if (!f) return 2;
    uint32_t n; if (fread(&n, 4, 1, f) != 1) return 2; long total = 0, over90 = 0, over135 = 0, turning = 0; long reversals = 0;
    for (uint32_t i = 0; i < n && i < 6; i++) {
        uint8_t h[4]; Stage st; uint8_t walls[237], title[32];
        if (fread(h, 1, 4, f) != 4 || fread(st.tiles, 1, 108, f) != 108 || fread(walls, 1, 237, f) != 237 || fread(title, 1, 32, f) != 32) break;
        for (int r = 0; r < 10; r++) for (int c = 0; c < 12; c++) st.hw[r * 12 + c] = walls[25 * r + c];
        for (int r = 0; r < 9; r++) for (int c = 0; c < 13; c++) st.vw[r * 13 + c] = walls[25 * r + 12 + c];
        if (h[0] != 2) continue;
        BattleGame g; for (int q = 0; q < 4; q++) g.setCpu(q, 3); g.rouletteManager = true; g.baseScale = 1.0f; g.roundFrames = 3600; g.start(st, 31 + i);
        std::vector<int> ang; std::vector<int> lastHeading;
        for (int t = 0; t < 3600; t++) {
            g.tick(); auto& E = g.sim.ents;
            while (ang.size() < E.size()) { ang.push_back(E[ang.size()].heading << 14); lastHeading.push_back(E[ang.size() - 1].heading); }
            for (size_t k = 0; k < E.size(); k++) { if (!E[k].alive || E[k].done || E[k].rocketIn) continue;
                ang[k] = stepAngle(ang[k], E[k].heading, E[k].mouse ? g.sim.mouseSpeed : g.sim.catSpeed);
                int d = diffAngle(ang[k], E[k].heading << 14); total++; if (d > 0x4000) over90++; if (d > 0x6000) over135++; if (d) turning++;
                if (((E[k].heading ^ lastHeading[k]) & 3) == 2) reversals++; lastHeading[k] = E[k].heading; }
        }
    }
    printf("entity-ticks %ld: turning %.1f%%, facing >90 deg away from heading %.2f%%, >135 deg %.2f%%, heading reversals (180 deg) %ld\n", total, 100.0 * turning / total, 100.0 * over90 / total, 100.0 * over135 / total, reversals);
}
