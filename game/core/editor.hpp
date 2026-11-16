// Puzzle Edit: conversion of the editor's board data into a puzzle stage (Android 1.15 Editor::convertField, ghidra 0x2d0ec), verified against the
// emulated original (tools/oracle/editor_convert_diff.py, tools/oracle/make_editor_golden.py, game/tests/editor_test.cpp).
// Cell word: bits 8..11 object class (0x100 rocket, 0x200 / 0x300 / 0x400 arrows of direction 0 / 1 / 3 -> stock bytes), low byte the tile
// (nibble 1 cat, 2 mouse with colour 1..4 in the high nibble, 3 rocket, 4 hole), bits 12 / 13 north / south wall, bits 14 / 15 west / east wall.
#pragma once
#include <cstdint>
#include <cstring>
#include <vector>
namespace ccr {
struct EditorArrow { uint16_t x, y; uint32_t type; };
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
} // namespace ccr
