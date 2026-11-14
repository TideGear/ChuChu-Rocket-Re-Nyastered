// Game Boy Advance CPU player, transcribed from the ROM's own routines (docs/gba_notes.md); each function is differential-tested against the original in tools/oracle/gba_cpu_gen.py.
#pragma once
#include <cstdint>
#include <cstring>
#include <utility>
#include <cstdio>
#include <cstdlib>
namespace gba {
struct Env {
    uint8_t field[567 + 2];            // wall/occupancy lattice, 27 bytes per row (one border cell); index = (2x+2) + 27*(2y+2) for the cell (x, y)
    int16_t heat[108];                 // 9 rows x 12 cells
    uint8_t curx[4], cury[4];          // cursor pixel positions ((v - 2) >> 1 = cell)
    uint8_t flags[4];                  // personality bit mask per player
    uint8_t phase = 0;                 // global phase counter
    uint8_t qn = 0; uint8_t q[3][4];   // candidate queue
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
        auto at = [&](int j, int xo, int yo) { (void)j; return e.f((xp + xo) + 27 * (yp + yo)); };
        static int o2 = getenv("O2") ? atoi(getenv("O2")) : 3, o3 = getenv("O3") ? atoi(getenv("O3")) : 0, o4 = getenv("O4") ? atoi(getenv("O4")) : 0, o5 = getenv("O5") ? atoi(getenv("O5")) : 0;
        if (at(0, kOff[2 * (k + 2)], kOff[2 * (k + 2) + 1])) continue;
        if (at(0, kOff[2 * (k + 1)], kOff[2 * (k + 1) + 1])) { e.push(A, B, kCand[k + o2]); continue; }
        if (at(0, 0, kOff[2 * k + 1])) { e.push(A, B, kCand[k + o3]); continue; }
        if (at(0, kOff[2 * k], kOff[2 * k + 1])) { e.push(A, B, kCand[k + o4]); continue; }
        e.push(A, B, kCand[k + o5 + (((e.phase >> 2) + p) & 1)]);
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
}
