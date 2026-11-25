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
ANSI_BASE, ANSI_STEP = 0x20, 36   # 12 x 24 glyphs for characters 0x20..0x7e, rows of 12 bits packed MSB first

def glyph(rom, offset):
    rows = []
    for r in range(24):
        v = int.from_bytes(rom[offset + 3 * r: offset + 3 * r + 3], 'big')
        rows.append([(v >> (23 - c)) & 1 for c in range(24)])
    out = [[rows[r][c] | (rows[r][c - 1] if c else 0) for c in range(24)] for r in range(24)]
    return [[out[r][c] | (out[r - 1][c] if r else 0) for c in range(24)] for r in range(24)]

def ansi_glyph(rom, ch):
    off = ANSI_BASE + (ch - 0x20) * ANSI_STEP
    bits = ''.join(f'{b:08b}' for b in rom[off:off + ANSI_STEP])
    rows = [[int(bits[r * 12 + c]) for c in range(12)] for r in range(24)]
    out = [[rows[r][c] | (rows[r][c - 1] if c else 0) for c in range(12)] for r in range(24)]
    return [[out[r][c] | (out[r - 1][c] if r else 0) for c in range(12)] for r in range(24)]

WIDE = [0x8140, 0x8148, 0x815E] + list(range(0x824F, 0x8259))   # full-width space, ？, ／, ０-９ (the app's frame index for each code, in this order)

def sjis_to_jis(code):
    lead, trail = code >> 8, code & 0xff
    row = (lead - (0x71 if lead < 0xa0 else 0xb1)) * 2 + 1
    if trail > 0x7f: trail -= 1
    if trail >= 0x9e: row += 1; col = trail - 0x7d
    else: col = trail - 0x1f
    return row, col

def is_bios(data):
    """True for a 2 MiB image whose ROM font holds the verified full-width zero (116 lit pixels after thickening)."""
    return len(data) == 2097152 and sum(map(sum, glyph(data[0x100000:0x200000], ZERO))) == 116

def main(bios, out):
    data = open(bios, 'rb').read()
    if not is_bios(data):
        raise SystemExit('Not a Dreamcast BIOS image with the expected ROM font')
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
    # Verified in the Puzzle hint bubble (Flycast frame 2390): "Where to go?" is these glyphs at a 12 px advance, 0 differing pixels.
    atlas = Image.new('RGBA', (12 * 95, 24))
    for k in range(95):
        px = ansi_glyph(rom, 0x20 + k)
        cell = Image.new('RGBA', (12, 24))
        cell.putdata([(255, 255, 255, 255) if px[r][c] else (0, 0, 0, 0) for r in range(24) for c in range(12)])
        atlas.paste(cell, (12 * k, 0))
    with open(os.path.join(out, 'dc_bios_ansi.tex.bin'), 'wb') as f:
        f.write(struct.pack('<2I', atlas.width, atlas.height)); f.write(atlas.tobytes())
    with open(os.path.join(out, 'dc_bios_ansi.frames.bin'), 'wb') as f:
        f.write(struct.pack('<I', 95))
        for i in range(95): f.write(struct.pack('<9f', 12 * i / 1140, 0, 12 * (i + 1) / 1140, 1, 0, 0, 0, 0, 0))
    print('dc_bios_ansi 1140x24')
    # Full-width Shift-JIS glyphs used by the Options strings at 0x8c083060 (e.g. "Monaural ^  Stereo", "< OO >"): JIS row/column from the
    # Shift-JIS code, ROM offset 10400 + ((row - 0x21) * 94 + (col - 0x21)) * 72 (gives the verified zero 25016 and colon 10832). Order: WIDE below.
    wide = Image.new('RGBA', (24 * len(WIDE), 24))
    for k, code in enumerate(WIDE):
        row, col = sjis_to_jis(code)
        px = glyph(rom, 10400 + ((row - 0x21) * 94 + (col - 0x21)) * 72)
        cell = Image.new('RGBA', (24, 24))
        cell.putdata([(255, 255, 255, 255) if px[r][c] else (0, 0, 0, 0) for r in range(24) for c in range(24)])
        wide.paste(cell, (24 * k, 0))
    with open(os.path.join(out, 'dc_bios_wide.tex.bin'), 'wb') as f:
        f.write(struct.pack('<2I', wide.width, wide.height)); f.write(wide.tobytes())
    with open(os.path.join(out, 'dc_bios_wide.frames.bin'), 'wb') as f:
        f.write(struct.pack('<I', len(WIDE)))
        for i in range(len(WIDE)): f.write(struct.pack('<9f', 24 * i / wide.width, 0, 24 * (i + 1) / wide.width, 1, 0, 0, 0, 0, 0))
    print('dc_bios_wide %dx24' % wide.width)

if __name__ == '__main__':
    if len(sys.argv) != 3: raise SystemExit(__doc__)
    main(sys.argv[1], sys.argv[2])
