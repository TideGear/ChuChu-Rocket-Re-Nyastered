// Battle-mode mouse/cat generators (original GE_Generator4Exe). Verified against the original's spawn logs (tests/gen_test.cpp).
#pragma once
#include "rng.hpp"
#include <vector>
namespace ccr {
struct GenCell { int x, y, dir; };
struct Spawn { int frame; bool cat; int x, y, dir, mouseType; };
struct GenParams {                       // 7-word block filled by GE_StartGenerator4Manager (values seen in free-for-all battle)
    int capMice = 100, capSpecial1 = 2, capSpecial2 = 1;
    float pSpawn = 0.0125f, pSpecial1 = 0.01f, pSpecial2 = 0.1f, pCat = 0.05f;
};
class Generator {
public:
    Generator(std::vector<GenCell> cells, uint32_t seed, GenParams p = {}) : cells_(std::move(cells)), rng_(seed), p_(p) {}
    uint32_t flags = 0;                  // GE_SetProhibitGenerator mask: 1 no normal mice, 2 no special 1, 4 no special 2, 8 no cats
    int mice = 0, cnt1 = 0, cnt2 = 0;    // alive counts per mouse type (GE_MouseCountUp/Down index word type + 6 of the manager block): mice = normal mice only, the one the cap check reads
    bool catOut = false;                 // cleared by GE_CatIsLost
    int spawnLag = 2;   // frames of spawns the cap check does not see (this frame included)
    int lagA_ = 0, lagB_ = 0, lagC_ = 0;            // mice spawned this frame / last frame: GE_MouseCountUp runs when the new mouse task first executes, after the generator task of the frame that created it, so the cap check does not see them yet (measured: the count block lags the spawns by one frame)
    int timer = 0;                       // frames since the last cat was lost
    std::vector<Spawn> spawns;
    GenParams& params() { return p_; }
    Rng& rng() { return rng_; }          // shared with the cat respawn (FUN_000292c0 draws from the same stream)
    void frame(int f) {
        if (lock2_ > 0) lock2_--;
        if (lock1_ > 0) lock1_--;
        lagC_ = lagB_; lagB_ = lagA_; lagA_ = 0;
        for (const GenCell& g : cells_) {
            if (!(flags & 8) && !catOut && timer > 299) { put(f, true, g, 0); catOut = true; continue; }
            if (mice - lagA_ - (spawnLag >= 2 ? lagB_ : 0) - (spawnLag >= 3 ? lagC_ : 0) >= p_.capMice) break;
            float r = rng_.next();
            if (!(r < p_.pSpawn)) continue;
            float r2 = rng_.next(); float thr = p_.pSpecial1;
            if (!(flags & 2) && lock1_ == 0 && cnt1 < p_.capSpecial1 && r2 < thr) { lock1_ = 15; put(f, false, g, 1); cnt1++; continue; }
            thr = thr + p_.pSpecial2;
            if (!(flags & 4) && lock2_ == 0 && cnt2 < p_.capSpecial2 && r2 < thr) { lock2_ = 15; put(f, false, g, 2); cnt2++; continue; }
            if (!(flags & 8) && !catOut && r2 < thr + p_.pCat) { put(f, true, g, 0); catOut = true; continue; }
            if (flags & 1) continue;
            put(f, false, g, 0); mice++; lagA_++;
        }
        timer = catOut ? 0 : timer + 1;
    }
private:
    void put(int f, bool cat, const GenCell& g, int type) { spawns.push_back({f, cat, g.x, g.y, g.dir, type}); }
    std::vector<GenCell> cells_; Rng rng_; GenParams p_; int lock1_ = 0, lock2_ = 0;
};
} // namespace ccr
