// Small output-stage helpers for the shared stereo PCM mixer.
#pragma once
#include <cstddef>
#include <cstdint>

namespace ccr {
inline int16_t clampSoundSample(int32_t sample) {
    return static_cast<int16_t>(sample < -32768 ? -32768 : sample > 32767 ? 32767 : sample);
}

// The Dreamcast mono option configures the AICA voice mixer (command 0x8a);
// CDDA music remains a separate stereo return. Fold each effect voice before
// adding it to the output instead of collapsing the already-mixed stream.
inline void mixSoundVoice(int16_t* destination, const int16_t* source, size_t frames,
                          int volume, bool monaural) {
    const float gain = static_cast<float>(volume) / 255.0f;
    for (size_t i = 0; i < frames; ++i) {
        const int32_t left = static_cast<int32_t>(source[2 * i] * gain);
        const int32_t right = static_cast<int32_t>(source[2 * i + 1] * gain);
        if (monaural) {
            const int32_t mono = (left + right) / 2;
            destination[2 * i] = clampSoundSample(static_cast<int32_t>(destination[2 * i]) + mono);
            destination[2 * i + 1] = clampSoundSample(static_cast<int32_t>(destination[2 * i + 1]) + mono);
        } else {
            destination[2 * i] = clampSoundSample(static_cast<int32_t>(destination[2 * i]) + left);
            destination[2 * i + 1] = clampSoundSample(static_cast<int32_t>(destination[2 * i + 1]) + right);
        }
    }
}
} // namespace ccr
