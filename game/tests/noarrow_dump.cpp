// Prints, for every stage of a stage file, the ticks at which mice leave the board when no arrows are placed (for cross-version comparison).
#include "../core/sim.hpp"
#include <cstdio>
#include <cstdlib>
#include <cstring>
using namespace ccr;
int main(int argc, char** argv) {
    FILE* f = fopen(argc > 1 ? argv[1] : "../local/cache/assets/gba/gba_stages.bin", "rb"); if (!f) return 2;
    int src = argc > 2 ? atoi(argv[2]) : 0, horizon = argc > 3 ? atoi(argv[3]) : 900;
    uint32_t n; if (fread(&n, 4, 1, f) != 1) return 2;
    for (uint32_t i = 0; i < n; i++) {
        uint8_t h[4], w[237], t[32]; Stage st; if (fread(h, 1, 4, f) != 4 || fread(st.tiles, 1, 108, f) != 108 || fread(w, 1, 237, f) != 237) break;
        fseek(f, h[1] * 3, SEEK_CUR); if (fread(t, 1, 32, f) != 32) break;
        for (int r = 0; r < 10; r++) for (int c = 0; c < 12; c++) st.hw[r * 12 + c] = w[25 * r + c];
        for (int r = 0; r < 9; r++) for (int c = 0; c < 13; c++) st.vw[r * 13 + c] = w[25 * r + 12 + c];
        if (h[0] != src) continue;
        Sim sim; sim.load(st);
        if (argc > 4) { int x, y, d; const char* p = argv[4]; while (sscanf(p, "%d,%d,%d", &x, &y, &d) == 3) { sim.placeArrow(x, y, d); const char* q = strchr(p, ';'); if (!q) break; p = q + 1; } }
        for (int k = 0; k < horizon; k++) sim.tick();
        printf("STAGE %d %d:", h[0], h[2] | (h[3] << 8)); for (int tk : sim.endTicks) printf(" %d", tk); printf("\n");
    }
    return 0;
}
