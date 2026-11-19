"""Compare native note-on field setup to original ARM instructions.

Executes sample/envelope, filter and mix setup blocks. Full note-on/voice
allocation comparisons are in dc_note_on_live_alloc_probe.py.
"""
import argparse
import struct
import sys
from pathlib import Path
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM
from unicorn.arm_const import UC_ARM_REG_R2, UC_ARM_REG_R5, UC_ARM_REG_R8, UC_ARM_REG_PC

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dc_sound_pitch import PitchTable
from dc_sound_controls import envelope_words, sample_words, filter_words, MixTables
from arm7_bus import Arm7Bus


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


def verify_filters(driver):
    """Compare native setup with actual ARM instructions, including clamps."""
    import random
    PitchTable(driver)
    uc = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    uc.mem_map(0, 0x200000)
    uc.mem_map(0x210000, 0x1000)
    uc.mem_map(0x800000, 0x10000)
    uc.mem_write(0, driver[32:])
    for reg, value in ((UC_ARM_REG_R2, 0x210000), (UC_ARM_REG_R5, 0x210100), (UC_ARM_REG_R8, 0x800000)):
        uc.reg_write(reg, value)
    rng = random.Random(0x12581464)
    for case in range(8192):
        split, control = bytearray(36), bytearray(0x80)
        # Every raw rate and byte offset, with distinct permutations for
        # other fields; seeded arbitrary levels, signed coarse offsets and
        # the exact lower/upper saturation boundaries.
        rate, offset = case // 256, case & 255
        rates = rate << 8 | (rate ^ 31) | ((rate + 7) & 31) << 24 | ((rate + 19) & 31) << 16
        struct.pack_into('<I', split, 0x20, rates)
        control[0x32:0x36] = bytes((offset, 255 - offset, (offset + 37) & 255, (offset * 17) & 255))
        control[0x27], control[0x3d] = offset, (case * 13) & 255
        struct.pack_into('<H', split, 0x14, case & 63)
        coarse = rng.choice((0, 7, 8, -8, -0x2000, 0x1ff7, 0x1ff8, 0x1ff9, rng.getrandbits(32)))
        struct.pack_into('<I', control, 0x40, coarse & 0xffffffff)
        for index in range(5):
            struct.pack_into('<H', split, 0x16 + index * 2, rng.getrandbits(16))
            struct.pack_into('<H', control, 0x28 + index * 2, rng.getrandbits(16))
        uc.mem_write(0x210000, bytes(split))
        uc.mem_write(0x210100, bytes(control))
        uc.emu_start(0x1258, 0x1468, count=1000)
        if uc.reg_read(UC_ARM_REG_PC) != 0x1468:
            raise AssertionError('Filter setup did not finish')
        actual = (struct.unpack('<I', uc.mem_read(0x16d4, 4))[0],
                  *struct.unpack('<7I', uc.mem_read(0x80002c, 28)))
        expected = filter_words(split, control)
        if actual != expected:
            raise AssertionError(('Filter setup', case, actual, expected))
    return 8192


def verify_mix(driver):
    import random
    tables = MixTables(driver)
    uc = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    bus = Arm7Bus(uc)
    uc.mem_map(0, 0x200000)
    uc.mem_map(0x210000, 0x1000)
    uc.mem_map(0x800000, 0x10000)
    uc.mem_write(0, driver[32:])
    uc.mem_write(0x16bc, struct.pack('<I', 0x210300))
    uc.mem_write(0x16d4, struct.pack('<I', 0x2a))
    from unicorn.arm_const import UC_ARM_REG_R6
    for reg, value in ((UC_ARM_REG_R2, 0x210000), (UC_ARM_REG_R5, 0x210100),
                       (UC_ARM_REG_R6, 0x210200), (UC_ARM_REG_R8, 0x800000)):
        uc.reg_write(reg, value)
    rng = random.Random(0x11f01588)
    for case in range(8192):
        split, control, group = bytearray(48), bytearray(128), bytearray(32)
        split[0x10:0x16] = rng.randbytes(6)
        control[0x36], control[0x46] = case & 255, (case * 13) & 255
        control[10], control[11] = (case * 17) & 127, (case * 31) & 127
        struct.pack_into('<I', control, 0x18, 0x210400)
        for at, value in ((4, case >> 5), (6, case * 29), (9, case * 37), (11, case * 41)):
            group[at] = value & 255
        curve = rng.randbytes(128)
        velocity = case & 127
        uc.mem_write(0x210000, bytes(split)); uc.mem_write(0x210100, bytes(control))
        uc.mem_write(0x210300, bytes(group)); uc.mem_write(0x210400, curve)
        uc.mem_write(0x16b0, bytes([velocity]))
        for start, stop in ((0x11f0, 0x1258), (0x1468, 0x158c)):
            uc.emu_start(start, stop, count=1000)
            bus.flush()
            if uc.reg_read(UC_ARM_REG_PC) != stop:
                raise AssertionError('Mix setup did not finish')
        dsp, direct, full_level = struct.unpack('<3I', uc.mem_read(0x800020, 12))
        volume, pan = uc.mem_read(0x210208, 2)
        actual = dsp, direct, full_level & ~63, volume, pan
        expected = tables.words(split, control, group, curve, velocity)
        if actual != expected or full_level & 63 != 0x2a:
            raise AssertionError(('Mix setup', case, actual, expected, full_level))
    return 8192


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('driver', type=Path)
    args = parser.parse_args()
    print(f'{verify(args.driver.read_bytes())} amplitude setup cases match original ARM')
    print(f'{verify_samples(args.driver.read_bytes())} sample setup cases match original ARM')
    print(f'{verify_filters(args.driver.read_bytes())} filter setup cases match original ARM')
    print(f'{verify_mix(args.driver.read_bytes())} mix setup cases match original ARM')
