// Cases for the second half of the CPU task (state 1: move the cursor one cell towards the target, then put the arrow) for the Dreamcast differential test tools/oracle/dc_cpu_move.py.
// Line: player cx cy tx ty dir timer count | state timer count cx cy put px py pdir     (put = 1 when the port placed an arrow this call)
// usage: cpu_dc_move_gen <cases> <out.txt>
#include "../core/cpu.hpp"
#include <cstdio>
#include <cstdlib>
#include <random>
using namespace ccr;
int main(int argc, char** argv) {
    int n = argc > 1 ? atoi(argv[1]) : 3000; FILE* out = fopen(argc > 2 ? argv[2] : "cpu_dc_move_cases.txt", "w"); if (!out) return 2; std::mt19937 rng(77); int puts = 0;
    for (int i = 0; i < n; i++) {
        CpuEnv env; env.globalTime = (int)(rng() % 1000) * 2; env.cursorFree = [](int) { return true; };
        int put = 0, ppl = 0, px = 0, py = 0, pd = 0; env.putArrow = [&](int pl, int x, int y, int d) { put = 1; ppl = pl; px = x; py = y; pd = d; };
        CpuPlayer cp; cp.player = rng() % 4; cp.flags = 0x55; cp.state = 1; cp.cx = rng() % 12; cp.cy = rng() % 9;
        if (rng() % 3 == 0) { cp.tx = cp.cx; cp.ty = cp.cy; } else if (rng() % 2) { cp.tx = rng() % 12; cp.ty = cp.cy; } else { cp.tx = rng() % 12; cp.ty = rng() % 9; }
        cp.dir = rng() % 4; cp.timer = 1 + rng() % 44; cp.count = (uint16_t)(rng() % 300);
        fprintf(out, "%d %d %d %d %d %d %d %d", cp.player, cp.cx, cp.cy, cp.tx, cp.ty, cp.dir, cp.timer, (int)cp.count);
        CpuLcg lg; cp.step(env, lg); puts += put;
        fprintf(out, " | %d %d %d %d %d %d %d %d %d\n", cp.state, cp.timer, (int)cp.count, cp.cx, cp.cy, put, px, py, pd);
    }
    printf("wrote %d cases (%d placed an arrow)\n", n, puts); fclose(out); return 0;
}
