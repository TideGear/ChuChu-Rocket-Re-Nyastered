"""Compare a fresh sequence's events, loops and commands with original scheduler calls.

Runs original context initialization/start and scheduler, draining the command
FIFO, optionally dispatching against captured loaded sound RAM. Compares events, command words and all 64 gates
through sequence end/pending-gate expiry or bounded infinite-loop repeats,
not audio or CPU cycles.
"""
import argparse
import struct
import sys
from pathlib import Path
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R12, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from arm7_bus import Arm7Bus
from dc_sound_pitch import PitchTable
from dc_sound_timing import SequenceClock
from dc_sound_sequence import SequenceCommands
from mlt_extract import sections
from mlt_sequences import inventory
from dc_aica_state import inspect
from dc_sound_channels import ChannelCommands


def verify(driver, mlt, bank_index=0, sequence_index=19, short_tail_control=False, loop_passes=2, state=None, voice_worker=False):
    if voice_worker and state is None:
        raise ValueError('Voice worker comparison requires loaded dispatch state')
    PitchTable(driver)
    sequence = next(b for b in inventory(mlt) if b['bank'] == bank_index)['sequences'][sequence_index]
    if short_tail_control:
        previous, end = sequence['events'][-2:]
        if previous['type'] != 'note' or end['type'] != 'end':
            raise ValueError('Tail control requires a final note followed by end')
        width = 2 if previous['status'] & 0x10 else 1
        if previous['offset'] + 3 + (previous['status'] >> 5) + 1 + width != end['offset']:
            raise ValueError('Tail control requires contiguous note/end bytes')
        position = sequence['file_offset'] + end['offset'] - width
        modified = bytearray(mlt)
        modified[position:position + width] = bytes(width)
        mlt = bytes(modified)
        sequence = next(b for b in inventory(mlt) if b['bank'] == bank_index)['sequences'][sequence_index]
    native = SequenceClock(sequence)
    command_model = SequenceCommands(sequence)
    section = next(s for s in sections(mlt) if s['tag'] == 'SMSB' and s['bank'] == bank_index)
    sequence_address = section['address'] + sequence['file_offset'] - section['offset']
    uc = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    uc.mem_map(0, 0x200000)
    if state is not None:
        report = inspect(state, mlt)
        base, regs = report['sound_ram_offset'], report['register_offset']
        uc.mem_write(0, state[base:base + 0x200000])
        uc.mem_map(0x800000, 0x10000)
        uc.mem_write(0x800000, state[regs:regs + 0x8000])
    else:
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
    channels = (ChannelCommands(driver, bytes(uc.mem_read(0, 0x200000)),
                                bytes(uc.mem_read(0x800000, 0x8000)))
                if state is not None else None)
    register_writes = []
    write_count = 0
    def register_write(machine, access, address, size, value, unused):
        register_writes.append((address - 0x800000, size, value & ((1 << (size * 8)) - 1)))
    if channels is not None:
        uc.hook_add(UC_HOOK_MEM_WRITE, register_write, begin=0x800000, end=0x807fff)

    def event(machine, pc, size, unused):
        pointer = machine.reg_read(UC_ARM_REG_R12)
        status = machine.mem_read(pointer, 1)[0]
        # Parser expands references and folds gate/step extension prefixes.
        # Compare semantic reads at their original source offsets.
        if status != 0x81 and not 0x88 <= status <= 0x8f:
            observed.append(pointer - sequence_address)

    uc.hook_add(UC_HOOK_CODE, event, begin=0x6aac, end=0x6aac)
    count = command_count = 0
    end_tick = pending_at_end = None
    for tick in range(1, 100001):
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
            actual_loops = struct.unpack('<I', uc.mem_read(0x1106c, 4))[0]
            if actual_loops != native.loop_repeats:
                raise AssertionError(('Loop count differs', tick, actual_loops, native.loop_repeats))
            actual_remaining = uc.mem_read(0x11068, 1)[0]
            actual_start = struct.unpack('<I', uc.mem_read(0x11074, 4))[0]
            expected_start = (sequence_address + native.events[native.loop_start]['offset'] + 1
                              if native.loop_start is not None else 0)
            if (actual_remaining, actual_start) != (native.loop_remaining, expected_start):
                raise AssertionError(('Loop state differs', tick, actual_remaining, actual_start,
                                      native.loop_remaining, expected_start))
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
        if channels is not None:
            for command in actual_commands:
                register_writes.clear()
                uc.reg_write(UC_ARM_REG_R1, command)
                call(0xd68)
                channels.apply(command)
                if register_writes != channels.writes:
                    raise AssertionError(('Dispatch write order', tick, hex(command), register_writes, channels.writes))
                write_count += len(register_writes)
                if bytes(uc.mem_read(0x800000, 0x8000)) != channels.registers:
                    raise AssertionError(('Dispatch registers', tick, hex(command)))
                for start, length in ((0xc000, 0x4000), (0x10000, channels.count() * 64),
                                      (channels.voice_map_at, 64), (0xadc, 1)):
                    actual = bytes(uc.mem_read(start, length))
                    expected_bytes = channels.ram[start:start + length]
                    if actual != expected_bytes:
                        differences = [(hex(start + i), a, b) for i, (a, b) in enumerate(zip(actual, expected_bytes)) if a != b]
                        raise AssertionError(('Dispatch RAM', tick, hex(command), differences[:12]))
            if voice_worker:
                register_writes.clear()
                call(0xb6c)
                channels.update_voices()
                if register_writes != channels.writes or bytes(uc.mem_read(0x800000, 0x8000)) != channels.registers:
                    raise AssertionError(('Voice worker registers', tick))
                if bytes(uc.mem_read(0x10000, channels.count() * 64)) != channels.ram[0x10000:0x10000 + channels.count() * 64]:
                    raise AssertionError(('Voice worker records', tick))
                write_count += len(register_writes)
        count += len(observed)
        if native.loop_remaining == 128 and native.loop_repeats >= loop_passes:
            return dict(updates=tick, sequence_end=None, pending_at_end=None,
                        loop_repeats=native.loop_repeats, events=count, commands=command_count)
        if native.ended:
            flags = uc.mem_read(0x11051, 1)[0]
            if flags & 1:
                raise AssertionError('Original sequence did not end')
            if end_tick is None:
                end_tick = tick
                pending_at_end = sum(bool(g.command) for g in command_model.gates)
            if not any(g.command for g in command_model.gates):
                return dict(updates=tick, sequence_end=end_tick, pending_at_end=pending_at_end,
                            events=count, commands=command_count, dispatch_writes=write_count)
    raise AssertionError('Sequence exceeded bounded update window')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('driver', type=Path)
    parser.add_argument('mlt', type=Path)
    parser.add_argument('--bank', type=int, default=0)
    parser.add_argument('--sequence', type=int, default=19)
    parser.add_argument('--all', action='store_true', help='verify every sequence in the MLT')
    parser.add_argument('--short-tail-control', action='store_true', help='synthetic control: zero the final note step')
    parser.add_argument('--loop-passes', type=int, default=2, help='infinite-loop repetitions to verify')
    parser.add_argument('--dispatch-state', type=Path, help='also compare native dispatch using captured loaded sound RAM; no voice worker or hardware synthesis')
    parser.add_argument('--voice-worker', action='store_true', help='also call voice worker after each manual tick; no hardware status reads or real main-loop timing')
    args = parser.parse_args()
    if args.all and (args.short_tail_control or args.dispatch_state):
        parser.error('--all cannot be combined with --short-tail-control or --dispatch-state')
    if args.loop_passes < 1:
        parser.error('--loop-passes must be positive')
    if args.voice_worker and not args.dispatch_state:
        parser.error('--voice-worker requires --dispatch-state')
    driver, mlt = args.driver.read_bytes(), args.mlt.read_bytes()
    if args.all:
        results = [verify(driver, mlt, bank['bank'], sequence['index'], loop_passes=args.loop_passes)
                   for bank in inventory(mlt) for sequence in bank['sequences']
                   if not sequence.get('empty')]
        print(dict(sequences=len(results), events=sum(r['events'] for r in results),
                   updates=sum(r['updates'] for r in results), commands=sum(r['commands'] for r in results),
                   looped_sequences=sum(r['sequence_end'] is None for r in results),
                   post_end_updates=sum(r['updates'] - r['sequence_end'] for r in results if r['sequence_end'] is not None),
                   sequences_with_pending_tails=sum(bool(r['pending_at_end']) for r in results)))
    else:
        print(verify(driver, mlt, args.bank, args.sequence, args.short_tail_control, args.loop_passes,
                     args.dispatch_state.read_bytes() if args.dispatch_state else None, args.voice_worker))
