"""Ground truth for the battle setup players pane (HD 1.0): PlayerSelectScreen::renderPlayersPane 0x33514. Logs the low-level draw calls for a given state.
Not yet verified: the state layout of the screen object (offsets are read from the code, see docs/roadmap.md)."""
import os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hd_env
env = hd_env.make(); o = env.o; scr = env.alloc(0xe00); o.write(scr + 0xa44, struct.pack('<i', 0))
def render(sel=0, state=0):
    o.write(scr + 0xa44, struct.pack('<i', 0)); del env.log[:]
    try: o.call(0x33514, scr)
    except Exception as e: print('fault', e)
    return list(env.log)
if __name__ == '__main__':
    for l in render(): print(l[:7] if l[0] != 'PrintString' else l[:4] + l[8:])
