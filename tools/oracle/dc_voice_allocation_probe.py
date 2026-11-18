"""Compare full original voice allocator with boundary and seeded record sets."""
import argparse
import itertools
import random
import struct
import sys
from pathlib import Path
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R6, UC_ARM_REG_R8, UC_ARM_REG_LR, UC_ARM_REG_PC

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from arm7_bus import Arm7Bus
from dc_sound_pitch import PitchTable
from dc_sound_voices import allocate_voice


def record(flags=0, field3=0, priority=0, tail=0):
    value = bytearray(64)
    value[0:4] = bytes([flags, 1, 0, field3])
    value[0x3e:0x40] = bytes([priority, tail])
    return bytes(value)


def cases():
    for fields in itertools.product((0, 0x20, 0xe0), (0, 1, 255), (0, 31, 255), (0, 1, 255)):
        first = record(*fields)
        for other in itertools.product((0, 0x80), (0, 1, 255), (0, 31, 255), (0, 1, 255)):
            for priority in (0, 31, 255):
                yield [first, record(*other)], priority
    rng = random.Random(0x16f0)
    for count in (1, 2, 4, 48, 64):
        for _ in range(256):
            records = [rng.randbytes(64) for _ in range(count)]
            if rng.randrange(3) == 0:
                at = rng.randrange(count)
                records[at] = bytes(4) + records[at][4:]
            yield records, rng.randrange(256)


def verify(driver):
    PitchTable(driver)
    uc = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    uc.mem_map(0, 0x200000)
    uc.mem_write(0, driver[32:])
    count_pointer = struct.unpack_from('<I', driver, 32 + 0x1884)[0]
    bus = Arm7Bus(uc)
    total = invalid = rejected = 0
    ordinary = ((records, priority, False) for records, priority in cases())
    zero_controls = (([record(priority=255), record(priority=255)], priority, True)
                     for priority in (0, 1, 31, 254))
    for records, priority, zero_low_ram in itertools.chain(ordinary, zero_controls):
        low_ram = bytes(264) if zero_low_ram else driver[32:32 + 264]
        uc.mem_write(0, low_ram)
        raw = b''.join(records)
        uc.mem_write(0x10000, raw)
        uc.mem_write(count_pointer, bytes([len(records)]))
        uc.mem_write(0x16ad, bytes([priority]))
        uc.reg_write(UC_ARM_REG_LR, 0x1ff000)
        uc.emu_start(0x16f0, 0x1ff000, count=10000)
        bus.flush()
        if uc.reg_read(UC_ARM_REG_PC) != 0x1ff000:
            raise AssertionError('Original allocator did not return')
        expected = allocate_voice(records, priority, low_ram)
        status, voice, hardware = (uc.reg_read(reg) for reg in (UC_ARM_REG_R0, UC_ARM_REG_R6, UC_ARM_REG_R8))
        if (status, voice, hardware) != (expected.status, expected.voice_address, expected.register_address):
            raise AssertionError((priority, expected, status, voice, hardware))
        if expected.index(len(records)) is None:
            invalid += 1
        rejected += bool(expected.status)
        if bytes(uc.mem_read(0x10000, len(raw))) != raw:
            raise AssertionError('Allocator changed a voice record')
        total += 1
    return dict(cases=total, non_voice_returns=invalid, failure_statuses=rejected)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('driver', type=Path)
    args = parser.parse_args()
    print(verify(args.driver.read_bytes()))
