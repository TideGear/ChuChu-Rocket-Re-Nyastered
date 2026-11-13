// Battle scoreboard (original SC_AddScore / SC_CatHasCome); verified against the original (tests/score_test.cpp).
#pragma once
namespace ccr {
class Scoreboard {
public:
    static constexpr int kMax = 999;
    int player[4] = {0, 0, 0, 0};
    int team[2] = {0, 0};
    int catCounter[2] = {20, 20};            // per team parity; decremented (min 0) whenever a cat enters a rocket
    void add(int p, int delta) {             // SC_AddScore
        player[p] += delta; if (player[p] < 0) player[p] = 0;
        team[p & 1] += delta; if (team[p & 1] < 0) team[p & 1] = 0;
        if (player[p] > kMax) player[p] = kMax;
        if (team[p & 1] > kMax) team[p & 1] = kMax;
    }
    void catHasCome(int p) {                 // SC_CatHasCome: the cat takes a third (rounded up) of the player's and the team's score
        player[p] += (player[p] + 2) / -3; if (player[p] < 0) player[p] = 0;
        team[p & 1] += (team[p & 1] + 2) / -3; if (team[p & 1] < 0) team[p & 1] = 0;
        if (--catCounter[p & 1] < 0) catCounter[p & 1] = 0;
    }
    int catDemerit(int p, bool teamMode) const { return ((teamMode ? team[p & 1] : player[p]) + 2) / 3; }   // SC_GetCatDemerit
};
} // namespace ccr
