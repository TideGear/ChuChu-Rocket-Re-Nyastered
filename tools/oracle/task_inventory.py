#!/usr/bin/env python3
"""List every task the Dreamcast game creates, from the code (goal.md: animations and sounds come from the decompile, not from captures).

usage: task_inventory.py [--creator 0x8c01f0a0] [--call 0xADDR ...]
For each call site of the task creator (r4 = update callback, r5 = draw callback, as at 0x8c01410a), prints the call site, the function it sits in
(the nearest preceding `sts.l pr,@-r15` prologue), and the r4/r5/r6/r7 values loaded from literal pools before the call. With --call, lists call
sites of other functions the same way (e.g. a sound-effect entry), with their argument registers."""
import argparse, os, struct
from capstone import Cs, CS_ARCH_SH, CS_MODE_SH4, CS_MODE_LITTLE_ENDIAN, CS_MODE_SHFPU

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
B = 0x8c010000


def load():
    return open(os.path.join(ROOT, 'local/cache/assets/dreamcast/files/1ST_READ.BIN'), 'rb').read()


def scan(d, targets):
    md = Cs(CS_ARCH_SH, CS_MODE_SH4 | CS_MODE_LITTLE_ENDIAN | CS_MODE_SHFPU)
    u16 = lambda a: struct.unpack_from('<H', d, a - B)[0]
    u32 = lambda a: struct.unpack_from('<I', d, a - B)[0]
    regs = {}; func = B; out = []
    pc = B; end = B + len(d) - 2
    while pc < end:
        op = u16(pc)
        if op == 0x4f22: func = pc; regs = {}                          # sts.l pr,@-r15: a function prologue
        n = (op >> 8) & 15
        if (op & 0xf000) == 0xd000:                                      # mov.l @(disp,pc),Rn
            t = ((pc + 4) & ~3) + (op & 0xff) * 4
            if t < end: regs[n] = u32(t)
        elif (op & 0xf000) == 0x9000:                                    # mov.w @(disp,pc),Rn
            t = pc + 4 + (op & 0xff) * 2; v = u16(t); regs[n] = v - 0x10000 if v & 0x8000 else v
        elif (op & 0xf000) == 0xe000:                                    # mov #imm,Rn
            v = op & 0xff; regs[n] = v - 0x100 if v & 0x80 else v
        elif (op & 0xf0ff) in (0x400b, 0x402b) or (op & 0xf000) == 0xb000:   # jsr/jmp @Rn, or bsr disp (a direct call within +-4 KB)
            if (op & 0xf000) == 0xb000: disp = op & 0xfff; tgt = pc + 4 + 2 * (disp - 0x1000 if disp & 0x800 else disp)
            else: tgt = regs.get(n)
            if tgt in targets:
                d0 = u16(pc + 2); nd = (d0 >> 8) & 15                    # the delay slot may load an argument
                args = dict(regs)
                if (d0 & 0xf000) == 0xd000: args[nd] = u32(((pc + 6) & ~3) + (d0 & 0xff) * 4)
                elif (d0 & 0xf000) == 0xe000: v = d0 & 0xff; args[nd] = v - 0x100 if v & 0x80 else v
                out.append((tgt, pc, func, [args.get(r) for r in (4, 5, 6, 7)]))
        pc += 2
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--creator', default='0x8c01f0a0'); ap.add_argument('--call', nargs='*', default=[])
    a = ap.parse_args()
    targets = {int(a.creator, 16)} | {int(x, 16) for x in a.call}
    fmt = lambda v: '-' if v is None else hex(v) if isinstance(v, int) and v > 0xffff else str(v)
    for tgt, site, func, args in scan(load(), targets):
        print(f'{tgt:#x} at {site:#x} in {func:#x}: r4 {fmt(args[0])} r5 {fmt(args[1])} r6 {fmt(args[2])} r7 {fmt(args[3])}')


if __name__ == '__main__':
    main()
