// Differential test: ccr::adjustAngle / diffAngle vs the results recorded from the original Android code (tools/oracle/make_angle_golden.py). usage: angle_test <angle_golden.txt>
#include "../core/angle.hpp"
#include <cstdio>
using namespace ccr;
int main(int argc, char** argv) {
    FILE* f = fopen(argc > 1 ? argv[1] : "../local/testdata/angle_golden.txt", "r"); if (!f) { printf("cannot open golden\n"); return 2; }
    unsigned cur, tgt, st, adj, dif; int n = 0, bad = 0;
    while (fscanf(f, "%u %u %u %u %u", &cur, &tgt, &st, &adj, &dif) == 5) {
        n++; unsigned a = adjustAngle((int)cur, (int)tgt, (int)st), d = (unsigned)diffAngle((int)cur, (int)tgt);
        if (a != adj || d != dif) { if (bad++ < 5) printf("MISMATCH cur %u tgt %u step %u: adjust %u (orig %u) diff %u (orig %u)\n", cur, tgt, st, a, adj, d, dif); }
    }
    printf("angle golden: %d cases, %d different\n", n, bad); return bad ? 1 : 0;
}
