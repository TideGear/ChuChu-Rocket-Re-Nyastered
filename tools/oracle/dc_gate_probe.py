"""Trace a queued MANATEE note-off through scheduler, FIFO and dispatcher.

Usage: dc_gate_probe.py <MANATEE.DRV> <snapshot.state> <loaded.MLT> [--channel 1]
Runs one original scheduler update per increment of its captured clock. This is
a direct-routine check, not a sample-accurate ARM/timer emulation. No gate time
is inferred from waveform similarity. Requires Unicorn and ARM7 bus correction.
"""
import argparse
import json
import struct
import sys
from pathlib import Path

from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R5, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from arm7_bus import Arm7Bus
from dc_aica_state import inspect
from dc_sound_pitch import PitchTable
from mlt_extract import sections
from mlt_sequences import inventory


def trace(driver, state, mlt, channel=1):
    if not 0 <= channel < 64:
        raise ValueError('Channel must be in 0..63')
    PitchTable(driver)
    report = inspect(state, mlt)
    ram = state[report['sound_ram_offset']:report['sound_ram_offset'] + 0x200000]
    voice = ram[0x10000 + channel * 64:0x10040 + channel * 64]
    group, midi_channel, note, velocity = voice[4:8]
    word = group << 20 | midi_channel << 16 | note << 8 | velocity
    gates = [(0x11380 + 12 * i, struct.unpack_from('<3I', ram, 0x11380 + 12 * i)) for i in range(64)]
    matching = [(address, row) for address, row in gates if row[0] == word]
    if len(matching) != 1:
        raise ValueError('Expected one queued gate for the selected voice')
    gate_address, (_, elapsed, remaining) = matching[0]
    context = 0x11000 + group * 0x50
    increment = struct.unpack_from('<I', ram, context + 0x3c)[0]
    if not increment:
        raise ValueError('Selected sequence is not advancing')
    expected_tick = (remaining + increment - 1) // increment
    if expected_tick > 10000:
        raise ValueError('Gate exceeds bounded probe window')
    start = struct.unpack_from('<I', ram, context + 0x14)[0]
    sequence = None
    for section in sections(mlt):
        if section['tag'] != 'SMSB' or section['offset'] == 0xffffffff:
            continue
        file_offset = section['offset'] + start - section['address']
        for bank in inventory(mlt):
            if bank['bank'] == section['bank']:
                for entry in bank['sequences']:
                    if entry.get('file_offset') == file_offset:
                        sequence = dict(bank=bank['bank'], index=entry['index'], file_offset=file_offset)
    if sequence is None:
        raise ValueError('Captured sequence pointer did not resolve to the loaded MLT')
    uc = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    bus = Arm7Bus(uc)
    uc.mem_map(0, 0x200000)
    uc.mem_map(0x210000, 0x1000)
    uc.mem_map(0x800000, 0x10000)
    uc.mem_write(0, ram)
    uc.mem_write(0x800000, state[report['register_offset']:report['register_offset'] + 0x8000])
    tick, queued, dispatched = 0, [], []

    def observe(machine, pc, size, unused):
        if pc == 0x714c and machine.reg_read(UC_ARM_REG_R0) == gate_address:
            queued.append((tick, machine.reg_read(UC_ARM_REG_R5)))
        if pc == 0xdd0 and machine.reg_read(UC_ARM_REG_R1) == word:
            dispatched.append(tick)

    uc.hook_add(UC_HOOK_CODE, observe, begin=0x714c, end=0x714c)
    uc.hook_add(UC_HOOK_CODE, observe, begin=0xdd0, end=0xdd0)

    def call(address):
        uc.reg_write(UC_ARM_REG_SP, 0x210ff0)
        uc.reg_write(UC_ARM_REG_LR, 0x1ff000)
        uc.emu_start(address, 0x1ff000, count=100000)
        bus.flush()
        if uc.reg_read(UC_ARM_REG_PC) != 0x1ff000:
            raise AssertionError(f'Routine {address:#x} did not return')

    for tick in range(1, expected_tick + 1):
        clock = struct.unpack('<I', uc.mem_read(0x12418, 4))[0]
        uc.mem_write(0x12418, struct.pack('<I', clock + 1))
        call(0x68d4)
        for _ in range(256):
            if uc.mem_read(0x12000, 4) == uc.mem_read(0x12004, 4):
                break
            call(0x1cd8)
            call(0xd68)
        else:
            raise AssertionError('Command FIFO did not drain')
    if queued != [(expected_tick, word)] or dispatched != [expected_tick]:
        raise AssertionError((expected_tick, queued, dispatched))
    if uc.mem_read(gate_address, 12) != bytes(12):
        raise AssertionError('Released gate was not cleared')
    control = struct.unpack('<I', uc.mem_read(0x800000 + channel * 128, 4))[0]
    if control & 0x4000:
        raise AssertionError('Note-off did not clear the selected key-on bit')
    return dict(channel=channel, group=group, midi_channel=midi_channel, note=note,
                velocity=velocity, sequence=sequence, gate_address=gate_address,
                remaining=remaining, increment=increment, prior_updates=elapsed,
                key_off_update=expected_tick, command=word,
                unaligned_reads=bus.reads, unaligned_writes=bus.writes)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('driver', type=Path)
    parser.add_argument('state', type=Path)
    parser.add_argument('mlt', type=Path)
    parser.add_argument('--channel', type=int, default=1)
    args = parser.parse_args()
    print(json.dumps(trace(args.driver.read_bytes(), args.state.read_bytes(), args.mlt.read_bytes(), args.channel), indent=2))
