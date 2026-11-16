"""Export the Dreamcast DLC puzzle packs (PuzzleP, DEPuzzle) as boards in the same record layout as export_testdata.py (DEPuzzle with its stored solutions).
usage: export_dlc_stages.py [out.bin]   (derived data in local/, git-ignored)"""
import os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stage_registry as R
import export_dc_solutions as E
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
            t, w = R.dlc_to_board(s); recs.append((src, k, t, w, E.solution(s) if name == 'DEPuzzle' else []))   # PuzzleP slots store no arrow cells (zeros), see docs/dlc.md
    with open(out, 'wb') as f:
        f.write(struct.pack('<I', len(recs)))
        for src, k, t, w, sol in recs:
            f.write(struct.pack('<BBH', src, len(sol), k)); f.write(t); f.write(w)
            for x, y, d in sol: f.write(bytes((x, y, d)))
            f.write(b'\0' * 32)
    print('dlc boards', len(recs), 'unknown tile bytes', sum(1 for r in recs for b in r[2] if b == 0xff))
if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else r'c:\Dev\ChuChu Rocket\local\testdata\dlc_stages.bin',
         sys.argv[2] if len(sys.argv) > 2 else None)
