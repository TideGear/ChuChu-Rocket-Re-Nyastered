// Generates random CPU-decision cases from real battle states for the Dreamcast differential test (tools/oracle/dc_cpu_decide.py).
// Each output line: inputs (game type, time, player, flags, count, timer, LCG state, ranks, rocket cells, collision words, heat map) and the port's results after one CpuPlayer::step with state 0.
// usage: cpu_dc_gen <battle_stages.bin> <cases> <out.txt>
#include "../core/battle.hpp"
#include <cstdio>
#include <cstdlib>
#include <random>
using namespace ccr;
int main(int argc, char** argv) {
    FILE* f = fopen(argc > 1 ? argv[1] : "../local/cache/assets/battle_stages.bin", "rb"); if (!f) { printf("cannot open stages\n"); return 2; }
    int cases = argc > 2 ? atoi(argv[2]) : 500; FILE* out = fopen(argc > 3 ? argv[3] : "cpu_dc_cases.txt", "w"); if (!out) return 2;
    uint32_t n; if (fread(&n, 4, 1, f) != 1) return 2; std::vector<Stage> stages;
    for (uint32_t i = 0; i < n; i++) {
        uint8_t h[4]; Stage st; uint8_t walls[237], title[32];
        if (fread(h, 1, 4, f) != 4 || fread(st.tiles, 1, 108, f) != 108 || fread(walls, 1, 237, f) != 237 || fread(title, 1, 32, f) != 32) break;
        for (int r = 0; r < 10; r++) for (int c = 0; c < 12; c++) st.hw[r * 12 + c] = walls[25 * r + c];
        for (int r = 0; r < 9; r++) for (int c = 0; c < 13; c++) st.vw[r * 13 + c] = walls[25 * r + 12 + c];
        if (h[0] == 2) stages.push_back(st);
    }
    std::mt19937 rng(2024); int done = 0, found = 0;
    for (int c = 0; done < cases; c++) {
        BattleGame g; g.rouletteManager = false; g.baseScale = 0.25f; g.roundFrames = 1 << 30; for (int p = 0; p < 4; p++) g.setCpu(p, 3);
        g.start(stages[rng() % stages.size()], rng()); int frames = 100 + rng() % 1500; for (int t = 0; t < frames; t++) g.tick();
        for (int k = 0; k < 4 && done < cases; k++) {
            CpuEnv env = g.cpuEnv; env.gameType = (rng() % 4 == 0) ? 1 : 0; env.globalTime = (int)(rng() % 5000) * 2;
            int player = rng() % 4; static const uint32_t lv[4] = {0x55, 0x56, 0x48, 0x2a}; CpuPlayer cp; cp.player = player; cp.flags = lv[rng() % 4]; cp.state = 0;
            cp.count = (uint16_t)(rng() % 400); cp.timer = (int)(rng() % 5); CpuLcg lg; lg.state = rng();
            int rk[4]; for (int p = 0; p < 4; p++) rk[p] = env.rank(p);
            fprintf(out, "%d %d %d %u %d %d %u", env.gameType, env.globalTime, player, cp.flags, (int)cp.count, cp.timer, lg.state);
            for (int p = 0; p < 4; p++) fprintf(out, " %d", rk[p]);
            for (int p = 0; p < 4; p++) fprintf(out, " %d %d", env.rocketX[p], env.rocketY[p]);
            for (int y = 0; y < 9; y++) for (int x = 0; x < 12; x++) { uint32_t w = g.sim.fieldCollision(x, y); if (w & kRocket) w |= (uint32_t)(g.sim.rocketOwner[y][x] & 3); fprintf(out, " %u", w); }   // the original keeps the rocket owner in the low 2 bits of the collision word
            for (int y = 0; y < 9; y++) for (int x = 0; x < 12; x++) fprintf(out, " %d", (int)g.sim.heat[y * 12 + x]);
            cp.step(env, lg);
            fprintf(out, " | %d %d %d %d %d %d %u %d\n", cp.state, cp.timer, (int)cp.count, cp.tx, cp.ty, cp.dir, lg.state, cp.branch);
            done++; if (cp.state == 1) found++;
        }
    }
    printf("wrote %d cases (%d with a target found)\n", done, found); fclose(out); return 0;
}
