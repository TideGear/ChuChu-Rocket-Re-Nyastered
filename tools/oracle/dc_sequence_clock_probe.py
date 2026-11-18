"""Compare a fresh linear sequence's event timing with original scheduler calls.

Runs original context initialization/start and scheduler, draining the command
FIFO without voice dispatch. Compares events, command words and all 64 gates
through sequence end, not audio, post-end gate tails or CPU cycles.
"""
import argparse
import struct
import sys
from pathlib import Path
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R12, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from arm7_bus import Arm7Bus
from dc_sound_pitch import PitchTable
from dc_sound_timing import LinearSequenceClock
from dc_sound_sequence import SequenceCommands
from mlt_extract import sections
from mlt_sequences import inventory


def verify(driver, mlt, bank_index=0, sequence_index=19):
    PitchTable(driver)
    sequence = next(b for b in inventory(mlt) if b['bank'] == bank_index)['sequences'][sequence_index]
    native = LinearSequenceClock(sequence)
    command_model = SequenceCommands(sequence)
    section = next(s for s in sections(mlt) if s['tag'] == 'SMSB' and s['bank'] == bank_index)
    sequence_address = section['address'] + sequence['file_offset'] - section['offset']
    uc = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    uc.mem_map(0, 0x200000)
    uc.mem_write(0, driver[32:])
    uc.mem_write(section['address'], mlt[section['offset']:section['offset'] + section['size']])
    bus = Arm7Bus(uc)

    def call(address):
        uc.reg_write(UC_ARM_REG_SP, 0x1efff0)
        uc.reg_write(UC_ARM_REG_LR, 0x1ff000)
        uc.emu_start(address, 0x1ff000, count=100000)
        bus.flush()
        if uc.reg_read(UC_ARM_REG_PC) != 0x1ff000:
            raise AssertionError(f'Original routine {address:x} did not return')

    call(0x88c0)
    for reg, value in ((UC_ARM_REG_R0, 1), (UC_ARM_REG_R1, sequence_index),
                       (UC_ARM_REG_R2, 0), (UC_ARM_REG_R12, section['address'])):
        uc.reg_write(reg, value)
    call(0x891c)
    observed = []

    def event(machine, pc, size, unused):
        pointer = machine.reg_read(UC_ARM_REG_R12)
        status = machine.mem_read(pointer, 1)[0]
        # Parser expands references and folds gate/step extension prefixes.
        # Compare semantic reads at their original source offsets.
        if status != 0x81 and not 0x88 <= status <= 0x8f:
            observed.append(pointer - sequence_address)

    uc.hook_add(UC_HOOK_CODE, event, begin=0x6aac, end=0x6aac)
    count = command_count = 0
    for tick in range(1, 10001):
        observed.clear()
        uc.mem_write(0x12418, struct.pack('<I', tick))
        call(0x68d4)
        expected = [row['offset'] for row in native.update()]
        if observed != expected:
            raise AssertionError((tick, observed, expected))
        if not native.ended:
            actual_time = struct.unpack('<I', uc.mem_read(0x11078, 4))[0]
            actual_scale = struct.unpack('<I', uc.mem_read(0x1105c, 4))[0]
            if (actual_time, actual_scale) != (native.timing.time, native.timing.scale):
                raise AssertionError(('Timing state differs', tick, actual_time, native.timing.time))
        expected_commands = command_model.update()
        write, read = struct.unpack('<2I', uc.mem_read(0x12000, 8))
        actual_commands = []
        while read != write:
            actual_commands.append(struct.unpack('<I', uc.mem_read(0xb000 + read, 4))[0])
            read = (read + 4) & 0xfff
            if len(actual_commands) > 1024:
                raise AssertionError('Invalid FIFO pointers')
        if actual_commands != expected_commands:
            raise AssertionError(('Command output differs', tick, actual_commands, expected_commands))
        actual_gates = bytes(uc.mem_read(0x11380, 64 * 12))
        expected_gates = b''.join(struct.pack('<3I', g.command, g.elapsed, g.remaining) for g in command_model.gates)
        if actual_gates != expected_gates:
            raise AssertionError(('Pending gate table differs', tick))
        command_count += len(actual_commands)
        # Isolate scheduling from voice dispatch, keeping FIFO capacity available.
        uc.mem_write(0x12004, bytes(uc.mem_read(0x12000, 4)))
        count += len(observed)
        if native.ended:
            flags = uc.mem_read(0x11051, 1)[0]
            if flags & 1:
                raise AssertionError('Original sequence did not end')
            return dict(updates=tick, events=count, commands=command_count)
    raise AssertionError('Sequence exceeded bounded update window')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('driver', type=Path)
    parser.add_argument('mlt', type=Path)
    parser.add_argument('--bank', type=int, default=0)
    parser.add_argument('--sequence', type=int, default=19)
    parser.add_argument('--all', action='store_true', help='verify every sequence in the MLT')
    args = parser.parse_args()
    driver, mlt = args.driver.read_bytes(), args.mlt.read_bytes()
    if args.all:
        results = [verify(driver, mlt, bank['bank'], sequence['index'])
                   for bank in inventory(mlt) for sequence in bank['sequences']
                   if not sequence.get('empty')]
        print(dict(sequences=len(results), events=sum(r['events'] for r in results),
                   updates=sum(r['updates'] for r in results)))
    else:
        print(verify(driver, mlt, args.bank, args.sequence))
