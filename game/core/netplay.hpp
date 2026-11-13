// Deterministic lockstep netplay core (transport-agnostic: UDP sockets, WebRTC data channels or a test network all just move byte vectors).
// Every peer runs the same fixed-tick simulation; only the players' inputs travel. Inputs made at tick t take effect at t + delay, a tick runs only when every human's input for it is known,
// and every packet repeats all inputs the receiver has not acknowledged (so loss and reordering never desynchronise, they only add waiting).
#pragma once
#include <cstdint>
#include <cstring>
#include <vector>
namespace ccr {
struct NetInput { uint8_t has = 0, x = 0, y = 0, dir = 0; };       // one arrow placement per player per tick (or none)
class Lockstep {
public:
    int me = 0, players = 2, delay = 6; uint32_t tick = 0;           // tick = next tick to simulate
    std::vector<std::vector<NetInput>> known;                         // known[p][t]: p's input for tick t, contiguous from 0
    std::vector<uint32_t> peerAck;                                    // peerAck[p]: how many of MY inputs player p has confirmed
    void start(int self, int n, int inputDelay) {
        me = self; players = n; delay = inputDelay; tick = 0; known.assign(n, {}); peerAck.assign(n, 0);
        for (int p = 0; p < n; p++) for (int t = 0; t < delay; t++) known[p].push_back(NetInput());   // the first `delay` ticks carry no input from anyone
    }
    // the local player's input for the tick `delay` ahead; call once per simulated tick (has = 0 for no input)
    void localInput(const NetInput& in) { if (known[me].size() <= tick + delay) known[me].push_back(in); }
    bool ready() const { for (int p = 0; p < players; p++) if (known[p].size() <= tick) return false; return true; }
    bool needLocal() const { return known[me].size() <= tick + delay; }
    const NetInput& inputOf(int p) const { return known[p][tick]; }   // valid when ready(); apply for all players, then advance
    void advance() { tick++; }
    // ---- packets: [from u8][ack u32 = my known count of the receiver][first u32][count u8][count x 4 bytes]
    std::vector<uint8_t> makePacket(int to) const {
        std::vector<uint8_t> b; b.push_back((uint8_t)me); uint32_t ack = (uint32_t)known[to].size(), first = peerAck[to] < known[me].size() ? peerAck[to] : (uint32_t)known[me].size();
        uint32_t cnt = (uint32_t)known[me].size() - first; if (cnt > 255) cnt = 255;
        auto u32 = [&](uint32_t v) { for (int i = 0; i < 4; i++) b.push_back((uint8_t)(v >> (8 * i))); }; u32(ack); u32(first); b.push_back((uint8_t)cnt);
        for (uint32_t k = 0; k < cnt; k++) { const NetInput& in = known[me][first + k]; b.push_back(in.has); b.push_back(in.x); b.push_back(in.y); b.push_back(in.dir); }
        return b;
    }
    void receive(const std::vector<uint8_t>& b) {
        if (b.size() < 10) return; int from = b[0]; if (from < 0 || from >= players || from == me) return;
        auto u32 = [&](size_t o) { uint32_t v = 0; for (int i = 0; i < 4; i++) v |= (uint32_t)b[o + i] << (8 * i); return v; };
        uint32_t ack = u32(1), first = u32(5); uint32_t cnt = b[9]; if (b.size() < 10 + cnt * 4) return;
        if (ack > peerAck[from]) peerAck[from] = ack;
        for (uint32_t k = 0; k < cnt; k++) { uint32_t t = first + k; if (t != known[from].size()) continue;       // only the next contiguous tick is accepted
            NetInput in; in.has = b[10 + 4 * k]; in.x = b[11 + 4 * k]; in.y = b[12 + 4 * k]; in.dir = b[13 + 4 * k]; known[from].push_back(in); }
    }
};
} // namespace ccr
