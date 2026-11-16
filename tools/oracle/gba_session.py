"""Interactive-ish GBA session helper: boot to the Mode Select menu once (cached snapshot), then run key scripts from there.
usage: gba_session.py <snapshot name> <frames> <keyscript f:KEYS,...> <png prefix> [snaps...]   (keys: A B S(elect) T(start) R L U D r(R shoulder) l)"""
import os, pickle, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gba_oracle import GBA
from gba_render import render
from PIL import Image
ROM = r'C:\Dev\ChuChu Rocket\analysis\gba\ccr.gba'; SNAPDIR = r'C:\Dev\ChuChu Rocket\local\gba_snaps'
KMAP = {'A': 1, 'B': 2, 'S': 4, 'T': 8, 'R': 16, 'L': 32, 'U': 64, 'D': 128, 'r': 256, 'l': 512}
def boot_to_menu(cache=True):
    p = os.path.join(SNAPDIR, 'menu.pkl')
    g = GBA(ROM)
    if cache and os.path.exists(p):
        with open(p, 'rb') as stream:
            g.load_state(pickle.load(stream))
        return g
    script = {420: 'A', 520: 'A', 1200: 'A', 1300: 'A', 1400: 'A', 1620: 'T'}
    run(g, 1760, script)
    if cache:
        os.makedirs(SNAPDIR, exist_ok=True)
        with open(p, 'wb') as stream:
            pickle.dump(g.save_state(), stream)
    return g
def run(g, frames, script, snaps=(), prefix=None, base=0):
    keys = 0; hold = 0
    for f in range(frames):
        if f in script: keys = sum(KMAP[c] for c in script[f] if c in KMAP); hold = 8
        elif hold: hold -= 1
        else: keys = 0
        g.run_frames(1, keys)
        if prefix and (f + 1) in snaps: render(g).resize((480, 320), Image.NEAREST).save('%s_%d.png' % (prefix, f + 1))
if __name__ == '__main__':
    g = boot_to_menu(); frames = int(sys.argv[2])
    if sys.argv[1] != 'menu': g.load_state(pickle.load(open(os.path.join(SNAPDIR, sys.argv[1] + '.pkl'), 'rb')))
    script = {}
    for part in (sys.argv[3].split(',') if sys.argv[3] else []): f, k = part.split(':'); script[int(f)] = k
    snaps = [int(x) for x in sys.argv[5:]]
    run(g, frames, script, snaps, sys.argv[4]); print('frame', g.frame, 'pc', hex(g.pc))
    if os.environ.get('SAVE'): pickle.dump(g.save_state(), open(os.path.join(SNAPDIR, os.environ['SAVE'] + '.pkl'), 'wb'))
