// Original engine RNG (BHLib_SeedRNG / BHLib_GetRandomNumber / njRandom): MT19937 with the old multiplicative seeding.
#pragma once
#include <cstdint>
namespace ccr {
class Rng {
public:
    explicit Rng(uint32_t seed = 1) { seedWith(seed); }
    void seedWith(uint32_t seed) {
        uint32_t s = seed | 1u; mt_[0] = s;
        for (int i = 1; i < 624; i++) { s = 69069u * s; mt_[i] = s; }
        idx_ = 624;
    }
    uint32_t u32() {
        if (idx_ >= 624) twist();
        uint32_t y = mt_[idx_++];
        y ^= y >> 11; y ^= (y << 7) & 0x9d2c5680u; y ^= (y << 15) & 0xefc60000u; y ^= y >> 18;
        return y;
    }
    float next() { return (float)u32() * (1.0f / 4294967296.0f); }     // njRandom: raw / 2^32 in float32
private:
    void twist() {
        for (int k = 0; k < 624; k++) {
            uint32_t y = (mt_[k] & 0x80000000u) | (mt_[(k + 1) % 624] & 0x7fffffffu);
            mt_[k] = mt_[(k + 397) % 624] ^ (y >> 1) ^ ((y & 1u) ? 0x9908b0dfu : 0u);
        }
        idx_ = 0;
    }
    uint32_t mt_[624]; int idx_;
};
} // namespace ccr
