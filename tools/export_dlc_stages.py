"""Export the Dreamcast DLC puzzle packs (PuzzleP, DEPuzzle) as boards in the same record layout as export_testdata.py (DEPuzzle with its stored solutions).
usage: export_dlc_stages.py [out.bin]   (derived data in local/, git-ignored)"""
import os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stage_registry as R
import export_dc_solutions as E
def stock(slot):
    count = slot[475]
    if count > 12: raise ValueError('invalid DLC arrow count')
    directions = slot[488] | slot[489] << 8 | slot[490] << 16
    return [(0, 0, (directions >> (2 * i)) & 3) for i in range(count)]
def main(out, dlc_dir=None):
    saves = {file.lower(): file for file in os.listdir(dlc_dir or R.DLC_DIR)}
    recs = []
    for src, name in ((2, 'PuzzleP'), (3, 'DEPuzzle')):
        filename = saves.get((name + '.VMS').lower())
        if not filename:
            continue
        data = open(os.path.join(dlc_dir or R.DLC_DIR, filename), 'rb').read()[640:]
        slots = (data[offset:offset + 1536] for offset in range(0, len(data) - 474, 1536))
        for k, s in enumerate(slots):
            t, w = R.dlc_to_board(s); title = (name + ' ' + str(k + 1).zfill(2)).encode('ascii')
            arrows = E.solution(s) if name == 'DEPuzzle' else stock(s)
            recs.append((src, k, t, w, arrows, title))   # PuzzleP has no saved arrow cells; its count/directions encode stock only
    with open(out, 'wb') as f:
        f.write(struct.pack('<I', len(recs)))
        for src, k, t, w, sol, title in recs:
            f.write(struct.pack('<BBH', src, len(sol), k)); f.write(t); f.write(w)
            for x, y, d in sol: f.write(bytes((x, y, d)))
            f.write(title[:32].ljust(32, b'\0'))
    print('dlc boards', len(recs), 'unknown tile bytes', sum(1 for r in recs for b in r[2] if b == 0xff), 'with arrow stock', sum(1 for r in recs if r[4]))
if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else r'c:\Dev\ChuChu Rocket\local\testdata\dlc_stages.bin',
         sys.argv[2] if len(sys.argv) > 2 else None)
