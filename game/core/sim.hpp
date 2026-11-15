// ChuChu Rocket! Re-Nyastered - simulation core (puzzle rules).
// Rules reverse-engineered from the original mobile builds; see docs/rules_*.md.
// Units: world units (1 cell = 15.0), one tick = one original logic step (60 Hz). float32 like the original.
#pragma once
#include "angle.hpp"
#include "mouse_ghost.hpp"
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <vector>
#include <functional>
#include <cstdio>
#include <cstring>

namespace ccr {

constexpr int kCols = 12, kRows = 9;
constexpr float kCell = 15.0f;
constexpr uint32_t kRocketStepBits = 0xbd088889u;   // -1/30 as stored in the original (Android 0x293c0)
enum Dir : int { South = 0, West = 1, North = 2, East = 3 };   // heading+1 = turn right (clockwise)

// Collision word bits (original FI_GetFieldCollision layout).
constexpr uint32_t kWallS = 0x10000, kWallW = 0x20000, kWallN = 0x40000, kWallE = 0x80000, kWallAny = 0xf0000;
constexpr uint32_t kRocket = 0x100, kHole = 0x400, kArrow = 0x800, kGenerator = 0x200;   // generator cells carry 0x200 | heading (measured)
constexpr uint32_t kWallOfDir[4] = {kWallS, kWallW, kWallN, kWallE};

enum Tile : uint8_t { T_Floor = 0, T_Rocket = 1, T_MouseS = 9, T_CatS = 13, T_Hole = 17 };

struct Stage {
    uint8_t tiles[kCols * kRows];
    uint8_t hw[10 * kCols];     // horizontal wall edge above row r (r=0..9), column c
    uint8_t vw[kRows * 13];     // vertical wall edge left of column c (c=0..12), row r
};

struct Arrow { int x, y, dir, hits; bool live; int owner = 0, ttl = -1; };   // ttl: frames left (battle), -1 = no expiry

struct Entity {
    bool mouse = true, alive = true, done = false, hit = false;   // hit: contact flag set by the collision pass, consumed at the start of the next tick
    float x = 0, z = 0;
    bool rocketIn = false; float rocketCounter = 1.0f;   // battle cat inside a rocket (30-tick animation, then respawn at a random generator)
    bool reg = false;
    bool fresh = false;         // spawned before this tick's entity pass: first moves next tick, no contact this tick
    int slot = -1;              // task-pool slot (the collision entry stores the task pointer: a reused slot is read through the new occupant)
              // registered a collision entry this tick (SmpColColliEntry): only these feed the AI heat map
    int type = 0;               // battle mouse type: 0 normal, 1 golden (50 points), 2 roulette
    int heading = 0;            // Dir
    int gx = 0, gy = 0;         // clamped grid cell
    bool jime = false; int angle = 0;   // Mouse Monopoly (MO_MouseJimeExe): the mouse flies toward the roller's rocket; angle = the task's +0x24 heading angle (16-bit circle)
};

// Events produced in battle mode (consumed by BattleGame).
struct Event { enum Kind { MouseRocket, CatRocket, MouseEaten, MouseHole, MouseGone } kind; int player; int type; int slot = -1; };   // slot: pool slot of the task that raised it

struct Result { int mice = 0, saved = 0, killed = 0, cats = 0; bool stuck = false; int ticks = 0; int byCat = 0, byHole = 0, catRocket = 0, broken = 0; };

class Sim {
public:
    float mouseSpeed = 1.5f, catSpeed = 1.0f;
    std::vector<int> endTicks;                    // tick of every mouse removal (saved, eaten, fell): for comparisons with other versions
    std::vector<int> saveTicks;                   // tick of every save (for differential tests)
    int breakAt = 2;                              // experiment: strikes that destroy an arrow
    bool trace = false; int now = 0;
    int order = 0;                                // experiment: 0 spawn order, 1 cats first, 2 mice first
    int catRot = 0;                               // experiment: rotate cat start headings
    float eatRadius = 7.5f;                       // cat-mouse contact distance (original compares against 5.0 in SmpColAnalyze)     // GA_GetMouseSpeed / GA_GetCatSpeed defaults
    bool battle = false;                          // battle stage coding: tiles 1..4 rockets (owner = code-1), 5..8 generators
    struct Gen { int x, y, dir; };
    std::vector<Gen> gens;
    std::vector<Event> events;
    // Task pool model (SmpTsk, 1024 slots): content[s] = entity index, -2 = a non-entity task (zero fields), -1 = never used.
    int content[1024]; bool freeSlot_[1024];
    void resetPool() { for (int i = 0; i < 1024; i++) { content[i] = -1; freeSlot_[i] = true; } }
    int allocSlot(int code) {                              // SmpTskEntry: first free slot (dead entities' slots count as free)
        for (int i = 0; i < 1024; i++) {
            if (freeSlot_[i]) { freeSlot_[i] = false; content[i] = code; return i; }
        }
        return -1;
    }
    void releaseSlot(int s) { if (s >= 0) freeSlot_[s] = true; }
    // Deferred task deletion (original: eaten mouse -> state 0x354f8 runs next tick, creates a 48-tick effect task (if < 12 alive) then deletes the mouse;
    // mouse in rocket -> 0x35488 runs next tick and deletes). Slots matter because collision entries keep task pointers.
    struct PendingFree { int ent, when; bool effect; };
    std::vector<PendingFree> pendingFree;
    std::vector<MouseGhost> effects;
    bool poolModel = false;                                                              // battle mode only
    void scheduleFree(size_t ent, int when, bool effect) { if (poolModel) pendingFree.push_back({(int)ent, when, effect}); }
    void poolTick() {
        for (auto& e : effects) e.tick();
        for (size_t i = 0; i < effects.size();) { if (effects[i].age >= 48) { releaseSlot(effects[i].slot); effects.erase(effects.begin() + i); } else i++; }
        for (size_t i = 0; i < pendingFree.size();) {
            PendingFree& p = pendingFree[i];
            if (p.when <= now) {
                if (p.effect && effects.size() < 12) {
                    const int slot = allocSlot(-2);
                    const auto& mouse = ents[p.ent];
                    if (slot >= 0) effects.push_back({slot, ents.size(), mouse.x, mouse.z, mouse.heading << 14});
                }
                releaseSlot(ents[p.ent].slot); pendingFree.erase(pendingFree.begin() + i);
            } else i++;
        }
    }
    void occupyBase(int n) { for (int i = 0; i < n; i++) allocSlot(-2); }
    int16_t heat[kRows * kCols] = {};             // SmpColAnalyze danger/value map used by the CPU players (cat -100 spread, mouse value)
    std::function<float()> rnd;                   // njRandom (battle): cat respawn picks generator floor(n*0.99*r)
    uint8_t rocketOwner[kRows][kCols] = {};
    int rocketPos[4][2] = {};                     // battle: rocket cell of each player (RO_GetRocketFieldGrid)
    int spdSlot = -1; float spdMouse = 0, spdCat = 0;   // pending mid-frame speed change (see tick)
    int monopoly = -1;                 // MO_StartHitorijime(player) / -1: the global read by MO_MouseExe's tail and MO_MouseJimeExe
    std::vector<Entity> ents;
    std::vector<Arrow> arrows;
    uint32_t coll[kRows][kCols];
    int saved = 0, killed = 0, killedByCat = 0, killedByHole = 0, catsInRocket = 0, arrowsBroken = 0;

    void load(const Stage& s) {
        ents.clear(); endTicks.clear(); resetPool(); pendingFree.clear(); effects.clear(); poolModel = battle; arrows.clear(); gens.clear(); events.clear(); saveTicks.clear(); now = 0; saved = killed = killedByCat = killedByHole = catsInRocket = arrowsBroken = 0;
        for (int r = 0; r < kRows; r++)
            for (int c = 0; c < kCols; c++) {
                uint32_t f = 0;
                if (s.hw[r * kCols + c]) f |= kWallN;
                if (s.hw[(r + 1) * kCols + c]) f |= kWallS;
                if (s.vw[r * 13 + c]) f |= kWallW;
                if (s.vw[r * 13 + c + 1]) f |= kWallE;
                uint8_t t = s.tiles[r * kCols + c];
                if (battle) {
                    rocketOwner[r][c] = 0;
                    if (t >= 1 && t <= 4) { f |= kRocket; rocketOwner[r][c] = (uint8_t)(t - 1); rocketPos[t - 1][0] = c; rocketPos[t - 1][1] = r; t = 0; }
                    else if (t >= 5 && t <= 8) { gens.push_back({c, r, t - 5}); t = 0; f |= kGenerator | (uint32_t)(gens.back().dir & 3); }
                }
                if (t == T_Rocket) f |= kRocket;
                if (t == T_Hole) f |= kHole;
                coll[r][c] = f;
                if ((t >= T_MouseS && t < T_MouseS + 4) || (t >= T_CatS && t < T_CatS + 4)) {
                    Entity e; e.mouse = t < T_CatS; e.heading = (t - (e.mouse ? T_MouseS : T_CatS)); if (!e.mouse) e.heading = (e.heading + catRot) & 3;
                    e.gx = c; e.gy = r; e.x = (c + 0.5f) * kCell; e.z = (r + 0.5f) * kCell;
                    ents.push_back(e);
                }
            }
    }
    void spawn(bool mouse, int type, int gx, int gy, int heading, bool fresh = false) {      // MO_PutMouse / CA_PutCat in battle mode
        Entity e; e.mouse = mouse; e.type = type; e.heading = heading & 3; e.gx = gx; e.gy = gy; e.fresh = fresh;
        e.slot = allocSlot((int)ents.size());
        e.x = (gx + 0.5f) * kCell; e.z = (gy + 0.5f) * kCell; ents.push_back(e);
    }
    void refreshCell(int x, int y) { refresh(x, y); }
    bool placeArrow(int x, int y, int dir) {
        if (coll[y][x] & (kRocket | kHole)) return false;
        for (auto& a : arrows) if (a.live && a.x == x && a.y == y) { a.dir = dir; refresh(x, y); return true; }
        arrows.push_back({x, y, dir, 0, true}); refresh(x, y); return true;
    }
    void removeArrow(int x, int y) {                  // puzzle "tap the same arrow again" removal
        for (auto& a : arrows) if (a.live && a.x == x && a.y == y) a.live = false;
        refresh(x, y);
    }
    void tick() {
        now++;
        for (auto& e : ents) e.reg = false;
        if (poolModel) poolTick();
        for (auto& m : ents) if (m.mouse && m.alive && !m.done && m.hit) {      // mouse tick: if (flags & 1) -> eaten state, no movement
            m.alive = false; m.hit = false; killed++; killedByCat++; endTicks.push_back(now); scheduleFree(&m - ents.data(), now + 1, true);
            if (battle) events.push_back({Event::MouseEaten, 0, m.type});
            if (trace) printf("t=%d mouse eaten at (%.1f,%.1f) cell (%d,%d)\n", now, m.x, m.z, m.gx, m.gy);
        }
        if (order == 0 && spdSlot >= 0) {   // a roulette event task changes the character speed this frame: tasks run in pool-slot order, so entities after the event's slot already see the new speed (SmpTskExeServer)
            std::vector<size_t> idx(ents.size()); for (size_t i = 0; i < idx.size(); i++) idx[i] = i;
            std::stable_sort(idx.begin(), idx.end(), [&](size_t a, size_t b) { return ents[a].slot < ents[b].slot; });
            bool applied = false;
            for (size_t i : idx) { Entity& e = ents[i]; if (!applied && e.slot > spdSlot) { mouseSpeed = spdMouse; catSpeed = spdCat; applied = true; }
                if (e.alive && !e.done && !e.fresh) { if (e.rocketIn) rocketInTick(e); else step(e); } }
            if (!applied) { mouseSpeed = spdMouse; catSpeed = spdCat; }
            spdSlot = -1;
        }
        else if (order == 0) { for (auto& e : ents) if (e.alive && !e.done && !e.fresh) { if (e.rocketIn) rocketInTick(e); else step(e); } }
        else { for (int pass = 0; pass < 2; pass++) for (auto& e : ents) if (e.alive && !e.done && (e.mouse == ((pass == 0) == (order == 2)))) step(e); }
        resolveCats();
        for (auto& e : ents) e.fresh = false;
    }
    Result run(int maxTicks) {
        int t = 0;
        for (; t < maxTicks; t++) {
            tick();
            bool any = false; for (auto& e : ents) if (e.mouse && e.alive && !e.done) any = true;
            if (!any) break;
        }
        Result r; r.ticks = t; r.saved = saved; r.killed = killed; r.byCat = killedByCat; r.byHole = killedByHole; r.catRocket = catsInRocket; r.broken = arrowsBroken;
        for (auto& e : ents) { if (e.mouse) r.mice++; else r.cats++; }
        r.stuck = (saved + killed) < r.mice;
        return r;
    }
    static bool unchangedByCorrect(uint32_t f, int d) { int h = d; correct(f, h); return h == d; }
    void buildHeat() {                                    // second half of SmpColAnalyze (run after all tasks each frame)
        for (auto& h : heat) h = 0;
        static const int mouseValue[4] = {1, 50, 25, 85};
        for (auto& e : ents) {
            if (!e.reg) continue;                    // entries registered this frame count even if the task is deleted later in the frame
            int gx = e.gx, gy = e.gy, ty = e.type;                       // fields are read from whatever task occupies the slot now
            if (e.slot >= 0) { int c = content[e.slot]; if (c >= 0) { gx = ents[c].gx; gy = ents[c].gy; ty = ents[c].type; } else { gx = 0; gy = 0; ty = 0; } }
            int v = e.mouse ? mouseValue[ty & 3] : -100;
            if (gx < 0 || gx >= kCols || gy < 0 || gy >= kRows) continue;
            if (e.mouse && v == 1) { heat[gy * kCols + gx] += 1; continue; }
            uint8_t visited[kRows * kCols] = {};
            spread(gx, gy, v, 8, visited);
        }
    }
private:
    void spread(int x, int y, int v, int depth, uint8_t* visited) {     // FUN_000299ac
        heat[y * kCols + x] += (int16_t)v; visited[y * kCols + x] = 1;
        if (depth != 1 && (unsigned)(v + 1) > 2u) {
            static const int dx[4] = {0, -1, 0, 1}, dy[4] = {1, 0, -1, 0};
            for (int d = 0; d < 4; d++) {
                uint32_t f = fieldCollision(x, y);
                if (!unchangedByCorrect(f, d)) continue;
                int nx = x + dx[d], ny = y + dy[d];
                if (nx < 0) nx += kCols; else if (nx >= kCols) nx -= kCols;
                if (ny < 0) ny += kRows; else if (ny >= kRows) ny -= kRows;
                if (!visited[ny * kCols + nx]) spread(nx, ny, v / 2, depth - 1, visited);
            }
        }
    }
public:
    uint32_t fieldCollision(int x, int y) const { return (x < 0 || x >= kCols || y < 0 || y >= kRows) ? 0u : coll[y][x]; }   // FI_GetFieldCollision
private:
    void refresh(int x, int y) {
        uint32_t& f = coll[y][x]; f &= ~(kArrow | 3u);
        for (auto& a : arrows) if (a.live && a.x == x && a.y == y) f |= kArrow | (uint32_t)a.dir;
    }
    static void gridOf(float x, float z, int& gx, int& gy) {
        gx = (int)(x * 0.06666667f); gy = (int)(z * 0.06666667f);
        if (x < 0) gx = 0; if (gx < 0) gx = 0; if (gx > kCols - 1) gx = kCols - 1;
        if (z < 0) gy = 0; if (gy < 0) gy = 0; if (gy > kRows - 1) gy = kRows - 1;
    }
    static void warp(Entity& e) {                     // FI_CheckWarp
        if (e.x < -7.5f) e.x += 195.0f; else if (e.x > 187.5f) e.x -= 195.0f;
        if (e.z < -7.5f) e.z += 150.0f; else if (e.z > 142.5f) e.z -= 150.0f;
    }
    // FI_CheckAndCorrectAngle: arrow sets heading; then first free of d, d+1 (right), d+3 (left), d+2 (back). Returns true on dead end.
    static bool correct(uint32_t f, int& h) {
        if (f & kArrow) h = (int)(f & 3);
        if (!(f & kWallAny)) return false;
        const int order[4] = {0, 1, 3, 2};
        for (int k = 0; k < 4; k++) { int d = (h + order[k]) & 3; if (!(f & kWallOfDir[d])) { h = d; return false; } }
        return true;
    }
    void strikeArrow(int x, int y) {                   // AR_CatHitArrow -> AR_StrikeArrow
        for (auto& a : arrows) if (a.live && a.x == x && a.y == y) { if (trace) printf("t=%d cat strikes arrow (%d,%d) hit #%d\n", now, x, y, a.hits + 1); if (++a.hits >= breakAt) { a.live = false; arrowsBroken++; if (trace) printf("t=%d cat breaks arrow at (%d,%d)\n", now, x, y); refresh(x, y); } return; }
    }
    static float njSin(int a) { static float tab[65536]; static bool built = false; if (!built) { for (int i = 0; i < 65536; i++) tab[i] = (float)std::sin((double)(float)((double)i * 6.283184 * 1.52587890625e-05)); built = true; } return tab[a & 0xffff]; }   // njSin table = njSinOrg (sinf of i * 6.283184 / 65536); libm rounding on the original device not verified
    static float njCos(int a) { return njSin(a + 0x4000); }   // cos table from njCosOrg: cosf of the same argument; cos(x) = sin(x + pi/2) to within the table's rounding (not verified bit for bit)
    void jimeStep(Entity& e) {   // MO_MouseJimeExe (iOS 0x1497c)
        float tx = 90.0f, tz = 67.5f;
        if (monopoly < 0) { float dx = e.x - tx, dz = e.z - tz; if (180.0f < std::sqrt(dx * dx + dz * dz)) { e.alive = false; e.reg = false; events.push_back({Event::MouseGone, 0, e.type}); scheduleFree(&e - ents.data(), now + 1, false); return; } }
        else {
            tx = (rocketPos[monopoly][0] + 0.5f) * kCell; tz = (rocketPos[monopoly][1] + 0.5f) * kCell;
            float dx = e.x - tx, dz = e.z - tz; float d = std::sqrt(dx * dx + dz * dz);
            if (d < 2.5f) { events.push_back({Event::MouseRocket, monopoly, e.type, e.slot}); e.done = true; e.reg = false; scheduleFree(&e - ents.data(), now + 1, false); return; }   // arrives: same as entering the rocket (score, puku, sound 8 for gold)
            float f = std::atan2(e.x - tx, tz - e.z); int tgt = (int)(long long)(((double)f * 65536.0) / 6.283184);
            e.angle = (int)adjustAngle(e.angle, tgt, 0x400);
        }
        e.x += njSin(e.angle) * -2.5f; e.z += njCos(e.angle) * 2.5f; gridOf(e.x, e.z, e.gx, e.gy); e.reg = false;
    }
    void step(Entity& e) {
        if (e.mouse && e.jime) { jimeStep(e); return; }
        const float speed = e.mouse ? mouseSpeed : catSpeed;
        float thr = speed * (e.mouse ? 0.52f : 0.51f);
        if (thr < 0.01f) thr = 0.01f;
        static const float sinv[4] = {0, 1, 0, -1}, cosv[4] = {1, 0, -1, 0};   // sin/cos of heading*90 degrees
        const float cx = (e.gx + 0.5f) * kCell, cz = (e.gy + 0.5f) * kCell;
        const float ddx = e.x - cx, ddz = e.z - cz;
        if (std::sqrt(ddx * ddx + ddz * ddz) < thr) {            // at a cell centre
            uint32_t f = coll[e.gy][e.gx];
            if (battle && (f & kRocket)) {
                events.push_back({e.mouse ? Event::MouseRocket : Event::CatRocket, rocketOwner[e.gy][e.gx], e.type, e.slot});
                if (e.mouse || !rnd) e.done = true; else e.rocketIn = true;
                if (e.mouse) scheduleFree(&e - ents.data(), now + 1, false);       // mouse: removed; cat: rocket-in animation then respawn (FUN_000292c0)
                return;
            }
            if (f & kRocket) { if (e.mouse) { saved++; saveTicks.push_back(now); endTicks.push_back(now); if (trace) printf("SAVED t=%d n=%d" "\n", now, saved); } else { catsInRocket++; if (trace) printf("t=%d cat enters rocket at (%d,%d)\n", now, e.gx, e.gy); } e.done = true; return; }
            if (battle && (f & kHole)) { events.push_back(e.mouse ? Event{Event::MouseHole, 0, e.type} : Event{Event::CatRocket, -1, 0});
                if (e.mouse || !rnd) e.alive = false; else e.rocketIn = true;      // a cat falling into a hole also ends in the rocket-in/respawn function
                return; }   // cat lost in a hole: player -1, no score
            if (f & kHole)   { if (e.mouse) { killed++; killedByHole++; endTicks.push_back(now); if (trace) printf("t=%d mouse falls in hole at (%d,%d)\n", now, e.gx, e.gy); } e.alive = false; return; }
            if (!e.mouse && (f & kArrow)) {                      // cat arriving head-on to an arrow strikes it
                if (((e.heading + 2) & 3) == (int)(f & 3)) strikeArrow(e.gx, e.gy);   // note: the turn below still uses the flags read before the strike (as the original does)
            }
            const int before = e.heading;
            if (correct(f, e.heading)) return;                   // dead end: no movement this tick
            if (e.heading != before) { e.x = cx; e.z = cz; }     // turning snaps to the cell centre
        }
        e.x += -speed * sinv[e.heading];                         // original: x += -speed*sin(h), z += speed*cos(h)
        e.z +=  speed * cosv[e.heading];
        warp(e);
        gridOf(e.x, e.z, e.gx, e.gy);
        e.reg = true;
        if (e.mouse && battle && monopoly >= 0) { e.jime = true; e.angle = e.heading << 14; }   // MO_MouseExe tail: ChangeExeFunction(MO_MouseJimeExe) while Mouse Monopoly runs (the collision entry of this tick is still made)
    }
    static float bitsToFloat(uint32_t b) { float f; static_assert(sizeof f == 4, ""); std::memcpy(&f, &b, 4); return f; }
    void rocketInTick(Entity& e) {
        const float kRocketStep = bitsToFloat(kRocketStepBits);                      // Android FUN_000292c0 (game types 0/1): counter -= 1/30 each tick, finished when <= 0
        e.rocketCounter = e.rocketCounter + 1.0f * kRocketStep;
        if (!(e.rocketCounter <= 0.0f)) return;
        e.rocketCounter = 1.0f;
        if (!gens.empty()) {
            float r = rnd();
            int i = (int)((float)gens.size() * 0.99f * r);
            if (trace) printf("t=%d cat respawn draw r=%.6f gen %d\n", now, r, i);
            e.gx = gens[i].x; e.gy = gens[i].y; e.heading = gens[i].dir & 3;
            e.x = (e.gx + 0.5f) * kCell; e.z = (e.gy + 0.5f) * kCell;
        }
        e.rocketIn = false;
    }
public:
    void resolveNewMice(size_t firstNew) {              // a mouse registers for collision when it is put; a cat only on its first tick (measured)
        for (size_t i = firstNew; i < ents.size(); i++) { Entity& m = ents[i]; if (!m.mouse) continue;
            for (size_t j = 0; j < firstNew; j++) { Entity& c = ents[j]; if (c.mouse || !c.alive || c.done || c.rocketIn) continue;
                if (m.jime) continue;
                float ax = c.x - m.x, az = c.z - m.z; if (std::sqrt(ax * ax + az * az) < 5.0f) m.hit = true; } }
    }
    void resolveCats() {                               // SmpColAnalyze: cat and mouse closer than 5.0 (registered end-of-tick positions)
        for (auto& c : ents) if (!c.mouse && c.alive && !c.done && !c.rocketIn && !c.fresh)
            for (auto& m : ents) if (m.mouse && m.alive && !m.done && !m.fresh && !m.jime) {
                float ax = c.x - m.x, az = c.z - m.z;
                if (std::sqrt(ax * ax + az * az) < 5.0f) m.hit = true;
            }
    }
};

} // namespace ccr
