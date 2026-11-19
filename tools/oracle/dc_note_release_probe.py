"""Compare native note release with complete original MANATEE ARM commands.

Generated flags exercise held, sustained, release-suppressed and empty records.
Optional captured states check actual held keys. Register write order/width is
compared; hardware KYONEX consumption and audio timing remain separate checks.
"""
import argparse
import random
import struct
import sys
from pathlib import Path
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_MEM_WRITE
from unicorn.arm_const import UC_ARM_REG_R1, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dc_sound_pitch import PitchTable
from dc_sound_channels import ChannelCommands
from dc_aica_state import inspect
from arm7_bus import Arm7Bus


class Comparison:
    def __init__(self, driver):
        PitchTable(driver)
        self.driver = driver
        self.uc = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        self.uc.mem_map(0, 0x200000); self.uc.mem_map(0x800000, 0x10000)
        self.bus = Arm7Bus(self.uc)
        self.writes = []
        self.uc.hook_add(UC_HOOK_MEM_WRITE, self.write, begin=0x800000, end=0x807fff)
        self.native = ChannelCommands(driver, bytes(0x200000), bytes(0x8000))
        self.cases = self.events = 0

    def write(self, machine, access, address, size, value, unused):
        self.writes.append((address - 0x800000, size, value & ((1 << (size * 8)) - 1)))

    def check(self, ram, registers, command):
        self.native.ram[:] = ram; self.native.registers[:] = registers
        self.uc.mem_write(0, bytes(ram)); self.uc.mem_write(0x800000, bytes(registers))
        self.native.apply(command); self.writes.clear()
        self.uc.reg_write(UC_ARM_REG_R1, command)
        self.uc.reg_write(UC_ARM_REG_SP, 0x1efff0); self.uc.reg_write(UC_ARM_REG_LR, 0x1ff000)
        self.uc.emu_start(0xd68, 0x1ff000, count=200000); self.bus.flush()
        if self.uc.reg_read(UC_ARM_REG_PC) != 0x1ff000:
            raise AssertionError('Original note release did not return')
        if bytes(self.uc.mem_read(0xc000, 0x5000)) != self.native.ram[0xc000:0x11000]:
            raise AssertionError(('Note release state', hex(command), self.cases))
        if bytes(self.uc.mem_read(0x800000, 0x8000)) != self.native.registers or self.writes != self.native.writes:
            raise AssertionError(('Note release AICA writes', hex(command), self.cases, self.writes, self.native.writes))
        self.cases += 1; self.events += len(self.writes)


def commands(group, channel, note):
    base = group << 20 | channel << 16 | note << 8
    return base, base | 0x01000000, base | 31 << 27, base | 127


def verify(driver, mlt=None, states=()):
    compare = Comparison(driver)
    base = bytearray(0x200000); base[:len(driver) - 32] = driver[32:]
    count_at = struct.unpack_from('<I', driver, 32 + 0x1884)[0]
    rng = random.Random(0xdd80e80)
    for count in (0, 1, 8, 48):
        for flags in range(256):
            ram = bytearray(base); ram[count_at] = count
            group, channel, note = flags & 7, flags >> 3 & 15, flags * 17 & 127
            ram[0xc000:0x10000] = rng.randbytes(0x4000)
            registers = bytearray(rng.randbytes(0x8000))
            for index in range(count):
                voice = bytearray(rng.randbytes(64))
                voice[0] = (flags + index) & 255
                voice[4:7] = bytes((group, channel if index % 3 != 2 else (channel + 1) & 15,
                                    note if index % 4 != 3 else (note + 1) & 127))
                if index % 7 == 4:
                    voice[:4] = bytes(4)
                ram[0x10000 + index * 64:0x10040 + index * 64] = voice
            for command in commands(group, channel, note):
                compare.check(ram, registers, command)
    print('Generated complete original note-release commands match:', compare.cases)
    generated = compare.cases
    for path in states:
        state = path.read_bytes(); report = inspect(state, mlt)
        ram = state[report['sound_ram_offset']:report['sound_ram_offset'] + 0x200000]
        registers = state[report['register_offset']:report['register_offset'] + 0x8000]
        held = set()
        for index in range(ram[count_at]):
            voice = ram[0x10000 + index * 64:0x10040 + index * 64]
            if voice[0] & 0x80:
                held.add(tuple(voice[4:7]))
        for group, channel, note in sorted(held):
            for command in commands(group, channel, note):
                compare.check(ram, registers, command)
        print(path.name, 'held-key targets checked:', len(held))
    print('Captured-state release commands match:', compare.cases - generated)
    print('Ordered AICA write events match:', compare.events)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('driver', type=Path)
    parser.add_argument('--mlt', type=Path); parser.add_argument('--states', type=Path, nargs='+', default=[])
    args = parser.parse_args()
    if args.states and args.mlt is None:
        parser.error('--states requires --mlt')
    verify(args.driver.read_bytes(), args.mlt.read_bytes() if args.mlt else None, args.states)
