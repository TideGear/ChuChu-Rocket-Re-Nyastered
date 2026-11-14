"""Run one pure function of the GBA ROM's CPU player code (user's own ROM, Unicorn ARM/Thumb) on random states and write cases + the original's outputs, for the port's differential test.
usage: gba_cpu_gen.py <rule> <cases> <out.txt> [seed]    rule = neighbour (0x08009D60) | area (0x0800A434) | follow (0x0800A654)
Line format: player flags phase mode cursorx_px cursory_px tx ty target | 108 heat | 567 field | 4 thr... | count then entries (x y dir) of the queue."""
import os, random, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gba_oracle import GBA
from unicorn.arm_const import *
from unicorn import UC_HOOK_CODE
ROM = r'C:\Dev\ChuChu Rocket\analysis\gba\ccr.gba'
FN = {'neighbour': 0x8009D60, 'area': 0x800A434, 'follow': 0x800A654, 'path': 0x800990C, 'dirdelta': 0x80098A0, 'special': 0x800A854, 'finish': 0x800AA1C, 'think': 0x800AC1C, 'heatstep': 0x8009568, 'task': 0x800ACE8, 'ready': 0x8009D44, 'longest': 0x8009B2C, 'wallclass': 0x8009C80, 'walk': 0x8009A20, 'target': 0x800AAF4}
LCG = 0x30001f8
REC, PHASE, QCNT, QBUF, HEAT, FIELD, CURS, MODE = 0x3000220, 0x3000274, 0x3000260, 0x3000268, 0x3000278, 0x30029a0, 0x3002c68, 0x3002990
FAKE = 0x3000700
def main():
    rule, n, out = sys.argv[1], int(sys.argv[2]), sys.argv[3]; rnd = random.Random(int(sys.argv[4]) if len(sys.argv) > 4 else 1)
    g = GBA(ROM); uc = g.uc; fn = FN[rule]; lines = []
    for _ in range(n):
        p = rnd.randrange(4); flags = rnd.choice([0x00, 0x55, 0x66, 0x48, 0x6a, rnd.randrange(256)]); phase = rnd.randrange(256); cx, cy = rnd.randrange(12), rnd.randrange(9)
        px, py = 2 * cx + 2 + rnd.randrange(2), 2 * cy + 2 + rnd.randrange(2)
        heat = [rnd.choice([0, 0, rnd.randrange(-200, 400), rnd.randrange(-30, 30), -100, 100, 50]) for _ in range(108)]
        field = bytes(rnd.choice([0, 0, 0, 0, 0x80, 0x80, 0x20, 0xa0, 0x10, rnd.randrange(256)]) for _ in range(567))
        tgt = rnd.choice([-1, rnd.randrange(4)]); tx, ty = rnd.randrange(12), rnd.randrange(9)
        for k in range(4): uc.mem_write(CURS + 2 * k, bytes([2 * rnd.randrange(12) + 2, 2 * rnd.randrange(9) + 2]))
        uc.mem_write(CURS + 2 * p, bytes([px, py]))
        if tgt >= 0 and tgt != p: uc.mem_write(CURS + 2 * tgt, bytes([2 * tx + 2, 2 * ty + 2]))
        uc.mem_write(REC + 16 * p + 1, bytes([flags])); uc.mem_write(REC + 16 * p + 2, bytes([tgt & 0xff]))
        phase = (phase & ~3) | p if (rule in ('area', 'follow') and rnd.random() < 0.9) else phase; uc.mem_write(PHASE, bytes([phase])); uc.mem_write(MODE, bytes([0]))
        uc.mem_write(HEAT, struct.pack('<108h', *heat)); uc.mem_write(FIELD, field)
        uc.mem_write(FAKE, bytes([0, 0, 0, p] + [0] * 60))
        uc.mem_write(QCNT, bytes([0]))
        ARR = 0x3002c10
        ex = []
        for k in range(4):
            n = rnd.randrange(4); base = ARR + 20 * k; uc.mem_write(base, struct.pack('<h', rnd.randrange(-5, 400))); uc.mem_write(base + 6, bytes([n]))
            for j in range(n):
                ax, ay, ad = rnd.randrange(12), rnd.randrange(9), rnd.choice([0, 4, 8, 12])
                uc.mem_write(base + 7 + 4 * j, bytes([ad])); uc.mem_write(base + 8 + 4 * j, bytes([2 * ax + 2 + rnd.randrange(2), 2 * ay + 2 + rnd.randrange(2)]))
                ex.append((ax, ay, ad))
        for k in range(4): uc.mem_write(0x3002c90 + 3 * k, bytes([rnd.choice([0, 0, 1, 2, 3, 4, 5, 6])])); uc.mem_write(0x3000508 + k, bytes([k])); uc.mem_write(0x300050c + k, bytes([k]))
        order = list(range(4)); rnd.shuffle(order)
        for k in range(4): uc.mem_write(0x300050c + k, bytes([order[k]])); uc.mem_write(0x3000508 + order[k], bytes([k]))
        uc.mem_write(REC + 16 * p + 0xc, bytes(4)); st8 = rnd.choice([0, 100, 0x257, 0x258, 0x300, 1000]); stc = rnd.randrange(4); uc.mem_write(REC + 16 * p + 8, struct.pack('<H', st8)); uc.mem_write(REC + 16 * p + 0xa, bytes([stc]))
        sv = [rnd.randrange(-50, 50), rnd.randrange(-50, 50)]; sc = [rnd.randrange(12), rnd.randrange(9), rnd.randrange(12), rnd.randrange(9)]
        uc.mem_write(0x3000500, struct.pack('<hh', *sv)); uc.mem_write(0x3000504, bytes(sc))
        if rule in ('target', 'think'): uc.mem_write(MODE, bytes([rnd.choice([0, 0, 0, 1, 6, 2])]))
        qn0 = 0
        if rule == 'finish':
            qn0 = rnd.randrange(4); uc.mem_write(QCNT, bytes([qn0]))
            for j in range(qn0):
                c = rnd.choice(ex) if ex and rnd.random() < 0.6 else (rnd.randrange(12), rnd.randrange(9), rnd.choice([0, 4, 8, 12]))
                uc.mem_write(QBUF + 4 * j, bytes([c[0], c[1], c[2], 0]))
        if rule == 'heatstep':
            for base in (0x3002de0, 0x3000350, 0x3000428): uc.mem_write(base, struct.pack('<108h', *[rnd.choice([0, 0, rnd.randrange(-300, 600), -100, 50, 25]) for _ in range(108)]))
        if rule == 'task':
            cell_x, cell_y = rnd.randrange(12), rnd.randrange(9)
            sx, sy = cell_x * 16 + rnd.randrange(16), cell_y * 16 + rnd.randrange(16)
            uc.mem_write(FAKE + 8, struct.pack('<H', 2 * (sx >> 4) + 2)); uc.mem_write(FAKE + 0xc, struct.pack('<H', 2 * (sy >> 4) + 2)); uc.mem_write(FAKE + 0x1e, bytes([sx, sy]))
            uc.mem_write(CURS + 2 * p, bytes([2 * (sx >> 4) + 2 + rnd.randrange(2), 2 * (sy >> 4) + 2 + rnd.randrange(2)]))
            uc.mem_write(REC + 16 * p, bytes([rnd.choice([0, 0, 1, 1, 2])])); uc.mem_write(REC + 16 * p + 4, struct.pack('<H', rnd.choice([0, 3, 9, 10, 11, 20])))
            uc.mem_write(REC + 16 * p + 6, struct.pack('<h', rnd.randrange(-5, 400)))
            uc.mem_write(REC + 16 * p + 0xc, bytes([rnd.randrange(12), rnd.randrange(9), rnd.choice([0, 4, 8, 12]), 0]))
            if rnd.random() < 0.4: uc.mem_write(REC + 16 * p + 0xc, bytes([sx >> 4, sy >> 4, rnd.choice([0, 4, 8, 12]), 0]))
            c4 = rnd.choice([0xb, 0, 3]); uc.mem_write(0x3002cc4, bytes([c4]))
        lcg0 = rnd.randrange(1 << 32); uc.mem_write(LCG, struct.pack('<I', lcg0))
        args = [FAKE, 0, 0, 0]
        if rule == 'path': args = [p, rnd.randrange(-1, 13) & 0xff, rnd.randrange(-1, 10) & 0xff, rnd.choice([0, 4, 8, 12])]
        if rule in ('longest', 'wallclass', 'walk'): args = [rnd.randrange(0, 12), rnd.randrange(0, 9), 0, 0]
        if rule == 'dirdelta': args = [rnd.randrange(-6, 7) & 0xffffffff, rnd.randrange(-6, 7) & 0xffffffff, 0, 0]
        for i, a in enumerate(args): uc.reg_write(UC_ARM_REG_R0 + i, a & 0xffffffff)
        uc.reg_write(UC_ARM_REG_SP, 0x3007e00)
        ret = 0x2000100; uc.mem_write(ret, b'\xfe\xe7'); uc.reg_write(UC_ARM_REG_LR, ret | 1)
        seed_in = bytes(uc.mem_read(0x3002de0, 216)); a_in = bytes(uc.mem_read(0x3000350, 216)); b_in = bytes(uc.mem_read(0x3000428, 216))
        sx_in = struct.unpack('<2B', bytes(uc.mem_read(FAKE + 0x1e, 2)))[0]; sy_in = uc.mem_read(FAKE + 0x1f, 1)[0]; c4_in = uc.mem_read(0x3002cc4, 1)[0]
        tin = [uc.mem_read(REC + 16 * p, 1)[0], struct.unpack('<H', bytes(uc.mem_read(REC + 16 * p + 4, 2)))[0], struct.unpack('<h', bytes(uc.mem_read(REC + 16 * p + 6, 2)))[0]] + list(uc.mem_read(REC + 16 * p + 0xc, 3)) + [struct.unpack('<H', bytes(uc.mem_read(FAKE + 8, 2)))[0], struct.unpack('<H', bytes(uc.mem_read(FAKE + 0xc, 2)))[0]]
        pushes = []
        hk = uc.hook_add(UC_HOOK_CODE, lambda u, a, sz, d: pushes.append((u.reg_read(UC_ARM_REG_LR) & ~1, bytes(u.mem_read(u.reg_read(UC_ARM_REG_R0), 3)))), begin=0x8009870, end=0x8009871)
        plc = []
        def plc_hook(u, a, sz, d):
            plc.append((u.reg_read(UC_ARM_REG_R1) & 0xff, struct.unpack('<H', bytes(u.mem_read(FAKE + 8, 2)))[0], struct.unpack('<H', bytes(u.mem_read(FAKE + 0xc, 2)))[0])); u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))
        hk2 = uc.hook_add(UC_HOOK_CODE, plc_hook, begin=0x8004ef0, end=0x8004ef1)
        uc.emu_start(fn | 1, ret, count=2000000); uc.hook_del(hk); uc.hook_del(hk2)
        if os.environ.get('GBAPUSH'): print(len(lines) + 1, [(hex(a), list(b)) for a, b in pushes])
        cnt = uc.mem_read(QCNT, 1)[0]; q = bytes(uc.mem_read(QBUF, 4 * 3)); r0 = uc.reg_read(UC_ARM_REG_R0) & 0xffffffff; lcg1 = struct.unpack('<I', bytes(uc.mem_read(LCG, 4)))[0]
        lines.append('%d %d %d %d %d %d %d %d %d | %s | %s | %d %s' % (p, flags, phase, 0, px, py, tx, ty, tgt, ' '.join(map(str, heat)), field.hex(), cnt, ' '.join(str(b) for b in q)) + ' | %d %d %d %s' % (r0, lcg0, lcg1, ' '.join(map(str, args))) + ' | ' + ' '.join(str(b) for b in uc.mem_read(REC + 16 * p + 0xc, 4)) + ' | ' + ' '.join(str(b) for b in uc.mem_read(ARR, 80)) + ' | %d %d %d %d %d %d %d %d' % ((qn0, uc.mem_read(MODE, 1)[0]) + tuple(sv) + tuple(sc)) + ' | ' + ' '.join(str(b) for b in uc.mem_read(0x3000508, 8)) + ' | ' + ' '.join(str(b) for b in uc.mem_read(0x3002c90, 12)) + ' | ' + ' '.join(str(b) for b in q) + ' | %d %d %d' % (uc.mem_read(REC + 16 * p + 2, 1)[0], struct.unpack('<H', bytes(uc.mem_read(REC + 16 * p + 8, 2)))[0], uc.mem_read(REC + 16 * p + 0xa, 1)[0]) + ' | %d %d' % (st8, stc) + ' | ' + ' '.join(str(b) for b in uc.mem_read(CURS, 8)) + ' | ' + ' '.join(map(str, struct.unpack('<108h', bytes(uc.mem_read(0x3000350, 216))) + struct.unpack('<108h', bytes(uc.mem_read(0x3000428, 216))) + struct.unpack('<108h', bytes(uc.mem_read(0x3000278, 216))))) + ' | ' + ' '.join(map(str, struct.unpack('<108h', seed_in))) + ' | ' + ' '.join(map(str, struct.unpack('<108h', bytes(uc.mem_read(0x3000350, 216)) if False else a_in))) + ' | ' + ' '.join(map(str, struct.unpack('<108h', b_in))) + ' | ' + ' '.join(str(b) for b in uc.mem_read(0x3000500, 8)) + ' | ' + ' '.join(map(str, [uc.mem_read(REC + 16 * p, 1)[0], struct.unpack('<H', bytes(uc.mem_read(REC + 16 * p + 4, 2)))[0], struct.unpack('<h', bytes(uc.mem_read(REC + 16 * p + 6, 2)))[0], struct.unpack('<H', bytes(uc.mem_read(REC + 16 * p + 8, 2)))[0]] + list(uc.mem_read(REC + 16 * p + 0xc, 3)) + list(uc.mem_read(FAKE + 0x1e, 2)) + [struct.unpack('<H', bytes(uc.mem_read(FAKE + o, 2)))[0] for o in (8, 0xc, 0xa, 0xe)] + [uc.mem_read(FAKE + 0x18, 1)[0], len(plc)] + [v for t in plc for v in t])) + ' | %d %d %d %s' % (sx_in, sy_in, c4_in, ' '.join(map(str, tin))))
    open(out, 'w').write('\n'.join(lines) + '\n'); print('wrote', len(lines), 'cases for', rule)
main()
