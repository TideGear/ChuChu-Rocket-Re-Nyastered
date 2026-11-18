#!/usr/bin/env python3
"""Export the Dreamcast BIOS ROM glyphs the game uses for run-time text on the Challenge select clocks.

usage: export_dc_bios_font.py <dc_boot.bin> <ret_all directory>

The BIOS image comes from the user; nothing from it is shipped. The game (1ST_READ FUN_8c0229c0) reads 24 x 24 one-bit glyphs
(three bytes per row, most significant bit first) from the ROM font at 0x100000 and thickens them by OR-ing each glyph with
itself shifted one pixel right and then one pixel down. Verified against the Flycast frame at Challenge select (docs/HANDOFF.md):
the full-width zero at ROM offset 0x100000 + 25016 and the colon at + 10832 reproduce the game's texture with 0 differing pixels;
digits 1..9 follow the zero at 72-byte steps. Writes dc_select_clock (11 glyphs of 24 x 24: digits 0..9, then the colon)."""
import os, struct, sys
from PIL import Image

ZERO, COLON, STRIDE = 25016, 10832, 72

def glyph(rom, offset):
    rows = []
    for r in range(24):
        v = int.from_bytes(rom[offset + 3 * r: offset + 3 * r + 3], 'big')
        rows.append([(v >> (23 - c)) & 1 for c in range(24)])
    out = [[rows[r][c] | (rows[r][c - 1] if c else 0) for c in range(24)] for r in range(24)]
    return [[out[r][c] | (out[r - 1][c] if r else 0) for c in range(24)] for r in range(24)]

def main(bios, out):
    data = open(bios, 'rb').read()
    if len(data) != 2097152:
        raise SystemExit('Expected a 2 MiB Dreamcast BIOS image')
    rom = data[0x100000:0x200000]
    sheet = Image.new('RGBA', (24 * 11, 24))
    for index, offset in enumerate([ZERO + STRIDE * k for k in range(10)] + [COLON]):
        px = glyph(rom, offset)
        cell = Image.new('RGBA', (24, 24))
        cell.putdata([(255, 255, 255, 255) if px[r][c] else (0, 0, 0, 0) for r in range(24) for c in range(24)])
        sheet.paste(cell, (24 * index, 0))
    with open(os.path.join(out, 'dc_select_clock.tex.bin'), 'wb') as f:
        f.write(struct.pack('<2I', sheet.width, sheet.height)); f.write(sheet.tobytes())
    with open(os.path.join(out, 'dc_select_clock.frames.bin'), 'wb') as f:
        f.write(struct.pack('<I', 11))
        for i in range(11): f.write(struct.pack('<9f', 24 * i / 264, 0, 24 * (i + 1) / 264, 1, 0, 0, 0, 0, 0))
    print('dc_select_clock 264x24')

if __name__ == '__main__':
    if len(sys.argv) != 3: raise SystemExit(__doc__)
    main(sys.argv[1], sys.argv[2])
