// Free-runs the port's generator (4 cells, Dreamcast rand() stream) from a state read off Flycast and compares its rand() calls per frame with the game's.
// usage: dc_spawn_probe <draws.txt>   lines: frame state draws   (draws = rand() calls the game made that frame, -1 unknown)
// Outside influences (a cat lost, mice eaten, other rand() users) are not modelled, so the comparison stops being meaningful after the first divergence; the probe prints how far it agrees.
#include "../core/generator.hpp"
#include <cstdio>
using namespace ccr;
int main(int argc, char** argv) {
    FILE* f = fopen(argc > 1 ? argv[1] : "draws.txt", "r"); if (!f) { puts("cannot open"); return 2; }
    int frame; unsigned state; int draws; std::vector<std::array<long, 3>> rows;
    while (fscanf(f, "%d %u %d", &frame, &state, &draws) == 3) rows.push_back({frame, (long)state, draws});
    if (rows.empty()) return 2;
    std::vector<GenCell> cells = {{1, 1, 0}, {10, 1, 0}, {1, 7, 0}, {10, 7, 0}};   // four generators (positions do not affect the draws)
    Generator g(cells, 0); g.rng().seedDreamcast((uint32_t)rows[0][1]);
    int agree = 0, first = -1;
    for (size_t i = 0; i < rows.size(); ++i) {
        const unsigned long long before = g_rngDraws;
        g.frame((int)i + 1);
        const int mine = (int)(g_rngDraws - before);
        if ((int)rows[i][2] == mine) { if (first < 0) ++agree; } else if (first < 0) { first = (int)i; printf("first divergence at frame %ld: game drew %d, port drew %d\n", rows[i][0], (int)rows[i][2], mine); }
    }
    printf("port generator agrees with the game on %d consecutive frames from the first recorded state\n", agree);
    return 0;
}
