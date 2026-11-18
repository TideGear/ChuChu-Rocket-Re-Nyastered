"""Verify original note/velocity split bounds for every seven-bit input pair."""
import argparse
import sys
from pathlib import Path
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R2, UC_ARM_REG_R11, UC_ARM_REG_PC

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dc_sound_pitch import PitchTable
from mlt_programs import split_matches


def verify(driver):
    PitchTable(driver)
    uc = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    uc.mem_map(0, 0x200000)
    uc.mem_map(0x210000, 0x1000)
    uc.mem_write(0, driver[32:])
    uc.reg_write(UC_ARM_REG_R2, 0x210000)
    uc.hook_add(UC_HOOK_CODE, lambda machine, address, size, unused: machine.emu_stop(), begin=0x1688, end=0x1688)
    count = 0
    for low_note, high_note, low_velocity, high_velocity in (
            (0, 127, 0, 127), (48, 72, 32, 96), (72, 48, 96, 32), (128, 255, 128, 255)):
        split = bytearray(48)
        split[36:38] = bytes([low_note, high_note])
        split[43:45] = bytes([low_velocity, high_velocity])
        uc.mem_write(0x210000, bytes(split))
        for note in range(128):
            for velocity in range(128):
                uc.mem_write(0x16af, bytes([note, velocity]))
                uc.emu_start(0xf3c, 0xf74, count=100)
                pc = uc.reg_read(UC_ARM_REG_PC)
                if pc not in (0xf74, 0x1688) or (pc == 0xf74) != split_matches(split, note, velocity):
                    raise AssertionError((note, velocity, pc, split.hex()))
                count += 1
    return count


def verify_layer_flags(driver):
    PitchTable(driver)
    uc = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    uc.mem_map(0, 0x200000)
    uc.mem_map(0x210000, 0x1000)
    uc.mem_write(0, driver[32:])
    uc.hook_add(UC_HOOK_CODE, lambda machine, address, size, unused: machine.emu_stop(), begin=0x1694, end=0x1694)
    for count_word in range(256):
        uc.reg_write(UC_ARM_REG_R0, 0x210000)
        uc.mem_write(0x210000, count_word.to_bytes(4, 'little'))
        uc.emu_start(0xf20, 0xf30, count=100)
        pc = uc.reg_read(UC_ARM_REG_PC)
        if pc != (0x1694 if count_word & 128 else 0xf30):
            raise AssertionError(('Layer disable flag differs', count_word, pc))
        if not count_word & 128 and uc.reg_read(UC_ARM_REG_R11) != count_word & 127:
            raise AssertionError('Layer split count differs')
    return 256


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('driver', type=Path)
    args = parser.parse_args()
    print(f'{verify(args.driver.read_bytes())} split-bound cases match original ARM')
    print(f'{verify_layer_flags(args.driver.read_bytes())} layer flag cases match original ARM')
