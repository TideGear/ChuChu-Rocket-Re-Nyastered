"""Run one pure function of the GBA ROM's CPU player code (user's own ROM, Unicorn ARM/Thumb) on random states and write cases + the original's outputs, for the port's differential test.
usage: gba_cpu_gen.py <rule> <cases> <out.txt> [seed]    rule = neighbour (0x08009D60) | area (0x0800A434) | follow (0x0800A654)
Line format: player flags phase mode cursorx_px cursory_px tx ty target | 108 heat | 567 field | 4 thr... | count then entries (x y dir) of the queue."""
import os, random, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gba_oracle import GBA
from unicorn.arm_const import *
from unicorn import UC_HOOK_CODE
ROM = r'C:\Dev\ChuChu Rocket\analysis\gba\ccr.gba'
FN = {'neighbour': 0x8009D60, 'area': 0x800A434, 'follow': 0x800A654}
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
        uc.mem_write(PHASE, bytes([phase])); uc.mem_write(QCNT, bytes([0])); uc.mem_write(MODE, bytes([0]))
        uc.mem_write(HEAT, struct.pack('<108h', *heat)); uc.mem_write(FIELD, field)
        uc.mem_write(FAKE, bytes([0, 0, 0, p, 0, 0, 0, 0]))
        uc.reg_write(UC_ARM_REG_R0, FAKE); uc.reg_write(UC_ARM_REG_SP, 0x3007e00)
        ret = 0x2000100; uc.mem_write(ret, b'\xfe\xe7'); uc.reg_write(UC_ARM_REG_LR, ret | 1)
        pushes = []
        hk = uc.hook_add(UC_HOOK_CODE, lambda u, a, sz, d: pushes.append((u.reg_read(UC_ARM_REG_LR) & ~1, bytes(u.mem_read(u.reg_read(UC_ARM_REG_R0), 3)))), begin=0x8009870, end=0x8009871)
        uc.emu_start(fn | 1, ret, count=2000000); uc.hook_del(hk)
        if os.environ.get('GBAPUSH'): print(len(lines) + 1, [(hex(a), list(b)) for a, b in pushes])
        cnt = uc.mem_read(QCNT, 1)[0]; q = bytes(uc.mem_read(QBUF, 4 * 3))
        lines.append('%d %d %d %d %d %d %d %d %d | %s | %s | %d %s' % (p, flags, phase, 0, px, py, tx, ty, tgt, ' '.join(map(str, heat)), field.hex(), cnt, ' '.join(str(b) for b in q)))
    open(out, 'w').write('\n'.join(lines) + '\n'); print('wrote', len(lines), 'cases for', rule)
main()
