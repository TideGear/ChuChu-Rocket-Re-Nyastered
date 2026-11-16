"""Record Editor::convertField cases from the emulated original: local/testdata/editor_golden.bin
Per case: 432 bytes of cell words (9 x 12 x u32), 22 bytes title (21 + terminator, zero padded), u32 arrow count, 0x175 bytes of stage output, then count x (u16 x, u16 y, u32 type).
usage: make_editor_golden.py [cases] [seed]"""
import random, struct, sys
sys.path.insert(0, '.')
from cat_probe import *
cases = int(sys.argv[1]) if len(sys.argv) > 1 else 300; rng = random.Random(int(sys.argv[2]) if len(sys.argv) > 2 else 7)
out = open(r'C:\Dev\ChuChu Rocket\local\testdata\editor_golden.bin', 'wb'); out.write(struct.pack('<I', cases))
for k in range(cases):
    data = bytearray(0x1b0 + 0x20)
    for r in range(9):
        for c in range(12):
            w = 0
            if rng.random() < 0.5: w |= rng.choice((1, 2, 3, 4)) | rng.choice((0, 0x10, 0x20, 0x30, 0x40))
            if rng.random() < 0.25: w |= rng.choice((0x100, 0x200, 0x300, 0x400, 0x500))
            w |= rng.getrandbits(4) << 12
            if rng.random() < 0.1: w |= rng.getrandbits(8) << 16
            struct.pack_into('<I', data, 0x30 * r + 4 * c, w)
    title = bytes(rng.randrange(1, 255) for _ in range(rng.randrange(0, 24)))
    data[0x1b0:0x1b0 + len(title)] = title[:0x1f]
    buf = o.heap_ptr; o.heap_ptr += 0x400; stg = o.heap_ptr; o.heap_ptr += 0x400; arr = o.heap_ptr; o.heap_ptr += 0x400
    o.write(buf, bytes(data)); o.write(stg, b'\0' * 0x200); o.write(arr, b'\0' * 0x400)
    n = o.call(0x2d0ec - G, stg, arr, buf) & 0xffffffff
    out.write(bytes(data[:432])); out.write(bytes(data[0x1b0:0x1b0 + 22])); out.write(struct.pack('<I', n)); out.write(o.read(stg, 0x175)); out.write(o.read(arr, 8 * n))
out.close(); print(cases, 'cases ->', 'local/testdata/editor_golden.bin')
