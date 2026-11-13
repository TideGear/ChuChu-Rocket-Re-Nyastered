"""Export GBA stages (with reference-solution arrows) to a simple binary file for the C++ simulation tests.
Output stays in ./local/ (git-ignored): derived from the user's own ROM.
Layout: u32 count; per stage: u8 source(0 main,1 user) u8 nsol u16 index; 108 tiles; 237 walls; nsol*(x,y,dir) bytes; 32-byte title.
Directions use the game's own encoding: 0=south(down) 1=west 2=north 3=east (heading+1 = turn right).
Tiles: 0 floor, 1 rocket, 9..12 mouse(dir), 13..16 cat(dir), 17 hole."""
import struct, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gba_stages as G
GBA_DIR_TO_DC = {0: 3, 1: 0, 2: 1, 3: 2}      # GBA overlay/mouse dir (0=E,1=S,2=W,3=N) -> game dir
def tile_of(v):
    base = (v & 0xfff) & ~0x4c
    t = {0: 0, 0x20: 1, 0x80: 17}.get(base)
    if t is not None: return t
    if base & 0xf00 == 0x100: return 9 + GBA_DIR_TO_DC[base & 3]
    if base & 0xf00 == 0x200: return 13 + GBA_DIR_TO_DC[base & 3]
    return 0xff
def main(out):
    rom = open(G.ROM, 'rb').read(); stages = []
    for src, recs in ((0, G.main_records(rom)), (1, G.user_records(rom))):
        for k, o in enumerate(recs):
            c = G.cells(rom, o)
            tiles = bytes(tile_of(v) for v in c)
            _, walls = G.to_board(c)
            sol = []
            for i, v in enumerate(c):
                f = v & 0x4c
                if f: sol.append((i % 12, i // 12, GBA_DIR_TO_DC[(f - 0x40) >> 2]))
            title = G.title(rom, o)[:31].encode('ascii', 'replace') if src == 0 else b''
            stages.append((src, k, tiles, walls, sol, title))
    with open(out, 'wb') as f:
        f.write(struct.pack('<I', len(stages)))
        for src, k, tiles, walls, sol, title in stages:
            f.write(struct.pack('<BBH', src, len(sol), k)); f.write(tiles); f.write(walls)
            for x, y, d in sol: f.write(bytes((x, y, d)))
            f.write(title.ljust(32, b'\0'))
    print('stages', len(stages), 'bytes', os.path.getsize(out), 'unknown tiles:', sum(1 for s in stages for t in s[2] if t == 0xff))
if __name__ == '__main__': main(sys.argv[1] if len(sys.argv) > 1 else r'c:\Dev\ChuChu Rocket\local\testdata\gba_stages.bin')
