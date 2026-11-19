// Original engine RNG (BHLib_SeedRNG / BHLib_GetRandomNumber / njRandom): MT19937 with the old multiplicative seeding.
#pragma once
#include <cstdint>
namespace ccr {
inline unsigned long long g_rngDraws = 0;   // verification only: total BHLib_GetRandomNumber-equivalent draws
class Rng {
public:
    explicit Rng(uint32_t seed = 1) { seedWith(seed); }
    void seedWith(uint32_t seed) {
        uint32_t s = seed | 1u; mt_[0] = s;
        for (int i = 1; i < 624; i++) { s = 69069u * s; mt_[i] = s; }
        idx_ = 624;
    }
    uint32_t u32() {
        g_rngDraws++;
        if (idx_ >= 624) twist();
        uint32_t y = mt_[idx_++];
        y ^= y >> 11; y ^= (y << 7) & 0x9d2c5680u; y ^= (y << 15) & 0xefc60000u; y ^= y >> 18;
        return y;
    }
    float next() {   // njRandom: raw / 2^32 in float32; Dreamcast mode: the executable's rand() at 0x8c060e2c, state at 0x8c0d2184
        if (dc_) { g_rngDraws++; dcState_ = dcState_ * 1103515245u + 12345u; return (float)((dcState_ >> 16) & 0x7fffu) * (1.0f / 32768.0f); }
        return (float)u32() * (1.0f / 4294967296.0f);
    }
    // Dreamcast Battle spawn draws come from rand() (an LCG), not the mobile Mersenne Twister: verified on 314 of 315 Flycast frames of a live stage-0 battle (the state advances 4 steps per
    // frame for four generators, 5 when one passes the 0.0125 test and draws a second number). The attract demo seeds it with srand(0xdead0cab).
    uint32_t dreamcastState() const { return dcState_; }   // read-only Flycast stream comparison
    void seedDreamcast(uint32_t seed) { dc_ = true; dcState_ = seed; }
private:
    void twist() {
        for (int k = 0; k < 624; k++) {
            uint32_t y = (mt_[k] & 0x80000000u) | (mt_[(k + 1) % 624] & 0x7fffffffu);
            mt_[k] = mt_[(k + 397) % 624] ^ (y >> 1) ^ ((y & 1u) ? 0x9908b0dfu : 0u);
        }
        idx_ = 0;
    }
    uint32_t mt_[624]; int idx_; bool dc_ = false; uint32_t dcState_ = 0;
};
} // namespace ccr
