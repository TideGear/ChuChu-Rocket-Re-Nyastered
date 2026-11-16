"""Differential test of Editor::convertField (Android 1.15, ghidra 0x2d0ec) against a Python model of the same conversion.
usage: editor_convert_diff.py [cases] [seed]
The editor data is 12 x 9 little-endian 32-bit cell words (row stride 0x30) followed at +0x1b0 by the zero-terminated title.
Cell word: bits 8..11 object class (0x100 rocket, 0x200 arrow of direction 0, 0x300 arrow 1, 0x400 arrow 3 -> counted in stock bytes 0x15e, 0x15c, 0x15d, 0x15f),
low byte: nibble 1 = cat (colour in the high nibble 1..4 -> tiles 0xf 0xd 0xe 0x10), 2 = mouse (1..4 -> 0xb 9 0xa 0xc), 3 = rocket tile 1, 4 = hole tile 0x11;
bit 12 north wall of the cell, bit 13 south wall (read for the bottom row), bit 14 west wall, bit 15 east wall (read for the last column)."""
import random, struct, sys
sys.path.insert(0, '.')
from cat_probe import *


def model(cells, title):
    """cells[9][12] words, title bytes -> (stage bytes 0x180, arrow list, count)"""
    st = bytearray(0x180)
    arrows = []
    for r in range(9):
        for c in range(12):
            w = cells[r][c]
            cls = w & 0xf00
            if cls == 0x200: st[0x15c] += 1; arrows.append((c, r, 0))
            elif cls == 0x300: st[0x15d] += 1; arrows.append((c, r, 1))
            elif cls == 0x100: st[0x15e] += 1; arrows.append((c, r, 2))
            elif cls == 0x400: st[0x15f] += 1; arrows.append((c, r, 3))
            low, high = w & 0xf, w & 0xf0
            t = 0
            if low == 2: t = {0x10: 0xb, 0x20: 9, 0x30: 0xa, 0x40: 0xc}.get(high, 0)
            elif low == 1: t = {0x10: 0xf, 0x20: 0xd, 0x30: 0xe, 0x40: 0x10}.get(high, 0)
            elif low == 3: t = 1
            elif low == 4: t = 0x11
            st[12 * r + c] = t
    for r in range(10):
        for c in range(12):
            st[0x6c + 25 * r + c] = (cells[r][c] >> 12) & 1 if r < 9 else (cells[8][c] >> 13) & 1
    for r in range(9):
        for c in range(12): st[0x78 + 25 * r + c] = (cells[r][c] >> 14) & 1
        st[0x78 + 25 * r + 12] = (cells[r][11] >> 15) & 1
    t = bytearray()
    for i in range(0x15):
        ch = title[i] if i < len(title) else 0
        t.append(ch)
        if ch == 0:
            t.extend(b'\0' * (0x15 - i - 1)); break
    st[0x160:0x160 + 0x15] = t[:0x15]
    return bytes(st), arrows, len(arrows)


def main(cases, seed):
    rng = random.Random(seed)
    fn = 0x2d0ed - 1
    bad = 0
    for k in range(cases):
        cells = [[0] * 12 for _ in range(9)]
        for r in range(9):
            for c in range(12):
                w = 0
                if rng.random() < 0.5: w |= rng.choice((1, 2, 3, 4)) | rng.choice((0, 0x10, 0x20, 0x30, 0x40))
                if rng.random() < 0.25: w |= rng.choice((0x100, 0x200, 0x300, 0x400, 0x500))
                w |= rng.getrandbits(4) << 12
                if rng.random() < 0.1: w |= rng.getrandbits(8) << 16
                cells[r][c] = w
        title = bytes(rng.randrange(1, 255) for _ in range(rng.randrange(0, 24)))
        if rng.random() < 0.3 and title: title = title[:rng.randrange(0, len(title) + 1)]
        buf = o.heap_ptr; o.heap_ptr += 0x400
        stg = o.heap_ptr; o.heap_ptr += 0x400
        arr = o.heap_ptr; o.heap_ptr += 0x400
        data = bytearray(0x1b0 + 0x20)
        for r in range(9):
            for c in range(12): struct.pack_into('<I', data, 0x30 * r + 4 * c, cells[r][c])
        data[0x1b0:0x1b0 + len(title)] = title
        o.write(buf, bytes(data)); o.write(stg, b'\xaa' * 0x200); o.write(arr, b'\xaa' * 0x400)
        got_n = o.call(0x2d0ec - G, stg, arr, buf) & 0xffffffff
        got = o.read(stg, 0x180)
        want, arrows, n = model(cells, title)
        got_arrows = [struct.unpack('<HHI', o.read(arr + 8 * i, 8)) for i in range(n)]
        written = list(range(0x159)) + list(range(0x15c, 0x175))   # bytes 0x159 to 0x15b and everything from 0x175 are never written by the function
        ok = all(got[i] == want[i] for i in written) and got_n == n and got_arrows == arrows
        if not ok:
            bad += 1
            diff = [i for i in written if got[i] != want[i]]
            print('case', k, 'MISMATCH count got', got_n, 'want', n, 'first byte diffs', diff[:8], 'arrows same', got_arrows == arrows)
            if bad > 5: break
    print('editor convertField: %d cases, mismatches %d' % (cases, bad))


if __name__ == '__main__':
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 200, int(sys.argv[2]) if len(sys.argv) > 2 else 1)
