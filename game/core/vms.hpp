// Dreamcast ChuChu Rocket puzzle packs (.VMS + .VMI): reader and writer, the C++ twin of tools/vms_pack.py (docs/dlc.md). A pack has a 640-byte header
// and 25 1,536-byte slots; the final slot is truncated to 896 bytes in the 38,400-byte retail file (unused slot padding is omitted).
#pragma once
#include <algorithm>
#include <array>
#include <cstdint>
#include <cstring>
#include <ctime>
#include <string>
#include <vector>
namespace ccr {
struct VmsPuzzle {
    uint8_t tiles[108] = {};     // mobile layout (0 empty, 1 rocket, 9..0x10 mice and cats, 0x11 hole)
    uint8_t walls[237] = {};     // 10 rows of 12 horizontal edges at 25*i + c, 9 rows of 13 vertical edges at 25*i + 12 + c
    struct Arrow { uint8_t x, y, dir; };
    std::vector<Arrow> arrows;   // the stored solution, also the arrow stock (<= 12)
    std::string title;           // up to 20 characters
};
namespace vms {
constexpr size_t kHeader = 640, kSlot = 1536, kVmiSize = 108, kFinalSlot = 896, kPackSize = kHeader + kSlot * 24 + kFinalSlot;
inline int latticeToTile(uint8_t v) { switch (v) { case 0x09: return 0; case 0x0a: return 1; case 0x07: return 0x11; case 0x3d: return 9; case 0x3e: return 10; case 0x3f: return 11; case 0x40: return 12; case 0x47: return 13; case 0x48: return 14; case 0x49: return 15; case 0x4a: return 16; default: return -1; } }
inline int tileToLattice(uint8_t t) { switch (t) { case 0: return 0x09; case 1: return 0x0a; case 0x11: return 0x07; case 9: return 0x3d; case 10: return 0x3e; case 11: return 0x3f; case 12: return 0x40; case 13: return 0x47; case 14: return 0x48; case 15: return 0x49; case 16: return 0x4a; default: return -1; } }
// Reads one slot (at least 512 bytes). Returns false when a tile code is unknown or the arrow count is above 12.
inline bool decodeSlot(const uint8_t* s, size_t size, VmsPuzzle& out) {
    if (size < 512) return false;
    for (int r = 0; r < 9; r++) for (int c = 0; c < 12; c++) { int t = latticeToTile(s[(2 * r + 1) * 25 + 2 * c + 1]); if (t < 0) return false; out.tiles[r * 12 + c] = (uint8_t)t; }
    std::memset(out.walls, 0, sizeof out.walls);
    for (int i = 0; i < 10; i++) for (int c = 0; c < 12; c++) out.walls[25 * i + c] = s[(2 * i) * 25 + 2 * c + 1] ? 1 : 0;
    for (int i = 0; i < 9; i++) for (int c = 0; c < 13; c++) out.walls[25 * i + 12 + c] = s[(2 * i + 1) * 25 + 2 * c] ? 1 : 0;
    const int n = s[475]; if (n > 12) return false;
    const uint32_t dirs = s[488] | s[489] << 8 | s[490] << 16;
    out.arrows.clear();
    for (int k = 0; k < n; k++) {
        const uint8_t x = s[476 + k] >> 4, y = s[476 + k] & 15;
        if (x >= 12 || y >= 9) return false;
        out.arrows.push_back({x, y, (uint8_t)((dirs >> (2 * k)) & 3)});
    }
    out.title.assign((const char*)s + 491, strnlen((const char*)s + 491, 21));
    return true;
}
inline bool encodeSlot(const VmsPuzzle& p, uint8_t* s /* kSlot bytes */) {
    if (p.arrows.size() > 12) return false;
    std::memset(s, 0, kSlot);
    for (int r = 0; r < 9; r++) for (int c = 0; c < 12; c++) { int v = tileToLattice(p.tiles[r * 12 + c]); if (v < 0) return false; s[(2 * r + 1) * 25 + 2 * c + 1] = (uint8_t)v; }
    for (int i = 0; i < 10; i++) for (int c = 0; c < 12; c++) s[(2 * i) * 25 + 2 * c + 1] = p.walls[25 * i + c] ? 1 : 0;
    for (int i = 0; i < 9; i++) for (int c = 0; c < 13; c++) s[(2 * i + 1) * 25 + 2 * c] = p.walls[25 * i + 12 + c] ? 1 : 0;
    for (int i = 0; i < 10; i++) for (int c = 0; c < 13; c++) s[(2 * i) * 25 + 2 * c] = (i == 0 || i == 9 || c == 0 || c == 12) ? 1 : 0;   // border posts
    s[475] = (uint8_t)p.arrows.size(); uint32_t dirs = 0;
    for (size_t k = 0; k < p.arrows.size(); k++) { s[476 + k] = (uint8_t)(p.arrows[k].x << 4 | (p.arrows[k].y & 15)); dirs |= (uint32_t)(p.arrows[k].dir & 3) << (2 * k); }
    s[488] = (uint8_t)dirs; s[489] = (uint8_t)(dirs >> 8); s[490] = (uint8_t)(dirs >> 16);
    std::memcpy(s + 491, p.title.data(), p.title.size() < 20 ? p.title.size() : 20);
    return true;
}
// Whole pack. Returns the number of puzzles read (slots that decode), or -1 when the data does not look like a puzzle pack.
inline int readPack(const std::vector<uint8_t>& data, std::vector<VmsPuzzle>& out) {
    out.clear();
    if (data.size() < kHeader + 512 || std::memcmp(data.data(), "CHU_CHU__D", 10) != 0) return -1;   // puzzle packs are 'CHU_CHU__D01'; character packs are 'CHU_CHU__C00'
    for (size_t k = 0; kHeader + k * kSlot + 512 <= data.size() && k < 25; k++) {
        const size_t offset = kHeader + k * kSlot;
        VmsPuzzle p;
        if (decodeSlot(data.data() + offset, data.size() - offset, p)) { out.push_back(p); continue; }
        // Zero-filled unused slots are the pack terminator; a damaged populated slot must not be treated as a shorter pack.
        if (std::any_of(data.begin() + offset, data.end(), [](uint8_t b) { return b != 0; })) { out.clear(); return -1; }
        break;
    }
    return (int)out.size();
}
inline std::vector<uint8_t> writePack(const std::vector<VmsPuzzle>& puzzles, const uint8_t* header = nullptr) {
    if (puzzles.empty() || puzzles.size() > 25) return {};
    std::vector<uint8_t> v(kPackSize, 0);
    if (header) std::memcpy(v.data(), header, kHeader);
    else {
        std::memcpy(v.data(), "CHU_CHU__D01    ", 16); std::memset(v.data() + 16, ' ', 32); std::memcpy(v.data() + 16, "CCR Re-Nyastered puzzles", 24); std::memcpy(v.data() + 48, "ChuChu Rocket!", 14); v[64] = 1;
    }
    for (size_t k = 0; k < puzzles.size() && k < 25; k++) {
        std::array<uint8_t, kSlot> slot{}; if (!encodeSlot(puzzles[k], slot.data())) return {};
        const size_t offset = kHeader + k * kSlot;
        std::memcpy(v.data() + offset, slot.data(), std::min(kSlot, v.size() - offset));
    }
    return v;
}
inline std::vector<uint8_t> writeVmi(size_t vmsSize, const std::string& resource = "CCRPUZ", const std::string& vmsName = "CHU_CHU__D00") {
    std::vector<uint8_t> v(kVmiSize, 0);
    for (size_t i = 0; i < 4; ++i) v[i] = (uint8_t)(i < resource.size() ? resource[i] : 0) & (uint8_t)"SEGA"[i];
    std::memcpy(v.data() + 4, "CCR puzzles", 11);
    std::memcpy(v.data() + 36, "Dreamcast Live", 14);
    const std::time_t now = std::time(nullptr); std::tm stamp{};
#ifdef _WIN32
    localtime_s(&stamp, &now);
#else
    localtime_r(&now, &stamp);
#endif
    auto put16 = [&](size_t at, uint16_t n) { v[at] = (uint8_t)n; v[at + 1] = (uint8_t)(n >> 8); };
    put16(68, (uint16_t)(stamp.tm_year + 1900)); v[70] = (uint8_t)(stamp.tm_mon + 1); v[71] = (uint8_t)stamp.tm_mday;
    v[72] = (uint8_t)stamp.tm_hour; v[73] = (uint8_t)stamp.tm_min; v[74] = (uint8_t)stamp.tm_sec; v[75] = (uint8_t)((stamp.tm_wday + 1) % 7);
    put16(76, 0x0100); put16(78, 1);
    std::memcpy(v.data() + 80, resource.data(), std::min<size_t>(8, resource.size()));
    std::memcpy(v.data() + 88, vmsName.data(), std::min<size_t>(12, vmsName.size()));
    put16(100, 0); put16(102, 0); const uint32_t size = (uint32_t)vmsSize;
    v[104] = (uint8_t)size; v[105] = (uint8_t)(size >> 8); v[106] = (uint8_t)(size >> 16); v[107] = (uint8_t)(size >> 24);
    return v;
}
}  // namespace vms
}  // namespace ccr
