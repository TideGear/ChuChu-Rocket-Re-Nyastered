// Compare human-cursor positions/cells with synchronous Flycast FLY_WATCH captures.
// cursor watch: 186cf0:84:1770; pads watch: 1aee88:208:1770. USA attract demo.
#include "../core/dc_cursor.hpp"
#include "../core/dc_demo.hpp"
#include <array>
#include <cstdio>
#include <cstring>
#include <map>
using namespace ccr;
template<size_t N> static bool load(const char* path, std::map<int, std::array<unsigned char, N>>& rows) {
    FILE* f = fopen(path, "rb"); if (!f) return false;
    int frame; std::array<unsigned char, N> data;
    while (fread(&frame, 4, 1, f) == 1) {
        if (fread(data.data(), 1, N, f) != N || rows.count(frame)) { fclose(f); return false; }
        rows[frame] = data;
    }
    const bool ok = !ferror(f) && ftell(f) % (N + 4) == 0; fclose(f); return ok;
}
template<class T> static T read(const unsigned char* p) { T v; memcpy(&v, p, sizeof v); return v; }
int main(int argc, char** argv) {
    if (argc == 2 && strcmp(argv[1], "--cases") == 0) {
        uint32_t seed = 1;
        auto next = [&]() { seed = seed * 1664525u + 1013904223u; return seed; };
        for (int i = 0; i < 2000; ++i) {
            DcCursor c;
            c.x = (i % 10 == 0) ? 180.0f : (next() % 18001) * 0.01f;
            c.y = (i % 11 == 0) ? 135.0f : (next() % 13501) * 0.01f;
            c.targetX = static_cast<int>(next() % 13) - 1;
            c.targetY = static_cast<int>(next() % 10) - 1;
            const unsigned held = next() & 0xf0;
            const int ax = i % 2 ? 0 : static_cast<int>(next() % 256) - 128;
            const int ay = i % 2 ? 0 : static_cast<int>(next() % 256) - 128;
            printf("%.9g %.9g %d %d %u %d %d | ", c.x, c.y, c.targetX, c.targetY, held, ax, ay);
            c.tick(held, ax, ay);
            printf("%.9g %.9g %d %d %d %d\n", c.x, c.y, c.targetX, c.targetY, c.cellX(), c.cellY());
        }
        return 0;
    }
    if (argc != 4) { puts("usage: dc_cursor_probe <cursor_watch.bin> <pads_watch.bin> <KEY_STAGE000.BIN>"); return 2; }
    DcDemo demo; if (!demo.load(argv[3])) { puts("cannot parse demo recording"); return 2; }
    std::map<int, std::array<unsigned char, 84>> cursors;
    std::map<int, std::array<unsigned char, 208>> pads;
    if (!load(argv[1], cursors) || !load(argv[2], pads)) return 2;
    DcCursor c[4];
    const auto first = cursors.find(1909);
    if (first == cursors.end()) return 2;
    for (int p = 0; p < 4; ++p) {
        const auto* row = first->second.data() + 4 + p * 20;
        c[p].x = read<float>(row + 8); c[p].y = read<float>(row + 16);
    }
    int checked = 0;
    int inputsChecked = 0;
    for (const auto& frame : pads) {
        const int tick = frame.first - 1789;
        if (tick < 0 || static_cast<size_t>(tick) >= demo.frames.size()) continue;
        for (int p = 0; p < 4; ++p) {
            const auto& recorded = demo.frames[tick][p];
            const auto* live = frame.second.data() + p * 52;
            if (recorded.held != read<uint32_t>(live + 8) || demo.pressed(tick, p) != read<uint32_t>(live + 16) ||
                recorded.x != read<int16_t>(live + 28) || recorded.y != read<int16_t>(live + 30)) {
                printf("demo input mismatch frame %d player %d\n", frame.first, p); return 1;
            }
            ++inputsChecked;
        }
    }
    // The original gates cursor updates while spinning roulette, from watch frame 2219.
    for (int f = 1910; f <= 2218; ++f) {
        if (!pads.count(f) || !cursors.count(f)) return 2;
        for (int p = 0; p < 4; ++p) {
            const auto* input = pads.at(f).data() + p * 52;
            c[p].tick(read<uint32_t>(input + 8), read<int16_t>(input + 28), read<int16_t>(input + 30));
            const auto* row = cursors.at(f).data() + 4 + p * 20;
            if (c[p].x != read<float>(row + 8) || c[p].y != read<float>(row + 16) ||
                c[p].cellX() != read<int16_t>(row + 2) || c[p].cellY() != read<int16_t>(row + 4)) {
                printf("cursor mismatch frame %d player %d: %.9g,%.9g vs %.9g,%.9g\n", f, p,
                       c[p].x, c[p].y, read<float>(row + 8), read<float>(row + 16)); return 1;
            }
            ++checked;
        }
    }
    printf("Dreamcast demo: %zu records, %d pad inputs and %d cursor positions/cells identical\n", demo.frames.size(), inputsChecked, checked); return 0;
}
