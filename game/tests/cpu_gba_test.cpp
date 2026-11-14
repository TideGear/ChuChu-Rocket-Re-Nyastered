// Differential test of the GBA CPU rules against the ROM's own code (cases from tools/oracle/gba_cpu_gen.py). usage: cpu_gba_test <rule> <cases.txt>
#include "../core/cpu_gba.hpp"
#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>
int main(int argc, char** argv) {
    std::string rule = argc > 1 ? argv[1] : "neighbour"; FILE* f = fopen(argc > 2 ? argv[2] : "../local/testdata/gba_nbr.txt", "r"); if (!f) { printf("cannot open cases\n"); return 2; }
    static char buf[1 << 16]; int n = 0, bad = 0;
    while (fgets(buf, sizeof buf, f)) {
        gba::Env e; memset(&e, 0, sizeof e); char* s = buf; int p, fl, ph, mode, px, py, tx, ty, tg; int used = 0;
        if (sscanf(s, "%d %d %d %d %d %d %d %d %d |%n", &p, &fl, &ph, &mode, &px, &py, &tx, &ty, &tg, &used) < 9) continue; s += used;
        for (int i = 0; i < 108; i++) { int v, u; sscanf(s, "%d%n", &v, &u); e.heat[i] = (int16_t)v; s += u; }
        s = strchr(s, '|') + 1; while (*s == ' ') s++;
        for (int i = 0; i < 567; i++) { unsigned v; sscanf(s, "%2x", &v); e.field[i + 1] = (uint8_t)v; s += 2; }
        s = strchr(s, '|') + 1; int cnt = 0, u; sscanf(s, "%d%n", &cnt, &u); s += u; int q[12]; for (int i = 0; i < 12; i++) { sscanf(s, "%d%n", &q[i], &u); s += u; }
        for (int k = 0; k < 4; k++) { e.curx[k] = 2; e.cury[k] = 2; } e.curx[p] = (uint8_t)px; e.cury[p] = (uint8_t)py; e.flags[p] = (uint8_t)fl; e.phase = (uint8_t)ph;
        s = strchr(s, '|') + 1; unsigned r0 = 0, l0 = 0, l1 = 0; int a[4] = {0, 0, 0, 0}; sscanf(s, "%u %u %u %d %d %d %d", &r0, &l0, &l1, &a[0], &a[1], &a[2], &a[3]); e.lcg = l0;
        std::vector<unsigned> taskOut, taskIn, tabs, sIn, aIn, bIn, scn;
        int ret = -1; unsigned rb[4] = {0, 0, 0, 0}, rec2 = 0, rs8 = 0, rsc = 0;
        { std::vector<std::string> fld; { std::string cur; for (char* c = s; *c; c++) { if (*c == '|') { fld.push_back(cur); cur.clear(); } else cur += *c; } fld.push_back(cur); }
          auto nums = [](const std::string& str) { std::vector<unsigned> v; const char* c = str.c_str(); char* end; while (true) { unsigned long x = strtoul(c, &end, 10); if (end == c) break; v.push_back((unsigned)x); c = end; } return v; };
          if (fld.size() >= 6) { auto v = nums(fld[1]); for (int i = 0; i < 4 && i < (int)v.size(); i++) rb[i] = v[i]; v = nums(fld[2]); for (int i = 0; i < 80 && i < (int)v.size(); i++) e.arr[i] = (uint8_t)v[i];
            v = nums(fld[3]); if (v.size() >= 2) { e.qn = (uint8_t)v[0]; e.mode = (uint8_t)v[1]; } if (v.size() >= 8) { e.scanv[0] = (int16_t)(int)v[2]; e.scanv[1] = (int16_t)(int)v[3]; e.scanc[0][0] = (uint8_t)v[4]; e.scanc[0][1] = (uint8_t)v[5]; e.scanc[1][0] = (uint8_t)v[6]; e.scanc[1][1] = (uint8_t)v[7]; } v = nums(fld[4]); for (int i = 0; i < 4 && i < (int)v.size(); i++) e.rank[i] = (uint8_t)v[i], e.order[i] = (uint8_t)v[4 + i];
            v = nums(fld[5]); for (int i = 0; i < 12 && i < (int)v.size(); i++) e.ptype[i] = (uint8_t)v[i]; v = nums(fld[6]); for (int i = 0; i < 12 && i < (int)v.size(); i++) e.q[i / 4][i % 4] = (uint8_t)v[i]; v = nums(fld[7]); if (v.size() >= 3) { rec2 = v[0]; rs8 = v[1]; rsc = v[2]; } v = nums(fld[8]); if (v.size() >= 2) { e.stall[p] = (uint16_t)v[0]; e.stallCnt[p] = (uint8_t)v[1]; } if (fld.size() > 9) { v = nums(fld[9]); for (int i = 0; i < 4 && 2 * i + 1 < (int)v.size(); i++) { e.curx[i] = (uint8_t)v[2 * i]; e.cury[i] = (uint8_t)v[2 * i + 1]; } } if (fld.size() > 16) { taskOut = nums(fld[15]); taskIn = nums(fld[16]); } if (fld.size() > 14) { tabs = nums(fld[10]); sIn = nums(fld[11]); aIn = nums(fld[12]); bIn = nums(fld[13]); scn = nums(fld[14]); } } }
        if (rule == "neighbour") gba::neighbourRule(e, p);
        else if (rule == "area") gba::areaRule(e, p);
        else if (rule == "follow") { e.target[p] = (int8_t)tg; if (tg >= 0 && tg != p) { e.curx[tg] = (uint8_t)(2 * tx + 2); e.cury[tg] = (uint8_t)(2 * ty + 2); } gba::followRule(e, p); }
        else if (rule == "path") { ret = gba::pathOk(e, a[0], a[1], a[2], a[3]) ? 1 : 0; cnt = (int)r0; e.qn = (uint8_t)r0; }
        else if (rule == "target") { /* mode, ranks, order and types come from the extras below */ gba::targetRule(e, p); ret = e.target[p] & 0xff; r0 = rec2; cnt = e.qn; }
        else if (rule == "longest" || rule == "wallclass" || rule == "walk") { int x = (int8_t)a[0], y = (int8_t)a[1]; ret = rule == "longest" ? gba::longestRun(e, x, y) : rule == "wallclass" ? gba::wallClass(e, x, y) : gba::randomWalk(e, x, y); cnt = (int)r0; e.qn = (uint8_t)r0; }
        else if (rule == "think") { e.qn = 0; bool r1 = gba::think(e, p); ret = r1 ? 1 : 0; cnt = e.qn; for (int i = 0; i < 3; i++) if (r1 && e.rec[p][i] != rb[i]) ret = 2; if (!r1 && (rb[0] | rb[1] | rb[2])) ret = 2; if (e.stall[p] != rs8 || e.stallCnt[p] != rsc || (e.target[p] & 0xff) != rec2) ret = 2; }
        else if (rule == "heatstep") {
            for (int i = 0; i < 108; i++) { e.seed[i] = (int16_t)(int)sIn[i]; e.tabA[i] = (int16_t)(int)aIn[i]; e.tabB[i] = (int16_t)(int)bIn[i]; }
            gba::heatStep(e); ret = 1; r0 = 1; cnt = e.qn;
            for (int i = 0; i < 108; i++) if (e.tabA[i] != (int16_t)(int)tabs[i] || e.tabB[i] != (int16_t)(int)tabs[108 + i] || e.heat[i] != (int16_t)(int)tabs[216 + i]) ret = 2;
            if ((e.phase & 3) == 3) { if (e.scanv[0] != (int16_t)(scn[0] | (scn[1] << 8)) || e.scanv[1] != (int16_t)(scn[2] | (scn[3] << 8)) || e.scanc[0][0] != scn[4] || e.scanc[0][1] != scn[5] || e.scanc[1][0] != scn[6] || e.scanc[1][1] != scn[7]) ret = 3; } }
        else if (rule == "task") {
            e.spx[p] = (uint8_t)taskIn[0]; e.spy[p] = (uint8_t)taskIn[1]; e.c2cc4 = (uint8_t)taskIn[2]; e.state[p] = (uint8_t)taskIn[3]; e.counter[p] = (uint16_t)taskIn[4]; e.prevScore[p] = (int16_t)(int)taskIn[5];
            e.rec[p][0] = (uint8_t)taskIn[6]; e.rec[p][1] = (uint8_t)taskIn[7]; e.rec[p][2] = (uint8_t)taskIn[8]; e.h8[p] = (uint16_t)taskIn[9]; e.hc[p] = (uint16_t)taskIn[10]; e.nPlaced = 0; e.qn = 0;
            gba::cpuTask(e, p); ret = 1; r0 = 1; cnt = e.qn;
            const std::vector<unsigned>& o = taskOut; int np = (int)o[14];
            bool same = e.state[p] == o[0] && e.counter[p] == o[1] && (int16_t)e.prevScore[p] == (int16_t)(int)o[2] && e.stall[p] == o[3] && e.rec[p][0] == o[4] && e.rec[p][1] == o[5] && e.rec[p][2] == o[6] && e.spx[p] == o[7] && e.spy[p] == o[8] && e.h8[p] == o[9] && e.hc[p] == o[10] && np == e.nPlaced;
            if (same && (e.ha[p] != o[11] || e.he[p] != o[12] || e.face[p] != o[13])) same = false;
            for (int i = 0; same && i < np; i++) if (e.placed[i].dir != (int)o[15 + 3 * i] || e.placed[i].x != (int)(((o[16 + 3 * i]) - 2) >> 1) || e.placed[i].y != (int)(((o[17 + 3 * i]) - 2) >> 1)) same = false;
            if (!same) { ret = 2; static int shown = 0; if (shown++ < 3) printf("task: in %u %u c4 %u st %u cnt %u prev %d t %u %u %u | port st %d cnt %d prev %d stall %d t %d %d %d sp %d %d h %d %d np %d | rom st %u cnt %u prev %d stall %u t %u %u %u sp %u %u h %u %u ha %u he %u np %u\n", taskIn[0], taskIn[1], taskIn[2], taskIn[3], taskIn[4], (int)taskIn[5], taskIn[6], taskIn[7], taskIn[8], e.state[p], e.counter[p], e.prevScore[p], e.stall[p], e.rec[p][0], e.rec[p][1], e.rec[p][2], e.spx[p], e.spy[p], e.h8[p], e.hc[p], e.nPlaced, o[0], o[1], (int)o[2], o[3], o[4], o[5], o[6], o[7], o[8], o[9], o[10], o[11], o[12], o[14]); } }
        else if (rule == "special") { e.qn = 0; gba::specialRule(e, p); }
        else if (rule == "finish") { bool r1 = gba::finishRule(e, p); ret = r1 ? 1 : 0; cnt = e.qn; for (int i = 0; i < 3; i++) if (r1 && e.rec[p][i] != rb[i]) ret = 2; if (!r1 && (rb[0] | rb[1] | rb[2])) ret = 2; }
        else if (rule == "dirdelta") { ret = gba::dirFromDelta(e, a[0], a[1]); cnt = (int)r0; e.qn = (uint8_t)r0; }
        bool ok = e.qn == cnt && (rule != "neighbour" ? e.lcg == l1 : true); if (rule == "follow") { /* the target's cursor and stall timer are checked through the queue only */ } if (ret >= 0 && ret != (int)r0) ok = false; for (int i = 0; i < cnt && i < 3 && ok; i++) for (int j = 0; j < 3; j++) if (e.q[i][j] != q[i * 4 + j]) ok = false;
        n++; if (!ok) { bad++; if (bad <= 5) { printf("MISMATCH case %d player %d flags %02x phase %d cur %d,%d lcg %d stall %u/%u cnt %u/%u tgt %d/%u ret %d r0 %u: port %d [", n, p, fl, ph, px, py, e.lcg == l1, e.stall[p], rs8, e.stallCnt[p], rsc, e.target[p], rec2, ret, r0, e.qn); for (int i = 0; i < e.qn; i++) printf("(%d %d %d)", e.q[i][0], e.q[i][1], e.q[i][2]); printf("] rom %d [", cnt); for (int i = 0; i < cnt; i++) printf("(%d %d %d)", q[i * 4], q[i * 4 + 1], q[i * 4 + 2]); printf("]\n"); } }
    }
    printf("gba cpu %s: %d cases, %d different\n", rule.c_str(), n, bad); return bad ? 1 : 0;
}
