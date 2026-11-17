// Replays ChallengeBattleGame (core/challenge_battle.hpp, Challenge types 3 and 4) with the hashed arrow schedule of tools/oracle/challenge_probe.py (ARROWS=<seed>) and
// prints "f<frame> phase <n>", "WORDS f<frame> w12 <a> w13 <b>" and "SCORE f<frame> <n>" lines in the original's frame numbering.
// usage: challenge_battle_game_test <battle_stages.bin> <stage> <seed> <frames> [arrow seed]
#include "../core/challenge_battle.hpp"
#include <cstdio>
#include <cstdlib>
using namespace ccr;
int main(int argc, char** argv) {
    if (argc < 5) { printf("usage: challenge_battle_game_test <bin> <stage> <seed> <frames> [arrow seed]\n"); return 2; }
    FILE* f = fopen(argv[1], "rb"); if (!f) { printf("cannot open %s\n", argv[1]); return 2; }
    const int want = atoi(argv[2]), seed = atoi(argv[3]), frames = atoi(argv[4]); const int arrowSeed = argc > 5 ? atoi(argv[5]) : 0;
    uint32_t n; fread(&n, 4, 1, f);
    for (uint32_t i = 0; i < n; i++) {
        uint8_t hdr[4]; fread(hdr, 1, 4, f); Stage st; uint8_t walls[237]; char title[32];
        fread(st.tiles, 1, 108, f); fread(walls, 1, 237, f); fread(title, 1, 32, f);
        for (int r = 0; r < 10; r++) for (int c = 0; c < 12; c++) st.hw[r * 12 + c] = walls[25 * r + c];
        for (int r = 0; r < 9; r++) for (int c = 0; c < 13; c++) st.vw[r * 13 + c] = walls[25 * r + 12 + c];
        if (hdr[0] != 3 || (hdr[2] | (hdr[3] << 8)) != want) continue;
        ChallengeBattleGame g; g.start(st, want, (uint32_t)seed); g.game.debug = g.game.sim.trace = getenv("BDEBUG") != nullptr; if (getenv("FORCE")) g.game.forceOutcome = atoi(getenv("FORCE"));
        printf("f0 phase 1\n");
        int lastPhase = 1, lastW0 = -1, lastW1 = -1, lastScore = -1, lastT0 = -1, lastT1 = -1; size_t putsShown = 0, spShown = 0;
        for (int fr = 1; fr <= frames; fr++) {
            if (arrowSeed && fr >= 480 && (fr - 480) % 40 == 0) { const int k = (fr - 480) / 40; const uint32_t h = ((uint32_t)arrowSeed * 1000003u + (uint32_t)k * 7919u) * 2654435761u; g.placeArrow((int)(h % 12), (int)((h >> 8) % 9), (int)((h >> 16) % 4)); }
            if (getenv("MPOS") && fr - 469 >= atoi(getenv("MPOS")) && fr - 469 <= atoi(getenv("MPOS")) + 8) for (const auto& e : g.game.sim.ents) if ((getenv("CATS") ? !e.mouse : e.mouse) && e.alive && !e.done && !e.rocketIn) printf("MPOS t%d %.3f %.3f\n", fr - 469, e.x, e.z);
            const unsigned long long d0 = ccr::g_rngDraws;
            g.tick();
            if (getenv("RNGDRAWS") && ccr::g_rngDraws != d0) printf("RNG f%d %llu\n", fr, ccr::g_rngDraws - d0);
            if (getenv("HEATAT") && fr >= atoi(getenv("HEATAT")) && fr < atoi(getenv("HEATAT")) + 4) { printf("HEAT f%d", fr); for (int x = 3; x <= 7; x++) printf(" (%d,5)=%d", x, g.game.sim.heat[5 * kCols + x]); for (const auto& e : g.game.sim.ents) if (!e.mouse && e.alive && !e.done && !e.rocketIn) printf(" cat[%d,%d]", e.gx, e.gy); printf(" coll55=%x rocket1=%d,%d rocket3=%d,%d", g.game.sim.fieldCollision(5, 5), g.game.cpuEnv.rocketX[1], g.game.cpuEnv.rocketY[1], g.game.cpuEnv.rocketX[3], g.game.cpuEnv.rocketY[3]); printf("%c", 10); }
            if (g.phase != lastPhase) { printf("f%d phase %d", fr, g.phase); if (g.failReason) printf(" (%s)", g.failReason); putchar(10); lastPhase = g.phase; }
            if (g.ownTeam() != lastW0 || g.enemyTeam() != lastW1) { printf("WORDS f%d w12 %d w13 %d", fr, g.ownTeam(), g.enemyTeam()); putchar(10); lastW0 = g.ownTeam(); lastW1 = g.enemyTeam(); }
            if (want == 24 && (g.teamScore(0) != lastT0 || g.teamScore(1) != lastT1)) { printf("WORDS f%d w8 %d w9 %d\n", fr, g.teamScore(0), g.teamScore(1)); lastT0 = g.teamScore(0); lastT1 = g.teamScore(1); }
            if (getenv("TRACKARR")) for (; putsShown < g.game.cpuPuts.size(); putsShown++) { const auto& q = g.game.cpuPuts[putsShown]; printf("ARRPUT f%d player %d cell %d %d dir %d\n", q.frame + 469, q.player, q.x, q.y, q.dir); }
            if (getenv("TRACKUP")) for (; spShown < g.game.gen->spawns.size(); spShown++) { const auto& q = g.game.gen->spawns[spShown]; printf("SPAWN f%d mouse %d type %d cell %d %d\n", q.frame + 469, (int)!q.cat, q.mouseType, q.x, q.y); }
            if (g.playerScore() != lastScore) { printf("SCORE f%d %d", fr, g.playerScore()); putchar(10); lastScore = g.playerScore(); }
        }
        return 0;
    }
    printf("stage %d not found\n", want); return 1;
}
