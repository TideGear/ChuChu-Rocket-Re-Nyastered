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
        int ret = -1; unsigned rb[4] = {0, 0, 0, 0};
        { char* r = strchr(s, '|'); if (r) { r++; sscanf(r, "%u %u %u %u", &rb[0], &rb[1], &rb[2], &rb[3]); r = strchr(r, '|'); if (r) { r++; for (int i = 0; i < 80; i++) { unsigned v; int u2; sscanf(r, "%u%n", &v, &u2); r += u2; e.arr[i] = (uint8_t)v; } r = strchr(r, '|'); if (r) { unsigned qn0; sscanf(r + 1, "%u", &qn0); e.qn = (uint8_t)qn0; r = strchr(r + 1, '|'); if (r) { r = strchr(r + 1, '|'); if (r) { r = strchr(r + 1, '|'); if (r) { r++; for (int i = 0; i < 12; i++) { unsigned v; int u2; sscanf(r, "%u%n", &v, &u2); r += u2; e.q[i / 4][i % 4] = (uint8_t)v; } } } } } } } }
        if (rule == "neighbour") gba::neighbourRule(e, p);
        else if (rule == "area") gba::areaRule(e, p);
        else if (rule == "follow") { e.target[p] = (int8_t)tg; if (tg >= 0 && tg != p) { e.curx[tg] = (uint8_t)(2 * tx + 2); e.cury[tg] = (uint8_t)(2 * ty + 2); } gba::followRule(e, p); }
        else if (rule == "path") { ret = gba::pathOk(e, a[0], a[1], a[2], a[3]) ? 1 : 0; cnt = (int)r0; e.qn = (uint8_t)r0; }
        else if (rule == "finish") { bool r1 = gba::finishRule(e, p); ret = r1 ? 1 : 0; cnt = e.qn; for (int i = 0; i < 4; i++) if (r1 && e.rec[p][i] != rb[i]) ret = 2; if (!r1 && (rb[0] | rb[1] | rb[2] | rb[3])) ret = 2; }
        else if (rule == "dirdelta") { ret = gba::dirFromDelta(e, a[0], a[1]); cnt = (int)r0; e.qn = (uint8_t)r0; }
        bool ok = e.qn == cnt && (rule != "neighbour" ? e.lcg == l1 : true); if (rule == "follow") { /* the target's cursor and stall timer are checked through the queue only */ } if (ret >= 0 && ret != (int)r0) ok = false; for (int i = 0; i < cnt && i < 3 && ok; i++) for (int j = 0; j < 3; j++) if (e.q[i][j] != q[i * 4 + j]) ok = false;
        n++; if (!ok) { bad++; if (bad <= 5) { printf("MISMATCH case %d player %d flags %02x phase %d cur %d,%d: port %d [", n, p, fl, ph, px, py, e.qn); for (int i = 0; i < e.qn; i++) printf("(%d %d %d)", e.q[i][0], e.q[i][1], e.q[i][2]); printf("] rom %d [", cnt); for (int i = 0; i < cnt; i++) printf("(%d %d %d)", q[i * 4], q[i * 4 + 1], q[i * 4 + 2]); printf("]\n"); } }
    }
    printf("gba cpu %s: %d cases, %d different\n", rule.c_str(), n, bad); return bad ? 1 : 0;
}
