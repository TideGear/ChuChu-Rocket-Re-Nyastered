"""List direct calls through a literal-pool load of FUN_8c01203a in 1ST_READ.BIN.

usage: dc_se_calls.py [1ST_READ.BIN] [functions.txt] (defaults: local/cache/assets/dreamcast/files, analysis/decomp/dc_1st)
Recognizes immediate IDs passed in r4 or via mov #imm,r5 -> mov r5,r4, including r5-to-r4 in the JSR delay slot. A '?' means this local scan did not resolve the ID; it does not prove the ID is dynamic."""
import bisect
import struct
import sys

BASE = 0x8c010000
TARGET = 0x8c01203a


def main(binary='local/cache/assets/dreamcast/files/1ST_READ.BIN', functions='analysis/decomp/dc_1st/1ST_READ.BIN.functions.txt'):
    data = open(binary, 'rb').read()
    starts = sorted(int(line.split()[0], 16) for line in open(functions))
    names = {int(line.split()[0], 16): line.split()[-1] for line in open(functions)}

    def func(address):
        return starts[bisect.bisect_right(starts, address) - 1]

    def word(i):
        return struct.unpack_from('<H', data, i)[0]

    rows = []
    for i in range(0, len(data) - 1, 2):
        op = word(i)
        if op & 0xf000 != 0xd000:                      # mov.l @(disp,PC),Rn
            continue
        pc = BASE + i
        ea = ((pc + 4) & ~3) + (op & 0xff) * 4
        j = ea - BASE
        if not 0 <= j <= len(data) - 4 or struct.unpack_from('<I', data, j)[0] != TARGET:
            continue
        reg = op >> 8 & 15
        for k in range(i + 2, min(i + 2 + 2 * 24, len(data) - 1), 2):
            call = word(k)
            if call == 0x400b | reg << 8:               # jsr @Rn
                cue = None
                delay = word(k + 2)
                if delay == 0x6453:                      # mov r5,r4 in the JSR delay slot
                    for m in range(k - 2, max(k - 2 * 8, 0), -2):
                        w = word(m)
                        if w & 0xff00 == 0xe500:         # nearest definition: mov #imm,r5
                            cue = w & 0xff
                            break
                        if w & 0x0f00 == 0x0500:         # r5 was computed/loaded first
                            break
                elif delay & 0xff00 == 0xe500:           # delay slot writes r5; resolve r4 before it
                    for m in range(k - 2, max(i - 2 * 14, 0), -2):
                        w = word(m)
                        if w & 0xff00 == 0xe400:         # mov #imm,r4
                            cue = w & 0xff
                            break
                        if w & 0xf00f == 0x6003 and (w >> 8) & 15 == 4:  # mov Rm,r4
                            src = (w >> 4) & 15
                            for n in range(m - 2, max(i - 2 * 14, 0), -2):
                                v = word(n)
                                if v & 0xf000 == 0xe000 and (v >> 8) & 15 == src:
                                    cue = v & 0xff
                                    break
                                if v & 0x0f00 == src << 8:
                                    break
                            break
                        if w & 0x0f00 == 0x0400 and w & 0xf000 in (0xe000, 0xd000, 0x6000, 0x1000):
                            break
                if cue is None:
                    for m in range(k + 2, max(i - 2 * 14, 0), -2): # delay slot first, then backwards
                        if m == k:
                            continue
                        w = word(m)
                        if w & 0xff00 == 0xe400:         # mov #imm,r4
                            cue = w & 0xff
                            break
                        if w & 0x0f00 == 0x0400 and w & 0xf000 in (0xe000, 0xd000, 0x6000, 0x1000):
                            break
                rows.append((BASE + k, func(BASE + k), cue))
                break
            if call & 0xf00f == 0x400b and (call >> 8 & 15) != reg:
                continue
    for site, f, cue in rows:
        print('%08x  func %08x  cue %s' % (site, f, '?' if cue is None else cue))
    print(len(rows), 'calls')


if __name__ == '__main__':
    main(*sys.argv[1:3])
