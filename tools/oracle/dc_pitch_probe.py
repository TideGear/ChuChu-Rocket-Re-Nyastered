"""Compare the pitch calculation with the user's original ARM sound driver.

Usage: dc_pitch_probe.py <MANATEE.DRV> [<failure.state> <loaded.MLT>]
Requires Unicorn. Executes only routine 0x1c30, with synthetic note/split records;
no hardware calls or stubs. Optional state checks link this direct probe to the
two PCM16 failure-cue channels captured from the complete original game.
"""
import argparse
import struct
import sys
from pathlib import Path

from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM
from unicorn.arm_const import UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7, UC_ARM_REG_R8, UC_ARM_REG_LR, UC_ARM_REG_PC

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dc_sound_pitch import PitchTable
from dc_aica_state import inspect
from mlt_programs import inventory


def verify(driver, state=None, mlt=None):
    table = PitchTable(driver)
    uc = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    uc.mem_map(0, 0x10000)
    uc.mem_write(0, driver[32:])
    uc.mem_map(0x210000, 0x1000)
    uc.mem_map(0x800000, 0x1000)
    cases = 0

    def original(note, root, fine, bend):
        uc.mem_write(0x210006, bytes([note]))
        uc.mem_write(0x210126, bytes([root, fine & 255]))
        for register, value in ((UC_ARM_REG_R5, 0x210000), (UC_ARM_REG_R6, 0x210100),
                                (UC_ARM_REG_R7, bend & 0xffffffff), (UC_ARM_REG_R8, 0x800000),
                                (UC_ARM_REG_LR, 0x9000)):
            uc.reg_write(register, value)
        uc.emu_start(0x1c30, 0x9000, count=1000)
        if uc.reg_read(UC_ARM_REG_PC) != 0x9000:
            raise AssertionError('Original pitch routine did not return')
        return struct.unpack('<I', uc.mem_read(0x800018, 4))[0]

    def check(note, root, fine=0, bend=0):
        nonlocal cases
        expected = original(note, root, fine, bend)
        actual = table.word(note, root, fine, bend)
        if actual != expected:
            raise AssertionError((note, root, fine, bend, hex(actual), hex(expected)))
        cases += 1

    for root in range(128):
        for note in range(128):
            check(note, root)
    for note in range(128):
        for root in (0, 60, 84, 127):
            for fine in (-128, -127, -1, 0, 1, 126, 127):
                for bend in (-6144, -257, -256, -1, 0, 1, 255, 256, 6144):
                    check(note, root, fine, bend)
    print('original ARM pitch matches:', cases)
    if state is not None:
        report = inspect(state, mlt)
        channels = [c for c in report['channels'] if c['key_on'] and
                    any(r['bank'] == 0 and r['tag'] == 'SMPB' and r['program'] == 27
                        for r in c['sample_references'])]
        # Sequence 27: first note is key 69, then key 72.
        if len(channels) != 2:
            raise AssertionError('Expected two program-27 failure channels')
        bank = next(b for b in inventory(mlt) if b['tag'] == 'SMPB' and b['bank'] == 0)
        splits = bank['programs'][27]['layers'][0]['splits']
        expected = set()
        for note in (69, 72):
            split = next(s for s in splits if s['note_low'] <= note <= s['note_high'])
            expected.add(table.word(note, split['base_note'], split['fine_tune']))
        if {c['pitch_raw'] for c in channels} != expected:
            raise AssertionError('Live failure pitch differs from direct routine')
        print('live failure-channel pitch words:', ', '.join(hex(v) for v in sorted(expected)))
    return cases


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('driver', type=Path)
    parser.add_argument('state', type=Path, nargs='?')
    parser.add_argument('mlt', type=Path, nargs='?')
    args = parser.parse_args()
    if bool(args.state) != bool(args.mlt):
        parser.error('Pass both state and MLT, or neither')
    verify(args.driver.read_bytes(), args.state.read_bytes() if args.state else None,
           args.mlt.read_bytes() if args.mlt else None)
