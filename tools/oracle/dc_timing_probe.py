"""Check SMSD header, tempo and step arithmetic against original ARM blocks.

Usage: dc_timing_probe.py <MANATEE.DRV> <bank.MLT>. Requires Unicorn.
Checks every nonempty sequence header plus seeded overflow operands; these are
direct block checks, not full sequence/sample scheduling verification.
"""
import argparse
import random
import struct
import sys
from pathlib import Path
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM
from unicorn.arm_const import UC_ARM_REG_R3, UC_ARM_REG_R11, UC_ARM_REG_R12, UC_ARM_REG_LR, UC_ARM_REG_PC

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from arm7_bus import Arm7Bus
from dc_sound_pitch import PitchTable
from dc_sound_timing import SequenceTiming
from mlt_sequences import inventory


def verify(driver, mlt):
    PitchTable(driver)
    uc = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    uc.mem_map(0, 0x200000)
    uc.mem_write(0, driver[32:])
    bus = Arm7Bus(uc)
    context, source = 0x11000, 0x180000
    headers = [tuple(s['header']) for b in inventory(mlt) for s in b['sequences'] if not s.get('empty')]
    rng = random.Random(0x89a0)
    operands = headers + [(rng.getrandbits(32), rng.getrandbits(32)) for _ in range(512)]

    def run(begin, end):
        uc.emu_start(begin, end, count=1000)
        bus.flush()
        if uc.reg_read(UC_ARM_REG_PC) != end:
            raise AssertionError('Original timing block did not finish')

    def read(offset):
        return struct.unpack('<I', uc.mem_read(context + offset, 4))[0]

    for resolution, tempo in operands:
        native = SequenceTiming(resolution, tempo)
        uc.mem_write(context, bytes(0x50))
        uc.mem_write(source, b'SMSD' + struct.pack('<2I', resolution, tempo))
        uc.reg_write(UC_ARM_REG_R11, context)
        uc.reg_write(UC_ARM_REG_R12, source)
        run(0x89a0, 0x89c4)
        if (read(8), read(0xc), read(0x38)) != (resolution, native.scale, tempo):
            raise AssertionError('Header timing differs')
        if uc.reg_read(UC_ARM_REG_R12) != source + 8:
            raise AssertionError('Header consumption differs')
        # A tempo event reads two big-endian bytes and its following step.
        native.tempo = rng.randrange(65536)
        uc.mem_write(source, native.tempo.to_bytes(2, 'big') + b'\x2c')
        uc.reg_write(UC_ARM_REG_R12, source)
        run(0x6f60, 0x6f84)
        if (read(0x38), read(0xc), uc.reg_read(UC_ARM_REG_R3)) != (native.tempo, native.scale, 44):
            raise AssertionError('Tempo event differs')
        if uc.reg_read(UC_ARM_REG_R12) != source + 3:
            raise AssertionError('Tempo event consumption differs')
        native.time, native.step_extension, step = (rng.getrandbits(32) for _ in range(3))
        uc.mem_write(context + 0x28, struct.pack('<2I', native.time, native.step_extension))
        uc.reg_write(UC_ARM_REG_R3, step)
        uc.reg_write(UC_ARM_REG_R12, source)
        uc.reg_write(UC_ARM_REG_LR, 0x1ff000)
        run(0x711c, 0x1ff000)
        if (read(0x28), read(0x2c), read(0x10)) != (native.advance(step), 0, source):
            raise AssertionError('Step timing differs')
    return dict(sequence_headers=len(headers), total_timing_cases=len(operands))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('driver', type=Path)
    parser.add_argument('mlt', type=Path)
    args = parser.parse_args()
    print(verify(args.driver.read_bytes(), args.mlt.read_bytes()))
