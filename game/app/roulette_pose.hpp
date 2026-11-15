#pragma once

#include "../core/sim.hpp"
#include <algorithm>
#include <cmath>

struct RoulettePose {
    float x, y, degrees, scale;
};

// HD 1.0 RL_RouletteExec, followed by RL_RouletteDrawPriority. The first
// visible frame is tick 0, after the task's first execution.
inline RoulettePose battleRoulettePose(int tick, int rocketX, int rocketY, int outcome,
                                      float originX, float originY, float fieldScale) {
    constexpr float targetX = 87.5f, targetY = 67.5f;
    constexpr int stoppedAngles[] = {16384, 24576, 57344, 32768, 8192, 0, 49152, 40960};
    float x = targetX, y = targetY, scale = 30.0f;
    int angle = stoppedAngles[outcome];
    if (tick < 30) {
        x = (rocketX + 0.5f) * ccr::kCell;
        y = (rocketY + 0.5f) * ccr::kCell;
        scale = 1.0f;
        for (int i = 0; i < tick; ++i) {
            x += (targetX - x) * 0.1f;
            y += (targetY - y) * 0.1f;
            scale += (30.0f - scale) * 0.5f;
        }
        angle = ((tick + 1) * 0x1000) & 0xffff;
    } else {
        const int pulseTick = std::min(tick - 30, 15);
        // CoreSettingsInit builds the original sine table with these constants.
        const float radians = static_cast<float>(pulseTick * 0x800 * 6.283184 / 65536.0);
        scale = (1.0f + 0.25f * std::sin(radians)) * 30.0f;
    }
    return {x * fieldScale + originX, y * fieldScale + originY, angle * (360.0f / 65536.0f), scale};
}
