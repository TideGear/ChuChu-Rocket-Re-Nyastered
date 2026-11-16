"""Verify the Android handset Puzzle HUD touch rectangles in both APKs."""
from itertools import product
from pathlib import Path
import argparse
import struct
import sys

from ccr_oracle import BASE, STACK, Oracle, f2u

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from extract_android import elf_symbols

RECTANGLES = (
    (0, 295, 60, 320),     # Pause
    (33, 148, 204, 215),   # Left pause option
    (265, 148, 440, 215),  # Right pause option
    (0, 0, 56, 40),       # Start / Dash
    (0, 39, 56, 84),      # Cancel
)


def verify(path):
    oracle = Oracle(str(path))
    symbols, _ = elf_symbols(oracle.d)
    add = symbols['_ZN5Input7addRectEiffff'][0]
    check = symbols['_ZN5Input9checkRectEiff'][0]
    layout = BASE + symbols['dataPhone'][0]
    rects = struct.unpack('<20f', oracle.read(layout + 0x4e8, 80))
    assert rects == tuple(value for rect in RECTANGLES for value in rect)
    assert struct.unpack('<12f', oracle.read(layout + 0x554, 48)) == (
        -5, -1, -111, -17, 101, -17, -126, -17, 119, -17, 1, 1)

    cases = 0
    for index, (left, top, right, bottom) in enumerate(RECTANGLES):
        # The APK passes the fifth argument to addRect on the stack.
        oracle.write(STACK + 0xf0000, struct.pack('<f', bottom))
        oracle.call(add, index, f2u(left), f2u(top), f2u(right))
        xs = (left - 1, left, (left + right) / 2, right, right + 1)
        ys = (top - 1, top, (top + bottom) / 2, bottom, bottom + 1)
        for x, y in product(xs, ys):
            got = oracle.call(check, index, f2u(x), f2u(y))
            assert got == (left <= x <= right and top <= y <= bottom), (index, x, y, got)
            cases += 1
    print(f'{path.parents[2].name}: {cases} touch checks matched, including inclusive edges')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('library', nargs='+', type=Path, help='extracted armeabi/libccrjni.so')
    for library in parser.parse_args().library:
        verify(library)
