// Lockstep over REAL UDP sockets on loopback (127.0.0.1 only: nothing leaves the machine): N peers, one socket each, each running its own BattleGame.
// All peers must produce the same per-tick state hash. usage: udp_netplay_test <battle_stages.bin> [peers]
#include "../core/battle.hpp"
#include "../core/netplay.hpp"
#include "../core/udp.hpp"
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <random>
#include <thread>
using namespace ccr;
static uint64_t mix(uint64_t h, uint64_t v) { h ^= v + 0x9e3779b97f4a7c15ull + (h << 6) + (h >> 2); return h; }
static uint64_t hashState(const BattleGame& g) { uint64_t h = 1469598103934665603ull; for (auto& e : g.sim.ents) { uint32_t a, b; memcpy(&a, &e.x, 4); memcpy(&b, &e.z, 4); h = mix(h, a); h = mix(h, b); } for (int p = 0; p < 4; p++) h = mix(h, (uint64_t)g.score.player[p]); return mix(h, g.sim.ents.size()); }
int main(int argc, char** argv) {
    FILE* f = fopen(argc > 1 ? argv[1] : "../local/cache/assets/battle_stages.bin", "rb"); if (!f) { printf("cannot open stages\n"); return 2; }
    int peers = argc > 2 ? atoi(argv[2]) : 3; uint32_t n; if (fread(&n, 4, 1, f) != 1) return 2;
    uint8_t h[4]; Stage st; uint8_t walls[237], title[32];
    if (fread(h, 1, 4, f) != 4 || fread(st.tiles, 1, 108, f) != 108 || fread(walls, 1, 237, f) != 237 || fread(title, 1, 32, f) != 32) return 2;
    for (int r = 0; r < 10; r++) for (int c = 0; c < 12; c++) st.hw[r * 12 + c] = walls[25 * r + c];
    for (int r = 0; r < 9; r++) for (int c = 0; c < 13; c++) st.vw[r * 13 + c] = walls[25 * r + 12 + c];
    const int TICKS = 60 * 60; std::mt19937 act(5);
    std::vector<UdpSocket> sock(peers); std::vector<UdpAddr> addr(peers);
    for (int p = 0; p < peers; p++) { uint16_t port = sock[p].open("127.0.0.1", 0); if (!port) { printf("socket open failed\n"); return 2; } addr[p] = makeAddr("127.0.0.1", port); }
    std::vector<BattleGame> g(peers); std::vector<Lockstep> ls(peers); std::vector<std::vector<uint64_t>> hash(peers);
    for (int p = 0; p < peers; p++) { for (int q = 0; q < 4; q++) g[p].setCpu(q, q < peers ? -1 : 3); g[p].rouletteManager = true; g[p].roundFrames = TICKS; g[p].start(st, 99); ls[p].start(p, peers, 6); }
    long iterations = 0, packets = 0; auto t0 = std::chrono::steady_clock::now();
    for (;; iterations++) {
        bool done = true;
        for (int p = 0; p < peers; p++) {
            std::vector<uint8_t> d; while (sock[p].recv(d)) ls[p].receive(d);
            if ((int)ls[p].tick < TICKS) {
                if (ls[p].needLocal()) { NetInput in; if (act() % 40 == 0) { in.has = 1; in.x = (uint8_t)(act() % 12); in.y = (uint8_t)(act() % 9); in.dir = (uint8_t)(act() & 3); } ls[p].localInput(in); }
                if (ls[p].ready()) { for (int q = 0; q < peers; q++) { const NetInput& in = ls[p].inputOf(q); if (in.has) g[p].placeArrow(q, in.x, in.y, in.dir); } ls[p].advance(); g[p].tick(); hash[p].push_back(hashState(g[p])); }
            }
            if ((int)ls[p].tick < TICKS) done = false;
            for (int q = 0; q < peers; q++) if (q != p) { sock[p].send(addr[q], ls[p].makePacket(q)); packets++; }
        }
        if (done) break;
        if (iterations % 8 == 0) std::this_thread::sleep_for(std::chrono::microseconds(50));
        if (std::chrono::steady_clock::now() - t0 > std::chrono::seconds(120)) { printf("timeout\n"); return 1; }
    }
    int bad = 0; for (int p = 1; p < peers; p++) { bool same = hash[p].size() == hash[0].size(); for (size_t t = 0; same && t < hash[0].size(); t++) if (hash[p][t] != hash[0][t]) { same = false; printf("peer %d differs at tick %zu\n", p, t); } if (!same) bad++; }
    printf("udp netplay (127.0.0.1): %d peers, %d ticks, %ld iterations, %ld packets sent, %d desyncs\n", peers, TICKS, iterations, packets, bad);
    return bad ? 1 : 0;
}
