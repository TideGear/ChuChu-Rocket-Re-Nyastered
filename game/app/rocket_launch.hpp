#pragma once

#include <algorithm>
#include <vector>

struct RocketSmoke {
    float height;
    int tickCount = -1;

    void tick() { ++tickCount; }
    bool visible() const { return tickCount >= 0 && tickCount < 30; }
};

struct RocketLaunch {
    float height = 0;
    std::vector<RocketSmoke> smoke;

    bool visible() const { return height <= 200.0f; }

    // RO_GoGoRocketExec creates smoke at the old height. Its task first
    // executes and submits a draw on the following tick.
    void tick(unsigned globalTime) {
        for (auto& puff : smoke) puff.tick();
        smoke.erase(std::remove_if(smoke.begin(), smoke.end(),
            [](const RocketSmoke& puff) { return !puff.visible(); }), smoke.end());
        if (!visible()) return;
        if ((globalTime & 7) == 0) smoke.push_back({height});
        height += 1.0f;
    }
};

struct RocketLaunchImage {
    int depth, image, frame, alpha;
    float x, y, scale;
};

inline RocketLaunchImage rocketLaunchImage(int player, bool team, float worldX, float worldZ,
                                           float height, float fieldScale, float originX, float originY) {
    constexpr int playerImage[] = {0x7a, 0x7d, 0x7c, 0x7b};
    return {std::max(-64, static_cast<int>(worldZ + height)),
            team ? 0x7e + (player & 1) : playerImage[player], 0, 255,
            worldX * fieldScale + originX, worldZ * fieldScale + originY - height,
            static_cast<float>((1.0f + height / 120.0f) * 0.4)};
}

inline RocketLaunchImage rocketSmokeImage(float worldX, float worldZ, const RocketSmoke& smoke,
                                          float fieldScale, float originX, float originY) {
    return {std::max(-64, static_cast<int>(worldZ + smoke.height - 1.0f)),
            0x92, smoke.tickCount / 3, 222,
            worldX * fieldScale + originX, worldZ * fieldScale + originY - smoke.height, 3.0f};
}
