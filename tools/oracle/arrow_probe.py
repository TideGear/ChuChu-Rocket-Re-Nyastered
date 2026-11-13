import struct, sys
sys.path.insert(0, '.')
from cat_run import *
def load_stage(index, src=0, path=r'C:\Dev\ChuChu Rocket\local\testdata\gba_stages.bin'):
    f = open(path, 'rb'); n, = struct.unpack('<I', f.read(4))
    for i in range(n):
        s, nsol, idx = struct.unpack('<BBH', f.read(4)); tiles = f.read(108); walls = f.read(237); sol = [tuple(f.read(3)) for _ in range(nsol)]; title = f.read(32).rstrip(b'\0')
        if s == src and idx == index: return tiles, walls, sol, title
def coll_from(tiles, walls):
    c = [[0] * 12 for _ in range(9)]
    for r in range(9):
        for k in range(12):
            if walls[25 * r + k]: c[r][k] |= 0x40000
            if walls[25 * (r + 1) + k]: c[r][k] |= 0x10000
            if walls[25 * r + 12 + k]: c[r][k] |= 0x20000
            if walls[25 * r + 12 + k + 1]: c[r][k] |= 0x80000
    return c
ARR = (lit(0x2823c) + 0x281fa - G + 0x28) & 0xffffffff          # puzzle arrow table (player 0, slot 0 begins at +8)
def put_arrow(slot, x, y, d, ttl=600):
    a = BASE + ARR + 8 + 0x18 * slot
    o.write(a, struct.pack('<BBHihh', d, 0, 0, ttl, x, y))   # +0 dir,+1 hits,+4 ttl,+8 x,+0xa y
def arrow_hits(slot): return o.read(BASE + ARR + 8 + 0x18 * slot, 12)
if __name__ == '__main__':
    tiles, walls, sol, title = load_stage(59)
    coll = coll_from(tiles, walls)
    print(title, 'arrows:', sol)
    # refresh arrow cell flags: (1,5) south
    coll[5][1] |= 0x800 | 0
    set_coll(coll)
    for s in range(12): o.write(BASE + ARR + 8 + 0x18 * s, struct.pack('<ii', 0, -1))   # all slots empty (ttl -1)
    put_arrow(0, 1, 5, 0)
    # fix ttl field layout check
    print('slot0 bytes', arrow_hits(0).hex())
    put_entity(1, 7, 2)
    last = None
    for t in range(1, 160):
        gcall(0x28ffc, ent); st = state(); h = arrow_hits(0)
        cur = (h[0], h[1], struct.unpack('<i', h[4:8])[0])
        if cur != last or t in (30, 31, 60, 90, 91, 92):
            print('t=%d cat %s arrow(dir,hits,ttl)=%s' % (t, st, cur)); last = cur
