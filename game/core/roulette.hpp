// Battle roulette outcome selector (original FUN_0003c2bc / RL_GetDeme). Verified against the original (tests/roulette_test.cpp).
// Weight rows are gameplay constants read from the original: 3 remaining-time buckets x 4 score ranks x 8 outcomes (row sums to 1.0; outcome 7 is the remainder).
#pragma once
#include "rng.hpp"
namespace ccr {
class Roulette {
public:
    // Fills the 128-entry threshold table with 128 consecutive njRandom() draws (RL_StartRoulette4Manager).
    Roulette() { for (int i = 0; i < 128; i++) table_[i] = 0.0f; }   // manager not started (as in the verification harness): all thresholds 0
    explicit Roulette(Rng& rng) { for (int i = 0; i < 128; i++) table_[i] = rng.next(); }
    int lastA = -1, lastB = -1;          // previous two outcomes
    // rank: score rank of the player (0..3); bcdTime: remaining time in BCD (TI_GetBCDTime); gameTime: frame counter; exclude: outcome to avoid (-1 none)
    int roll(int rank, unsigned bcdTime, int gameTime, int exclude) const {
        const float* row = kWeights[(bcdTime <= 0x2fffu ? 0 : bcdTime <= 0xffffu ? 1 : 2) * 4 + rank];
        int idx = 0;
        for (int attempt = 0; attempt < 128; attempt++) {
            float thr = table_[(gameTime + attempt) & 0x7f]; float cum = row[0]; idx = 0;
            while (!(cum >= thr)) { idx++; if (idx == 7) break; cum = cum + row[idx]; }
            if (idx == exclude) continue;
            if (idx >= 2 && idx <= 5) { if (lastA == idx) continue; return idx; }
            if (lastA != idx || lastA != lastB) return idx;
        }
        return idx;
    }
    void fillTable(float v) { for (float& t : table_) t = v; }   // test harness: constant thresholds (the emulated original's table can be written directly)
    void record(int outcome) { lastB = lastA; lastA = outcome; }
private:
    static constexpr float kWeights[12][8] = {
    {0.3499999940395355f, 0.23000000417232513f, 0.20000000298023224f, 0.05000000074505806f, 0.05000000074505806f, 0.10000000149011612f, 0.009999999776482582f, 0.009999999776482582f},   // bcd bucket A, rank 0
    {0.4099999964237213f, 0.20000000298023224f, 0.20000000298023224f, 0.05000000074505806f, 0.05000000074505806f, 0.05000000074505806f, 0.019999999552965164f, 0.019999999552965164f},   // bcd bucket A, rank 1
    {0.3400000035762787f, 0.25f, 0.20000000298023224f, 0.05000000074505806f, 0.05000000074505806f, 0.05000000074505806f, 0.029999999329447746f, 0.029999999329447746f},   // bcd bucket A, rank 2
    {0.3400000035762787f, 0.25f, 0.20000000298023224f, 0.05000000074505806f, 0.05000000074505806f, 0.05000000074505806f, 0.029999999329447746f, 0.029999999329447746f},   // bcd bucket A, rank 3
    {0.17000000178813934f, 0.25f, 0.05000000074505806f, 0.20000000298023224f, 0.15000000596046448f, 0.15000000596046448f, 0.009999999776482582f, 0.019999999552965164f},   // bcd bucket B, rank 0
    {0.15000000596046448f, 0.3499999940395355f, 0.05000000074505806f, 0.20000000298023224f, 0.10000000149011612f, 0.10000000149011612f, 0.019999999552965164f, 0.029999999329447746f},   // bcd bucket B, rank 1
    {0.15000000596046448f, 0.38999998569488525f, 0.05000000074505806f, 0.20000000298023224f, 0.07000000029802322f, 0.07000000029802322f, 0.029999999329447746f, 0.03999999910593033f},   // bcd bucket B, rank 2
    {0.10000000149011612f, 0.25f, 0.05000000074505806f, 0.20000000298023224f, 0.05000000074505806f, 0.05000000074505806f, 0.15000000596046448f, 0.15000000596046448f},   // bcd bucket B, rank 3
    {0.07999999821186066f, 0.1899999976158142f, 0.10000000149011612f, 0.10000000149011612f, 0.20000000298023224f, 0.30000001192092896f, 0.009999999776482582f, 0.019999999552965164f},   // bcd bucket C, rank 0
    {0.11999999731779099f, 0.30000001192092896f, 0.10999999940395355f, 0.10999999940395355f, 0.10999999940395355f, 0.20000000298023224f, 0.019999999552965164f, 0.029999999329447746f},   // bcd bucket C, rank 1
    {0.11999999731779099f, 0.30000001192092896f, 0.10999999940395355f, 0.10999999940395355f, 0.10999999940395355f, 0.10000000149011612f, 0.07000000029802322f, 0.07999999821186066f},   // bcd bucket C, rank 2
    {0.10999999940395355f, 0.30000001192092896f, 0.10000000149011612f, 0.10000000149011612f, 0.10000000149011612f, 0.10000000149011612f, 0.07000000029802322f, 0.11999999731779099f},   // bcd bucket C, rank 3
    };
    float table_[128];
};
} // namespace ccr
