"""Check Editor::calculateCRC (Android 1.15, 0x2ce38, table from Editor::initializeCRC 0x2cde0) against zlib.crc32 on random buffers.
usage: editor_crc_diff.py [cases]"""
import random, sys, zlib
sys.path.insert(0, '.')
from cat_probe import *
o.call(0x2cde0 - G)    # initializeCRC fills the library's table
rng = random.Random(5); bad = 0; cases = int(sys.argv[1]) if len(sys.argv) > 1 else 300
for k in range(cases):
    n = rng.choice((0, 1, 2, 7, 16, 100, 380, 0x17c, 724))
    data = bytes(rng.getrandbits(8) for _ in range(n))
    buf = o.heap_ptr; o.heap_ptr += 0x400; o.write(buf, data)
    got = o.call(0x2ce38 - G, buf, n) & 0xffffffff
    want = zlib.crc32(data) & 0xffffffff if n else 0
    if got != want:
        bad += 1; print('MISMATCH len', n, hex(got), hex(want))
        if bad > 5: break
print('calculateCRC: %d cases, mismatches %d (zero length returns 0)' % (cases, bad))
