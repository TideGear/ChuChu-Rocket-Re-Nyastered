// Replays the ChallengeGame class (core/challenge.hpp) on a Challenge board with the scripted arrows of tools/oracle/challenge_probe.py (ARROWS=1) and prints
// "f<frame> phase <n>" changes and "CNT f<frame> rocket R eaten E" counter changes in the original's frame numbering, to diff against challenge_probe.py output.
// usage: challenge_game_test <battle_stages.bin> <stage 0-24> <frames> [arrows]
#include "../core/challenge.hpp"
#include <cstdio>
#include <cstdlib>
using namespace ccr;
int main(int argc, char** argv) {
    if (argc < 4) { printf("usage: challenge_game_test <battle_stages.bin> <stage> <frames> [arrows]\n"); return 2; }
    FILE* f = fopen(argv[1], "rb"); if (!f) { printf("cannot open %s\n", argv[1]); return 2; }
    const int want = atoi(argv[2]), frames = atoi(argv[3]); const bool arrows = argc > 4;
    uint32_t n; fread(&n, 4, 1, f);
    for (uint32_t i = 0; i < n; i++) {
        uint8_t hdr[4]; fread(hdr, 1, 4, f); Stage st; uint8_t walls[237]; char title[32];
        fread(st.tiles, 1, 108, f); fread(walls, 1, 237, f); fread(title, 1, 32, f);
        for (int r = 0; r < 10; r++) for (int c = 0; c < 12; c++) st.hw[r * 12 + c] = walls[25 * r + c];
        for (int r = 0; r < 9; r++) for (int c = 0; c < 13; c++) st.vw[r * 13 + c] = walls[25 * r + 12 + c];
        if (hdr[0] != 3 || (hdr[2] | (hdr[3] << 8)) != want) continue;
        ChallengeGame g; g.start(st, want);
        printf("f0 phase 1 target %d\n", g.target);
        int lastPhase = 1, lastR = -1, lastE = -1;
        for (int fr = 1; fr <= frames; fr++) {
            if (arrows && fr >= 480 && (fr - 480) % 40 == 0) { const int k = (fr - 480) / 40; g.placeArrow((7 * k + 3) % 12, (5 * k + 1) % 9, k % 4); }
            g.tick();
            if (g.phase != lastPhase) { printf("f%d phase %d", fr, g.phase); if (g.failReason) printf(" (%s)", g.failReason); putchar(10); lastPhase = g.phase; }
            if (g.sim.saved != lastR || g.sim.killedByCat != lastE) { printf("CNT f%d rocket %d eaten %d", fr, g.sim.saved, g.sim.killedByCat); putchar(10); lastR = g.sim.saved; lastE = g.sim.killedByCat; }
        }
        return 0;
    }
    printf("stage %d not found\n", want); return 1;
}
