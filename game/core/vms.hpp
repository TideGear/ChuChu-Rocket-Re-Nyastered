// Dreamcast ChuChu Rocket puzzle packs (.VMS + .VMI): reader and writer, the C++ twin of tools/vms_pack.py (docs/dlc.md). A pack is a 640-byte header followed by
// 25 slots of 1,536 bytes: 25x19 lattice (475 bytes), arrow count, 12 arrow cells, a 24-bit direction field, a 21-byte title.
#pragma once
#include <array>
#include <cstdint>
#include <cstring>
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
constexpr size_t kHeader = 640, kSlot = 1536;
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
    for (int k = 0; k < n; k++) out.arrows.push_back({(uint8_t)(s[476 + k] >> 4), (uint8_t)(s[476 + k] & 15), (uint8_t)((dirs >> (2 * k)) & 3)});
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
        VmsPuzzle p; if (decodeSlot(data.data() + kHeader + k * kSlot, data.size() - (kHeader + k * kSlot), p)) out.push_back(p); else break;
    }
    return (int)out.size();
}
inline std::vector<uint8_t> writePack(const std::vector<VmsPuzzle>& puzzles) {
    std::vector<uint8_t> v(kHeader + kSlot * 25, 0);
    std::memcpy(v.data(), "CHU_CHU__D01    ", 16); std::memset(v.data() + 16, ' ', 32); std::memcpy(v.data() + 16, "CCR Re-Nyastered puzzles", 24); std::memcpy(v.data() + 48, "ChuChu Rocket!", 14); v[64] = 1;
    for (size_t k = 0; k < puzzles.size() && k < 25; k++) encodeSlot(puzzles[k], v.data() + kHeader + k * kSlot);
    while (v.size() % 512) v.push_back(0);
    return v;
}
}  // namespace vms
}  // namespace ccr
