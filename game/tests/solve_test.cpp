// Replays the GBA reference-solution arrows against the simulation. Data: local/testdata/gba_stages.bin (from tools/export_testdata.py).
#include "../core/sim.hpp"
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>
using namespace ccr;

int main(int argc, char** argv) {
    const char* path = argc > 1 ? argv[1] : "../local/testdata/gba_stages.bin";
    FILE* f = fopen(path, "rb"); if (!f) { printf("cannot open %s\n", path); return 2; }
    uint32_t n; fread(&n, 4, 1, f);
    int solved = 0, total = 0, noSol = 0; int fail[3] = {0, 0, 0};
    int shown = 0; long agg[4] = {0,0,0,0}; int failWithCatRocket = 0, failWithBroken = 0; int stat[2][2] = {{0,0},{0,0}}; /* [hasCat][ok] */
    for (uint32_t i = 0; i < n; i++) {
        uint8_t hdr[4]; fread(hdr, 1, 4, f); int src = hdr[0], nsol = hdr[1];
        Stage st; uint8_t walls[237]; char title[32];
        fread(st.tiles, 1, 108, f); fread(walls, 1, 237, f);
        std::vector<uint8_t> sol(nsol * 3); if (nsol) fread(sol.data(), 1, sol.size(), f);
        fread(title, 1, 32, f);
        for (int r = 0; r < 10; r++) for (int c = 0; c < 12; c++) st.hw[r * 12 + c] = walls[25 * r + c];
        for (int r = 0; r < 9; r++) for (int c = 0; c < 13; c++) st.vw[r * 13 + c] = walls[25 * r + 12 + c];
        if (!nsol) { noSol++; continue; }
        Sim sim; if (getenv("BREAKAT")) sim.breakAt = atoi(getenv("BREAKAT")); if (getenv("ORDER")) sim.order = atoi(getenv("ORDER")); if (getenv("CATROT")) sim.catRot = atoi(getenv("CATROT")); if (getenv("CATSPD")) sim.catSpeed = (float)atof(getenv("CATSPD")); if (getenv("MSPD")) sim.mouseSpeed = (float)atof(getenv("MSPD")); if (getenv("EAT")) sim.eatRadius = (float)atof(getenv("EAT")); sim.load(st);
        for (int k = 0; k < nsol; k++) sim.placeArrow(sol[k * 3], sol[k * 3 + 1], sol[k * 3 + 2]);
        bool dbg = getenv("DBG") && atoi(getenv("DBG")) == (int)(hdr[2] | (hdr[3] << 8)) && src == 0;
        if (dbg) {
            printf("--- %s  (S=south W=west N=north E=east; mouse m, cat c, rocket R, hole H, solution arrow v < ^ >)\n", title);
            const char* aglyph = "v<^>";
            for (int y = 0; y < 9; y++) { for (int x = 0; x < 12; x++) { char ch = '.'; uint8_t t = st.tiles[y * 12 + x];
                if (t == T_Rocket) ch = 'R'; else if (t == T_Hole) ch = 'H'; else if (t >= T_MouseS && t < T_MouseS + 4) ch = "SWNE"[t - T_MouseS] + 32; else if (t >= T_CatS && t < T_CatS + 4) ch = "SWNE"[t - T_CatS];
                for (int k = 0; k < nsol; k++) if (sol[k * 3] == x && sol[k * 3 + 1] == y) ch = aglyph[sol[k * 3 + 2]];
                printf(" %c", ch); } printf("\n"); }
            for (int r = 0; r < 19; r++) { for (int c = 0; c < 25; c++) { char ch = ' ';
                if (r % 2 == 0 && c % 2 == 1) ch = st.hw[(r / 2) * 12 + c / 2] ? '-' : ' ';
                else if (r % 2 == 1 && c % 2 == 0) ch = st.vw[(r / 2) * 13 + c / 2] ? '|' : ' ';
                else if (r % 2 == 1 && c % 2 == 1) { uint8_t t = st.tiles[(r / 2) * 12 + c / 2]; ch = t == T_Rocket ? 'R' : t == T_Hole ? 'H' : (t >= T_MouseS && t < T_MouseS + 4) ? "swne"[t - T_MouseS] : (t >= T_CatS && t < T_CatS + 4) ? "SWNE"[t - T_CatS] : '.'; }
                else ch = '+';
                putchar(ch); } putchar('\n'); }
            sim.trace = true;
        }
        Result r = sim.run(getenv("HORIZON") ? atoi(getenv("HORIZON")) : 60 * 180);
        if (getenv("DUMP")) { printf("STAGE %d %d %d:", src, hdr[2] | (hdr[3] << 8), (int)sim.saveTicks.size()); for (int tk : sim.saveTicks) printf(" %d", tk); printf("" "\n"); }
        total++;
        bool ok = r.mice > 0 && r.saved == r.mice && r.killed == 0;
        stat[r.cats > 0][ok]++; if (!ok) { agg[0] += r.byCat; agg[1] += r.byHole; if (r.catRocket) failWithCatRocket++; if (r.broken) failWithBroken++; } if (ok) solved++; else { if (r.killed) fail[0]++; else if (r.stuck) fail[1]++; else fail[2]++;
            if (shown < 5 && src == 0) { printf("  FAIL main[%d] %s: mice %d saved %d killed %d cats %d ticks %d\n", hdr[2] | (hdr[3] << 8), title, r.mice, r.saved, r.killed, r.cats, r.ticks); shown++; } }
    }
    printf("stages %u, with solutions %d: solved %d (%.1f%%); failed: killed %d, unfinished %d, other %d; no-solution stages %d\n", n, total, solved, 100.0 * solved / (total ? total : 1), fail[0], fail[1], fail[2], noSol);
    printf("no cats: ok %d fail %d | with cats: ok %d fail %d\n", stat[0][1], stat[0][0], stat[1][1], stat[1][0]);
    printf("failures: mice killed by cats %ld, by holes %ld; failing stages with a cat in a rocket %d, with a broken arrow %d\n", agg[0], agg[1], failWithCatRocket, failWithBroken);
    return solved == total ? 0 : 1;
}
