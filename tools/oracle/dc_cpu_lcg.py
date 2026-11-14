"""Differential test: the Dreamcast CPU-AI random generator (0x8C012720 in 1ST_READ.BIN, state at 0x8C186B34, run in the SH-4 interpreter) vs the port's CpuLcg (game/core/cpu.hpp):
state = state * 1103515245 + 12345 (32 bit); result = float((state << 1) >> 17) * (1/32768). usage: dc_cpu_lcg.py [seeds] [draws]"""
import sys, os, struct, random
sys.path.insert(0, os.path.dirname(__file__))
from sh4 import SH4, u2f
d = open(os.path.join(os.path.dirname(__file__), '../../local/cache/assets/dreamcast/files/1ST_READ.BIN'), 'rb').read()
S = 0x8c186b34
seeds = int(sys.argv[1]) if len(sys.argv) > 1 else 20; draws = int(sys.argv[2]) if len(sys.argv) > 2 else 2000
rng = random.Random(4); bad = 0; total = 0
m = SH4(); m.load(0x8C010000, d)
for s in range(seeds):
    st = rng.getrandbits(32) if s else 0; m.wr32(S, st); port = st
    for k in range(draws):
        m.call(0x8c012720); got = u2f(m.fr[0])
        port = (port * 1103515245 + 12345) & 0xffffffff
        exp = struct.unpack('<f', struct.pack('<f', float((port << 1 & 0xffffffff) >> 17) * (1.0 / 32768.0)))[0]
        total += 1
        if struct.pack('<f', got) != struct.pack('<f', exp) or m.rd32(S) != port:
            bad += 1
            if bad < 4: print('MISMATCH seed', hex(st), 'draw', k, got, exp)
print('dreamcast CPU-AI LCG: %d draws over %d seeds, %d different' % (total, seeds, bad))
