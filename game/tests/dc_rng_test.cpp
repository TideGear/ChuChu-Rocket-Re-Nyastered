// The Dreamcast rand() model (game/core/rng.hpp seedDreamcast) against states read from the real game (Flycast, 4-generator stage-0 Battle, per-frame watch of RAM 0x8c0d2184).
// Each row: frame, state before, state after the frame, and the number of rand() calls the game made that frame (4 = one test draw per generator, 5 = one spawn, 8 = two).
// The model must reach the "after" state in exactly that many steps and return (state >> 16) & 0x7fff / 32768 each time.
#include "../core/battle.hpp"
#include <cstdio>
struct Row { int frame; uint32_t before, after; int draws; };
static const Row kRows[] = {
    {3000, 0xe27bfaccu, 0xead3f7b8u, 4},
    {3001, 0xead3f7b8u, 0x74acd764u, 4},
    {3002, 0x74acd764u, 0x591205d0u, 4},
    {3003, 0x591205d0u, 0xf0687985u, 5},
    {3004, 0xf0687985u, 0x20bc2901u, 4},
    {3005, 0x20bc2901u, 0x3f41543du, 4},
    {3037, 0x62821967u, 0x0aeece5fu, 8},
    {3125, 0x98ba715du, 0x687f9aa0u, 3},
    {3190, 0x7508fd59u, 0xb972c71bu, 6},
    {3191, 0xb972c71bu, 0xd9375ed0u, 9}
};
int main() {
    int bad = 0;
    for (const Row& row : kRows) {
        ccr::Rng r; r.seedDreamcast(row.before);
        uint32_t state = row.before;
        for (int i = 0; i < row.draws; ++i) {
            state = state * 1103515245u + 12345u;
            const float expected = (float)((state >> 16) & 0x7fffu) * (1.0f / 32768.0f);
            if (r.next() != expected) ++bad;
        }
        if (state != row.after) { ++bad; printf("frame %d: state mismatch\n", row.frame); }
    }
    // Reusing a BattleGame must reset the spawn-log cursor and both roulette-manager paths.
    for (bool dc : {false, true}) for (bool manager : {false, true}) {
        ccr::Stage st{}; st.tiles[13] = 5;
        ccr::BattleGame g; g.dreamcastRng = dc; g.rouletteManager = manager;
        g.generatorParams.pSpawn = 1.0f;
        g.generatorParams.pSpecial1 = g.generatorParams.pSpecial2 = g.generatorParams.pCat = 0.0f;
        for (int run = 0; run < 2; ++run) {
            g.lastRoll.push_back(7); g.start(st, 777); g.tick();
            if (g.sim.ents.size() != 1 || !g.lastRoll.empty() || !g.roulette) {
                ++bad; printf("battle restart mismatch: dc=%d manager=%d run=%d\n", dc, manager, run);
            }
        }
    }
    printf("dreamcast rand model and battle restart: %d mismatches over %zu recorded frames and 8 starts\n", bad, sizeof kRows / sizeof kRows[0]);
    return bad ? 1 : 0;
}
