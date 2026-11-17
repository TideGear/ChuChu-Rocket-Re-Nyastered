// Challenge stage types 3 and 4 on the battle engine: runs BattleGame on a Challenge board with a fixed seed and logs the eaten-mouse counter changes
// in the original's frame numbering (play tick 1 = frame 470), to diff against tools/oracle/challenge_probe.py (SEED=<seed> TRACKCNT=1).
// usage: challenge_battle_test <battle_stages.bin> <stage> <seed> <ticks> [gen mask]
#include "../core/battle.hpp"
#include <cstdio>
#include <cstdlib>
using namespace ccr;
int main(int argc, char** argv) {
    if (argc < 5) { printf("usage: challenge_battle_test <battle_stages.bin> <stage> <seed> <ticks> [mask]\n"); return 2; }
    FILE* f = fopen(argv[1], "rb"); if (!f) { printf("cannot open %s\n", argv[1]); return 2; }
    const int want = atoi(argv[2]), seed = atoi(argv[3]), ticks = atoi(argv[4]), mask = argc > 5 ? atoi(argv[5]) : 6;
    uint32_t n; fread(&n, 4, 1, f);
    for (uint32_t i = 0; i < n; i++) {
        uint8_t hdr[4]; fread(hdr, 1, 4, f); Stage st; uint8_t walls[237]; char title[32];
        fread(st.tiles, 1, 108, f); fread(walls, 1, 237, f); fread(title, 1, 32, f);
        for (int r = 0; r < 10; r++) for (int c = 0; c < 12; c++) st.hw[r * 12 + c] = walls[25 * r + c];
        for (int r = 0; r < 9; r++) for (int c = 0; c < 13; c++) st.vw[r * 13 + c] = walls[25 * r + 12 + c];
        if (hdr[0] != 3 || (hdr[2] | (hdr[3] << 8)) != want) continue;
        BattleGame b; b.roundFrames = 1 << 30; b.baseScale = getenv("SCALE") ? (float)atof(getenv("SCALE")) : 1.0f; b.rouletteEnabled = false; b.rouletteManager = false;   // ChallengeLoop uses the puzzle speed (GA_SetCharaSpeed 1.0), not the quarter speed of the battle harness
        b.start(st, (uint32_t)seed); b.gen->flags = (uint32_t)mask; if (want % 5 == 4) { b.teamMode = true; b.gen->flags = 0xF; b.startCatFever(); }   // type 4: team battle, generators off, four cats if (want % 5 == 3) b.gen->params().pSpawn = 0.075f;   // GE_StartGenerator4Manager in Challenge mode (0x34bf6): stage type 3 raises the spawn probability to 0.075
        size_t shown = 0;
        int last = -1, lastScore = -1, lastW0 = -1, lastW1 = -1;
        if (getenv("COLLDUMP")) for (int r = 0; r < 9; r++) { printf("COLL row %d", r); for (int c = 0; c < 12; c++) printf(" %03x", (unsigned)(b.sim.coll[r][c] & 0xfff)); putchar(10); }
        for (int t = 1; t <= ticks; t++) {
            if (getenv("MPOS") && t >= atoi(getenv("MPOS"))) for (auto& e : b.sim.ents) if (e.mouse && e.alive && !e.done && !e.fresh) { printf("MPOS t%d %.3f %.3f", t, e.x, e.z); putchar(10); }
            if (getenv("CPOS") && t >= atoi(getenv("CPOS"))) for (auto& e : b.sim.ents) if (!e.mouse && e.alive && !e.done && !e.fresh && !e.rocketIn) { printf("CPOS t%d %.3f %.3f", t, e.x, e.z); putchar(10); }
            if (getenv("ARROWS") && t + 469 >= 480 && (t + 469 - 480) % 40 == 0) { const int k = (t + 469 - 480) / 40; const uint32_t sd = (uint32_t)atoi(getenv("ARROWS")), h = (sd * 1000003u + (uint32_t)k * 7919u) * 2654435761u; b.placeArrow(0, (int)(h % 12), (int)((h >> 8) % 9), (int)((h >> 16) % 4)); }   // the scripted arrows of challenge_probe.py (ARROWS=1)
            b.tick();
            if (getenv("SPAWNS")) for (; shown < b.gen->spawns.size(); shown++) { const auto& sp = b.gen->spawns[shown]; printf("UP f%d type %d%s", sp.frame + 469, sp.mouseType, sp.cat ? " cat" : ""); putchar(10); }
            if (getenv("TRACKWORDS") && (b.score.catCounter[0] != lastW0 || b.score.catCounter[1] != lastW1)) { printf("WORDS f%d w12 %d w13 %d", t + 469, b.score.catCounter[0], b.score.catCounter[1]); putchar(10); lastW0 = b.score.catCounter[0]; lastW1 = b.score.catCounter[1]; }
            if (getenv("TRACKSCORE") && b.score.player[0] != lastScore) { printf("SCORE f%d %d", t + 469, b.score.player[0]); putchar(10); lastScore = b.score.player[0]; }
            if (b.sim.killedByCat != last) { printf("CNT f%d rocket 0 eaten %d", t + 469, b.sim.killedByCat); putchar(10); last = b.sim.killedByCat; }
        }
        return 0;
    }
    printf("stage %d not found\n", want); return 1;
}
