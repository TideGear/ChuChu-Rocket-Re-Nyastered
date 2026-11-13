#include "../core/score.hpp"
#include <cstdio>
using namespace ccr;
int main(int argc, char** argv) {
    FILE* f = fopen(argc > 1 ? argv[1] : "../local/testdata/score_golden.txt", "r"); if (!f) { printf("cannot open golden file\n"); return 2; }
    Scoreboard s; char line[128]; int ops = 0, bad = 0;
    while (fgets(line, sizeof line, f)) {
        int p, d;
        if (sscanf(line, "A %d %d", &p, &d) == 2) { s.add(p, d); ops++; }
        else if (sscanf(line, "C %d", &p) == 1) { s.catHasCome(p); ops++; }
        else if (line[0] == 'R') {
            int r[8]; sscanf(line, "R %d %d %d %d %d %d %d %d", r, r + 1, r + 2, r + 3, r + 4, r + 5, r + 6, r + 7);
            if (r[0] != s.player[0] || r[1] != s.player[1] || r[2] != s.player[2] || r[3] != s.player[3] || r[4] != s.team[0] || r[5] != s.team[1] || r[6] != s.catCounter[0] || r[7] != s.catCounter[1]) { if (bad < 3) printf("diverged at op %d\n", ops); bad++; }
        }
    }
    printf("score golden: %d operations, divergences: %d\n", ops, bad);
    return bad ? 1 : 0;
}
