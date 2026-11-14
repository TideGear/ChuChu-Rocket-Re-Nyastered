// Loads every board of a stage file (record layout of tools/export_testdata.py / export_dlc_stages.py) and checks it is a valid puzzle:
// known tiles only, at least one mouse and one rocket, loads into the simulation and runs 60 s of ticks without arrows without error.
#include "../core/sim.hpp"
#include <cstdio>
#include <vector>
using namespace ccr;
int main(int argc, char** argv) {
    int rc = 0;
    for (int a = 1; a < argc; a++) {
        FILE* f = fopen(argv[a], "rb"); if (!f) { printf("cannot open %s\n", argv[a]); return 2; }
        uint32_t n; fread(&n, 4, 1, f); int ok = 0, bad = 0;
        for (uint32_t i = 0; i < n; i++) {
            uint8_t hdr[4]; fread(hdr, 1, 4, f); int nsol = hdr[1];
            Stage st; uint8_t walls[237]; char title[32];
            fread(st.tiles, 1, 108, f); fread(walls, 1, 237, f);
            std::vector<uint8_t> sol(nsol * 3); if (nsol) fread(sol.data(), 1, sol.size(), f);
            fread(title, 1, 32, f);
            for (int r = 0; r < 10; r++) for (int c = 0; c < 12; c++) st.hw[r * 12 + c] = walls[25 * r + c];
            for (int r = 0; r < 9; r++) for (int c = 0; c < 13; c++) st.vw[r * 13 + c] = walls[25 * r + 12 + c];
            int mice = 0, rockets = 0, unknown = 0;
            for (int k = 0; k < 108; k++) { uint8_t t = st.tiles[k]; if (t == T_Rocket) rockets++; else if (t >= T_MouseS && t < T_MouseS + 4) mice++; else if (!(t == 0 || t == T_Hole || (t >= T_CatS && t < T_CatS + 4))) unknown++; }
            Sim sim; sim.load(st); Result r = sim.run(60 * 60);
            bool good = mice > 0 && rockets > 0 && !unknown && r.mice == mice;
            if (good) ok++; else { bad++; printf("  %s board %u (src %d idx %d): mice %d rockets %d unknown %d sim mice %d\n", argv[a], i, hdr[0], hdr[2] | (hdr[3] << 8), mice, rockets, unknown, r.mice); }
        }
        fclose(f); printf("%s: %u boards, valid %d, invalid %d\n", argv[a], n, ok, bad); if (bad) rc = 1;
    }
    return rc;
}
