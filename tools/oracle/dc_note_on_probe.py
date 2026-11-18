"""Verify modulation and note-on channel setup against the original ARM driver.

Usage: dc_note_on_probe.py <MANATEE.DRV> <failure.state> <loaded.MLT>
Requires Unicorn. Modulation executes a bounded setup block. The note-on probe
executes command entry 0xd68 through its return, using captured channel/program
settings but clearing voice allocations. No hardware calls are stubbed. Compare
all 18 meaningful register words with the two live program-27 failure channels,
excluding only KYONEX, which real AICA hardware clears after a key-on command.
This verifies register preparation; it does not synthesize the audible waveform.
"""
import argparse
import struct
import sys
from pathlib import Path

from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM
from unicorn.arm_const import UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R5, UC_ARM_REG_R8, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dc_sound_controls import modulation_word
from dc_sound_pitch import PitchTable
from dc_aica_state import inspect


def verify(driver, state, mlt):
    PitchTable(driver)  # Reject unverified driver revisions before executing code.
    uc = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    uc.mem_map(0, 0x200000)
    uc.mem_map(0x210000, 0x1000)
    uc.mem_map(0x800000, 0x10000)
    uc.mem_write(0, driver[32:])
    uc.reg_write(UC_ARM_REG_R2, 0x210000)
    uc.reg_write(UC_ARM_REG_R5, 0x210100)
    uc.reg_write(UC_ARM_REG_R8, 0x800000)
    cases = 0
    for depth in range(128):
        for pitch in range(8):
            for amplitude in range(8):
                raw = 0xff18 | pitch << 5 | amplitude
                uc.mem_write(0x21000c, struct.pack('<I', raw << 16))
                uc.mem_write(0x210102, bytes([depth]))
                uc.emu_start(0x1188, 0x11f0, count=1000)
                if uc.reg_read(UC_ARM_REG_PC) != 0x11f0:
                    raise AssertionError('Modulation setup block did not finish')
                actual = struct.unpack('<I', uc.mem_read(0x80001c, 4))[0]
                if actual != modulation_word(raw, depth):
                    raise AssertionError((depth, pitch, amplitude, actual))
                cases += 1
    print('original ARM modulation matches:', cases)

    report = inspect(state, mlt)
    base, registers = report['sound_ram_offset'], report['register_offset']
    ram = state[base:base + 0x200000]
    if ram[0xd68:0x16ac] != driver[32 + 0xd68:32 + 0x16ac]:
        raise ValueError('Loaded note-on routine differs from the verified driver')
    channels = [c for c in report['channels'] if c['key_on'] and
                any(r['tag'] == 'SMPB' and r['bank'] == 0 and r['program'] == 27
                    for r in c['sample_references'])]
    if len(channels) != 2:
        raise AssertionError('Expected two program-27 failure channels')
    for channel in channels:
        voice = ram[0x10000 + 64 * channel['channel']:0x10040 + 64 * channel['channel']]
        group, midi_channel, note, velocity = voice[4:8]
        controller = 0xc000 + group * 0x800 + midi_channel * 0x80
        split = struct.unpack_from('<I', voice, 0x10)[0]
        lfo = struct.unpack_from('<H', ram, split + 14)[0]
        if modulation_word(lfo, ram[controller + 2]) & 0x7fff != channel['lfo_raw']:
            raise AssertionError('Calculated LFO differs from live channel')
        uc.mem_write(0, ram)
        uc.mem_write(0x10000, bytes(48 * 64))
        uc.mem_write(0x800000, state[registers:registers + 0x8000])
        uc.mem_write(0x800000, bytes(64 * 128))
        command = 0x01000000 | group << 20 | midi_channel << 16 | note << 8 | velocity
        uc.reg_write(UC_ARM_REG_R1, command)
        uc.reg_write(UC_ARM_REG_SP, 0x210ff0)
        uc.reg_write(UC_ARM_REG_LR, 0x1ff000)
        uc.emu_start(0xd68, 0x1ff000, count=100000)
        if uc.reg_read(UC_ARM_REG_PC) != 0x1ff000:
            raise AssertionError('Original note-on command did not return')
        raw = uc.mem_read(0x800000, 72)
        words = [struct.unpack_from('<I', raw, i)[0] for i in range(0, 72, 4)]
        words[0] &= ~0x8000
        if words != channel['register_words']:
            raise AssertionError((channel['channel'], words, channel['register_words']))
        print('live channel', channel['channel'], 'note', note,
              ': all 18 register words match (KYONEX excluded)')
    return cases


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('driver', type=Path)
    parser.add_argument('state', type=Path)
    parser.add_argument('mlt', type=Path)
    args = parser.parse_args()
    verify(args.driver.read_bytes(), args.state.read_bytes(), args.mlt.read_bytes())
