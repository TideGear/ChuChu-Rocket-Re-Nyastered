// Stage Challenge, puzzle-based stage types 0 to 2 (stage index mod 5): the original's ChallengeLoop (Android 0x30388) phase machine on top of the puzzle simulation,
// with the battle arrow manager. Every rule here was checked against the emulated original (docs/modes.md and docs/roadmap.md, 2026-11-16):
//  phases: 1 intro 362 frames (a tap skips it), 2 ready/go 108 frames, 3 play (the simulation ticks; frame 470 of the original is tick 1) with a 1800 tick limit,
//  4 success display 210 frames (types 0 and 1 only; type 2 goes straight to 5) then 5 result, 6 failure (restart or quit).
//  win: types 0 and 1 rocket mice == target (all mice of the board), type 2 eaten mice == target; the success phase starts one frame after the counter reaches it.
//  failure: types 0 and 1 a mouse killed or a cat in a rocket, type 2 a mouse or cat in a hole; the failure phase starts one frame after the trigger; time out detected at tick 1800 (the failure phase shows at frame 2270). Frame numbering: the original's frame 0 is the set-up call, so tick() is first called for frame 1.
//  arrows: 3 slots per player in a ring, lifetime 600 ticks, refused on rocket, hole and arrow cells; a placement registers its collision flag one tick later.
#pragma once
#include "sim.hpp"
#include <vector>
namespace ccr {
class ChallengeGame {
public:
    static constexpr int kIntroFrames = 362, kCountdownFrames = 108, kLimitTicks = 1800, kSuccessFrames = 210, kArrowSlots = 3, kArrowTtl = 600;
    enum Phase { Intro = 1, Countdown = 2, Play = 3, Success = 4, Result = 5, Failure = 6 };
    Sim sim;
    int stage = 0, type = 0, target = 0, phase = Intro, phaseFrame = 0, playTick = 0;
    const char* failReason = nullptr;
    bool supported() const { return type <= 2; }
    void start(const Stage& st, int stageIndex) {
        stage = stageIndex; type = stageIndex % 5; sim = Sim(); sim.load(st);
        target = 0; for (const auto& e : sim.ents) if (e.mouse) target++;
        phase = Intro; phaseFrame = 0; playTick = 0; failReason = nullptr; ring_ = 0; for (int& s : slot_) s = -1; pending_.clear(); ready_.clear();
    }
    void skipIntro() { if (phase == Intro) { phase = Countdown; phaseFrame = 0; } }   // flag 1 (a tap) skips the intro banner
    // Player arrow input (before the frame, as the original's touch handler does). Returns whether the arrow was accepted.
    bool placeArrow(int x, int y, int dir) {
        if (phase != Play || x < 0 || x >= 12 || y < 0 || y >= 9) return false;
        pending_.push_back({x, y, dir});   // the arrow task is created now and runs in the next frame: the whole placement (slot, cell flags, arrow) happens one tick later
        return true;
    }
    // One frame of ChallengeLoop.
    void tick() {
        ++phaseFrame;
        switch (phase) {
        case Intro: if (phaseFrame >= kIntroFrames) { phase = Countdown; phaseFrame = 0; } break;
        case Countdown: if (phaseFrame >= kCountdownFrames) { phase = Play; phaseFrame = 0; playFrame(); } break;   // the last countdown frame already runs the first play tick (measured: tick 1 is frame 470, the frame that reports phase 3)
        case Play: playFrame(); break;
        case Success: if (phaseFrame >= kSuccessFrames) { phase = Result; phaseFrame = 0; } break;
        default: break;
        }
    }
    int counter() const { return type == 2 ? sim.killedByCat : sim.saved; }
    // Data::clearChallenge(stage, BCD time left) stores limit - whole seconds left (30 s; 60 s for the last stage), the clock frozen at the tick the stage was cleared (measured: floor((1800 - tick) / 60) in the original's argument).
    int secondsLeft() const { return (kLimitTicks - playTick) / 60; }
    int clearSeconds() const { return (stage == 24 ? 60 : 30) - secondsLeft(); }
private:
    void playFrame() {
        if (decided_) { phase = decidedPhase_; phaseFrame = 0; decided_ = false; return; }   // the outcome shows one frame after the check that found it
        ++playTick;
        for (auto& a : sim.arrows) if (a.live && a.ttl > 0 && --a.ttl == 0) { a.live = false; sim.refreshCell(a.x, a.y); }
        for (const auto& p : ready_) applyPlacement(p);   // placements made before the previous frame's check register now
        ready_ = pending_; pending_.clear();
        sim.tick();
        const char* why = nullptr;
        if (type <= 1 && sim.killed > 0) why = "mouse killed";
        if (type <= 1 && !why && sim.catsInRocket > 0) why = "cat in rocket";
        if (type == 2) { if (sim.killedByHole > 0) why = "mouse in hole"; for (const auto& e : sim.ents) if (!e.mouse && e.catHoleFallTick >= 0) why = "cat in hole"; }
        if (why) { failReason = why; decided_ = true; decidedPhase_ = Failure; return; }
        if (counter() == target && target > 0) { decided_ = true; decidedPhase_ = type == 2 ? Result : Success; return; }   // type 2 goes straight to the result (measured: no 210 frame display)
        if (playTick >= kLimitTicks) { failReason = "time out"; decided_ = true; decidedPhase_ = Failure; }
    }
    int ring_ = 0, slot_[kArrowSlots] = {-1, -1, -1};
    struct Pending { int x, y, dir; };
    std::vector<Pending> pending_, ready_;
    void applyPlacement(const Pending& p) {
        const uint32_t f = sim.coll[p.y][p.x];
        if (f & (kArrow | kRocket | kHole)) return;   // refused: rocket, hole or an arrow already there
        const int old = slot_[ring_];
        if (old >= 0 && sim.arrows[old].live) { sim.arrows[old].live = false; sim.refreshCell(sim.arrows[old].x, sim.arrows[old].y); }
        sim.arrows.push_back({p.x, p.y, p.dir, 0, true, 0, kArrowTtl}); sim.refreshCell(p.x, p.y);
        slot_[ring_] = static_cast<int>(sim.arrows.size()) - 1; ring_ = (ring_ + 1) % kArrowSlots;
    }
    bool decided_ = false; int decidedPhase_ = Failure;
};
} // namespace ccr
