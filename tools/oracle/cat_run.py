import struct, math, sys, random
sys.path.insert(0, '.')
from cat_probe import *
init_tables(); gcall(0x2ed04); gcall(0x2ed30, 0)
COLL = (lit(0x2de50) + 0x2de74 - G) & 0xffffffff
ent = o.heap_ptr; o.heap_ptr += 0x100
def set_coll(coll):          # coll[r][c] words
    for r in range(9):
        for c in range(12): o.write(BASE + COLL + 4 * (r * 12 + c), struct.pack('<I', coll[r][c]))
def put_entity(gx, gy, heading, speed_cat=True):
    o.write(ent, b'\0' * 0x100)
    o.write(ent + 0x10, struct.pack('<hh', gx, gy))
    o.write(ent + 0x14, struct.pack('<fff', (gx + 0.5) * 15, 0.0, (gy + 0.5) * 15))
    o.write(ent + 0x20, struct.pack('<II', heading << 14, heading << 14))
    o.write(ent + 0x2c, struct.pack('<f', 1.0))
def state():
    gx, gy = struct.unpack('<hh', o.read(ent + 0x10, 4)); x, y, z = struct.unpack('<fff', o.read(ent + 0x14, 12))
    hd = struct.unpack('<I', o.read(ent + 0x24, 4))[0]
    return gx, gy, round(x, 3), round(z, 3), hd >> 14
if __name__ == '__main__':
    # open board with an outer wall ring, cat at (5,4) heading south
    W = {'S': 0x10000, 'W': 0x20000, 'N': 0x40000, 'E': 0x80000}
    coll = [[0] * 12 for _ in range(9)]
    for c in range(12): coll[0][c] |= W['N']; coll[8][c] |= W['S']
    for r in range(9): coll[r][0] |= W['W']; coll[r][11] |= W['E']
    set_coll(coll); put_entity(5, 4, 0)
    for t in range(1, 80):
        gcall(0x28ffc, ent)
        if t % 5 == 0 or t < 4: print(t, state())
    print('imports used:', sorted(set(o.calls)), 'unhandled:', o.unhandled)
