// Lockstep netplay test: 2-4 peers each run their own BattleGame (humans = peers, the rest CPU) over a simulated hostile network (loss, random latency, duplication).
// Every peer's per-tick state hash must be identical to all others, and the game must finish.
// Usage: netplay_test <battle_stages.bin> [peers] [loss%] [--inject-desync]
#include "../core/battle.hpp"
#include "../core/netplay.hpp"
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <deque>
#include <random>
using namespace ccr;
static uint64_t mix(uint64_t h, uint64_t v) { h ^= v + 0x9e3779b97f4a7c15ull + (h << 6) + (h >> 2); return h; }
static uint64_t hashState(const BattleGame& g) { uint64_t h = 1469598103934665603ull; for (auto& e : g.sim.ents) { uint32_t a, b; memcpy(&a, &e.x, 4); memcpy(&b, &e.z, 4); h = mix(h, a); h = mix(h, b); } for (int p = 0; p < 4; p++) h = mix(h, (uint64_t)g.score.player[p]); return mix(h, g.sim.ents.size()); }
struct Pkt { int due, to; std::vector<uint8_t> data; };
int main(int argc, char** argv) {
    const bool injectDesync = argc == 5 && std::strcmp(argv[4], "--inject-desync") == 0;
    if (argc > 4 && !injectDesync) return 2;
    const uint32_t desyncTick = 120;
    FILE* f = fopen(argc > 1 ? argv[1] : "../local/cache/assets/battle_stages.bin", "rb"); if (!f) { printf("cannot open stages\n"); return 2; }
    int peers = argc > 2 ? atoi(argv[2]) : 2; int loss = argc > 3 ? atoi(argv[3]) : 30; uint32_t n; if (fread(&n, 4, 1, f) != 1) return 2;
    int checked = 0, bad = 0; long iterations = 0;
    for (uint32_t i = 0; i < n && checked < 5; i++) {
        uint8_t h[4]; Stage st; uint8_t walls[237], title[32];
        if (fread(h, 1, 4, f) != 4 || fread(st.tiles, 1, 108, f) != 108 || fread(walls, 1, 237, f) != 237 || fread(title, 1, 32, f) != 32) break;
        for (int r = 0; r < 10; r++) for (int c = 0; c < 12; c++) st.hw[r * 12 + c] = walls[25 * r + c];
        for (int r = 0; r < 9; r++) for (int c = 0; c < 13; c++) st.vw[r * 13 + c] = walls[25 * r + 12 + c];
        if (h[0] != 2) continue; checked++;
        const int TICKS = 60 * 60; std::mt19937 net(1000 + i), act(77 + i);
        std::vector<BattleGame> g(peers); std::vector<Lockstep> ls(peers); std::vector<std::vector<uint64_t>> hash(peers); std::deque<Pkt> wire;
        for (int p = 0; p < peers; p++) { for (int q = 0; q < 4; q++) g[p].setCpu(q, q < peers ? -1 : 3); g[p].rouletteManager = true; g[p].roundFrames = TICKS; g[p].start(st, 555 + i); ls[p].start(p, peers, 6); }
        for (int it = 0; ; it++, iterations++) {
            bool done = true;
            for (int p = 0; p < peers; p++) {
                for (size_t k = 0; k < wire.size();) { if (wire[k].to == p && wire[k].due <= it) { ls[p].receive(wire[k].data); wire.erase(wire.begin() + k); } else k++; }
                if ((int)ls[p].tick < TICKS) {
                    if (ls[p].needLocal()) { NetInput in; if (act() % 40 == 0) { in.has = 1; in.x = (uint8_t)(act() % 12); in.y = (uint8_t)(act() % 9); in.dir = (uint8_t)(act() & 3); } ls[p].localInput(in); }
                    if (ls[p].ready()) {
                        for (int q = 0; q < peers; q++) {
                            const NetInput& in = ls[p].inputOf(q);
                            if (in.has) g[p].placeArrow(q, in.x, in.y, in.dir);
                        }
                        ls[p].advance();
                        g[p].tick();
                        if (injectDesync && p == 1 && ls[p].tick == desyncTick) ++g[p].score.player[0];
                        hash[p].push_back(hashState(g[p]));
                    }
                }
                if ((int)ls[p].tick < TICKS) done = false;
                for (int q = 0; q < peers; q++) if (q != p) { int copies = (net() % 10 == 0) ? 2 : 1;
                    for (int c = 0; c < copies; c++) if ((int)(net() % 100) >= loss) wire.push_back({it + 1 + (int)(net() % 8), q, ls[p].makePacket(q)}); }
            }
            if (done) break;
            if (it > 400000) { printf("stage %u: no progress (stuck)\n", i); bad++; break; }
        }
        for (int p = 1; p < peers; p++) { bool same = hash[p].size() == hash[0].size(); for (size_t t = 0; same && t < hash[0].size(); t++) if (hash[p][t] != hash[0][t]) { same = false; printf("stage %u: peer %d differs from peer 0 at tick %zu\n", i, p, t + 1); } if (!same) bad++; }
    }
    printf("netplay: %d stages x %d peers, loss %d%% + jitter 1-8 iterations + 10%% duplication, %ld iterations, %d desyncs/stalls\n", checked, peers, loss, iterations, bad);
    return checked == 0 ? 2 : bad ? 1 : 0;
}
