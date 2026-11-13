// Replays golden spawn logs recorded from the original's battle generator (tools/oracle/make_spawn_golden.py).
// The generator is a pure function of its RNG and the externally driven state (mouse counts, cat-out flag, prohibit flags),
// which the log supplies per frame. Frames from the first prohibit-flag change (end of round) on are not compared.
#include "../core/generator.hpp"
#include <cstdio>
#include <cstring>
#include <map>
using namespace ccr;
struct Ext { int mice, cnt1, cnt2, catOut, flags; };
int main(int argc, char** argv) {
    const char* path = argc > 1 ? argv[1] : "../local/testdata/spawn_golden.txt";
    FILE* f = fopen(path, "r"); if (!f) { printf("cannot open %s\n", path); return 2; }
    char line[256]; int cases = 0, ok = 0;
    while (fgets(line, sizeof line, f)) {
        int idx, seed, frames, ng, ns, nf;
        if (sscanf(line, "CASE %d %d %d %d %d %d", &idx, &seed, &frames, &ng, &ns, &nf) != 6) continue;
        std::vector<GenCell> cells; std::vector<Spawn> want; std::map<int, Ext> ext;
        for (int i = 0; i < ng; i++) { fgets(line, sizeof line, f); GenCell g; sscanf(line, "G %d %d %d", &g.x, &g.y, &g.dir); cells.push_back(g); }
        for (int i = 0; i < nf; i++) { fgets(line, sizeof line, f); int fr; Ext e; sscanf(line, "F %d %d %d %d %d %d", &fr, &e.mice, &e.cnt1, &e.cnt2, &e.catOut, &e.flags); ext[fr] = e; }
        for (int i = 0; i < ns; i++) { fgets(line, sizeof line, f); Spawn s; char kind[8];
            sscanf(line, "S %d %7s %d %d %d %d", &s.frame, kind, &s.x, &s.y, &s.dir, &s.mouseType); s.cat = !strcmp(kind, "cat"); want.push_back(s); }
        int last = frames;
        for (auto& kv : ext) if (kv.second.flags != 0) { last = kv.first - 2; break; }        // end of round: not part of the generator
        Generator g(cells, (uint32_t)seed);
        for (int fr = 1; fr <= last; fr++) {
            auto it = ext.find(fr);
            if (it != ext.end()) { g.mice = it->second.mice; g.cnt1 = it->second.cnt1; g.cnt2 = it->second.cnt2; g.flags = (uint32_t)it->second.flags; if (!it->second.catOut) g.catOut = false; }
            g.frame(fr);
        }
        std::vector<Spawn> w; for (auto& s : want) if (s.frame <= last) w.push_back(s);
        bool same = g.spawns.size() == w.size(); size_t bad = 0;
        for (size_t i = 0; i < w.size() && i < g.spawns.size(); i++) {
            const Spawn& a = g.spawns[i]; const Spawn& b = w[i];
            if (!(a.frame == b.frame && a.cat == b.cat && a.x == b.x && a.y == b.y && a.dir == b.dir && a.mouseType == b.mouseType)) { same = false; bad = i; break; }
        }
        cases++; if (same) ok++; else printf("MISMATCH stage %d seed %d (frames<=%d): got %zu spawns, want %zu, first diff at %zu\n", idx, seed, last, g.spawns.size(), w.size(), bad);
    }
    printf("generator golden cases: %d, identical: %d\n", cases, ok);
    return ok == cases ? 0 : 1;
}
