// Game Boy Advance CPU player, transcribed from the ROM's own routines (docs/gba_notes.md); each function is differential-tested against the original in tools/oracle/gba_cpu_gen.py.
#pragma once
#include <cstdint>
#include <cstring>
#include <utility>
namespace gba {
struct Env {
    uint8_t field[567 + 2];            // wall/occupancy lattice, 27 bytes per row (one border cell); index = (2x+2) + 27*(2y+2) for the cell (x, y)
    int16_t heat[108];                 // 9 rows x 12 cells
    uint8_t curx[4], cury[4];          // cursor pixel positions ((v - 2) >> 1 = cell)
    uint8_t flags[4];                  // personality bit mask per player
    uint8_t phase = 0;                 // global phase counter
    uint8_t qn = 0; uint8_t q[3][4];   // candidate queue
    uint16_t stall[4] = {0, 0, 0, 0};  // record halfword +8: ticks without progress
    uint8_t stallCnt[4] = {0, 0, 0, 0};   // record byte +0xA
    int8_t target[4] = {-1, -1, -1, -1}; // record byte +2: the opponent being harassed (-1 none)
    uint8_t arr[80] = {0};             // 0x03002C10: per player 20 bytes: score halfword, +6 arrow count, then 4-byte arrow entries from +7 (direction) / +8, +9 (cursor pixel position)
    uint8_t rec[4][4] = {{0}};         // record bytes +0xC..+0xF: the chosen target cell and direction
    uint8_t ptype[12] = {0};           // 0x03002C90: CPU type per player (3 bytes each, 0 = human)
    uint8_t rank[4] = {0, 1, 2, 3}, order[4] = {0, 1, 2, 3};   // 0x03000508 / 0x0300050C
    int16_t scanv[2] = {0, 0}; uint8_t scanc[2][2] = {{0, 0}, {0, 0}};   // 0x03000500 / 0x03000502 best-cell values, 0x03000504-07 their cells
    int16_t seed[108] = {0}, tabA[108] = {0}, tabB[108] = {0};   // 0x03002DE0 seed, 0x03000350 and 0x03000428 working tables (heat is the table at 0x03000278)
    uint8_t spx[4] = {0}, spy[4] = {0}; uint16_t h8[4] = {0}, hc[4] = {0}, ha[4] = {0}, he[4] = {0}; uint8_t face[4] = {0}, c2cc4 = 0;   // CPU cursor sprite: pixel position (+0x1E/+0x1F), cell positions (+8/+0xC), screen position (+0xA/+0xE), facing (+0x18)
    uint8_t state[4] = {0}; uint16_t counter[4] = {0}; int16_t prevScore[4] = {0};       // task state (+0), thinking counter (+4), last score (+6)
    int nPlaced = 0; struct Placed { int p, x, y, dir; } placed[8];                       // arrows the CPUs placed this call
    struct Obj { uint16_t px, py; uint8_t type; }; Obj cats[32], mice[32]; int nCats = 0, nMice = 0;   // objects seen by the heat seeding (pixel positions +0xA/+0xE, type +0x1B)
    uint8_t mode = 0;                  // 0x03002990 game mode
    uint32_t lcg = 0;                  // the ROM's random generator state (0x030001F8)
    int rnd() { lcg = lcg * 1103515245u + 12345u; return (int)((lcg << 1) >> 17); }   // 0x080054F4: 15-bit result
    int cellX(int p) const { return (uint8_t)((curx[p] - 2) >> 1); }
    int cellY(int p) const { return (uint8_t)((cury[p] - 2) >> 1); }
    uint8_t f(int idx) const { return (idx < -1 || idx > 567) ? 0 : field[idx + 1]; }
    int16_t h(int x, int y) const { return heat[y * 12 + x]; }
    bool empty(int x, int y) const { int xi = ((x << 1) + 2) & 0xff, yi = ((y << 1) + 2) & 0xff; return (f(xi + 27 * yi) & 0xf0) == 0; }   // 0x08009464
    void push(int x, int y, int dir) { if (qn <= 2) { q[qn][0] = (uint8_t)x; q[qn][1] = (uint8_t)y; q[qn][2] = (uint8_t)dir; q[qn][3] = 0; qn++; } }   // 0x08009870
    static void wrap(int& x, int& y) { x = (int8_t)(uint8_t)x; y = (int8_t)(uint8_t)y; if (x < 0) x += 12; else if (x > 11) x -= 12; if (y < 0) y += 9; else if (y > 8) y -= 9; }   // 0x080090FC
};
static const int8_t kOff[16] = {1, 0, 0, 1, -1, 0, 0, -1, 1, 0, 0, 1, -1, 0, 1, -1};              // 0x080A9523
static const uint8_t kCand[8] = {0, 4, 8, 12, 0, 4, 8, 1};                                         // 0x080A951C
static const int8_t kDiag[14] = {1, -1, 1, 1, -1, 1, -1, -1, 1, -1, 1, 1, -1, 1};                  // 0x080A9531
static const uint8_t kDiagDir[7] = {12, 0, 4, 8, 12, 0, 4};                                        // 0x080A953F
static const uint8_t kStep[4][2] = {{1, 0}, {0, 1}, {255, 0}, {0, 255}};                           // 0x080A9548 (dx, dy)
static const uint8_t kStepDir[4] = {0, 4, 8, 12};                                                  // 0x080A9558

// 0x08009D60: neighbour rule
inline void neighbourRule(Env& e, int p) {
    int cx = (e.curx[p] - 2) >> 1 & 0xff, cy = (e.cury[p] - 2) >> 1 & 0xff;
    int thr = (int16_t)(0xffce + ((e.flags[p] & 2) ? 0x2e : 0));
    int16_t hv[4]; uint8_t ord[4];
    for (int k = 0; k < 4; k++) {
        int nx = (cx + kOff[2 * k]) & 0xff, ny = (int8_t)((cy + kOff[2 * k + 1]) & 0xff);
        hv[k] = (nx <= 11 && ny >= 0 && ny <= 8) ? e.h(nx, ny) : (int16_t)thr; ord[k] = (uint8_t)k;
    }
    for (int pass = 3; pass > 0; pass--) for (int j = 0; j < pass; j++) if (hv[j] > hv[j + 1]) { std::swap(hv[j], hv[j + 1]); std::swap(ord[j], ord[j + 1]); }
    for (int sl = 0; sl < 4 && hv[sl] < thr; sl++) {
        int k = ord[sl]; int A = (cx + kOff[2 * k]) & 0xff, B = (cy + kOff[2 * k + 1]) & 0xff;
        int xp = (2 * A + 2) & 0xff, yp = (2 * B + 2) & 0xff;
        auto at = [&](int d) { return e.f((xp + kOff[2 * d]) + 27 * (yp + kOff[2 * d + 1])); };   // lattice slot beside the neighbour cell in direction d
        if (at(k + 2)) continue;                                  // wall between the cursor and this neighbour
        if (at(k + 1)) { e.push(A, B, kCand[k + 3]); continue; }
        if (at(k)) { e.push(A, B, kCand[k]); continue; }
        if (at(k + 3)) { e.push(A, B, kCand[k + 3]); continue; }
        e.push(A, B, kCand[k + (((e.phase >> 2) + p) & 1)]);
    }
    if (e.qn > 2) return;
    int q = (cx > 5 ? 3 : 0); if (cy <= 3) q = (cx > 5) ? 2 : 1;
    for (int i = 0; i < 4; i++) {
        int m = i + q; int dx = kDiag[2 * m], dy = kDiag[2 * m + 1]; int A = (cx + dx) & 0xff, B = (cy + dy) & 0xff;
        if (A > 11 || (int8_t)B < 0 || (int8_t)B > 8) continue;
        if (!(e.h(A, (int8_t)B) < thr)) continue;
        if (!e.empty(A, B)) continue;
        int xp = (2 * A + 2) & 0xff, yp = (2 * B + 2) & 0xff;
        bool ok = e.f((xp - dx) + 27 * yp) == 0 || e.f(xp + 27 * (yp - dy)) == 0;
        if (ok) e.push(A, B, kDiagDir[m]);
    }
    if (e.qn > 2 || !(e.flags[p] & 2)) return;
    int lim = thr + (thr >> 1); int best = lim, bestk = 0;
    for (int k = 0; k < 4; k++) {
        int x = cx, y = cy; bool ok = true;
        for (int s = 0; s < 2 && ok; s++) {
            x += kStep[k][0]; y += kStep[k][1]; Env::wrap(x, y);
            int dxs = (int8_t)kStep[k][0], dys = (int8_t)kStep[k][1];
            if (e.f((2 * x + 2 - dxs) + 27 * (2 * y + 2 - dys)) != 0) ok = false;
            else if (!e.empty(x, y)) ok = false;
        }
        if (!ok) continue;
        int hh = e.h(x, y); if (best > hh) { best = hh; bestk = k; }
    }
    if (best < lim) {
        int x = cx + 2 * (int8_t)kStep[bestk][0], y = cy + 2 * (int8_t)kStep[bestk][1]; Env::wrap(x, y); e.push(x, y, kStepDir[bestk]);
    }
}

// 0x080098A0: arrow direction code (0, 4, 8, 12) pointing along the larger offset component; a diagonal draws one random bit
inline int dirFromDelta(Env& e, int dx, int dy) {
    static const uint8_t t[8] = {8, 12, 0, 4, 4, 8, 0, 12};
    dx = (int8_t)dx; dy = (int8_t)dy;
    if (dx == dy) return t[(dx >= 0 ? 0 : 2) + (e.rnd() & 1)];
    if (dx == -dy) return t[(dx >= 0 ? 4 : 6) + (e.rnd() & 1)];
    if (dx > dy) return dx < -dy ? 4 : 8;
    return dx >= -dy ? 12 : 0;
}
// 0x0800990C: walk from (x, y) one cell on in the arrow direction until the cursor's row or column is reached (1) or a wall / blocked cell stops it (0)
inline bool pathOk(Env& e, int p, int x, int y, int dir) {
    static const int8_t t[8] = {1, 0, 0, 1, -1, 0, 0, -1};
    int sl = e.cellX(p), sb = e.cellY(p); int tdx = t[(dir >> 1) & 7], tdy = t[((dir >> 1) & 7) + 1];
    int sx = (x + tdx) & 0xff, sy = (y + tdy) & 0xff;
    for (int guard = 0; guard < 64; guard++) {
        Env::wrap(sx, sy); sx &= 0xff; sy &= 0xff;
        int lx = (int8_t)((2 * sx + 2) & 0xff), ly = (int8_t)((2 * sy + 2) & 0xff);
        if (e.f((lx - tdx) + 27 * (ly - tdy)) != 0) return false;
        if ((tdx == 0 && sy == sb) || (tdy == 0 && sx == sl)) return true;
        if ((e.f(lx + 27 * ly) & 0xa0) != 0) return false;
        sx = (sx + tdx) & 0xff; sy = (sy + tdy) & 0xff;
    }
    return false;
}
// 0x0800A434: area search (only on the player's own turn)
inline void areaRule(Env& e, int p) {
    if ((e.phase & 3) != p) return;
    int cx = e.cellX(p), cy = e.cellY(p); int init = (e.flags[p] & 8) ? 0 : 3; int best = init; int bx = 0, by = 0, bd = 0;
    static const uint8_t decay[9] = {0, 0, 1, 2, 3, 4, 5, 5, 5};
    for (int dy = -6; dy <= 6; dy++) {
        int lim = 6 - (dy < 0 ? -dy : dy);
        for (int dx = -lim; dx <= lim; dx++) {
            int x = (cx + dx) & 0xff, y = (cy + dy) & 0xff;
            if (dx == 0 || dy == 0) { Env::wrap(x, y); x &= 0xff; y &= 0xff; }
            else if (x > 11 || (int8_t)y < 0 || (int8_t)y > 8) continue;
            int hv = e.h(x, (int8_t)y);
            if (!(hv > best)) continue;
            if (!e.empty(x, y)) continue;
            int d = (dx < 0 ? -dx : dx) + (dy < 0 ? -dy : dy); int sc = (int16_t)hv >> decay[d];
            if (!(sc > best)) continue;
            int dir = dirFromDelta(e, dx, dy);
            if (!pathOk(e, p, (int8_t)x, (int8_t)y, dir)) continue;
            bx = x; by = y; bd = dir; best = sc;
        }
    }
    if (best > init) e.push(bx, by, bd);
}

// 0x0800A654: follow the target opponent (flags & 0x30); looks at cells within distance 4 of the target's cursor
inline void followRule(Env& e, int p) {
    if ((e.phase & 3) != p) return;
    int t = e.target[p]; if (t == -1) return;
    int thr0 = (int16_t)(0xffc4 + ((e.flags[p] & 0x20) ? 0x35 : 0)); int best = thr0;
    int tcx = (int8_t)(((e.curx[t] - 2) << 23) >> 24), tcy = (int8_t)(((e.cury[t] - 2) >> 1) & 0xff);
    int bx = 0, by = 0, bd = 0;
    for (int dy = -4; dy <= 4; dy++) for (int dx = -4; dx <= 4; dx++) {
        int d = (dx < 0 ? -dx : dx) + (dy < 0 ? -dy : dy); if (d > 4) continue;
        int x = (tcx + dx) & 0xff, y = (tcy + dy) & 0xff;
        if (x > 11 || (int8_t)y < 0 || (int8_t)y > 8) continue;
        if (!e.empty(x, y)) continue;
        int hv = e.h(x, (int8_t)y); if (best <= hv) continue;
        int sh = d - 1; if (sh < 0) sh = 0; int sc = (int16_t)hv >> sh; if (best <= sc) continue;
        int dir = dirFromDelta(e, dx, dy);
        if (!pathOk(e, t, x, (int8_t)y, dir)) continue;
        bx = x; by = y; bd = dirFromDelta(e, dx, dy); best = sc;
    }
    if (best < thr0) { e.push(bx, by, bd); e.stall[p] = 480; }
}

// 0x0800AA1C: take the first queued candidate that does not duplicate one of the player's own live arrows (same cell and direction)
inline bool finishRule(Env& e, int p) {
    const uint8_t* a = e.arr + 20 * p; int n = a[6];
    for (int i = 0; i < e.qn; i++) {
        bool dup = false;
        for (int k = 0; k < n && !dup; k++) {
            int ex = (uint8_t)((a[8 + 4 * k] - 2) >> 1), ey = (uint8_t)((a[9 + 4 * k] - 2) >> 1);
            if (e.q[i][0] == ex && e.q[i][1] == ey && e.q[i][2] == a[7 + 4 * k]) dup = true;
        }
        if (!dup) { memcpy(e.rec[p], e.q[i], 4); return true; }
    }
    return false;
}

// 0x0800AAF4: choose the opponent to harass (record byte +2); 0xFF = none
inline void targetRule(Env& e, int p) {
    e.target[p] = -1;
    if (e.mode == 1 || e.mode == 6) { e.target[p] = (int8_t)((p + 1) & 3); return; }
    if (e.mode != 0) return;
    auto score = [&](int k) { return (int16_t)(e.arr[20 * k] | (e.arr[20 * k + 1] << 8)); };
    auto human = [&](int k) { return e.ptype[3 * k] == 0; };
    int rk = e.rank[p];
    int cand, lead;
    if (rk == 0 || rk == 3) { int t = e.order[rk == 0 ? 1 : 0]; if (human(t) && score(t) > 0) e.target[p] = (int8_t)t; return; }
    cand = e.order[rk == 1 ? 2 : 1]; lead = e.order[0];
    if (human(lead) && score(lead) > 0) { e.target[p] = (int8_t)lead; return; }
    if (human(cand) && score(cand) > 0) e.target[p] = (int8_t)cand;
}

static const int8_t kWalk[16] = {1, 0, 0, 0, 0, 1, 0, 0, -1, 0, 0, 0, 0, -1, 0, 0};   // 0x080A94FC and 0x080A950C: 4-byte entries (dx, dy, 0, 0)

// 0x08009B2C: direction code with the longest free run (up to 4 cells), ties broken by a random bit
inline int longestRun(Env& e, int x, int y) {
    int best = 0, bestk = 0;
    for (int k = 0; k < 4; k++) {
        int dx = kWalk[4 * k], dy = kWalk[4 * k + 1]; int sx = x & 0xff, sy = y & 0xff; int run = 0;
        while (true) {
            int lx = 2 * (int8_t)sx + 2 + dx, ly = 2 * (int8_t)sy + 2 + dy;
            if (e.f(lx + 27 * ly) != 0) break;
            sx = (sx + dx) & 0xff; sy = (sy + dy) & 0xff; Env::wrap(sx, sy); sx &= 0xff; sy &= 0xff;
            if (e.f((2 * (int8_t)sx + 2) + 27 * (2 * (int8_t)sy + 2)) & 0x80) break;
            run++; if (run > 3) break;
        }
        if (best < run) { best = run; bestk = k; }
        else if (best == run && (e.rnd() & 1) == 0) { best = run; bestk = k; }
    }
    return (bestk << 2) & 0xff;
}
// 0x08009C80: wall classifier: exactly one wall around the cell -> the direction code away from it, otherwise the longest run
inline int wallClass(Env& e, int x, int y) {
    int xp = (int8_t)((2 * (int8_t)x + 2) & 0xff), yp = (int8_t)((2 * (int8_t)y + 2) & 0xff); int cnt = 0, dir = 0;
    if (e.f(xp - 1 + 27 * yp) != 0) cnt = 1;
    if (e.f(xp + 1 + 27 * yp) != 0) { cnt++; dir = 8; }
    if (e.f(xp + 27 * (yp - 1)) != 0) { cnt++; dir = 4; }
    if (e.f(xp + 27 * (yp + 1)) != 0) { cnt++; dir = 12; }
    if (cnt == 1) return dir;
    return longestRun(e, x, y);
}
// 0x08009A20: from a random start direction, the first direction whose neighbour cell has no wall behind it and no wall flag (0x80)
inline int randomWalk(Env& e, int x, int y) {
    int start = e.rnd() & 3, d = start;
    for (int i = 0; i < 4; i++, d = (d + 1) & 3) {
        int dx = kWalk[4 * d], dy = kWalk[4 * d + 1]; int nx = ((int8_t)x + dx) & 0xff, ny = ((int8_t)y + dy) & 0xff; Env::wrap(nx, ny); nx &= 0xff; ny &= 0xff;
        int xp = 2 * (int8_t)nx + 2, yp = 2 * (int8_t)ny + 2;
        if (e.f((xp - dx) + 27 * (yp - dy)) != 0) continue;
        if ((e.f(xp + 27 * yp) & 0x80) == 0) return d * 4;
    }
    return start * 4;
}

// 0x0800A854: the "stuck" rule: a random cell with heat, plus the scan's best cells, one picked at random with a random arrow direction
inline void specialRule(Env& e, int p) {
    (void)p; uint8_t lx[16], ly[16]; int n = 0; int x = 0, y = 0;
    for (int t = 0; t <= 7; t++) {
        x = (e.rnd() * 3) >> 13; y = (e.rnd() * 9) >> 15;
        if (e.h(x, y) != 0 && e.empty(x, y)) break;
    }
    lx[n] = (uint8_t)x; ly[n++] = (uint8_t)y;
    if (e.scanv[0] > 0 && e.empty(e.scanc[0][0], e.scanc[0][1])) { lx[n] = e.scanc[0][0]; ly[n++] = e.scanc[0][1]; }
    if (e.scanv[1] < 0 && e.empty(e.scanc[1][0], e.scanc[1][1])) { lx[n] = e.scanc[1][0]; ly[n++] = e.scanc[1][1]; }
    int sel = (n * e.rnd()) >> 15; int cx = lx[sel], cy = ly[sel];
    int dir = (e.rnd() & 1) ? randomWalk(e, (int8_t)cx, (int8_t)cy) : wallClass(e, (int8_t)cx, (int8_t)cy);
    e.push(cx, cy, dir);
}

// 0x0800AC1C: one thinking step: choose the target, run the rules the personality allows, return whether an arrow was chosen
inline bool think(Env& e, int p) {
    targetRule(e, p); e.qn = 0; int fl = e.flags[p];
    if ((fl & 0x40) && e.stall[p] > 0x257) {
        specialRule(e, p);
        if (e.qn <= 2 && (fl & 0xc)) areaRule(e, p);
        e.stallCnt[p]++;
        if (e.stallCnt[p] > 2) { e.stall[p] = 0; e.stallCnt[p] = 0; } else e.stall[p] = 0x21c;
    } else {
        if (e.qn <= 2) {
            if (fl & 3) neighbourRule(e, p);
            if (e.qn <= 2 && (fl & 0xc)) areaRule(e, p);
        }
    }
    if (e.qn <= 2 && (fl & 0x30)) followRule(e, p);
    return finishRule(e, p);
}

// 0x080091C4: one diffusion pass over the quadrant selected by phase & 0xC: each cell = own value + (open, unblocked neighbours' values >> 3)
inline void diffuse(Env& e, const int16_t* src, int16_t* dst) {
    static const uint8_t rects[16] = {0, 6, 0, 4, 6, 12, 0, 4, 0, 6, 4, 9, 6, 12, 4, 9};
    const uint8_t* r = rects + (e.phase & 0xc); int x0 = r[0], x1 = r[1], y0 = r[2], y1 = r[3];
    for (int y = y0; y < y1; y++) for (int x = x0; x < x1; x++) {
        int xp = 2 * x + 2, yp = 2 * y + 2; uint16_t sum = (uint16_t)src[y * 12 + x];
        int nx = x + 1 > 11 ? 0 : x + 1;
        if (e.f(xp + 1 + 27 * yp) == 0 && (e.f((2 * nx + 2) + 27 * yp) & 0xa0) == 0) sum = (uint16_t)(sum + (src[y * 12 + nx] >> 3));
        nx = x - 1 < 0 ? 11 : x - 1;
        if (e.f(xp - 1 + 27 * yp) == 0 && (e.f((2 * nx + 2) + 27 * yp) & 0xa0) == 0) sum = (uint16_t)(sum + (src[y * 12 + nx] >> 3));
        int ny = y + 1 > 8 ? 0 : y + 1;
        if (e.f(xp + 27 * (yp + 1)) == 0 && (e.f(xp + 27 * (2 * ny + 2)) & 0xa0) == 0) sum = (uint16_t)(sum + (src[ny * 12 + x] >> 3));
        ny = y - 1 < 0 ? 8 : y - 1;
        if (e.f(xp + 27 * (yp - 1)) == 0 && (e.f(xp + 27 * (2 * ny + 2)) & 0xa0) == 0) sum = (uint16_t)(sum + (src[ny * 12 + x] >> 3));
        dst[y * 12 + x] = (int16_t)sum;
    }
}
// 0x080094A0: best (largest, smallest) heat among empty cells; scan runs y 8..0, x 11..0 and keeps the first of equal values
inline void scanHeat(Env& e) {
    e.scanv[0] = e.scanv[1] = 0; e.scanc[0][0] = e.scanc[0][1] = e.scanc[1][0] = e.scanc[1][1] = 0;
    for (int y = 8; y >= 0; y--) for (int x = 11; x >= 0; x--) {
        int hv = e.heat[y * 12 + x]; if (hv == 0 || !e.empty(x, y)) continue;
        if (e.scanv[0] < hv) { e.scanv[0] = (int16_t)hv; e.scanc[0][0] = (uint8_t)x; e.scanc[0][1] = (uint8_t)y; }
        else if (e.scanv[1] > hv) { e.scanv[1] = (int16_t)hv; e.scanc[1][0] = (uint8_t)x; e.scanc[1][1] = (uint8_t)y; }
    }
}
// 0x08009568: the per-frame diffusion step (phase & 3 picks the stage)
inline void heatStep(Env& e) {
    switch (e.phase & 3) {
        case 0: diffuse(e, e.seed, e.tabA); break;
        case 1: diffuse(e, e.tabA, e.tabB); break;
        case 2: diffuse(e, e.tabB, e.tabA); break;
        default: diffuse(e, e.tabA, e.heat); scanHeat(e); break;
    }
}

// 0x08009748: has the cursor reached the target cell?
inline bool atTarget(const Env& e, int p) { return (int)((e.h8[p] - 2) >> 1) == e.rec[p][0] && (int)((e.hc[p] - 2) >> 1) == e.rec[p][1]; }
// 0x0800977C + 0x080097D0: move the cursor sprite 2 px per call toward the target cell centre and refresh the cell and screen positions
inline void moveCursor(Env& e, int p) {
    int tx = (uint8_t)(e.rec[p][0] * 16 + 8), ty = (uint8_t)(e.rec[p][1] * 16 + 8);
    if (e.spx[p] < tx) e.spx[p] += 2; else if (e.spx[p] > tx) e.spx[p] -= 2;
    if (e.spy[p] < ty) e.spy[p] += 2; else if (e.spy[p] > ty) e.spy[p] -= 2;
    e.ha[p] = (uint16_t)(e.spx[p] + 0x29); e.he[p] = (uint16_t)(e.spy[p] + 3);
    e.face[p] = (e.c2cc4 == 0xb || (int16_t)e.he[p] > 0x80) ? 4 : 8;
    e.h8[p] = (uint16_t)(((e.spx[p] >> 3) & 0xfe) + 2); e.hc[p] = (uint16_t)(((e.spy[p] >> 3) & 0xfe) + 2);
}
// 0x08009810: at target -> 1; otherwise move and test again
inline bool moveTo(Env& e, int p) { if (atTarget(e, p)) return true; moveCursor(e, p); return atTarget(e, p); }
// 0x0800ACE8: the per-CPU task: think, travel, place
inline void cpuTask(Env& e, int p) {
    if (e.state[p] == 0) {
        e.counter[p]++;
        if (think(e, p)) { e.counter[p] = 0; e.state[p] = 1; }
        else if (e.counter[p] > 10) { e.rec[p][0] = (uint8_t)((e.curx[p] - 2) >> 1); e.rec[p][1] = (uint8_t)((e.cury[p] - 2) >> 1); moveTo(e, p); }
    } else if (e.state[p] == 1) {
        if (moveTo(e, p)) {
            if (e.empty(e.rec[p][0], e.rec[p][1]) && e.nPlaced < 8) e.placed[e.nPlaced++] = {p, e.rec[p][0], e.rec[p][1], e.rec[p][2]};   // 0x08009844 -> arrow primitive 0x08004EF0
            e.state[p] = 0;
        }
    }
    int sc = (int16_t)(e.arr[20 * p] | (e.arr[20 * p + 1] << 8));
    if (sc < e.prevScore[p]) e.stall[p] = (uint16_t)(e.stall[p] + 0x78); else if (sc == e.prevScore[p]) e.stall[p] = (uint16_t)(e.stall[p] + 1); else e.stall[p] = 0;
    e.prevScore[p] = (int16_t)sc;
}

// 0x080095D8: rank the four players by score (descending bubble sort; the rank array is only rewritten on swaps, as in the ROM)
inline void sortScores(Env& e) {
    int16_t sc[4]; for (int i = 0; i < 4; i++) { sc[i] = (int16_t)(e.arr[20 * i] | (e.arr[20 * i + 1] << 8)); e.order[i] = (uint8_t)i; }
    for (int top = 3; top > 0; top--) for (int j = 0; j < top; j++) {
        int k = j + 1;
        if (sc[j] < sc[k]) { int16_t t = sc[j]; sc[j] = sc[k]; sc[k] = t; uint8_t oj = e.order[j], ok = e.order[k]; e.order[k] = oj; e.rank[oj] = (uint8_t)k; e.order[j] = ok; e.rank[ok] = (uint8_t)j; }
    }
}
// 0x08008FDC: per frame: seed the heat (cats -100, mice + weight by type) and run the global step (diffusion stage, score sort, phase counter)
inline void frameStep(Env& e) {
    if (e.mode > 1 && e.mode != 6) return;
    memset(e.seed, 0, sizeof e.seed);
    for (int i = 0; i < e.nCats; i++) { int cx = (int)(((int)(int16_t)e.cats[i].px - 0x28) >> 4) & 0xff, cy = (int)(((int)(int16_t)e.cats[i].py - 2) >> 4) & 0xff; if (cx <= 11 && cy <= 8) e.seed[cy * 12 + cx] = (int16_t)(e.seed[cy * 12 + cx] - 100); }
    static const int16_t w[4] = {1, 50, 25, 25};
    for (int i = 0; i < e.nMice; i++) { int cx = (int)(((int)(int16_t)e.mice[i].px - 0x28) >> 4) & 0xff, cy = (int)(((int)(int16_t)e.mice[i].py - 2) >> 4) & 0xff; if (cx <= 11 && cy <= 8) e.seed[cy * 12 + cx] = (int16_t)(e.seed[cy * 12 + cx] + w[e.mice[i].type & 3]); }
    heatStep(e); sortScores(e); e.phase++;
}
}
