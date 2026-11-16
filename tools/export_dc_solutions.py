"""Export Dreamcast puzzle slots (PZSTAGE100.DAT main puzzles, DLC PuzzleP/DEPuzzle) WITH their stored solutions in the stage-file layout of export_testdata.py.
Slot format (1,536 bytes; PZSTAGE100 slots start 640 bytes into each record... see stage_registry.py): 25x19 lattice (475 bytes), then byte +0 = number of solution arrows n (<= 12), bytes +1..+12 = the arrows' cells
(one byte each; high nibble and low nibble are x and y in some order, see ORDER), bytes +13..+15 = 24-bit little-endian field of 2-bit directions (arrow i = bits 2i..2i+1, game direction codes 0 S, 1 W, 2 N, 3 E), title at +16.
Verified 2026-11-14: the per-direction counts of these arrows equal the arrow stock of the mobile ports (mobile struct bytes 0x15C..0x15F) for all 100 PZSTAGE100 puzzles.
usage: export_dc_solutions.py <out.bin> [nibble order: xy|yx]"""
import os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stage_registry as R
def solution(sl, order='xy'):
    n = sl[475]; dirs = sl[488] | sl[489] << 8 | sl[490] << 16; out = []
    for i in range(min(n, 12)):
        b = sl[476 + i]; hi, lo = b >> 4, b & 15; x, y = (hi, lo) if order == 'xy' else (lo, hi)
        out.append((x, y, (dirs >> (2 * i)) & 3))
    return out

def main_slots(data):
    return (data[k * 1536 + 640:(k + 1) * 1536] for k in range(100))

def write_record(stream, source, number, slot, order='xy'):
    tiles, walls = R.dlc_to_board(slot)
    arrows = solution(slot, order)
    stream.write(struct.pack('<BBH', source, len(arrows), number))
    stream.write(tiles)
    stream.write(walls)
    for x, y, direction in arrows:
        stream.write(bytes((x, y, direction)))
    stream.write(slot[0x1eb:0x200].split(b'\0')[0].ljust(32, b'\0'))

def main(out, order='xy'):
    recs = []
    d = open(os.path.join(R.ROOT, 'extracted', 'dc_files', 'ENGLISH', 'PZSTAGE100.DAT'), 'rb').read()
    for k, slot in enumerate(main_slots(d)): recs.append((4, k, slot))
    for src, name in ((2, 'PuzzleP'), (3, 'DEPuzzle')):
        for k, s in enumerate(R.dlc_slots(name)): recs.append((src, k, s))
    with open(out, 'wb') as f:
        f.write(struct.pack('<I', len(recs)))
        for src, k, sl in recs:
            write_record(f, src, k, sl, order)
    print('records', len(recs))
if __name__ == '__main__': main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else 'xy')
