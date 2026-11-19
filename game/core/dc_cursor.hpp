// Dreamcast human cursor: FUN_8c014220 / 8c0143f0 / 8c016442.
#pragma once
#include <algorithm>
#include <cmath>
#include <cstdint>
namespace ccr {
struct DcCursor {
    float x = 0, y = 0;
    int targetX = -1, targetY = -1;
    int cellX() const { return std::clamp(static_cast<int>(x / 15.0f), 0, 11); }
    int cellY() const { return std::clamp(static_cast<int>(y / 15.0f), 0, 8); }
    void tick(uint32_t held, int stickX, int stickY) {
        const auto target = [&](int& t, int cell, int limit, uint32_t positive, uint32_t negative) {
            if (t != -1) return;
            if (held & positive) { t = cell + 1; if (t >= limit) t = -1; }
            if (held & negative) { t = cell - 1; if (t < 0) t = -1; }
        };
        target(targetX, cellX(), 12, 0x80, 0x40);
        target(targetY, cellY(), 9, 0x20, 0x10);
        const auto delta = [](int stick) {
            const float d = static_cast<float>(stick * 256) * 0.00009f; // literal 0x38bcbe62
            return std::fabs(d) < 0.09f ? 0.0f : d;
        };
        const float dx = delta(stickX), dy = delta(stickY);
        if (dx * dx + dy * dy != 0.0f) {
            x += dx; y += dy; targetX = targetY = -1;
        }
        const auto step = [](float& p, int& t) {
            if (t == -1) return;
            const float center = (static_cast<float>(t) + 0.5f) * 15.0f;
            const float low = center + -1.8f;
            if (p < low) p += 1.8f;
            else if (p > center + 1.8f) p -= 1.8f;
            else t = -1;
        };
        step(x, targetX); step(y, targetY);
        x = std::clamp(x, 0.0f, 180.0f);
        y = std::clamp(y, 0.0f, 135.0f);
    }
};
} // namespace ccr
