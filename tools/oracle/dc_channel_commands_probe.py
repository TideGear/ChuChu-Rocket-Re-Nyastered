"""Compare channel reset/program changes with complete original ARM commands.

Uses seeded controller/voice records and small bank-table fixtures. No hardware
KEY_ON/KYONEX consumption or audible playback is claimed by these checks.
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
from dc_sound_channels import reset_controllers, reset_sustain, program_change, ChannelCommands
from dc_aica_state import inspect
from arm7_bus import Arm7Bus


def verify(driver):
    PitchTable(driver)
    image = driver[32:]
    uc = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    uc.mem_map(0, 0x200000); uc.mem_map(0x800000, 0x10000)
    uc.mem_write(0, image)
    bus = Arm7Bus(uc)
    count_at = struct.unpack_from('<I', image, 0x1884)[0]

    def call(command):
        uc.reg_write(UC_ARM_REG_R1, command)
        uc.reg_write(UC_ARM_REG_SP, 0x1efff0)
        uc.reg_write(UC_ARM_REG_LR, 0x1ff000)
        uc.emu_start(0xd68, 0x1ff000, count=200000)
        bus.flush()
        if uc.reg_read(UC_ARM_REG_PC) != 0x1ff000:
            raise AssertionError('Original channel command did not return')

    rng = random.Random(0x328018ac)
    reset_cases = 0
    for count in (0, 1, 8, 48):
        for flags in range(256):
            group, channel = flags & 7, flags >> 3 & 15
            controller = rng.randbytes(128)
            at = 0xc000 + group * 0x800 + channel * 128
            voices, controls = [], []
            regs = bytearray(rng.randbytes(count * 128))
            for index in range(count):
                voice = bytearray(rng.randbytes(64))
                voice[0] = (flags + index) & 255
                voice[4:6] = bytes((group, channel if index % 3 else (channel + 1) & 15))
                if index % 4 == 1:
                    voice[:4] = bytes(4)
                voices.append(bytes(voice))
                controls.append(struct.unpack_from('<I', regs, index * 128)[0])
            want_voices, want_controls = reset_sustain(voices, controls, group, channel)
            expected_regs = bytearray(regs)
            for index, word in enumerate(want_controls):
                struct.pack_into('<I', expected_regs, index * 128, word)
            uc.mem_write(at, controller); uc.mem_write(count_at, bytes([count]))
            if count:
                uc.mem_write(0x10000, b''.join(voices)); uc.mem_write(0x800000, bytes(regs))
            call(0x03000000 | group << 20 | channel << 16 | 121 << 8 | flags & 127)
            if bytes(uc.mem_read(at, 128)) != reset_controllers(controller):
                raise AssertionError(('Controller reset', count, flags))
            if count and (bytes(uc.mem_read(0x10000, count * 64)) != b''.join(want_voices) or
                          bytes(uc.mem_read(0x800000, count * 128)) != expected_regs):
                raise AssertionError(('Sustain reset', count, flags))
            reset_cases += 1

    melodic_at, melodic_fallback, drums_at, drum_fallback = struct.unpack_from('<4I', image, 0x195c)
    fallbacks = (melodic_fallback, drum_fallback)
    banks = {address: image[address:address + struct.unpack_from('<I', image, address + 8)[0]]
             for address in fallbacks}
    for address, count in ((0x160000, 32), (0x168000, 64)):
        bank = bytearray(0x1000)
        bank[:4] = b'SMPB'
        struct.pack_into('<2I', bank, 4, 2, len(bank))
        struct.pack_into('<3I', bank, 16, 0x40, count, 0x800)
        for index in range(count):
            struct.pack_into('<I', bank, 0x40 + index * 4, 0x200 + index * 16 if index else 0)
        banks[address] = bytes(bank)
        uc.mem_write(address, bytes(bank))
    program_cases = 0
    for mode in (0, 1):
        for old in banks:
            for selected in (0, 0x160000, 0x168000):
                for program in range(128):
                    group, channel = program & 7, program >> 3 & 15
                    at = 0xc000 + group * 0x800 + channel * 128
                    record = bytearray(rng.randbytes(128))
                    record[0x3c] = (record[0x3c] & ~1) | mode
                    record[1] = program & 1
                    struct.pack_into('<I', record, 0x10, old)
                    melodic, drums = {}, {}
                    (drums if mode else melodic)[record[1]] = selected
                    # An opposite-mode entry verifies table selection too.
                    (melodic if mode else drums)[record[1]] = 0x168000 if selected != 0x168000 else 0x160000
                    for table, values in ((melodic_at, melodic), (drums_at, drums)):
                        for index in (0, 1):
                            uc.mem_write(table + index * 8, struct.pack('<I', values.get(index, 0)))
                    uc.mem_write(at, bytes(record))
                    call(0x04000000 | group << 20 | channel << 16 | program << 8)
                    expected = program_change(record, program, melodic, drums, banks, fallbacks)
                    if bytes(uc.mem_read(at, 128)) != expected:
                        raise AssertionError(('Program change', mode, old, selected, program))
                    program_cases += 1
    print('Original ARM channel reset/sustain matches:', reset_cases)
    print('Original ARM bank/program selection matches:', program_cases)
    # The unused mode's registry must never be dereferenced. The original
    # command succeeds even if that unrelated pointer is unmapped.
    for mode in (0, 1):
        record = bytearray(128); record[0x3c] = mode
        struct.pack_into('<I', record, 0x10, melodic_fallback)
        uc.mem_write(0xc000, bytes(record))
        uc.mem_write(drums_at if mode else melodic_at, struct.pack('<I', 0x160000))
        uc.mem_write(melodic_at if mode else drums_at, struct.pack('<I', 0xffffffff))
        native = ChannelCommands(driver, bytes(uc.mem_read(0, 0x200000)), bytes(uc.mem_read(0x800000, 0x8000)))
        native.apply(0x04000100)
        call(0x04000100)
        if bytes(uc.mem_read(0xc000, 128)) != native.ram[0xc000:0xc080]:
            raise AssertionError('Unused bank registry affected program change')
    print('Unused opposite-mode bank pointers ignored: 2 cases match')
    ignored_cases = 0
    for control in sorted(native.ignored_controls):
        ram = bytes(uc.mem_read(0, 0x200000)); regs = bytes(uc.mem_read(0x800000, 0x8000))
        native.ram[:] = ram; native.registers[:] = regs
        command = 0x03000000 | control << 8 | 127
        native.apply(command); call(command)
        if bytes(uc.mem_read(0, 0x200000)) != native.ram or bytes(uc.mem_read(0x800000, 0x8000)) != native.registers:
            raise AssertionError(('Ignored controller', control))
        ignored_cases += 1
    print('Original no-op controller commands match:', ignored_cases)


def verify_live(driver, mlt, states):
    PitchTable(driver)
    uc = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    uc.mem_map(0, 0x200000); uc.mem_map(0x800000, 0x10000)
    bus = Arm7Bus(uc)
    total = 0
    writes = []
    def register_write(machine, access, address, size, value, unused):
        writes.append((address - 0x800000, size, value & ((1 << (size * 8)) - 1)))
    uc.hook_add(UC_HOOK_MEM_WRITE, register_write, begin=0x800000, end=0x807fff)
    register_writes = 0
    for path in states:
        state = path.read_bytes()
        report = inspect(state, mlt)
        ram = state[report['sound_ram_offset']:report['sound_ram_offset'] + 0x200000]
        registers = state[report['register_offset']:report['register_offset'] + 0x8000]
        native = ChannelCommands(driver, ram, registers)
        for group in range(8):
            for channel in range(16):
                for value in (0, 1, 63, 64, 127):
                    commands = [0x03000000 | control << 8 | value for control in (1, 7, 10, 11, 32, 121, 123)]
                    commands += [0x04000000 | value << 8, 0x05000000 | value << 8, 0x06000000 | value]
                    for command in commands:
                        command |= group << 20 | channel << 16
                        uc.mem_write(0, ram); uc.mem_write(0x800000, registers)
                        native.ram[:] = ram; native.registers[:] = registers
                        native.apply(command)
                        writes.clear()
                        uc.reg_write(UC_ARM_REG_R1, command)
                        uc.reg_write(UC_ARM_REG_SP, 0x1efff0); uc.reg_write(UC_ARM_REG_LR, 0x1ff000)
                        uc.emu_start(0xd68, 0x1ff000, count=200000)
                        bus.flush()
                        if uc.reg_read(UC_ARM_REG_PC) != 0x1ff000:
                            raise AssertionError('Original live channel command did not return')
                        original = bytes(uc.mem_read(0xc000, 0x5000))
                        expected = bytes(native.ram[0xc000:0x11000])
                        if original != expected:
                            differences = [(hex(0xc000 + i), a, b) for i, (a, b) in enumerate(zip(original, expected)) if a != b]
                            raise AssertionError(('Live channel fields', path.name, hex(command), differences[:12]))
                        if bytes(uc.mem_read(0x800000, 0x8000)) != native.registers:
                            original_regs = bytes(uc.mem_read(0x800000, 0x8000))
                            differences = [(hex(i), a, b) for i, (a, b) in enumerate(zip(original_regs, native.registers)) if a != b]
                            raise AssertionError(('Live AICA writes', path.name, hex(command), differences[:12]))
                        if uc.mem_read(native.bank_error_at, 1)[0] != native.ram[native.bank_error_at]:
                            raise AssertionError('Bank error status differs')
                        if writes != native.writes:
                            raise AssertionError(('AICA write timeline', path.name, hex(command), writes, native.writes))
                        register_writes += len(writes)
                        total += 1
        print(path.name, 'live non-note commands checked')
        active = next(c['channel'] for c in report['channels'] if c['runtime']['enabled'])
        group, channel = ram[0x10004 + active * 64:0x10006 + active * 64]
        at = 0xc000 + group * 0x800 + channel * 128
        command = 0x03000100 | group << 20 | channel << 16 | ram[at + 2]
        uc.mem_write(0, ram); uc.mem_write(0x800000, registers)
        native.ram[:] = ram; native.registers[:] = registers
        for repeat in range(2):
            native.apply(command); writes.clear()
            uc.reg_write(UC_ARM_REG_R1, command)
            uc.reg_write(UC_ARM_REG_SP, 0x1efff0); uc.reg_write(UC_ARM_REG_LR, 0x1ff000)
            uc.emu_start(0xd68, 0x1ff000, count=200000); bus.flush()
            if not writes or writes != native.writes or bytes(uc.mem_read(0x800000, 0x8000)) != native.registers:
                raise AssertionError(('Repeated same-value modulation write', path.name, repeat))
            total += 1; register_writes += len(writes)
    print('Native channel updates match original complete ARM dispatch:', total)
    print('AICA write address/width/value/order matches:', register_writes)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('driver', type=Path)
    parser.add_argument('--mlt', type=Path)
    parser.add_argument('--states', nargs='+', type=Path)
    args = parser.parse_args()
    verify(args.driver.read_bytes())
    if args.states:
        if args.mlt is None:
            parser.error('--states requires --mlt')
        verify_live(args.driver.read_bytes(), args.mlt.read_bytes(), args.states)
