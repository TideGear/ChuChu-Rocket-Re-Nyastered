"""Ground truth for two players-pane helpers (HD 1.0): mutexPlayer (0x31xxx) and repositionSliderPanelItems. Prints the state they write, for given arguments."""
import os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hd_players_probe as P
from ios_oracle import s32
o = P.o; scr = P.scr
MUTEX = 0x2f438
REPOS = 0x2f474
def sym_addr(name):
    return o.sym(name)
def mutex(a, b, v):
    o.write(scr + 0x2e + 0x28 * a, bytes([0])); o.write(scr + 0x2e + 0x28 * b, bytes([0]))
    o.call(MUTEX, scr, a, b, v)
    return (o.read(scr + 0x2e + 0x28 * a, 1)[0], o.read(scr + 0x2e + 0x28 * b, 1)[0])
def reposition(x, y, row_heights):
    for i, h in enumerate(row_heights): o.write(scr + 0xd84 + 0x20 * i + 0xc, struct.pack('<i', h))
    o.write(scr + 0xd70, struct.pack('<i', 0))
    o.call(REPOS, scr, x & 0xffffffff, y & 0xffffffff)
    rows = []
    for i in range(5):
        rows.append((s32(o.u32(scr + 0xd84 + 0x20 * i)), s32(o.u32(scr + 0xd84 + 0x20 * i + 4))))
    return (s32(o.u32(scr + 0xd64)), s32(o.u32(scr + 0xd68))), rows
if __name__ == '__main__':
    print('mutex addr is found from the disassembly: see docs/roadmap.md')
