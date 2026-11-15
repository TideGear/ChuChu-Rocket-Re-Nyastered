#pragma once

#include <cmath>
#include <cstddef>

namespace ccr {
struct MouseGhost {
    int slot;
    std::size_t submission;
    float x, z;
    int angle;
    int age = 0;

    // HD 1.0 MO_ObakeExec, default overhead deformation.
    void tick() {
        if (++age >= 48) return;
        const auto radians = [](int a) {
            return static_cast<float>((a & 0xffff) * 6.283184 / 65536.0);
        };
        z -= 0.17675f;
        x += -0.5f * std::sin(radians(angle));
        z += 0.5f * std::cos(radians(angle));
        angle += static_cast<int>(2048.0f * std::sin(radians(age << 12)));
    }

    int image() const {
        if (angle > 24576 && angle <= 40960) return 45;
        return (angle > 8192 && angle <= 57344) ? 44 : 46;
    }
    int flags() const { return image() == 44 && angle < 32768 ? 2 : 0; }
    float scale() const {
        const float time = age * 0.020833334f;
        return time > 0.8f ? (1.0f - time) * 5.0000005f : 1.0f;
    }
};
}
