"""Compare dc_cursor_probe --cases output with the unmodified USA cursor routine.

usage: dc_cursor_probe.py <user RAM dump> <cases.txt>
Calls FUN_8c0145a0 including movement, clamp and grid conversion. Arrow callbacks
are observed stubs; no arrow buttons are set. This supplements, not replaces,
the C++ probe's live per-frame Flycast comparison.
"""
import struct
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from sh4 import SH4


def main():
    ram = Path(sys.argv[1]).read_bytes()
    m = SH4()
    if len(ram) != len(m.ram):
        raise ValueError('expected 16 MiB main RAM')
    m.ram[:] = ram
    task = 0x8c7f0000
    m.hooks[0x0c0109a0] = lambda _: None
    m.hooks[0x0c0109b0] = lambda _: None
    count = bad = 0
    for line in Path(sys.argv[2]).read_text().splitlines():
        raw, expected = line.split('|')
        fields = raw.split()
        x, y = map(float, fields[:2])
        tx, ty, held, ax, ay = map(int, fields[2:])
        output = expected.split()
        want_xy = struct.pack('<2f', *map(float, output[:2]))
        want_ints = tuple(map(int, output[2:]))
        m.load(task, bytes(64))
        m.wr8(task + 45, tx)
        m.wr8(task + 46, ty)
        m.load(0x8c1aee88, bytes(208))
        m.wr32(0x8c1aee90, held)
        m.wr16(0x8c1aeea4, ax)
        m.wr16(0x8c1aeea6, ay)
        m.load(0x8c186cf4, struct.pack('<BBhh2xfff', 1, 0, min(int(x / 15), 11), min(int(y / 15), 8), x, 0, y))
        m.call(0x8c0145a0, task, max_insn=20000)
        actual_xy = struct.pack('<II', m.rd32(0x8c186cfc), m.rd32(0x8c186d04))
        signed = lambda v: v - 256 if v & 128 else v
        actual_ints = (signed(m.rd8(task + 45)), signed(m.rd8(task + 46)),
                       m.rd16(0x8c186cf6), m.rd16(0x8c186cf8))
        count += 1
        if actual_xy != want_xy or actual_ints != want_ints:
            bad += 1
            if bad <= 5:
                print('mismatch', raw, struct.unpack('<ff', actual_xy), actual_ints, 'expected', expected)
    print(f'Dreamcast original cursor routine: {count} cases, {bad} mismatches')
    return 1 if bad else 0


if __name__ == '__main__':
    raise SystemExit(main())
