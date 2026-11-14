// Battle game: ties the verified components (Sim movement, Generator, Scoreboard, Roulette) into one fixed-tick battle.
// Verified parts: movement, generator spawn log, scoring, roulette selector. NOT yet verified against the original: frame order
// inside a tick, roulette event handler effects beyond the constants in docs/rules_events.md, round length, fever spawn changes.
#pragma once
#include "sim.hpp"
#include "generator.hpp"
#include "score.hpp"
#include "roulette.hpp"
#include "cpu.hpp"
#include <algorithm>
#include <memory>
#include <functional>
#include <cstdio>
namespace ccr {

class BattleGame {
public:
    static constexpr int kArrowTtl = 600, kArrowSlots = 3;
    Sim sim; std::unique_ptr<Generator> gen; Scoreboard score; std::unique_ptr<Roulette> roulette;   // table = first 128 draws of a fresh RNG with the battle seed (as verified in roulette_test)
    int frame = 0, clock = 0, roundFrames = 60 * 180;   // clock = frames the round countdown has run: it stops while the roulette wheel task is alive (FourBattleLoop phase 2 counts the timers only when RL_GetRoulette4Status() == 0)
          // round length: setting-dependent in the original (not extracted yet)
    float baseScale = 1.0f;                      // GA_OnGameFlag speed-option multiplier (0.25 with the option unset)
    float charaSpeed = 1.0f;                     // GA_SetCharaSpeed (events scale cat and mouse together); base speeds 1.0 / 1.5
    int event = -1, eventLeft = 0; bool over = false;
    int rankOf(int p) const { return rank_[p]; }
    bool rotateOwn = false;                      // true: re-placing on your own arrow rotates it (the flagged branch of FUN_0002859c)
    bool rouletteEnabled = true;                 // test harness: the emulated original rolls only under conditions not yet understood (see docs)
    bool genFirst = true;                        // generator task runs before the entity tasks (measured: 26/26 battles identical)
    // CPU players (Android CT_*): level 0..3 or 4 = chosen from time and player; -1 = human
    CpuEnv cpuEnv; CpuLcg cpuLcg; CpuPlayer cpu[4]; int cpuLevel[4] = {-1, -1, -1, -1}; bool cpuFirst = true, cpuReverse = false;
    struct Put { int frame, player, x, y, dir; }; std::vector<Put> cpuPuts;
    void setCpu(int p, int level) { cpuLevel[p] = level; }
    bool rouletteManager = true;                 // false: emulated-original harness never starts the roulette manager (table of zeros)
    int gtOff = 0; int fixedGameTime = -1, fixedBcd = -1;   // test harness: the emulated original never advances TI_GetGameTime / the BCD timer (both 0)
    std::function<void(int)> sfx;                // sound hook: ChuSECall ids (0x13 refused, 1 arrow placed, 6 mouse home, 7 cat in rocket, 10 roulette)
    int localPlayer = 0;
    int activeEventKind() const { return evs_.empty() ? -1 : evs_.back().kind; }   // roulette outcome (0..7) of the running event, or -1 (the original picks the BGM from it: FUN_0003c56c)
    bool rollPending() const { return roll_.active; }
    bool debug = false;
    int cursorLock = 0;                          // frames cursors stay locked (Cat Attack)
    std::vector<int> lastRoll;
    void start(const Stage& st, uint32_t seed) {
        sim.battle = true; sim.trace = debug; sim.load(st);
        std::vector<GenCell> cells; for (auto& g : sim.gens) cells.push_back({g.x, g.y, g.dir});
        for (auto& r : slot_) for (int& v : r) v = -1; for (int& v : ring_) v = 0;
        gen.reset(new Generator(cells, seed)); sim.rnd = [this]() { return gen->rng().next(); }; if (rouletteManager) roulette.reset(new Roulette(gen->rng())); else roulette.reset(new Roulette());   // RL_StartRoulette4Manager draws 128 numbers from the shared stream spawned_ = 0; lastRoll.clear();
        frame = 0; over = false; event = -1; eventLeft = 0; charaSpeed = 1.0f; applySpeed();
        clock = 0; score = Scoreboard(); for (int& r : rank_) r = 0; roll_ = Roll(); evs_.clear(); lastRoller_ = 0; pendingRoll_ = -1; cpuPuts.clear(); cpuLcg.state = (uint32_t)cpuEnv.globalTime;
        cpuEnv.sim = &sim; cpuEnv.gameType = 0;
        for (int p = 0; p < 4; p++) { cpuEnv.rocketX[p] = sim.rocketPos[p][0]; cpuEnv.rocketY[p] = sim.rocketPos[p][1]; }
        cpuEnv.rank = [this](int p) { return rankOf(p); };
        cpuEnv.cursorFree = [this](int) { return cursorLock <= 0; };
        cpuEnv.putArrow = [this](int pl, int x, int y, int d) { cpuPuts.push_back({frame, pl, x, y, d}); placeArrow(pl, x, y, d); };
        { int nb = 4; for (int p = 0; p < 4; p++) if (cpuLevel[p] >= 0) nb++; sim.occupyBase(nb); }   // manager tasks (arrows, roulette monitor, rockets, generator) + one task per CPU
        for (int p = 0; p < 4; p++) if (cpuLevel[p] >= 0) cpu[p].start(cpuEnv, p, cpuLevel[p]);
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
        if (pendingRoll_ >= 0) { int pr = pendingRoll_; pendingRoll_ = -1; startRoulette(pr); }
        for (auto& a : sim.arrows) if (a.live && a.ttl > 0 && --a.ttl == 0) { a.live = false; sim.refreshCell(a.x, a.y); }
        if (cursorLock > 0) cursorLock--;
        if (genFirst) { gen->frame(frame); spawnPending(true); }
        if (cpuFirst) runCpu();
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
    void applySpeed() { sim.catSpeed = baseScale * charaSpeed; sim.mouseSpeed = 1.5f * baseScale * charaSpeed; }
    void spawnPending(bool fresh) { for (size_t i = spawned_; i < gen->spawns.size(); i++) { const Spawn& s = gen->spawns[i]; sim.spawn(!s.cat, s.mouseType, s.x, s.y, s.dir, fresh); } spawned_ = gen->spawns.size(); }
    void runCpu() { if (cpuReverse) { for (int p = 3; p >= 0; p--) if (cpuLevel[p] >= 0) cpu[p].step(cpuEnv, cpuLcg); } else for (int p = 0; p < 4; p++) if (cpuLevel[p] >= 0) cpu[p].step(cpuEnv, cpuLcg); }
    void handle(const Event& e) {
        if (debug) printf("f%d event kind %d player %d type %d\n", frame, (int)e.kind, e.player, e.type);
        switch (e.kind) {
        case Event::MouseRocket: {
            static const int value[3] = {1, 50, 1};
            score.add(e.player, value[e.type]); updateRanks(); if (sfx) sfx(6); gen->mice--; if (e.type == 1) gen->cnt1--;
            if (e.type == 2) { gen->cnt2--; if (rouletteEnabled) pendingRoll_ = e.player; }     // RL_RollRoulette4 runs when the mouse task is destroyed: one frame later
            break; }
        case Event::MouseEaten: case Event::MouseHole:
            gen->mice--; if (e.type == 1) gen->cnt1--; if (e.type == 2) gen->cnt2--; break;
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
    struct Ev { int kind, state, count, limit; int rollerPlayer; int slot; };
    std::vector<Ev> evs_;
    void startRoulette(int p) {
        if (roll_.active) return;
        int rem = std::max(0, (roundFrames - clock) / 60);
        unsigned bcd = (unsigned)(((rem / 60) << 8) | (((rem % 60) / 10) << 4) | (rem % 10));   // minutes:seconds in BCD (TI_GetBCDTime layout still to be confirmed)
        int out = roulette->roll(rankOf(lastRoller_), fixedBcd >= 0 ? (unsigned)fixedBcd : (bcd << 8), fixedGameTime >= 0 ? fixedGameTime : frame + gtOff, -1); roulette->record(out);
        if (debug) printf("ROLL f%d player %d outcome %d\n", frame, p, out);
        if (sfx) sfx(10);
        lastRoller_ = p; sim.releaseSlot(roll_.slot); roll_.slot = sim.allocSlot(-2); roll_.active = true; roll_.elapsed = -1; roll_.outcome = out; lastRoll.push_back(out);
    }
    float feverDuration() const { return 600.0f; }
    void startEvent(int out) {                                            // dispatch: the event task is created; its first exec (state 0) is next frame
        int lim = 0;
        switch (out) { case 0: lim = (int)(600.0f * 2.0f); break; case 1: lim = 599; break; case 2: case 3: lim = 479; break; case 4: lim = 179; break;
                       case 5: lim = 59; break; case 6: lim = 0; break; default: lim = 239; }
        int es = sim.allocSlot(-2);                                       // the event task is created first, then the roulette task deletes itself (0x3c6e0..0x3c6f2)
        sim.releaseSlot(roll_.slot); roll_.slot = -1;
        evs_.push_back({out, 0, 0, lim, lastRoller_, es}); event = out;
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
                case 4: for (auto& a : sim.arrows) if (a.live) { a.live = false; sim.refreshCell(a.x, a.y); } gen->flags = 0xF; break;   // Place Arrows Again
                case 5: gen->flags = 0xF; cursorLock = 1 << 30; charaSpeed = 0.0f; break;           // Everybody Move (rocket shuffle NOT ported)
                case 6: gen->flags = 0xF; cursorLock = 1 << 30; charaSpeed = 0.0f; break;           // Cat Attack (cat presents NOT ported)
                default: gen->flags = 4; gen->params().pSpawn = 0.125f; break;                     // Mouse Monopoly (mouse behaviour NOT ported)
                }
                applySpeed(); i++; continue;
            }
            e.count++;
            if (e.kind == 0 && e.count < e.limit && e.count % 16 == 0) gen->rng().next();                                // cat sound roll: consumes one random number every 16 ticks
            if (e.kind == 2 && e.count == 300) gen->flags = 0;
            if (e.kind == 0) done = e.count >= e.limit; else done = e.count > e.limit;
            if (done) {
                switch (e.kind) {
                case 0: removeGroup(2, true); gen->flags = 0; gen->catOut = false; break;
                case 1: gen->flags = 0; gen->params().pSpawn = 0.0125f; gen->catOut = false; break;
                case 2: charaSpeed = 1.0f; gen->flags = 0; break;
                case 3: charaSpeed = 1.0f; break;
                case 4: gen->flags = 0; break;
                case 5: case 6: gen->flags = 0; cursorLock = 0; charaSpeed = 1.0f; break;
                default: gen->flags = 0; gen->params().pSpawn = 0.0125f; break;
                }
                applySpeed(); sim.releaseSlot(e.slot); evs_.erase(evs_.begin() + i); if (evs_.empty()) event = -1; continue;
            }
            i++;
        }
    }
    void removeGroup(int mask, bool unregister = false) {                                          // 0x3db58: delete tasks by group (1 = mice, 2 = cats); mice decrement the generator counters
        for (auto& e : sim.ents) {
            if (!e.alive || e.done) continue;
            if (e.mouse && (mask & 1)) { e.alive = false; sim.releaseSlot(e.slot); gen->mice--; if (e.type == 1) gen->cnt1--; if (e.type == 2) gen->cnt2--; }
            else if (!e.mouse && (mask & 2)) { e.alive = false; sim.releaseSlot(e.slot); }
            if (unregister && !e.alive) e.reg = false;       // measured: tasks deleted by an event's destructor no longer feed the heat map that frame
        }
    }
    void spawnCatFever() {                                                // GE_SetCatFever: four cats, generator slots in rotation
        size_t n = sim.gens.size(); if (n == 0) return;
        size_t idx = 0; for (int k = 0; k < 4; k++) { const auto& g = sim.gens[idx % n]; sim.spawn(false, 0, g.x, g.y, g.dir); idx++; }
    }
    void updateEvent() { stepRoulette(); if (roll_.active && ++roll_.elapsed == 121) { roll_.active = false; startEvent(roll_.outcome); } }
};
} // namespace ccr
