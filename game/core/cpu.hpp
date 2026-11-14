// CPU player ("CT_" computer think) ported from the Android 1.15 original (FUN_00029fa8 and helpers, see analysis/asm/android_cpu.asm).
// A CPU player is a task that every second global frame either moves its cursor one cell towards a chosen target and puts an arrow there,
// or decides on a new target. Decisions are driven by the heat map built by SmpColAnalyze (Sim::heat) and by a private LCG.
#pragma once
#include "sim.hpp"
#include <cmath>
#include <cstdint>
#include <functional>
namespace ccr {

struct CpuEnv {                                       // what the AI reads and does in the host game
    Sim* sim = nullptr;
    int gameType = 0;                                 // GA_GetGameType: 0 = free-for-all battle, 1 = team battle
    int globalTime = 0;                               // TI_GetGlobalTime (0 in the verification harness)
    std::function<int(int)> rank;                     // score rank of a player (score array index 4+p)
    std::function<void(int, int, int, int)> putArrow; // CU_PutArrow: player, cursor x, cursor y, direction
    std::function<bool(int)> cursorFree;              // CU_CursorControlByParameter succeeds when the cursor is not locked
    int rocketX[5] = {0, 0, 0, 0, 0}, rocketY[5] = {0, 0, 0, 0, 0};   // entry 4 is read past the table by the original (zeros)   // RO_GetRocketFieldGrid
};

struct CpuLcg {                                       // FUN_00029cbc: shared by all CPU tasks, seeded with TI_GetGlobalTime in CT_StartCompThink
    uint32_t state = 0;
    float next() { state = state * 1103515245u + 12345u; return (float)((state << 1) >> 17) * (1.0f / 32768.0f); }
};

class CpuPlayer {
public:
    static constexpr uint32_t kLevelFlags[4] = {0x55, 0x56, 0x48, 0x2a};
    int player = 0; uint32_t flags = 0;
    int state = 0, timer = 0, cx = 0, cy = 0, tx = 0, ty = 0, dir = 0; uint16_t count = 0; int branch = 0;   // branch: which decision found the target (1 defend, 2 attack enemy rocket, 3 attack own rocket, 4 random), for tests
    void start(CpuEnv& env, int p, int level) {      // CT_StartCompThink (level 4 = chosen from time and player)
        player = p; if (level == 4) level = (env.globalTime + p) & 3;
        flags = level < 4 ? kLevelFlags[level] : 0; cx = env.rocketX[p]; cy = env.rocketY[p]; state = 0; timer = 0; count = 0;
    }
    void step(CpuEnv& env, CpuLcg& lcg) {             // FUN_00029fa8
        if (env.globalTime & 1) return;
        if (state != 0) {
            if (state == 1) {
                if (timer > 0x29) { state = 0; timer = 1; count++; return; }
                if (!env.cursorFree(player)) { timer++; count++; return; }
                if (moveCursor()) { env.putArrow(player, cx, cy, dir); state = 0; timer = 1; count++; return; }
                // the arrow is put at the cursor position, which is the target here
            }
            timer++; count++; return;
        }
        bool found = false;
        if ((flags & 2) || ((flags & 1) && lcg.next() < 0.005f)) { found = defendRocket(env); if (found) branch = 1; }
        if (!found) {
            bool b = (flags & 0x20) || ((flags & 0x10) && lcg.next() < 0.01f);
            if (b) { found = attack(env, true); if (found) branch = 2; }
            if (!found) {
                bool c = (flags & 8) || ((flags & 4) && lcg.next() < 0.1f);
                if (c) { found = attack(env, false); if (found) branch = 3; }
                if (!found) {
                    if ((flags & 0x40) && count > 200 && lcg.next() < 0.05f) { randomTarget(env, lcg); found = true; branch = 4; }
                    else { dir = 0x10; timer++; count++; return; }
                }
            }
        }
        count = 0; state = 1; timer = 1; count++;      // LAB_0002a1b6, then the common tail (timer = 1, count + 1)
    }
private:
    bool moveCursor() {                               // CT_MoveCursorToTargetPos: x first, one cell per call
        if (cx == tx && cy == ty) return true;
        if (cx != tx) { cx += cx < tx ? 1 : -1; return false; }
        cy += cy < ty ? 1 : -1; return false;
    }
    static bool objectFree(const Sim& s, int x, int y) { return (s.fieldCollision(x, y) & 0xf00) == 0; }
    bool defendRocket(CpuEnv& e) {                    // 0x2a0e4: put an arrow next to the own rocket where cats are (negative heat), pointing E, W, S, N
        const Sim& s = *e.sim; int rx = e.rocketX[player], ry = e.rocketY[player]; uint32_t f = s.fieldCollision(rx, ry);
        auto negHeat = [&](int x, int y) { return s.heat[y * kCols + x] < 0; };
        int x = rx + 1;
        if (!((f & kWallE) || x > 11) && objectFree(s, x, ry) && negHeat(x, ry)) { tx = x; ty = ry; dir = 3; return true; }
        x = rx - 1;
        if (!((f & kWallW) || x < 0) && objectFree(s, x, ry) && negHeat(x, ry)) { tx = x; ty = ry; dir = 1; return true; }
        int y = ry + 1;
        if (!(f & kWallS) && y < 9 && objectFree(s, rx, y) && negHeat(rx, y)) { tx = rx; ty = y; dir = 0; return true; }
        y = ry - 1;
        if (!(f & kWallN) && y >= 0 && objectFree(s, rx, y) && negHeat(rx, y)) { tx = rx; ty = y; dir = 2; return true; }
        return false;
    }
    bool attack(CpuEnv& e, bool enemy) {              // 0x2a1d6 (enemy rocket, most negative heat) / 0x2a02e (own rocket, most positive heat)
        const Sim& s = *e.sim; int owner = player; int cxr, cyr;
        if (enemy) {
            if (e.gameType == 0) {
                int want = e.rank(player) == 0 ? 1 : 0; owner = 4;
                for (int i = 0; i < 4; i++) if (e.rank(i) == want) { owner = i; break; }
            } else owner = (e.globalTime & 2) + ((player + 1) & 1);
        }
        cxr = e.rocketX[owner]; cyr = e.rocketY[owner];
        int best = 0, bx = 0, by = 0, bdir = 0; bool any = false;
        for (int dy = -4; dy <= 4; dy++) for (int dx = -4; dx <= 4; dx++) {
            int x = cxr + dx, y = cyr + dy;
            if (x < 0 || x >= kCols || y < 0 || y >= 9) continue;
            uint32_t f = s.fieldCollision(x, y); if (f & 0xf00) continue;
            int val = s.heat[y * kCols + x]; int d2 = dx * dx + dy * dy; if (d2 != 0) val = val / d2;
            if (enemy ? !(val < best) : !(val > best)) continue;
            float ang = atan2f((float)(-dx), (float)dy);
            int a = (int)((double)ang * 65536.0 / 6.283185307179586);   // matches the original's double arithmetic order
            int d = ((a + 0x8000) >> 14) & 3;
            if (((f & 0xf0000) >> 16 >> d) & 1) continue;
            if (!pathReaches(s, owner, x, y, d)) continue;
            best = val; bx = x; by = y; bdir = d; any = true;
        }
        if (!any) return false;
        tx = bx; ty = by; dir = bdir; return true;
    }
    bool randomTarget(CpuEnv& e, CpuLcg& lcg) {       // 0x2a290: up to 10 random cells (the last one is used even if none fits)
        const Sim& s = *e.sim; int x = 0, y = 0, d = 0;
        for (int i = 0; i < 10; i++) {
            x = (int)(lcg.next() * 11.88f); y = (int)(lcg.next() * 8.91f); d = (int)(lcg.next() * 3.99f);
            uint32_t f = s.fieldCollision(x, y);
            if ((f & 0xf00) == 0 && !(((f & 0xf0000) >> 16 >> (d & 0xff)) & 1) && s.heat[(y < 0 ? 0 : y) * kCols + x] != 0) break;
        }
        tx = x; ty = y; dir = d; return true;
    }
    // FUN_00029f44 / FUN_00029db0: does an arrow at (x,y) pointing d lead (depth 8) to the rocket of `owner`? (returns false when the original's f44 returns non-zero)
    static bool pathReaches(const Sim& s, int owner, int x, int y, int d) {
        static const int dx[4] = {0, -1, 0, 1}, dy[4] = {1, 0, -1, 0};
        uint8_t visited[kRows * kCols] = {};
        return walk(s, owner, x + dx[d], y + dy[d], d, 8, x, y, visited);
    }
    static bool walk(const Sim& s, int owner, int x, int y, int h, int depth, int ax, int ay, uint8_t* visited) {
        static const int dx[4] = {0, -1, 0, 1}, dy[4] = {1, 0, -1, 0};
        if (x >= 0 && x < kCols && y >= 0 && y < kRows) visited[y * kCols + x] = 1;
        uint32_t f = s.fieldCollision(x, y);
        if (f & kRocket) return s.rocketOwner[y][x] == owner;
        if (!(f & kHole) && depth > 0) {
            for (int k = 0; k < 4; k++) {
                if (((h + 2) & 3) == k || (f & kWallOfDir[k])) continue;
                if ((f & kArrow) && (int)(f & 3) != k) continue;
                int nx = x + dx[k], ny = y + dy[k];
                if (nx < 0) nx += kCols; else if (nx >= kCols) nx -= kCols;
                if (ny < 0) ny += kRows; else if (ny >= kRows) ny -= kRows;
                if (visited[ny * kCols + nx] == 0 && !(nx == ax && ny == ay))
                    if (walk(s, owner, nx, ny, k, depth - 1, ax, ay, visited)) return true;
            }
        }
        return false;
    }
};
} // namespace ccr
