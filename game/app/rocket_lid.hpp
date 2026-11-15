#pragma once

#include <algorithm>
#include <cmath>

struct RocketLid {
    int phase = 0, count = 0, angle = 0;
    float openness = 0.0f;

    // HD 1.0 RO_FutaOpenExec after puzzle completion or battle round end.
    void tick(int cellX, int cellY, unsigned globalTime) {
        switch (phase) {
        case 0: {
            angle += 0x200;
            if (angle >= 0x4000) phase = 1;
            const float radians = static_cast<float>(angle * 6.283184 / 65536.0);
            openness = static_cast<float>(std::sin(static_cast<double>(radians)));
            break;
        }
        case 1:
            if (++count == 120) phase = ((globalTime + cellX + 12 * cellY) & 255) == 0 ? 3 : 2;
            break;
        case 2:
            openness = std::max(0.0f, openness - 0.005f);
            break;
        case 3:
            openness -= 0.005f;
            if (openness < 0.5f) { count = 0; phase = 4; }
            break;
        case 4:
            openness = 0.5f - static_cast<float>(++count & 15) * 0.006666667f;
            if (count == 61) { count = 0; phase = 5; }
            break;
        case 5:
            if (++count == 61) phase = 6;
            break;
        case 6:
            openness += 0.01f;
            if (openness >= 0.8f) phase = 2;
            break;
        }
    }
};

struct RocketLidImage {
    int image, frame, flags;
    float x, y;
};

// HD 1.0 getFutaType and RO_DrawRocketFuta2D, shared-screen primary image.
// Glow, flash visibility, and the optional front wall redraw are separate calls.
inline RocketLidImage rocketLidImage(int player, bool team, int cellX, int cellY,
                                    float openness, float worldX, float worldZ,
                                    float scale, float originX, float originY) {
    constexpr int direction[] = {1, 0, 1, 3, 2, 3, 5, 4, 5};
    constexpr float xOffset[] = {2, 2, 1, 2, 2, 0, 2, 2, 1};
    constexpr float yOffset[] = {2, 2, 2, 1, 1, 0, 0, 0, 0};
    const int region = cellY / 3 * 3 + cellX / 4;
    const int frame = direction[region] * 7 + std::min(6, static_cast<int>(openness * 6.0f));
    return {team ? 0x5a + (player & 1) : 0x56 + player, frame, cellX < 4 ? 2 : 0,
            worldX * scale + originX + xOffset[region], worldZ * scale + originY + yOffset[region]};
}
