// Small output-stage helpers for the shared stereo PCM mixer.
#pragma once
#include <cstddef>
#include <cstdint>

namespace ccr {
inline void applySoundOutput(int16_t* stereo, size_t frames, bool monaural) {
    if (!monaural) return;
    for (size_t i = 0; i < frames; ++i) {
        const int32_t mono = (static_cast<int32_t>(stereo[2 * i]) + stereo[2 * i + 1]) / 2;
        stereo[2 * i] = static_cast<int16_t>(mono);
        stereo[2 * i + 1] = static_cast<int16_t>(mono);
    }
}
} // namespace ccr
