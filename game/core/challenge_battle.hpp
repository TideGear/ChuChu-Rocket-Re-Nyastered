// Stage Challenge, battle-engine stage types 3 and 4 (stage index mod 5, not the last stage): the original's ChallengeLoop phase machine (same timings as core/challenge.hpp)
// on top of BattleGame. Checked against the emulated original (docs/roadmap.md, 2026-11-16):
//  type 3: generators with mask 6 and spawn probability 0.075 (GE_StartGenerator4Manager in Challenge mode), character speed scale 1.0, no computer players;
//          success when the player's score reaches 100.
//  type 4: team battle, generators prohibited (mask 0xf), four cats at the generator cells (GE_SetCatFever), computer players 1 and 3 (the second team) at level 0
//          with GA_GetGameType 2; they run from the first frame of the stage, through the intro, so the first arrows come at the original's frames. The two team
//          counters (score words 12 and 13, 20 each) drop by one when a cat enters a rocket of that team; the player loses when the first reaches 0 and wins when
//          the second does (the failure phase shows one frame later).
#pragma once
#include "battle.hpp"
namespace ccr {
class ChallengeBattleGame {
public:
    static constexpr int kIntroFrames = 362, kCountdownFrames = 108, kLimitTicks = 1800, kSuccessFrames = 210;
    enum Phase { Intro = 1, Countdown = 2, Play = 3, Success = 4, Result = 5, Failure = 6 };
    BattleGame game;
    int stage = 0, type = 0, phase = Intro, phaseFrame = 0, playTick = 0;
    const char* failReason = nullptr;
    static bool supports(int stageIndex) { return stageIndex == 24 || stageIndex % 5 == 3 || stageIndex % 5 == 4; }
    int teamScore(int t) const { return game.score.team[t]; }   // stage 24 words 8 and 9
    void start(const Stage& st, int stageIndex, uint32_t seed) {
        stage = stageIndex; type = stageIndex == 24 ? 5 : stageIndex % 5; limit_ = type == 5 ? 3600 : kLimitTicks; phase = Intro; phaseFrame = 0; playTick = 0; failReason = nullptr; decided_ = false;
        game = BattleGame(); game.roundFrames = type == 5 ? 3600 : 1 << 30; game.baseScale = 1.0f; game.rouletteEnabled = type == 5; game.rouletteManager = type == 5; if (type == 5) { game.fixedGameTime = 0; game.freezeOnRoll = true; game.cpuRunsOnFreeze = true; game.ffaShuffle = true; game.catManiaLimit = 601; }   // ChallengeLoop never advances TI_GetGameTime (only EditplayLoop and the battle loops call TI_CountUpGameTimer)
        if (type == 4) { game.cpuLevel[1] = game.cpuLevel[3] = 0; }
        if (type == 5) { game.cpuLevel[1] = game.cpuLevel[3] = 3; }
        game.start(st, seed);
        if (type == 3) { game.gen->flags = 6; game.gen->params().pSpawn = 0.075f; }
        else if (type == 5) { game.teamMode = true; game.cpuEnv.gameType = 2; game.preRollCpu(1); }
        else { game.teamMode = true; game.cpuEnv.gameType = 2; game.gen->flags = 0xF; game.startCatFever(); game.preRollCpu(1); }   // the frame-0 call of the original's loop
    }
    void skipIntro() { if (phase == Intro) { phase = Countdown; phaseFrame = 0; } }
    bool placeArrow(int x, int y, int dir) { return phase == Play && game.placeArrow(0, x, y, dir); }
    int secondsLeft() const { return type == 5 ? (limit_ - game.clock) / 60 : (limit_ - playTick) / 60; }   // the one minute timer stops while the roulette runs
    int clearSeconds() const { return (type == 5 ? 60 : 30) - secondsLeft(); }   // Data::clearChallenge stores limit minus the whole seconds left
    int ownTeam() const { return game.score.catCounter[0]; }
    int enemyTeam() const { return game.score.catCounter[1]; }
    int playerScore() const { return game.score.player[0]; }
    void tick() {
        ++phaseFrame;
        switch (phase) {
        case Intro: if (type >= 4) game.preRollCpu(1); if (phaseFrame >= kIntroFrames) { phase = Countdown; phaseFrame = 0; } break;
        case Countdown: if (type >= 4 && phaseFrame < kCountdownFrames) game.preRollCpu(1); if (phaseFrame >= kCountdownFrames) { phase = Play; phaseFrame = 0; playFrame(); } break;
        case Play: playFrame(); break;
        case Success: if (phaseFrame >= kSuccessFrames) { phase = Result; phaseFrame = 0; } break;
        default: break;
        }
    }
private:
    void playFrame() {
        if (decided_) { phase = decidedPhase_; phaseFrame = 0; decided_ = false; return; }   // the outcome shows one frame after the check that found it
        ++playTick;
        game.tick();
        if (type == 5) {
            if (teamScore(1) - teamScore(0) >= 100) { failReason = "the other team leads by 100"; decided_ = true; decidedPhase_ = Failure; return; }
            if (game.over) { if (teamScore(0) > teamScore(1)) { decided_ = true; decidedPhase_ = Success; } else { failReason = "time out"; decided_ = true; decidedPhase_ = Failure; } }
            return;
        }
        if (type == 3) { if (playerScore() >= 100) { decided_ = true; decidedPhase_ = Success; return; } }
        else {
            if (ownTeam() == 0) { failReason = "your team's cats ran out"; decided_ = true; decidedPhase_ = Failure; return; }
            if (enemyTeam() == 0) { decided_ = true; decidedPhase_ = Success; return; }
        }
        if (playTick >= kLimitTicks) {
            if (type == 4 && ownTeam() > enemyTeam()) { decided_ = true; decidedPhase_ = Success; }   // time out: success if +0x30 is greater than +0x34
            else { failReason = "time out"; decided_ = true; decidedPhase_ = Failure; }
        }
    }
    int limit_ = kLimitTicks; bool decided_ = false; int decidedPhase_ = Failure;
};
} // namespace ccr
