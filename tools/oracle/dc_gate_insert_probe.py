"""Compare native free-slot gate insertion with original ARM 0x6b34..0x6bd8.

Direct block check, not full sequence playback. Uses seeded boundary/random
operands and every note gate/step encoding width. Requires Unicorn.
"""
import argparse
import random
import struct
import sys
from pathlib import Path

from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R10, UC_ARM_REG_R11, UC_ARM_REG_R12, UC_ARM_REG_PC

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dc_sound_pitch import PitchTable
from dc_sound_gate import NoteGate


def verify(driver):
    PitchTable(driver)
    uc = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    uc.mem_map(0, 0x200000)
    uc.mem_write(0, driver[32:])
    rng = random.Random(0x6b34)
    count = 0
    for width in range(1, 5):
        for wide_step in (False, True):
            for case in range(64):
                gate = (0, 1, (1 << (8 * width)) - 1)[case] if case < 3 else rng.getrandbits(8 * width)
                base, group, channel = rng.randrange(256), rng.randrange(8), rng.randrange(16)
                note, velocity = rng.randrange(128), rng.randrange(128)
                scale, extension, time = (rng.getrandbits(32) for _ in range(3))
                status = ((width - 1) << 5) | (0x10 if wide_step else 0) | channel
                payload = bytes([note, velocity]) + gate.to_bytes(width, 'big') + (b'\x12\x34' if wide_step else b'\x34')
                context, event = 0x11000, 0x180000
                uc.mem_write(context, bytes(0x50))
                uc.mem_write(context, bytes([base]))
                for offset, value in ((0xc, scale), (0x30, extension), (0x28, time)):
                    uc.mem_write(context + offset, struct.pack('<I', value))
                uc.mem_write(0x11380, bytes(0x300))
                uc.mem_write(event, payload)
                for register, value in ((UC_ARM_REG_R0, status), (UC_ARM_REG_R10, group),
                                        (UC_ARM_REG_R11, context), (UC_ARM_REG_R12, event)):
                    uc.reg_write(register, value)
                uc.emu_start(0x6b34, 0x6bdc, count=1000)
                if uc.reg_read(UC_ARM_REG_PC) != 0x6bdc:
                    raise AssertionError('Insertion block did not finish')
                expected = NoteGate.from_note(base, group, channel, note, velocity, gate, scale, extension, time)
                actual = struct.unpack('<3I', uc.mem_read(0x11380, 12))
                if actual != (expected.command, expected.elapsed, expected.remaining):
                    raise AssertionError((width, case, actual, expected))
                if uc.reg_read(UC_ARM_REG_R12) != event + len(payload):
                    raise AssertionError('Incorrect event consumption')
                if uc.mem_read(context + 0x30, 4) != bytes(4):
                    raise AssertionError('Original gate extension was not consumed')
                count += 1
    return count


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('driver', type=Path)
    args = parser.parse_args()
    print(f'{verify(args.driver.read_bytes())} original ARM gate insertions match')
