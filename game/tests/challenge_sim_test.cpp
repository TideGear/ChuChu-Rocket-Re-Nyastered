// Runs the puzzle simulation on a Challenge board (src 3 of battle_stages.bin) with no arrows and logs every change of the
// saved (rocket) and eaten-by-cat mouse counters, to compare with the original's ChallengeLoop counters (tools/oracle/challenge_probe.py, TRACKCNT=1).
// usage: challenge_sim_test <battle_stages.bin> <challenge stage 0-24> [ticks]
#include "../core/sim.hpp"
#include <cstdio>
#include <cstdlib>
#include <vector>
using namespace ccr;
int main(int argc, char** argv) {
    if (argc < 3) { printf("usage: challenge_sim_test <battle_stages.bin> <stage> [ticks]\n"); return 2; }
    FILE* f = fopen(argv[1], "rb"); if (!f) { printf("cannot open %s\n", argv[1]); return 2; }
    const int want = atoi(argv[2]), ticks = argc > 3 ? atoi(argv[3]) : 1800;
    uint32_t n; fread(&n, 4, 1, f);
    for (uint32_t i = 0; i < n; i++) {
        uint8_t hdr[4]; fread(hdr, 1, 4, f); Stage st; uint8_t walls[237]; char title[32];
        fread(st.tiles, 1, 108, f); fread(walls, 1, 237, f); fread(title, 1, 32, f);
        for (int r = 0; r < 10; r++) for (int c = 0; c < 12; c++) st.hw[r * 12 + c] = walls[25 * r + c];
        for (int r = 0; r < 9; r++) for (int c = 0; c < 13; c++) st.vw[r * 13 + c] = walls[25 * r + 12 + c];
        if (hdr[0] != 3 || (hdr[2] | (hdr[3] << 8)) != want) continue;
        Sim sim; sim.load(st);
        int mice = 0; for (auto& e : sim.ents) if (e.mouse) mice++;
        printf("stage %d: %d mice, %d cats\n", want, mice, (int)sim.ents.size() - mice);
        int lastSaved = -1, lastEaten = -1;
        for (int t = 1; t <= ticks; t++) {
            sim.tick();
            if (sim.saved != lastSaved || sim.killedByCat != lastEaten) { printf("CNT t%d rocket %d eaten %d\n", t, sim.saved, sim.killedByCat); lastSaved = sim.saved; lastEaten = sim.killedByCat; }
        }
        return 0;
    }
    printf("stage %d not found\n", want); return 1;
}
