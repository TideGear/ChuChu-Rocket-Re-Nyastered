#pragma once

#include "../core/sim.hpp"
#include <algorithm>
#include <cmath>

struct RoulettePose {
    float x, y, degrees, scale;
};

struct DcRoulettePose { float x, height, z, scale; int angle; };
// FUN_8c01d774; stopped angles at 0x8c07686c. Raw task transform before draw.
inline DcRoulettePose dreamcastRoulettePose(int tick, int rocketX, int rocketY, int outcome) {
    constexpr int angles[] = {0x4000,0x6000,0xe000,0xc000,0x2000,0,0x8000,0xa000};
    DcRoulettePose p{87.5f,25.0f,67.5f,30.0f,angles[outcome]};
    if (tick < 30) {
        p = {(rocketX + 0.5f) * 15.0f, 0, (rocketY + 0.5f) * 15.0f, 1, (tick + 1) * 0x1000};
        for (int i = 0; i < tick; ++i) {
            p.x += (87.5f - p.x) * 0.1f;
            p.height += (25.0f - p.height) * 0.1f;
            p.z += (67.5f - p.z) * 0.1f;
            p.scale += (30.0f - p.scale) * 0.5f;
        }
    } else {
        // (1 + 0.25 * FSCA(counter << 11).sin) * 30. SH-4 FSCA differs by
        // a few ULPs from host sinf; these exact results are measured at task +44.
        constexpr float pulse[] = {
            0x1.ep+4f,0x1.f7692cp+4f,0x1.06f604p+5f,0x1.11558ep+5f,
            0x1.1a6d28p+5f,0x1.21e36p+5f,0x1.276ecap+5f,0x1.2ad8dcp+5f,
            0x1.2cp+5f,0x1.2ad8dcp+5f,0x1.276ecap+5f,0x1.21e36p+5f,
            0x1.1a6d28p+5f,0x1.11558ep+5f,0x1.06f604p+5f,0x1.f7692cp+4f};
        p.scale = pulse[std::min(tick - 30, 15)];
    }
    return p;
}

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
