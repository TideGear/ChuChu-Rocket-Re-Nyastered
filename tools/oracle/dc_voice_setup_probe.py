"""Compare note-on sample/envelope setup to original ARM blocks.

Executes 0x1058..0x10ac and 0x10b0..0x1184, not complete voice allocation.
"""
import argparse
import struct
import sys
from pathlib import Path
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM
from unicorn.arm_const import UC_ARM_REG_R2, UC_ARM_REG_R5, UC_ARM_REG_R8, UC_ARM_REG_PC

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dc_sound_pitch import PitchTable
from dc_sound_controls import envelope_words, sample_words


def verify(driver):
    PitchTable(driver)
    uc = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    uc.mem_map(0, 0x200000)
    uc.mem_map(0x210000, 0x1000)
    uc.mem_map(0x800000, 0x10000)
    uc.mem_write(0, driver[32:])
    uc.reg_write(UC_ARM_REG_R2, 0x210000)
    uc.reg_write(UC_ARM_REG_R5, 0x210100)
    uc.reg_write(UC_ARM_REG_R8, 0x800000)
    count = 0
    for rate in range(32):
        lower = rate | (rate ^ 31) << 6 | ((rate + 7) & 31) << 11
        upper = (rate ^ 17) | ((rate + 11) & 31) << 5 | (rate & 31) << 10
        amplitude = lower | upper << 16
        uc.mem_write(0x210008, struct.pack('<I', amplitude))
        for offset in range(256):
            attack, decay, level, release = offset, 255 - offset, (offset + 37) & 255, (offset * 17) & 255
            for at, value in ((0x37, attack), (0x38, decay), (0x39, level), (0x3b, release)):
                uc.mem_write(0x210100 + at, bytes([value]))
            uc.emu_start(0x10b0, 0x1188, count=1000)
            if uc.reg_read(UC_ARM_REG_PC) != 0x1188:
                raise AssertionError('Envelope setup did not finish')
            actual = struct.unpack('<2I', uc.mem_read(0x800010, 8))
            expected = envelope_words(amplitude, attack, decay, level, release)
            if actual != expected:
                raise AssertionError((rate, offset, actual, expected))
            count += 1
    return count


def verify_samples(driver):
    PitchTable(driver)
    uc = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    uc.mem_map(0, 0x200000)
    uc.mem_map(0x210000, 0x1000)
    uc.mem_map(0x800000, 0x10000)
    uc.mem_write(0, driver[32:])
    uc.reg_write(UC_ARM_REG_R2, 0x210000)
    uc.reg_write(UC_ARM_REG_R5, 0x210100)
    uc.reg_write(UC_ARM_REG_R8, 0x800000)
    count = 0
    for flags in range(16):
        for relative in (0, 1, 0x7ff, 0xffff, 0x10000, 0x7fffff):
            for base in (0, 0x28ce0, 0x1fffff, 0xfffffff0):
                packed = ((relative & 0xffff) << 16 | (relative >> 16) |
                          (flags & 7) << 8 | (flags >> 3) << 7)
                split = struct.pack('<2I', packed, 0xfedc1234)
                uc.mem_write(0x210000, split)
                uc.mem_write(0x210110, struct.pack('<I', base))
                uc.emu_start(0x1058, 0x10b0, count=1000)
                actual = (struct.unpack('<I', uc.mem_read(0x16d0, 4))[0],
                          *struct.unpack('<3I', uc.mem_read(0x800004, 12)))
                expected = sample_words(split, base)
                if actual != expected or uc.reg_read(UC_ARM_REG_PC) != 0x10b0:
                    raise AssertionError((flags, relative, base, actual, expected))
                count += 1
    return count


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('driver', type=Path)
    args = parser.parse_args()
    print(f'{verify(args.driver.read_bytes())} amplitude setup cases match original ARM')
    print(f'{verify_samples(args.driver.read_bytes())} sample setup cases match original ARM')
