"""Fresh-state press table for PlayerSelectScreen::handlePlayersPaneInput (HD 1.0 0x31d24), items 0..9.
The screen object is built once; its bytes are snapshotted and restored before each press, so every item starts from the same state."""
import os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hd_players_input_probe as H
o = H.o; scr = H.scr
SNAP = bytes(o.read(scr, 0xe00)) if hasattr(o, 'read') else None
def run_fresh(item, press=0):
    H.ITEM['v'] = item; del H.log[:]
    o.write(scr, SNAP)
    o.write(scr + 0xa08, struct.pack('<I', scr + 0x8))
    o.call(0x31d24, scr, 0, 0, press)
    return list(H.log)
if __name__ == '__main__':
    print('snapshot', SNAP is not None and len(SNAP), flush=True)
    for i in range(10):
        print(i, run_fresh(i), flush=True)
