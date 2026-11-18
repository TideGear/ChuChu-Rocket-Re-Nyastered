"""Run complete original 0x891c sequence-start routine for inactive contexts.

Compare all context bytes for every disc sequence and all eight groups.
This checks initialization, not original frame-loop playback or replacement.
"""
import argparse
import random
import struct
import sys
from pathlib import Path
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R12, UC_ARM_REG_LR, UC_ARM_REG_PC

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from arm7_bus import Arm7Bus
from dc_sound_pitch import PitchTable
from dc_sound_timing import start_inactive_context
from mlt_extract import sections
from mlt_sequences import inventory


def verify(driver, mlt):
    PitchTable(driver)
    uc = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    uc.mem_map(0, 0x200000)
    uc.mem_write(0, driver[32:])
    bus = Arm7Bus(uc)
    rng = random.Random(0x891c)
    total = 0
    for section in sections(mlt):
        if section['tag'] != 'SMSB' or section['offset'] == 0xffffffff:
            continue
        bank = mlt[section['offset']:section['offset'] + section['size']]
        address = section['address']
        uc.mem_write(address, bank)
        entries = next(b['sequences'] for b in inventory(mlt) if b['bank'] == section['bank'])
        for sequence in entries:
            if sequence.get('empty'):
                continue
            for group in range(8):
                context_address = 0x11000 + group * 0x50
                context = bytearray(rng.randbytes(0x50))
                context[1] &= 0xfe
                priority, clock = rng.getrandbits(32), rng.getrandbits(32)
                uc.mem_write(context_address, bytes(context))
                uc.mem_write(0x12418, struct.pack('<I', clock))
                expected = start_inactive_context(context, bank, address, sequence['index'], priority, clock)
                for reg, value in ((UC_ARM_REG_R0, group), (UC_ARM_REG_R1, sequence['index']),
                                   (UC_ARM_REG_R2, priority), (UC_ARM_REG_R12, address),
                                   (UC_ARM_REG_LR, 0x1ff000)):
                    uc.reg_write(reg, value)
                uc.emu_start(0x891c, 0x1ff000, count=1000)
                bus.flush()
                if uc.reg_read(UC_ARM_REG_PC) != 0x1ff000:
                    raise AssertionError('Sequence start did not return')
                actual = bytes(uc.mem_read(context_address, 0x50))
                if actual != expected:
                    raise AssertionError((section['bank'], sequence['index'], group,
                                          [(hex(i), a, e) for i, (a, e) in enumerate(zip(actual, expected)) if a != e]))
                total += 1
    return total


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('driver', type=Path)
    parser.add_argument('mlt', type=Path)
    args = parser.parse_args()
    print(f'{verify(args.driver.read_bytes(), args.mlt.read_bytes())} complete sequence starts match')
