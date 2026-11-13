import struct, sys
sys.path.insert(0, '.')
from cat_run import *
from unicorn import UC_HOOK_CODE
# second entity for the mouse
ent2 = o.heap_ptr; o.heap_ptr += 0x100
def put2(gx, gy, h, off=0.0):
    o.write(ent2, b'\0' * 0x100); o.write(ent2 + 0x10, struct.pack('<hh', gx, gy))
    o.write(ent2 + 0x14, struct.pack('<fff', (gx + 0.5) * 15 + off, 0.0, (gy + 0.5) * 15)); o.write(ent2 + 0x20, struct.pack('<II', h << 14, h << 14)); o.write(ent2 + 0x2c, struct.pack('<f', 1.0))
def st2():
    gx, gy = struct.unpack('<hh', o.read(ent2 + 0x10, 4)); x, y, z = struct.unpack('<fff', o.read(ent2 + 0x14, 12)); hd = struct.unpack('<I', o.read(ent2 + 0x24, 4))[0]
    return gx, gy, round(x, 3), round(z, 3), hd >> 14
log = []
def watch(ga, name):
    def cb(uc, a, s, u): log.append((name, uc.reg_read(UC_ARM_REG_R0), uc.reg_read(UC_ARM_REG_R1)))
    o.uc.hook_add(UC_HOOK_CODE, cb, begin=BASE + ga - G, end=BASE + ga - G + 2)
watch(0x3dc0c, 'SmpTskChangeExeFunction'); watch(0x3dc20, 'SmpTskChangeDrawFunction')
if __name__ == '__main__':
    W = {'S': 0x10000, 'W': 0x20000, 'N': 0x40000, 'E': 0x80000}
    coll = [[0] * 12 for _ in range(9)]
    for c in range(12): coll[0][c] |= W['N']; coll[8][c] |= W['S']
    for r in range(9): coll[r][0] |= W['W']; coll[r][11] |= W['E']
    set_coll(coll)
    for cat_start, mouse_start in (((9, 4, 1), (2, 4, 3)), ((6, 4, 1), (2, 4, 3)), ((2, 4, 3), (9, 4, 1))):
        o.write(BASE + 0, o.read(BASE, 1))
        put_entity(*cat_start); put2(*mouse_start); log.clear()
        eaten0 = gcall(0x34ea8)
        first = None
        for t in range(1, 200):
            gcall(0x2993c)                 # SmpColLoopInit
            gcall(0x28ffc, ent)            # cat tick
            gcall(0x3501c, ent2)           # mouse tick
            gcall(0x29b1c)                 # SmpColAnalyze
            c, m = state(), st2()
            d = math.hypot(c[2] - m[2], c[3] - m[3])
            if log and first is None:
                first = (t, d, c, m, [l[0] for l in log]); break
        print('cat start', cat_start, 'mouse start', mouse_start, '->', first, 'eaten counter', eaten0, gcall(0x34ea8))
