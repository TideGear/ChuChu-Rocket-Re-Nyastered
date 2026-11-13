// CPU player differential: compares our CPU players' arrow placements (frame, player, cell, direction) with the original's (local/testdata/cpu_golden.txt).
#include "../core/battle.hpp"
#include <cstdio>
#include <cstdlib>
using namespace ccr;
int main(int argc, char** argv) {
    FILE* sf = fopen("../local/cache/assets/battle_stages.bin", "rb"); FILE* g = fopen((getenv("GOLDEN") ? getenv("GOLDEN") : "../local/testdata/cpu_golden.txt"), "r");
    if (!sf || !g) { printf("missing files\n"); return 2; }
    uint32_t n; if (fread(&n, 4, 1, sf) != 1) return 2; std::vector<Stage> stages;
    for (uint32_t i = 0; i < n; i++) { uint8_t h[4], w[237], t[32]; Stage st; if (fread(h, 1, 4, sf) != 4) break; if (fread(st.tiles, 1, 108, sf) != 108 || fread(w, 1, 237, sf) != 237 || fread(t, 1, 32, sf) != 32) break;
        for (int r = 0; r < 10; r++) for (int c = 0; c < 12; c++) st.hw[r * 12 + c] = w[25 * r + c];
        for (int r = 0; r < 9; r++) for (int c = 0; c < 13; c++) st.vw[r * 13 + c] = w[25 * r + 12 + c]; stages.push_back(st); }
    char line[256]; int cases = 0, ok = 0; bool cpuFirst = !(getenv("CPULAST"));
    while (fgets(line, sizeof line, g)) {
        int idx, seed, frames, l[4], np; if (sscanf(line, "CASE %d %d %d %d %d %d %d %d", &idx, &seed, &frames, &l[0], &l[1], &l[2], &l[3], &np) != 8) continue;
        std::vector<BattleGame::Put> want;
        for (int i = 0; i < np; i++) { if (!fgets(line, sizeof line, g)) break; BattleGame::Put p; sscanf(line, "P %d %d %d %d %d", &p.frame, &p.player, &p.x, &p.y, &p.dir); want.push_back(p); }
        BattleGame b; b.roundFrames = 1 << 30; b.baseScale = 0.25f; b.rouletteEnabled = true; b.rouletteManager = false; b.fixedGameTime = 0; b.fixedBcd = 0; b.cpuFirst = cpuFirst; if (getenv("GTOFF")) b.gtOff = atoi(getenv("GTOFF")); b.debug = getenv("DBGROLL") && atoi(getenv("DBGROLL")) == idx; b.cpuReverse = getenv("CPUREV") != nullptr;
        for (int p = 0; p < 4; p++) b.setCpu(p, l[p]);
        b.start(stages[idx], (uint32_t)seed);
        FILE* dump = (getenv("DUMP") && getenv("HIDX") && atoi(getenv("HIDX")) == idx && (!getenv("CASEN") || atoi(getenv("CASEN")) == cases)) ? fopen(getenv("DUMP"), "w") : nullptr;
        FILE* full = (getenv("FULLDUMP") && getenv("CASEN") && atoi(getenv("CASEN")) == cases) ? fopen(getenv("FULLDUMP"), "w") : nullptr;
        for (int f = 1; f <= frames; f++) { std::vector<std::pair<float,float>> before; std::vector<char> wasIn; if (dump) for (auto& e : b.sim.ents) { before.push_back({e.x, e.z}); wasIn.push_back(e.rocketIn); } b.tick(); if (full) { fprintf(full, "H %d", f); for (int k = 0; k < 108; k++) fprintf(full, " %d", b.sim.heat[k]); fputc(10, full); for (int p = 0; p < 4; p++) if (l[p] >= 0) { auto& c = b.cpu[p]; fprintf(full, "C %d %d %d %d %d %d %d %d %d %d%c", f, p, c.state, c.timer, (int)c.count, c.cx, c.cy, c.tx, c.ty, c.dir, 10); } } if (getenv("ENTF") && idx == atoi(getenv("HIDX")) && f == atoi(getenv("ENTF"))) for (size_t k = 0; k < b.sim.ents.size(); k++) { auto& e = b.sim.ents[k]; printf("ENT %zu alive=%d done=%d %s %.2f %.2f reg=%d rin=%d%c", k, (int)e.alive, (int)e.done, e.mouse ? "mouse" : "cat", e.x, e.z, (int)e.reg, (int)e.rocketIn, 10); } if (getenv("CPUDBG") && idx == atoi(getenv("CPUDBG")) && f >= atoi(getenv("F0")) && f <= atoi(getenv("F1"))) { for (int p = 0; p < 4; p++) printf("f%d p%d st=%d timer=%d cnt=%d cur=(%d,%d) tgt=(%d,%d) dir=%d lcg=%u%c", f, p, b.cpu[p].state, b.cpu[p].timer, (int)b.cpu[p].count, b.cpu[p].cx, b.cpu[p].cy, b.cpu[p].tx, b.cpu[p].ty, b.cpu[p].dir, b.cpuLcg.state, 10); } if (dump) for (size_t k = 0; k < b.sim.ents.size() && k < before.size(); k++) { auto& e = b.sim.ents[k]; if (!e.done && !e.rocketIn && !wasIn[k] && (e.x != before[k].first || e.z != before[k].second)) fprintf(dump, "%d %zu %.3f %.3f%c", f, k, e.x, e.z, 10); } if (getenv("HEAT") && f == atoi(getenv("HEAT")) && idx == atoi(getenv("HIDX"))) { for (int y = 0; y < 9; y++) { for (int x = 0; x < 12; x++) printf("%5d", b.sim.heat[y * 12 + x]); printf("%c", 10); } } }
        if (full) fclose(full); if (dump) fclose(dump);
        size_t m = 0; for (; m < want.size() && m < b.cpuPuts.size(); m++) { auto& a = b.cpuPuts[m]; auto& w = want[m]; if (a.frame != w.frame || a.player != w.player || a.x != w.x || a.y != w.y || a.dir != w.dir) break; }
        cases++; bool same = m == want.size() && b.cpuPuts.size() == want.size();
        if (same) ok++; else printf("MISMATCH stage %d seed %d levels %d%d%d%d: matched %zu of %zu (ours %zu)%s\n", idx, seed, l[0], l[1], l[2], l[3], m, want.size(), b.cpuPuts.size(),
            (m < want.size() && m < b.cpuPuts.size()) ? "" : "");
        if (!same && m < want.size() && m < b.cpuPuts.size()) printf("   want f%d p%d (%d,%d) d%d | got f%d p%d (%d,%d) d%d\n", want[m].frame, want[m].player, want[m].x, want[m].y, want[m].dir, b.cpuPuts[m].frame, b.cpuPuts[m].player, b.cpuPuts[m].x, b.cpuPuts[m].y, b.cpuPuts[m].dir);
    }
    printf("cpu golden cases: %d, identical: %d\n", cases, ok); return ok == cases ? 0 : 1;
}
