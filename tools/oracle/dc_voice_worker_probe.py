"""Compare native voice aging/delays/drum cleanup with ARM 0xb6c.

Instruction-call fixtures only: hardware status observation and synthesis are
not executed. Generated status bytes explicitly exercise both cleanup routes.
"""
import argparse
import random
import struct
from pathlib import Path
from unicorn.arm_const import UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC
from dc_note_release_probe import Comparison


def verify(driver):
    compare = Comparison(driver)
    base = bytearray(0x200000)
    base[:len(driver) - 32] = driver[32:]
    count_at = struct.unpack_from('<I', driver, 32 + 0xcb8)[0]
    if count_at != compare.native.count_at:
        raise AssertionError('Worker and dispatcher voice-count pointers differ')
    rng = random.Random(0xb6cc08)
    for count in (0, 1, 8, 48, 64):
        for flags in range(256):
            ram = bytearray(base)
            ram[count_at] = count
            registers = rng.randbytes(0x8000)
            for index in range(count):
                voice = bytearray(rng.randbytes(64))
                voice[0] = (flags + index) & 255
                voice[0x3f] = (0, 1, 254, 255)[index % 4]
                voice[0x2b] = (0, 1, 255)[(flags + index) % 3]
                struct.pack_into('<I', voice, 0x38, (0, 1, 2, 0xffffffff)[(flags + index) % 4])
                ram[0x10000 + index * 64:0x10040 + index * 64] = voice
            compare.native.ram[:] = ram
            compare.native.registers[:] = registers
            compare.uc.mem_write(0, bytes(ram))
            compare.uc.mem_write(0x800000, registers)
            # Repeated calls exercise delay transitions and byte-age wrap.
            for step in range(3):
                compare.writes.clear()
                compare.native.update_voices()
                compare.uc.reg_write(UC_ARM_REG_SP, 0x1efff0)
                compare.uc.reg_write(UC_ARM_REG_LR, 0x1ff000)
                compare.uc.emu_start(0xb6c, 0x1ff000, count=200000)
                compare.bus.flush()
                if compare.uc.reg_read(UC_ARM_REG_PC) != 0x1ff000:
                    raise AssertionError('Voice worker did not return')
                if bytes(compare.uc.mem_read(0xc000, 0x5000)) != compare.native.ram[0xc000:0x11000]:
                    raise AssertionError(('Worker RAM', count, flags, step))
                if bytes(compare.uc.mem_read(0x800000, 0x8000)) != compare.native.registers or compare.writes != compare.native.writes:
                    raise AssertionError(('Worker writes', count, flags, step, compare.writes, compare.native.writes))
                compare.cases += 1
                compare.events += len(compare.writes)
    print(dict(worker_calls=compare.cases, ordered_register_writes=compare.events))
    monitor = struct.unpack_from('<I', driver, 32 + 0xd4c)[0]
    observer_cases = 0
    for count in (1, 48, 64):
        for case in range(512):
            ram = bytearray(base)
            ram[count_at] = count
            index = case % count
            ram[0xadc] = index
            voice = bytearray(rng.randbytes(64))
            voice[:4] = bytes(4) if case % 2 else bytes((0x20, 0, 0, 0))
            voice[0x3c] = (0, 1, 255)[case % 3]
            ram[0x10000 + index * 64:0x10040 + index * 64] = voice
            ram[compare.native.voice_map_at + index] = 0x81
            registers = bytearray(rng.randbytes(0x8000))
            # All 4 envelope phases crossed with all 5 upper level bits,
            # and low-level boundaries 0/1/127/255,
            # loop latch set/clear, plus unrelated high monitor bits.
            status = (rng.getrandbits(16) << 16 | (case >> 2 & 1) << 15 |
                      (case >> 5 & 3) << 13 | (case & 31) << 8 |
                      (0, 1, 127, 255)[case >> 7 & 3])
            struct.pack_into('<I', registers, monitor - 0x800000, status)
            compare.native.ram[:] = ram
            compare.native.registers[:] = registers
            compare.uc.mem_write(0, bytes(ram))
            compare.uc.mem_write(0x800000, bytes(registers))
            compare.writes.clear()
            compare.native.observe_voice(index, status)
            compare.uc.reg_write(UC_ARM_REG_SP, 0x1efff0)
            compare.uc.reg_write(UC_ARM_REG_LR, 0x1ff000)
            compare.uc.emu_start(0x93c, 0x1ff000, count=200000)
            compare.bus.flush()
            if compare.uc.reg_read(UC_ARM_REG_PC) != 0x1ff000:
                raise AssertionError('Voice observer did not return')
            for start, size in ((0x10000, count * 64), (compare.native.voice_map_at, 64)):
                if bytes(compare.uc.mem_read(start, size)) != compare.native.ram[start:start + size]:
                    raise AssertionError(('Observer RAM', count, case, hex(status)))
            if compare.writes or bytes(compare.uc.mem_read(0x800000, 0x8000)) != compare.native.registers:
                raise AssertionError('Observer register mutation')
            observer_cases += 1
    print(dict(sampled_voice_observations=observer_cases))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('driver', type=Path)
    args = parser.parse_args()
    verify(args.driver.read_bytes())
