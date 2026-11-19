// Dreamcast attract input recording: KEY_STAGE000.BIN, four 12-byte pads per tick.
#pragma once
#include <cstdint>
#include <cstdio>
#include <vector>
#include <array>
namespace ccr {
struct DcDemoPad { uint32_t held = 0; int16_t x = 0, y = 0; };
class DcDemo {
public:
    std::vector<std::array<DcDemoPad, 4>> frames;
    // FUN_8c015160 reuses ONE previous-held word across all four players.
    // Thus most held arrow buttons repeat each frame; simultaneous pads affect each other's edges.
    uint32_t pressed(size_t frame, int player) const {
        const uint32_t previous = player ? frames[frame][player - 1].held : frame ? frames[frame - 1][3].held : 0;
        return frames[frame][player].held & ~previous;
    }
    bool load(const char* path) {
        frames.clear();
        FILE* f = fopen(path, "rb"); if (!f) return false;
        bool end = false;
        for (;;) {
            unsigned char bytes[48];
            const size_t n = fread(bytes, 1, sizeof bytes, f);
            if (n >= 4 && word(bytes) == 0xffffffffu) { end = true; break; }
            if (n != sizeof bytes) break;
            std::array<DcDemoPad, 4> row;
            bool valid = true;
            for (int p = 0; p < 4; ++p) {
                const auto* b = bytes + p * 12;
                row[p] = {word(b), signed16(b + 8), signed16(b + 10)};
                // All records of the tested USA recording have an unused zero second word.
                if (word(b + 4) != 0 || row[p].x < -128 || row[p].x > 127 || row[p].y < -128 || row[p].y > 127) valid = false;
            }
            if (!valid) break;
            frames.push_back(row);
        }
        const bool ok = end && !frames.empty() && !ferror(f); fclose(f);
        if (!ok) frames.clear();
        return ok;
    }
private:
    static uint32_t word(const unsigned char* b) {
        return uint32_t(b[0]) | (uint32_t(b[1]) << 8) | (uint32_t(b[2]) << 16) | (uint32_t(b[3]) << 24);
    }
    static int16_t signed16(const unsigned char* b) {
        const int v = b[0] | (int(b[1]) << 8); return static_cast<int16_t>(v < 32768 ? v : v - 65536);
    }
};
} // namespace ccr
