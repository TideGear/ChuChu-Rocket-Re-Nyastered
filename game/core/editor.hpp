// Puzzle Edit: conversion of the editor's board data into a puzzle stage (Android 1.15 Editor::convertField, ghidra 0x2d0ec), verified against the
// emulated original (tools/oracle/editor_convert_diff.py, tools/oracle/make_editor_golden.py, game/tests/editor_test.cpp).
// Cell word: bits 8..11 object class (0x100 rocket, 0x200 / 0x300 / 0x400 arrows of direction 0 / 1 / 3 -> stock bytes), low byte the tile
// (nibble 1 cat, 2 mouse with colour 1..4 in the high nibble, 3 rocket, 4 hole), bits 12 / 13 north / south wall, bits 14 / 15 west / east wall.
#pragma once
#include <cstdint>
#include <array>
#include <cstddef>
#include <cstring>
#include <string>
#include <vector>
namespace ccr {
struct EditorArrow { uint16_t x, y; uint32_t type; };
// Dreamcast Puzzle Edit limits (error strings at 0x8c0bff52..0x8c0bffc9; input handler FUN_8c031f0a).
inline int editorObjectKind(uint8_t tile) {
    if (tile >= 9 && tile <= 12) return 1;   // mice, max 100
    if (tile >= 13 && tile <= 16) return 2;  // cats, max 20
    if (tile == 1) return 3;                 // goal rockets, max 30
    return 0;
}
inline bool editorCanPlaceTile(const uint8_t* tiles, size_t cell, uint8_t next) {
    const int kind = editorObjectKind(next), oldKind = editorObjectKind(tiles[cell]);
    if (!kind || kind == oldKind) return true;
    const int limit = kind == 1 ? 100 : kind == 2 ? 20 : 30;
    int count = 0;
    for (size_t i = 0; i < 108; ++i) count += editorObjectKind(tiles[i]) == kind;
    return count < limit;
}
inline bool editorCanAddArrow(size_t count) { return count < 12; }
struct EditorStage {
    uint8_t bytes[0x175] = {};   // tiles 0..0x6b, walls 0x6c..0x158 (row stride 25), stock 0x15c..0x15f, title 0x160..0x174 (bytes 0x159..0x15b are not written)
    std::vector<EditorArrow> arrows;
};
inline EditorStage convertEditorField(const uint32_t cells[9][12], const uint8_t* title /* zero terminated, at most 21 bytes used */) {
    EditorStage s;
    uint8_t* st = s.bytes;
    for (int r = 0; r < 9; r++) {
        for (int c = 0; c < 12; c++) {
            const uint32_t w = cells[r][c], cls = w & 0xf00;
            int idx = -1, type = 0;
            if (cls == 0x200) { idx = 0x15c; type = 0; }
            else if (cls == 0x300) { idx = 0x15d; type = 1; }
            else if (cls == 0x100) { idx = 0x15e; type = 2; }
            else if (cls == 0x400) { idx = 0x15f; type = 3; }
            if (idx >= 0) { st[idx]++; s.arrows.push_back({static_cast<uint16_t>(c), static_cast<uint16_t>(r), static_cast<uint32_t>(type)}); }
            const uint32_t low = w & 0xf, high = w & 0xf0;
            uint8_t t = 0;
            if (low == 2) t = high == 0x10 ? 0xb : high == 0x20 ? 9 : high == 0x30 ? 0xa : high == 0x40 ? 0xc : 0;
            else if (low == 1) t = high == 0x10 ? 0xf : high == 0x20 ? 0xd : high == 0x30 ? 0xe : high == 0x40 ? 0x10 : 0;
            else if (low == 3) t = 1;
            else if (low == 4) t = 0x11;
            st[12 * r + c] = t;
        }
    }
    for (int r = 0; r < 10; r++) for (int c = 0; c < 12; c++) st[0x6c + 25 * r + c] = r < 9 ? (cells[r][c] >> 12) & 1 : (cells[8][c] >> 13) & 1;
    for (int r = 0; r < 9; r++) {
        for (int c = 0; c < 12; c++) st[0x78 + 25 * r + c] = (cells[r][c] >> 14) & 1;
        st[0x78 + 25 * r + 12] = (cells[r][11] >> 15) & 1;
    }
    bool ended = false;
    for (int i = 0; i < 0x15; i++) {
        const uint8_t ch = ended ? 0 : title[i];
        st[0x160 + i] = ch;
        if (ch == 0) ended = true;
    }
    return s;
}
// Editor::calculateCRC (0x2ce38) with the table of Editor::initializeCRC (0x2cde0): the standard reflected CRC-32 (polynomial 0x04c11db7, init 0xffffffff,
// final complement); a zero length returns 0 (tools/oracle/editor_crc_diff.py: 300 random buffers equal zlib.crc32). sendLevel signs the 0x17c byte stage struct with it.
inline uint32_t editorCrc(const uint8_t* data, int length) {
    if (length == 0) return 0;
    static uint32_t table[256]; static bool built = false;
    if (!built) { for (uint32_t i = 0; i < 256; i++) { uint32_t c = i; for (int k = 0; k < 8; k++) c = (c & 1) ? 0xedb88320u ^ (c >> 1) : c >> 1; table[i] = c; } built = true; }
    uint32_t crc = 0xffffffffu;
    for (int i = 0; i < length; i++) crc = table[(crc & 0xff) ^ data[i]] ^ (crc >> 8);
    return ~crc;
}
// Editor::sendLevel (0x2cf80): the solution moves go out as lowercase hex, three bytes per move (the low bytes of the three fields of each 8 byte record,
// high nibble first), after "crc=%.8x&arw=" in the request "http://www.binaryhammer.com/ccrlvls/ccr_lvlup.php?crc=%.8x&arw=%s&lvl=" (the original's server, not used by the port).
inline std::string editorSolutionHex(const std::vector<std::array<uint8_t, 3>>& moves) {
    static const char* digits = "0123456789abcdef";
    std::string out;
    for (const auto& m : moves) for (uint8_t v : m) { out += digits[(v >> 4) & 0xf]; out += digits[v & 0xf]; }
    return out;
}
} // namespace ccr
