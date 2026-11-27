#include "../core/audio_mix.hpp"
#include <cstdint>
#include <cstdio>

int main() {
    const int16_t music[] = {1200, -400, -32768, 32767};
    int16_t output[4] = {music[0], music[1], music[2], music[3]};
    const int16_t centeredSfx[] = {800, 800, 2000, 2000};
    ccr::mixSoundVoice(output, centeredSfx, 2, 255, true);
    const int16_t expectedMono[] = {2000, 400, -30768, 32767};
    for (int i = 0; i < 4; ++i) {
        if (output[i] != expectedMono[i]) {
            std::printf("mono voice sample %d: expected %d, got %d\n", i, expectedMono[i], output[i]);
            return 1;
        }
    }

    int16_t stereoOutput[] = {music[0], music[1], 0, 0};
    const int16_t pannedSfx[] = {1000, -1000};
    ccr::mixSoundVoice(stereoOutput, pannedSfx, 1, 255, false);
    if (stereoOutput[0] != 2200 || stereoOutput[1] != -1400) {
        std::puts("stereo voice pan was not preserved");
        return 1;
    }
    std::puts("Dreamcast mono effect fold preserves stereo CDDA and mono voice output");
    return 0;
}
