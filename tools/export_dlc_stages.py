"""Export the Dreamcast DLC puzzle packs (PuzzleP, DEPuzzle) as boards in the same record layout as export_testdata.py (no solutions).
usage: export_dlc_stages.py [out.bin]   (derived data in local/, git-ignored)"""
import os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stage_registry as R
def main(out):
    recs = []
    for src, name in ((2, 'PuzzleP'), (3, 'DEPuzzle')):
        for k, s in enumerate(R.dlc_slots(name)):
            t, w = R.dlc_to_board(s); recs.append((src, k, t, w))
    with open(out, 'wb') as f:
        f.write(struct.pack('<I', len(recs)))
        for src, k, t, w in recs:
            f.write(struct.pack('<BBH', src, 0, k)); f.write(t); f.write(w); f.write(b'\0' * 32)
    print('dlc boards', len(recs), 'unknown tile bytes', sum(1 for r in recs for b in r[2] if b == 0xff))
main(sys.argv[1] if len(sys.argv) > 1 else r'c:\Dev\ChuChu Rocket\local\testdata\dlc_stages.bin')
