"""Verify the Android handset Puzzle HUD touch rectangles in both APKs."""
from itertools import product
from pathlib import Path
import argparse
import struct
import sys

from ccr_oracle import BASE, HEAP, STACK, Oracle, f2u, u2f
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP

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
    verify_overlay(oracle, symbols, layout)


def verify_overlay(oracle, symbols, layout):
    pause = symbols['_ZN6Render15drawPauseBannerEffb'][0] & ~1
    draw = BASE + (symbols['_ZN6Render9drawImageEiiffif'][0] & ~1)
    label = BASE + (symbols['_ZN6Render11printStringEPKhffhhhhftbi'][0] & ~1)
    got = BASE + pause + 0x16 + oracle.u32(BASE + pause + 0x37c)
    app = HEAP + 0x2000
    # Resolve the GOT entries from each binary's literal pool. The offsets
    # differ between Android 1.14 and 1.15.
    for literal, value in ((0x380, layout), (0x384, 0), (0x3a4, app)):
        address = oracle.u32(got + oracle.u32(BASE + pause + literal))
        oracle.write(address, struct.pack('<I', value))
    oracle.write(app + 0x697c, struct.pack('<i', -1))  # Core settings selects handset class 0.
    assert u2f(oracle.u32(layout + 0x538)) == 200.0
    calls = []

    def capture(uc, address, size, data):
        r0, r1, r2, r3 = (uc.reg_read(reg) for reg in
                           (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3))
        if address == draw:
            flags, scale = struct.unpack('<If', oracle.read(uc.reg_read(UC_ARM_REG_SP), 8))
            calls.append((r0, r1, u2f(r2), u2f(r3), flags, scale))
        else:
            calls.append(('label', u2f(r1), u2f(r2)))
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))

    for address in (draw, label):
        oracle.uc.hook_add(UC_HOOK_CODE, capture, begin=address, end=address)
    for swapped in (0, 1):
        calls.clear()
        oracle.call(pause, f2u(240), f2u(200), swapped)
        assert calls == [
            (0x86, 0, 240.0, 200.0, 0, 1.0),
            (0x85, 0, 235.0, 199.0, 2 * swapped, 1.0),
            (0x85, 1 + swapped, 129.0, 183.0, 0, 1.0),
            (0x85, 2 - swapped, 341.0, 183.0, 2, 1.0),
            ('label', 114.0, 183.0),
            ('label', 359.0, 183.0),
        ], (swapped, calls)
    print('Both handset overlay poses matched draw order, anchors, and mirroring')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('library', nargs='+', type=Path, help='extracted armeabi/libccrjni.so')
    for library in parser.parse_args().library:
        verify(library)
