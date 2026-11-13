#include "../core/roulette.hpp"
#include <cstdio>
using namespace ccr;
int main(int argc, char** argv) {
    FILE* f = fopen(argc > 1 ? argv[1] : "../local/testdata/roulette_golden.txt", "r"); if (!f) { printf("cannot open golden file\n"); return 2; }
    char line[160]; int seed = 1; unsigned ok = 0, n = 0;
    if (!fgets(line, sizeof line, f) || sscanf(line, "SEED %d", &seed) != 1) return 2;
    Rng rng((uint32_t)seed); Roulette r(rng);
    while (fgets(line, sizeof line, f)) {
        int rank, exclude, g, lastA, lastB, player, want; unsigned bcd;
        if (sscanf(line, "Q %d %d %u %d %d %d %d -> %d", &rank, &exclude, &bcd, &g, &lastA, &lastB, &player, &want) != 8) continue;
        r.lastA = lastA; r.lastB = lastB;
        int got = r.roll(rank, bcd, g, exclude); n++; if (got == want) ok++;
    }
    printf("roulette golden: %u calls, identical: %u\n", n, ok);
    return ok == n ? 0 : 1;
}
