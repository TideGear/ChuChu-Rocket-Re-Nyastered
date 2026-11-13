"""Export the Dreamcast built-in battle (BTSTAGE25.DAT) and challenge (CHSTAGE25.DAT) stages to the viewer/game stage format:
u32 n, then per stage: u8 src(2=battle,3=challenge), u8 0, u16 index, 108 tile bytes, 237 wall bytes, 32-byte title.
ASCII 25x19 lattice -> 12x9 cells (rule from the original's loader, see tools/oracle/battle_probe.py).
usage: export_battle.py <ENGLISH dir> <out file>"""
import os, struct, sys

def ascii_stage(rec):
    L = [rec[r * 25:(r + 1) * 25] for r in range(19)]
    def tile(ch): return 0x11 if ch == 0x37 else 0 if ch == 0x39 else (ch - 0x40) & 0xff
    tiles = bytes(tile(L[2 * r + 1][2 * c + 1]) for r in range(9) for c in range(12))
    walls = bytearray(237)
    for i in range(10):
        for c in range(12): walls[25 * i + c] = 1 if L[2 * i][2 * c + 1] == 0x31 else 0
    for i in range(9):
        for c in range(13): walls[25 * i + 12 + c] = 1 if L[2 * i + 1][2 * c] == 0x31 else 0
    return tiles, bytes(walls)

def records(path):
    d = open(path, 'rb').read()
    return [d[i:i + 475] for i in range(0, len(d) - 474, 477)]

def main(eng, out):
    recs = []
    for src, name in ((2, 'BTSTAGE25.DAT'), (3, 'CHSTAGE25.DAT')):
        for i, r in enumerate(records(os.path.join(eng, name))): recs.append((src, i, r))
    with open(out, 'wb') as f:
        f.write(struct.pack('<I', len(recs)))
        for src, i, r in recs:
            t, w = ascii_stage(r)
            f.write(struct.pack('<BBH', src, 0, i) + t + w + (b'Battle %d' % i if src == 2 else b'Challenge %d' % i).ljust(32, b'\0'))
    print(len(recs), 'stages ->', out)

if __name__ == '__main__': main(sys.argv[1], sys.argv[2])
