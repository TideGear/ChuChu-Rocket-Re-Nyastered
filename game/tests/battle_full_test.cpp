// Whole-battle differential: replays local/testdata/battle_golden.txt (original, emulated, scripted arrows) and compares the score timeline
// (frame of every score change) up to the first roulette trigger.
#include "../core/battle.hpp"
#include <cstdio>
#include <map>
#include <cstdlib>
using namespace ccr;
struct P { int f, pl, x, y, d; };
int main(int argc, char** argv) {
    FILE* sf = fopen("../local/cache/assets/battle_stages.bin", "rb"); FILE* g = fopen(argc > 1 ? argv[1] : "../local/testdata/battle_golden.txt", "r");
    if (!sf || !g) { printf("missing files\n"); return 2; }
    uint32_t n; fread(&n, 4, 1, sf); std::vector<Stage> stages;
    for (uint32_t i = 0; i < n; i++) { uint8_t h[4], w[237], t[32]; Stage st; fread(h, 1, 4, sf); fread(st.tiles, 1, 108, sf); fread(w, 1, 237, sf); fread(t, 1, 32, sf);
        for (int r = 0; r < 10; r++) for (int c = 0; c < 12; c++) st.hw[r * 12 + c] = w[25 * r + c];
        for (int r = 0; r < 9; r++) for (int c = 0; c < 13; c++) st.vw[r * 13 + c] = w[25 * r + 12 + c]; stages.push_back(st); }
    char line[256]; int cases = 0, ok = 0;
    while (fgets(line, sizeof line, g)) {
        int idx, seed, frames, nsc, nrl, nsp, npl; if (sscanf(line, "CASE %d %d %d %d %d %d %d", &idx, &seed, &frames, &nsc, &nrl, &nsp, &npl) != 7) continue;
        std::map<int, P> pl; std::vector<std::vector<int>> sc; std::vector<int> rl; std::vector<std::vector<int>> sp;
        std::vector<P> pv;
        for (int i = 0; i < npl + nsc + nrl + nsp; i++) {
            if (!fgets(line, sizeof line, g)) break;
            int a[5];
            if (line[0] == 'A' && sscanf(line, "A %d %d %d %d %d", &a[0], &a[1], &a[2], &a[3], &a[4]) == 5) pl[a[0]] = {a[0], a[1], a[2], a[3], a[4]};
            else if (line[0] == 'S' && line[1] == 'C') { int f, s0, s1, s2, s3; sscanf(line, "SC %d %d %d %d %d", &f, &s0, &s1, &s2, &s3); sc.push_back({f, s0, s1, s2, s3}); }
            else if (line[0] == 'S' && line[1] == ' ') { int f, x, y, d, t; char k[8]; sscanf(line, "S %d %7s %d %d %d %d", &f, k, &x, &y, &d, &t); sp.push_back({f, k[0] == 'c', x, y, d, t}); }
            else if (line[0] == 'R') { int f; sscanf(line, "RL %d", &f); rl.push_back(f); }
        }
        int last = (rl.empty() || getenv("FULL")) ? frames : rl[0] - 1;   // FULL=1: compare the whole log with the roulette (and its events) running in the port too
        FILE* dump = (getenv("DUMP") && getenv("DBG") && atoi(getenv("DBG")) == idx) ? fopen(getenv("DUMP"), "w") : nullptr;
        BattleGame b; b.roundFrames = 1 << 30; b.baseScale = 0.25f; b.rouletteEnabled = getenv("FULL") != nullptr; if (getenv("FORCE")) b.forceOutcome = atoi(getenv("FORCE")); if (getenv("TEAM")) b.teamMode = true; b.rouletteManager = false; if (getenv("DECLAG")) b.decLag = atoi(getenv("DECLAG")); if (getenv("FULL")) { b.fixedGameTime = getenv("GT") ? atoi(getenv("GT")) : 0; b.fixedBcd = getenv("BCD") ? (int)strtol(getenv("BCD"), nullptr, 0) : 0; }  b.debug = getenv("DBG") && atoi(getenv("DBG")) == idx; b.start(stages[idx], (uint32_t)seed); if (getenv("THR")) b.roulette->fillTable((float)atof(getenv("THR"))); if (getenv("SPEED")) b.setCharaSpeed((float)atof(getenv("SPEED")));
        std::vector<std::vector<int>> got; int prev[4] = {0, 0, 0, 0};
        for (int f = 1; f <= last; f++) {
            auto it = pl.find(f); if (it != pl.end()) { const int lockSaved = b.cursorLock; b.cursorLock = 0; /* the recorded placements call the original's arrow function directly, which the cursor lock does not gate */ bool okp = b.placeArrow(it->second.pl, it->second.x, it->second.y, it->second.d); b.cursorLock = lockSaved; if (b.debug) printf("PLACE f%d p%d (%d,%d) d%d -> %d coll=%x\n", f, it->second.pl, it->second.x, it->second.y, it->second.d, (int)okp, b.sim.coll[it->second.y][it->second.x]); }
            std::vector<std::pair<float,float>> before; if (dump) for (auto& e : b.sim.ents) before.push_back({e.x, e.z});
            if (getenv("POSDUMP") && atoi(getenv("POSDUMP")) == idx && seed == (getenv("POSSEED") ? atoi(getenv("POSSEED")) : seed)) { static FILE* pf = fopen(getenv("POSFILE") ? getenv("POSFILE") : "posdump.txt", "w"); fprintf(pf, "F %d\n", f); for (auto& e : b.sim.ents) if (e.mouse && e.alive && !e.done && !e.fresh) fprintf(pf, "M %.6f %.6f\n", e.x, e.z); }
            if (getenv("JIMEDUMP") && atoi(getenv("JIMEDUMP")) == idx && f >= (getenv("JLO") ? atoi(getenv("JLO")) : 1500) && f <= (getenv("JHI") ? atoi(getenv("JHI")) : 1552)) for (auto& e : b.sim.ents) if (e.mouse && e.jime && e.alive && !e.done) printf("POS f%d %.4f %.4f %d\n", f, e.x, e.z, e.angle);
            if (f == 1 && getenv("SPAWNLAG") && b.gen) b.gen->spawnLag = atoi(getenv("SPAWNLAG"));
            if (getenv("RNGDUMP") && atoi(getenv("RNGDUMP")) == idx && seed == 1000 + idx * 17) { static unsigned long long last = 0; if (f == 1) last = ccr::g_rngDraws; b.tick(); if (ccr::g_rngDraws != last) { printf("RNG f%d %llu\n", f, ccr::g_rngDraws - last); last = ccr::g_rngDraws; } } else
            b.tick();
            if (getenv("MICEDUMP") && atoi(getenv("MICEDUMP")) == idx && f >= (getenv("MFROM") ? atoi(getenv("MFROM")) : 0) && f <= (getenv("MTO") ? atoi(getenv("MTO")) : 0)) printf("MICE f%d %d cnt1 %d cnt2 %d\n", f, b.gen->mice, b.gen->cnt1, b.gen->cnt2);
            if (b.debug && f >= 1410 && f <= 1449) printf("C f%d coll(3,1)=%x\n", f, b.sim.coll[1][3]);
            if (dump) for (size_t k = 0; k < b.sim.ents.size(); k++) { auto& e = b.sim.ents[k]; if (k < before.size() && e.alive && !e.done && !e.rocketIn && (e.x != before[k].first || e.z != before[k].second)) fprintf(dump, "%d %zu %.3f %.3f\n", f, k, e.x, e.z); }
            if (b.debug && f == 682) for (size_t k = 0; k < b.sim.ents.size(); k++) { auto& e = b.sim.ents[k]; if (e.alive && !e.done) printf("ENT %zu m%d %.2f %.2f\n", k, (int)e.mouse, e.x, e.z); }
            if (b.debug && f % 10 == 0 && f < 700 && b.sim.ents.size() > 5) printf("M5 f%d %.2f %.2f\n", f, b.sim.ents[5].x, b.sim.ents[5].z);
            if (b.debug) for (auto& e : b.sim.ents) if (!e.mouse && (f % 20 == 0)) printf("CAT f%d %.2f %.2f\n", f, e.x, e.z);
            bool ch = false; for (int k = 0; k < 4; k++) if (b.score.player[k] != prev[k]) ch = true;
            if (ch) { got.push_back({f, b.score.player[0], b.score.player[1], b.score.player[2], b.score.player[3]}); for (int k = 0; k < 4; k++) prev[k] = b.score.player[k]; }
        }
        { size_t m = 0; bool bad2 = false; for (; m < sp.size() && m < b.gen->spawns.size(); m++) { auto& a = b.gen->spawns[m]; if (sp[m][0] > last) break;
              if (!(a.frame == sp[m][0] && (int)a.cat == sp[m][1] && a.x == sp[m][2] && a.y == sp[m][3] && a.dir == sp[m][4] && a.mouseType == sp[m][5])) { bad2 = true; break; } }
          if (bad2) printf("  stage %d: first spawn divergence #%zu: got f%d cat%d type%d, want f%d cat%d type%d\n", idx, m, b.gen->spawns[m].frame, (int)b.gen->spawns[m].cat, b.gen->spawns[m].mouseType, sp[m][0], sp[m][1], sp[m][5]); if (bad2) printf("     got xy %d,%d d%d want xy %d,%d d%d\n", b.gen->spawns[m].x, b.gen->spawns[m].y, b.gen->spawns[m].dir, sp[m][2], sp[m][3], sp[m][4]); }
        if (getenv("FULL")) { printf("  case %d seed %d: original rolled at f%d;", idx, seed, rl.empty() ? -1 : rl[0]); printf(" port outcomes:"); for (int o : b.lastRoll) printf(" %d", o); printf("\n"); }
        if (dump) fclose(dump);
        std::vector<std::vector<int>> want; for (auto& s : sc) if (s[0] <= last) want.push_back(s);
        // golden's first row is the initial state (zeros or first frame); drop all-zero rows
        auto strip = [](std::vector<std::vector<int>> v) { std::vector<std::vector<int>> o; for (auto& r : v) if (r[1] || r[2] || r[3] || r[4]) o.push_back(r); return o; };
        want = strip(want); got = strip(got);
        cases++; size_t bad = 0; bool same = want.size() == got.size();
        for (size_t i = 0; i < want.size() && i < got.size(); i++) if (want[i] != got[i]) { same = false; bad = i; break; }
        if (same) ok++; else printf("MISMATCH stage %d seed %d (<=%d): got %zu want %zu changes, first diff #%zu: got %d [%d %d %d %d] want %d [%d %d %d %d]\n", idx, seed, last, got.size(), want.size(), bad,
            bad < got.size() ? got[bad][0] : -1, bad < got.size() ? got[bad][1] : 0, bad < got.size() ? got[bad][2] : 0, bad < got.size() ? got[bad][3] : 0, bad < got.size() ? got[bad][4] : 0,
            bad < want.size() ? want[bad][0] : -1, bad < want.size() ? want[bad][1] : 0, bad < want.size() ? want[bad][2] : 0, bad < want.size() ? want[bad][3] : 0, bad < want.size() ? want[bad][4] : 0);
    }
    printf("battle full cases: %d, identical: %d\n", cases, ok); return ok == cases ? 0 : 1;
}
