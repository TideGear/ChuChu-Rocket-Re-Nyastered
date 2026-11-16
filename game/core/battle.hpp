// Battle game: ties the verified components (Sim movement, Generator, Scoreboard, Roulette) into one fixed-tick battle.
// Verified parts: movement, generator spawn log, scoring, roulette selector. NOT yet verified against the original: frame order
// inside a tick, roulette event handler effects beyond the constants in docs/rules_events.md, round length, fever spawn changes.
#pragma once
#include "sim.hpp"
#include "generator.hpp"
#include "score.hpp"
#include "cpu_gba.hpp"
#include "roulette.hpp"
#include "cpu.hpp"
#include <algorithm>
#include <memory>
#include <cstdlib>
#include <cstdio>
#include <functional>
#include <cstdio>
namespace ccr {

class BattleGame {
public:
    void setCharaSpeed(float v);   // test harness (defined below)
    bool teamMode = false;                          // Team Battle (GA game type 1): teams are the player parity (0 and 2 against 1 and 3); changes the roulette events' opponents and the rocket shuffle table
    float puku[4] = {1.0f, 1.0f, 1.0f, 1.0f};   // rocket size: RO_RocketSetPukuPuku adds 0.2 (literal 0x3e4ccccd) per mouse entering, capped at 1.5 (0x3fc00000); drawn at value x 0.8 of the sprite. The start value 1.0 is the puzzle manager's init (RO_StartRocketPzManager); the battle manager's init was not read.
    static constexpr int kArrowTtl = 600, kArrowSlots = 3;
    Sim sim; std::unique_ptr<Generator> gen; Scoreboard score; std::unique_ptr<Roulette> roulette;   // table = first 128 draws of a fresh RNG with the battle seed (as verified in roulette_test)
    int frame = 0, clock = 0, roundFrames = 60 * 180;   // clock = frames the round countdown has run: it stops while the roulette wheel task is alive (FourBattleLoop phase 2 counts the timers only when RL_GetRoulette4Status() == 0)
          // round length: setting-dependent in the original (not extracted yet)
    float baseScale = 1.0f;                      // GA_OnGameFlag speed-option multiplier (0.25 with the option unset)
    GenParams generatorParams;
    float charaSpeed = 1.0f;                     // GA_SetCharaSpeed (events scale cat and mouse together); base speeds 1.0 / 1.5
    int event = -1, eventLeft = 0; bool over = false;
    int rankOf(int p) const { return rank_[p]; }
    bool rotateOwn = false;                      // true: re-placing on your own arrow rotates it (the flagged branch of FUN_0002859c)
    bool rouletteEnabled = true;                 // test harness: the emulated original rolls only under conditions not yet understood (see docs)
    bool genFirst = true;                        // generator task runs before the entity tasks (measured: 26/26 battles identical)
    // CPU players (Android CT_*): level 0..3 or 4 = chosen from time and player; -1 = human
    bool gbaCpu = false; gba::Env gbaEnv; uint8_t gbaType[4] = {5, 5, 5, 5}; int humanCell[4][2] = {{2, 2}, {9, 2}, {2, 6}, {9, 6}};   // GBA CPU players (transcribed ROM routines, game/core/cpu_gba.hpp): personality type per player (5 = random), human cursor cells
    CpuEnv cpuEnv; CpuLcg cpuLcg; CpuPlayer cpu[4]; int cpuLevel[4] = {-1, -1, -1, -1}; bool cpuFirst = true, cpuReverse = false;
    struct Put { int frame, player, x, y, dir; }; std::vector<Put> cpuPuts;
    void setCpu(int p, int level) { cpuLevel[p] = level; }
    bool rouletteManager = true;                 // false: emulated-original harness never starts the roulette manager (table of zeros)
    int gtOff = 0; int fixedGameTime = -1, fixedBcd = -1;   // test harness: the emulated original never advances TI_GetGameTime / the BCD timer (both 0)
    std::function<void(int)> sfx;                // sound hook: ChuSECall ids (0x13 refused, 1 arrow placed, 6 mouse home, 7 cat in rocket, 10 roulette)
    int localPlayer = 0;
    int activeEventKind() const { return evs_.empty() ? -1 : evs_.back().kind; }   // roulette outcome (0..7) of the running event, or -1 (the original picks the BGM from it: FUN_0003c56c)
    bool rollPending() const { return roll_.active; }
    bool rouletteDrawState(int& tick, int& player, int& outcome) const {
        if (!roll_.active || roll_.elapsed <= 0) return false;
        tick = roll_.elapsed - 1;
        player = lastRoller_;
        outcome = roll_.outcome;
        return true;
    }
    bool debug = false;
    int cursorLock = 0;                          // frames cursors stay locked (Cat Attack)
    std::vector<int> lastRoll;
    int forceOutcome = -1;
    void start(const Stage& st, uint32_t seed) {
        for (float& q : puku) q = 1.0f;
        sim.battle = true; sim.trace = debug; sim.load(st);
        std::vector<GenCell> cells; for (auto& g : sim.gens) cells.push_back({g.x, g.y, g.dir});
        for (auto& r : slot_) for (int& v : r) v = -1; for (int& v : ring_) v = 0;
        gen = std::make_unique<Generator>(cells, seed, generatorParams); sim.rnd = [this]() { return gen->rng().next(); }; if (rouletteManager) roulette.reset(new Roulette(gen->rng())); else roulette.reset(new Roulette());   // RL_StartRoulette4Manager draws 128 numbers from the shared stream spawned_ = 0; lastRoll.clear();
        frame = 0; over = false; event = -1; eventLeft = 0; charaSpeed = 1.0f; applySpeed();
        clock = 0; score = Scoreboard(); for (int& r : rank_) r = 0; roll_ = Roll(); evs_.clear(); lastRoller_ = 0; pendingRoll_ = -1; cpuPuts.clear(); cpuLcg.state = (uint32_t)cpuEnv.globalTime;
        cpuEnv.sim = &sim; cpuEnv.gameType = 0;
        for (int p = 0; p < 4; p++) { cpuEnv.rocketX[p] = sim.rocketPos[p][0]; cpuEnv.rocketY[p] = sim.rocketPos[p][1]; }
        cpuEnv.rank = [this](int p) { return rankOf(p); };
        cpuEnv.cursorFree = [this](int) { return cursorLock <= 0; };
        cpuEnv.putArrow = [this](int pl, int x, int y, int d) { cpuPuts.push_back({frame, pl, x, y, d}); placeArrow(pl, x, y, d); };
        { int nb = 4; for (int p = 0; p < 4; p++) if (cpuLevel[p] >= 0) nb++; sim.occupyBase(nb); }   // manager tasks (arrows, roulette monitor, rockets, generator) + one task per CPU
        for (int p = 0; p < 4; p++) if (cpuLevel[p] >= 0) cpu[p].start(cpuEnv, p, cpuLevel[p]);
        if (gbaCpu) gbaStart(seed);
    }
    // Player arrow placement (Android FUN_0002859c, local path): own arrow on the cell -> only the direction changes; any other object bit
    // (0xF00: rocket, hole, arrow of another player) refuses; otherwise the slot at the player's ring index is freed and reused (3 slots, TTL 600).
    bool placeArrow(int player, int x, int y, int dir) {
        if (cursorLock > 0 || over) { if (sfx && player == localPlayer) sfx(0x13); return false; }
        uint32_t f = sim.coll[y][x];
        if ((f & kArrow) && !rotateOwn) { if (sfx && player == localPlayer) sfx(0x13); return false; }   // flag byte at Android 0x285db is 0 in the emulated battle setup: any arrow cell is refused (unverified for real play)
        if (f & kArrow) {
            for (int k = 0; k < kArrowSlots; k++) { int i = slot_[player][k]; if (i >= 0 && sim.arrows[i].live && sim.arrows[i].x == x && sim.arrows[i].y == y) { sim.arrows[i].dir = dir; sim.refreshCell(x, y); if (sfx && player == localPlayer) sfx(1); return true; } }
            if (sfx && player == localPlayer) sfx(0x13);
            return false;
        }
        if (f & (kRocket | kHole | kGenerator)) { if (sfx && player == localPlayer) sfx(0x13); return false; }
        int k = ring_[player]; int old = slot_[player][k];
        if (old >= 0 && sim.arrows[old].live) { sim.arrows[old].live = false; sim.refreshCell(sim.arrows[old].x, sim.arrows[old].y); }
        sim.arrows.push_back({x, y, dir, 0, true, player, kArrowTtl}); sim.refreshCell(x, y);
        slot_[player][k] = (int)sim.arrows.size() - 1; ring_[player] = (k + 1) % kArrowSlots;
        if (sfx && player == localPlayer) sfx(1);
        return true;
    }
    void tick() {
        if (over) return;
        frame++;
        if (!roll_.active) { clock++; int left = roundFrames - clock; if (sfx && left >= 0 && left % 60 == 0 && left / 60 <= 5) sfx(0x13 - left / 60); }   // FourBattleLoop: ChuSECall(0x13 - seconds) as the BCD countdown (mm:ss:ff, ff = 60 Hz frames) reaches 5, 4, 3, 2, 1, 0 s
        for (auto& a : sim.arrows) if (a.live && a.ttl > 0 && --a.ttl == 0) { a.live = false; sim.refreshCell(a.x, a.y); }
        if (cursorLock > 0) cursorLock--;
        applyMiceDec();
        if (genFirst) { gen->frame(frame); spawnPending(true); }
        if (pendingRoll_ >= 0) { int pr = pendingRoll_; pendingRoll_ = -1; startRoulette(pr, pendingRollSlot_); }   // the roll runs in the rolling mouse's destroy step, after the generator task (created first) of the same frame

        if (cpuFirst) runCpu();
        prepareSpeedChange();
        sim.events.clear(); sim.tick();
        for (const Event& e : sim.events) handle(e);
        if (!cpuFirst) runCpu();
        updateEvent();                                                     // roulette/event tasks run after the mouse and cat tasks
        sim.buildHeat();                                                   // SmpColAnalyze: heat map seen by the CPU players next frame
        if (!genFirst) { gen->frame(frame); spawnPending(false); }                                                 // entities spawned this frame first move next frame (measured against the original)
        if (clock >= roundFrames) { over = true; gen->flags = 0xF; }
    }
private:
    size_t spawned_ = 0; int slot_[4][3] = {{-1,-1,-1},{-1,-1,-1},{-1,-1,-1},{-1,-1,-1}}; int ring_[4] = {0,0,0,0};
    
    float mouseSpeed(float scale) const { return (1.5f * scale) * baseScale; }  // GA_GetMouseSpeed
    void applySpeed() { sim.catSpeed = baseScale * charaSpeed; sim.mouseSpeed = mouseSpeed(charaSpeed); }
    void spawnPending(bool fresh) { for (size_t i = spawned_; i < gen->spawns.size(); i++) { const Spawn& s = gen->spawns[i]; sim.spawn(!s.cat, s.mouseType, s.x, s.y, s.dir, fresh); } spawned_ = gen->spawns.size(); }
    void gbaStart(uint32_t seed) {
        gba::Env& e = gbaEnv; e = gba::Env(); e.lcg = seed * 2654435761u + 1u; e.mode = 0;
        for (int p = 0; p < 4; p++) { e.ptype[3 * p] = cpuLevel[p] >= 0 ? gbaType[p] : 0; int cx = cpuLevel[p] >= 0 ? sim.rocketPos[p][0] : humanCell[p][0], cy = cpuLevel[p] >= 0 ? sim.rocketPos[p][1] : humanCell[p][1];
            e.spx[p] = (uint8_t)(cx * 16 + 8); e.spy[p] = (uint8_t)(cy * 16 + 8); e.h8[p] = (uint16_t)(2 * cx + 2); e.hc[p] = (uint16_t)(2 * cy + 2); e.curx[p] = (uint8_t)e.h8[p]; e.cury[p] = (uint8_t)e.hc[p]; }
        for (int p = 0; p < 4; p++) if (cpuLevel[p] >= 0) gba::initCpu(e, p);
    }
    void gbaSync() {   // fill the ROM's lattice, score/arrow tables and object lists from the simulation
        gba::Env& e = gbaEnv; memset(e.field, 0, sizeof e.field); static const int dirCode[4] = {4, 8, 12, 0};
        auto put = [&](int xp, int yp, int v) { e.field[xp + 27 * yp + 1] = (uint8_t)v; };
        for (int y = 0; y < kRows; y++) for (int x = 0; x < kCols; x++) { uint32_t f = sim.coll[y][x];
            if (f & kWallN) put(2 * x + 2, 2 * y + 1, 0x10); if (f & kWallS) put(2 * x + 2, 2 * y + 3, 0x10); if (f & kWallW) put(2 * x + 1, 2 * y + 2, 0x10); if (f & kWallE) put(2 * x + 3, 2 * y + 2, 0x10);
            if (f & kRocket) put(2 * x + 2, 2 * y + 2, 0x20 | sim.rocketOwner[y][x]); else if (f & kHole) put(2 * x + 2, 2 * y + 2, 0x80); }
        memset(e.arr, 0, sizeof e.arr);
        for (int p = 0; p < 4; p++) { int sc = score.player[p]; e.arr[20 * p] = (uint8_t)(sc & 0xff); e.arr[20 * p + 1] = (uint8_t)(sc >> 8); }
        int cnt[4] = {0, 0, 0, 0};
        for (const Arrow& a : sim.arrows) if (a.live && a.owner >= 0 && a.owner < 4) { int p = a.owner, k = cnt[p]++; if (k < 3) { e.arr[20 * p + 7 + 4 * k] = (uint8_t)dirCode[a.dir & 3]; e.arr[20 * p + 8 + 4 * k] = (uint8_t)(2 * a.x + 2); e.arr[20 * p + 9 + 4 * k] = (uint8_t)(2 * a.y + 2); } put(2 * a.x + 2, 2 * a.y + 2, 0x60 | dirCode[a.dir & 3] | p); }
        for (int p = 0; p < 4; p++) e.arr[20 * p + 6] = (uint8_t)std::min(cnt[p], 3);
        e.nCats = e.nMice = 0;
        for (const Entity& en : sim.ents) { if (!en.alive || en.done || en.rocketIn) continue; uint16_t px = (uint16_t)(0x28 + (int)(en.x * 16.0f / 15.0f)), py = (uint16_t)(2 + (int)(en.z * 16.0f / 15.0f));
            if (en.mouse) { if (e.nMice < 32) e.mice[e.nMice++] = {px, py, (uint8_t)en.type}; } else if (e.nCats < 32) e.cats[e.nCats++] = {px, py, 0}; }
        for (int p = 0; p < 4; p++) { if (cpuLevel[p] >= 0) { e.curx[p] = (uint8_t)e.h8[p]; e.cury[p] = (uint8_t)e.hc[p]; } else { e.curx[p] = (uint8_t)(2 * humanCell[p][0] + 2); e.cury[p] = (uint8_t)(2 * humanCell[p][1] + 2); } }
    }
    void gbaRun() {
        gba::Env& e = gbaEnv; gbaSync(); gba::frameStep(e); e.nPlaced = 0;
        for (int p = 0; p < 4; p++) if (cpuLevel[p] >= 0) gba::cpuTask(e, p);
        static const int toDir[16] = {3, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 2, 0, 0, 0};   // ROM arrow direction code (0 east, 4 south, 8 west, 12 north: the wall classifier returns the direction away from the wall) -> port direction (0 south, 1 west, 2 north, 3 east)
        for (int i = 0; i < e.nPlaced; i++) { const auto& pl = e.placed[i]; int d = toDir[pl.dir & 15]; placeArrow(pl.p, pl.x, pl.y, d); }
    }
    void runCpu() { if (gbaCpu) { gbaRun(); return; } if (cpuReverse) { for (int p = 3; p >= 0; p--) if (cpuLevel[p] >= 0) cpu[p].step(cpuEnv, cpuLcg); } else for (int p = 0; p < 4; p++) if (cpuLevel[p] >= 0) cpu[p].step(cpuEnv, cpuLcg); }
    int pendMice_ = 0, pendCnt1_ = 0, pendCnt2_ = 0;   // GE_MouseCountDown runs when the mouse task is destroyed, one tick after the collision event
    void decMice(int type) { if (type == 0) pendMice_++; if (type == 1) pendCnt1_++; if (type == 2) pendCnt2_++; }
    int pend2Mice_ = 0, pend2Cnt1_ = 0, pend2Cnt2_ = 0;
    void applyMiceDec() { gen->mice -= pend2Mice_; gen->cnt1 -= pend2Cnt1_; gen->cnt2 -= pend2Cnt2_; pend2Mice_ = pendMice_; pend2Cnt1_ = pendCnt1_; pend2Cnt2_ = pendCnt2_; pendMice_ = pendCnt1_ = pendCnt2_ = 0; }
    void handle(const Event& e) {
        if (debug) printf("f%d event kind %d player %d type %d\n", frame, (int)e.kind, e.player, e.type);
        switch (e.kind) {
        case Event::MouseRocket: {
            { float& q = puku[e.player & 3]; q += 0.2f; if (q > 1.5f) q = 1.5f; }
            static const int value[3] = {1, 50, 1};
            score.add(e.player, value[e.type]); updateRanks(); if (sfx) sfx(6); decMice(e.type);
            if (e.type == 2) { if (rouletteEnabled) { pendingRoll_ = e.player; pendingRollSlot_ = e.slot; } }     // RL_RollRoulette4 runs when the mouse task is destroyed: one frame later
            break; }
        case Event::MouseGone:   // MO_MouseJimeExe deletes the task directly (0x3db0c) when it is more than 180 from the field centre: the counter drops in the same frame
            if (e.type == 0) gen->mice--; if (e.type == 1) gen->cnt1--; if (e.type == 2) gen->cnt2--; break;
        case Event::MouseEaten: case Event::MouseHole:
            decMice(e.type); break;
        case Event::CatRocket:
            if (e.player >= 0) { score.catHasCome(e.player); updateRanks(); if (sfx) sfx(7); }            // a cat in a rocket respawns at a generator: it stays 'out'
            // (hole: no score change; the cat respawns at a generator too, so it stays 'out')
            break;                                   // GE_CatIsLost
        }
    }
    int rank_[4] = {0, 0, 0, 0};                 // score array [4..7]: written only when a score changes (FUN_0003d168): dense ranking, ties share a rank
    void updateRanks() { for (int p = 0; p < 4; p++) { int r = 0; for (int q = 0; q < 4; q++) if (score.player[q] > score.player[p]) { bool counted = false; for (int k = 0; k < q; k++) if (score.player[k] == score.player[q]) counted = true; if (!counted) r++; } rank_[p] = r; } }

    // --- Roulette (Android FUN_0003c3b8 RL_RollRoulette4 / FUN_0003c56c / event tasks), measured with tools/oracle/rl_probe.py ---
    // A type-2 mouse entering a rocket rolls only if no roulette task is running; the outcome is selected with the rank of the player who rolled LAST time
    // (initially player 0; the original stores the new player after selecting). The event starts 121 frames after the roll (1 + 30 fly-in + 90).
    struct Roll { bool active = false; int elapsed = 0, outcome = 0, slot = -1; } roll_;
    struct PCat { int x, y, dir; }; std::vector<PCat> pendingCats_;
    int lastRoller_ = 0, pendingRoll_ = -1;
    struct Ev { int kind, state, count, limit; int rollerPlayer; int slot; int ord = 0; };   // ord: number of entities created before the event task (its place in the task list)
    std::vector<Ev> evs_;
    void startRoulette(int p, int rollSlot = -1) {
        if (roll_.active) return;
        cancelEvents(rollSlot);   // a new roll deletes the running event task (measured: GA_SetCharaSpeed(1.0) at the roll frame in the original)
        int rem = std::max(0, (roundFrames - clock) / 60);
        unsigned bcd = (unsigned)(((rem / 60) << 8) | (((rem % 60) / 10) << 4) | (rem % 10));   // minutes:seconds in BCD (TI_GetBCDTime layout still to be confirmed)
        int out = roulette->roll(rankOf(lastRoller_), fixedBcd >= 0 ? (unsigned)fixedBcd : (bcd << 8), fixedGameTime >= 0 ? fixedGameTime : frame + gtOff, -1); if (forceOutcome >= 0) out = forceOutcome; roulette->record(out);   // forceOutcome: verification only (the original's selector replaced by a constant)
        if (debug) printf("ROLL f%d player %d outcome %d\n", frame, p, out);
        lastRoller_ = p; sim.releaseSlot(roll_.slot); roll_.slot = sim.allocSlot(-2); roll_.active = true; roll_.elapsed = -1; roll_.outcome = out; lastRoll.push_back(out);
    }
    float feverDuration() const { return 600.0f; }
    void startEvent(int out) {                                            // dispatch: the event task is created; its first exec (state 0) is next frame
        int lim = 0;
        switch (out) { case 0: lim = (int)(600.0f * 2.0f); break; case 1: lim = 599; break; case 2: case 3: lim = 479; break; case 4: lim = 179; break;
                       case 5: case 6: lim = 59; break; default: lim = 239; }   // RL_Eve_Hikkoshi and RL_Eve_NekoPresent end when their counter exceeds 0x3b; RL_Eve_Hitorijime when it exceeds 0xef
        int es = sim.allocSlot(-2);                                       // the event task is created first, then the roulette task deletes itself (0x3c6e0..0x3c6f2)
        sim.releaseSlot(roll_.slot); roll_.slot = -1;
        evs_.push_back({out, 0, 0, lim, lastRoller_, es, (int)sim.ents.size()}); event = out;
    }
    bool nekoCheck(int roller, int p) const { return roller != p && (!teamMode || ((roller ^ p) & 1)); }   // RL_ENP_CheckNekoire (iOS 0x1d02c) = FUN_0003c9cc (Android)
    // RO_ShuffleRockets (iOS 0x158a0, Android 0x3b490), local battle path: a permutation chosen by the game time (TI_GetGameTime = frame count): free-for-all table[(t & 0x3f) mod 9], team table[(t & 0xf) mod 5];
    // rocket i moves to the cell of old rocket perm[i] (FI_ChangeFieldCollisionID(cell, i)) and the position table is permuted the same way. The net-battle path (global mode 0x10, owner list ranking) is not ported.
    void shuffleRockets() {
        static const uint8_t ffa[9][4] = {{1,0,3,2},{3,0,1,2},{2,0,3,1},{1,3,0,2},{2,3,0,1},{3,2,0,1},{1,2,3,0},{2,3,1,0},{3,2,1,0}};
        static const uint8_t team[5][4] = {{1,0,3,2},{2,0,3,1},{1,3,0,2},{3,2,0,1},{2,3,1,0}};
        int gt = fixedGameTime >= 0 ? fixedGameTime : frame + gtOff;
        const uint8_t* perm = teamMode ? team[(gt & 0xf) % 5] : ffa[(gt & 0x3f) % 9];
        int old[4][2]; for (int i = 0; i < 4; i++) { old[i][0] = sim.rocketPos[i][0]; old[i][1] = sim.rocketPos[i][1]; }
        for (int i = 0; i < 4; i++) { int x = old[perm[i]][0], y = old[perm[i]][1]; sim.rocketOwner[y][x] = (uint8_t)i; sim.rocketPos[i][0] = x; sim.rocketPos[i][1] = y; cpuEnv.rocketX[i] = x; cpuEnv.rocketY[i] = y; }
    }
    // Event tasks that call GA_SetCharaSpeed run inside the task pass at their pool slot: announce this frame's change to the simulation so entities with a later slot already use the new speed.
    void prepareSpeedChange() {
        for (const Ev& e : evs_) {
            float v = -1.0f;
            if (e.state == 0) v = -1.0f;   // the start (state 0) takes effect from the next frame (measured)
            else if (e.count + 1 > e.limit && e.kind != 0 && e.kind != 1 && e.kind != 4 && e.kind != 7) v = 1.0f;
            if (e.kind == 7 && e.state == 1 && e.count + 1 > e.limit) sim.monoEnd = e.ord;
            if (v >= 0.0f && e.slot >= 0) { sim.spdSlot = e.ord; sim.spdMouse = mouseSpeed(v); sim.spdCat = baseScale * v; }
        }
    }
    // The destructors of the event tasks (RL_Eve_*Dest): run when the task ends and also when a new roll deletes the running event (RL_RollRoulette4 deletes the task stored in its global).
    void eventDest(int kind) {
        switch (kind) {
        case 0: removeGroup(2, true); gen->flags = 0; gen->catOut = false; break;
        case 1: gen->flags = 0; gen->params().pSpawn = 0.0125f; gen->catOut = false; break;
        case 2: charaSpeed = 1.0f; gen->flags = 0; break;
        case 3: charaSpeed = 1.0f; break;
        case 4: gen->flags = 0; break;
        case 5: case 6: gen->flags = 0; cursorLock = 0; charaSpeed = 1.0f; break;
        default: gen->flags = 0; gen->params().pSpawn = 0.0125f; sim.monopoly = -1; break;   // RL_Eve_HitorijimeDest: prohibit 0, GE_CancelChu2Fever, MO_StopHitorijime
        }
    }
    int pendingRollSlot_ = -1;
    void cancelEvents(int atSlot) {   // the roll runs in the RideOn task of the mouse that entered the rocket: the speed restore applies from that task's pool slot on
        if (evs_.empty()) return;
        float before = charaSpeed;
        int atOrd = -1; if (atSlot >= 0) for (int k = (int)sim.ents.size() - 1; k >= 0; k--) if (sim.ents[k].slot == atSlot) { atOrd = k + 1; break; }   // the rolling mouse's place in the task list
        for (const Ev& e : evs_) { const int keep = sim.monopoly; eventDest(e.kind); sim.releaseSlot(e.slot); if (e.kind == 7 && atOrd >= 0 && keep >= 0) { sim.monopoly = keep; sim.monoEnd = atOrd; } }   // the Monopoly global is cleared from the rolling mouse's task on
        evs_.clear(); event = -1;
        if (charaSpeed != before) { sim.spdSlot = atOrd; sim.spdMouse = mouseSpeed(charaSpeed); sim.spdCat = baseScale * charaSpeed; if (atOrd < 0) applySpeed(); }
        else applySpeed();
    }
    void stepRoulette() {
        for (size_t i = 0; i < evs_.size();) {
            Ev& e = evs_[i]; bool done = false;
            if (e.state == 0) {
                e.state = 1;
                switch (e.kind) {
                case 0: removeGroup(3); gen->flags = 0xF; spawnCatFever(); break;                                   // Cat Mania: prohibit all, one cat per generator slot x4
                case 1: removeGroup(2); gen->flags = 0xC; gen->params().pSpawn = 0.125f; break;                    // Mouse Mania (GE_SetChu2Fever)
                case 2: charaSpeed = 2.0f; gen->flags = 4; break;                                   // Speed Up
                case 3: charaSpeed = 0.3f; break;                                                   // Speed Down
                case 4: if (sfx) sfx(0xd); for (auto& a : sim.arrows) if (a.live) { a.live = false; sim.refreshCell(a.x, a.y); } gen->flags = 0xF; break;   // Place Arrows Again
                case 5: gen->flags = 0xF; cursorLock = 1 << 30; charaSpeed = 0.0f; shuffleRockets(); if (sfx) sfx(0xc); break;   // Everybody Move: RL_Eve_Hikkoshi: ChuSECall(0xc), prohibit 0xF, RO_ShuffleRockets, cursor lock, speed 0
                case 6: gen->flags = 0xF; cursorLock = 1 << 30; charaSpeed = 0.0f; break;           // Cat Attack (cat presents NOT ported)
                default: gen->flags = 4; gen->params().pSpawn = 0.125f; sim.monopoly = e.rollerPlayer; break;   // Mouse Monopoly (RL_Eve_Hitorijime): MO_StartHitorijime(roller), prohibit 4, Chu2 fever; mice convert to MO_MouseJimeExe at the end of their next normal step
                }
                applySpeed(); i++; continue;
            }
            e.count++;
            // HD 1.0 RL_Eve_NekoFever rolls once every 16 ticks before expiry.
            if (e.kind == 0 && e.count < e.limit && e.count % 16 == 0) {
                const float chance = gen->rng().next();
                if (chance < 0.3f && sfx) sfx(0x1b);
            }
            if (e.kind == 2 && e.count == 300) gen->flags = 0;
            if (e.kind == 0) done = e.count >= e.limit; else done = e.count > e.limit;
            if (done) {
                if (e.kind == 6) { if (sfx) sfx(7); for (int p = 0; p < 4; p++) if (nekoCheck(e.rollerPlayer, p) && (!teamMode || p < 2)) { score.catHasCome(p); } updateRanks(); }   // RL_Eve_NekoPresent at counter 0x3c: sound 7, SC_CatHasCome for every opponent's rocket (one per team in Team Battle), then its Dest
                eventDest(e.kind);
                applySpeed(); sim.releaseSlot(e.slot); evs_.erase(evs_.begin() + i); if (evs_.empty()) event = -1; continue;
            }
            i++;
        }
    }
    void removeGroup(int mask, bool unregister = false) {                                          // 0x3db58: delete tasks by group (1 = mice, 2 = cats); mice decrement the generator counters
        for (auto& e : sim.ents) {
            if (!e.alive || e.done) continue;
            if (e.mouse && (mask & 1)) { e.alive = false; sim.releaseSlot(e.slot); if (e.type == 0) gen->mice--; if (e.type == 1) gen->cnt1--; if (e.type == 2) gen->cnt2--; }
            else if (!e.mouse && (mask & 2)) { e.alive = false; sim.releaseSlot(e.slot); }
            if (unregister && !e.alive) e.reg = false;       // measured: tasks deleted by an event's destructor no longer feed the heat map that frame
        }
    }
    void spawnCatFever() {                                                // GE_SetCatFever: four cats, generator slots in rotation
        size_t n = sim.gens.size(); if (n == 0) return;
        size_t idx = 0; for (int k = 0; k < 4; k++) { const auto& g = sim.gens[idx % n]; sim.spawn(false, 0, g.x, g.y, g.dir); idx++; }
    }
    void updateEvent() {
        stepRoulette();
        if (!roll_.active) return;
        ++roll_.elapsed;
        // HD 1.0 RL_RouletteExec. The task is registered on elapsed 0 and first executes on 1.
        if (sfx) {
            constexpr int voice[] = {119, 120, 117, 118, 122, 121, 123, 124};
            if (roll_.elapsed == 1) sfx(10);
            if (roll_.elapsed == 31) sfx(11);
            if (roll_.elapsed == 61) sfx(voice[roll_.outcome]);
        }
        if (roll_.elapsed == 121) {
            roll_.active = false;
            startEvent(roll_.outcome);
        }
    }
};
inline void BattleGame::setCharaSpeed(float v) { charaSpeed = v; applySpeed(); }
} // namespace ccr
