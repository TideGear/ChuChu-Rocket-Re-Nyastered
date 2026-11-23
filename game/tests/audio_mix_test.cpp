#include "../core/audio_mix.hpp"
#include <cstdint>
#include <cstdio>
#include <cstring>

int main() {
    const int16_t source[] = {1200, -400, -32768, 32767, -1001, 1000, 77, 78};
    int16_t stereo[8];
    std::memcpy(stereo, source, sizeof source);
    ccr::applySoundOutput(stereo, 4, false);
    if (std::memcmp(stereo, source, sizeof source) != 0) {
        std::puts("stereo output changed samples");
        return 1;
    }

    ccr::applySoundOutput(stereo, 4, true);
    const int16_t expected[] = {400, 400, 0, 0, 0, 0, 77, 77};
    for (int i = 0; i < 8; ++i) {
        if (stereo[i] != expected[i]) {
            std::printf("mono frame sample %d: expected %d, got %d\n", i, expected[i], stereo[i]);
            return 1;
        }
    }
    std::puts("stereo pass-through and mono fold: 4 frames passed");
    return 0;
}
