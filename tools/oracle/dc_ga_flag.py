"""Runs the Dreamcast GA_OnGameFlag (0x8C016AD4, from the user's 1ST_READ.BIN) in the SH-4 interpreter for every speed-option index; prints the scale it stores."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from sh4 import SH4, u2f
d = open(os.path.join(os.path.dirname(__file__), '../../local/cache/assets/dreamcast/files/1ST_READ.BIN'), 'rb').read()
for idx in range(5):
    m = SH4(); m.load(0x8C010000, d)
    m.hooks[0x8c01907c & 0x1fffffff] = lambda m: m.r.__setitem__(0, 12)            # GA_GetMode -> 12
    def opts(m): m.wr32(m.r[4] + 12, idx); m.r[0] = 1                                # option block
    m.hooks[0x8c052038 & 0x1fffffff] = opts
    m.call(0x8c016ad4)
    print('option', idx, 'scale', u2f(m.rd32(0x8c1ae8c4)))
