"""Trace the original iPad launch and first playable ticks on the ? board."""
from itertools import product
from pathlib import Path
import struct
import sys

from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools' / 'oracle'))
from hd_battle_preview import BattlePreviewOracle


def main():
    battle_data = (ROOT / 'local/cache/assets/battle_stages.bin').read_bytes()
    record_size = 4 + 108 + 237 + 32
    count, = struct.unpack_from('<I', battle_data)
    boards = {}
    for i in range(count):
        offset = 4 + i * record_size
        source, _, index = struct.unpack_from('<BBH', battle_data, offset)
        if source == 2:
            boards[index] = battle_data[offset + 4:offset + 4 + 108 + 237]

    cases = list(product((0, 1), (23, 24), (1, 987, 10001)))
    for mode, stage, seed in cases:
        o = BattlePreviewOracle().oracle
        requested_maps = []

        def record(uc, address, size, user):
            requested_maps.append((uc.reg_read(UC_ARM_REG_R0), uc.reg_read(UC_ARM_REG_R1)))

        # FI_GetFIPSp is called when the original builds the collision board.
        o.uc.hook_add(UC_HOOK_CODE, record, begin=0x15384, end=0x15384)
        o.call(0xa420, seed)      # BHLib_SeedRNG
        o.call(0x1c71c, mode)    # FourBattleInit
        o.call(0x1517c, stage)   # LevelSelect
        for _ in range(180):
            o.call(0x1c2b8)      # FourBattleLoop
        assert requested_maps == [(mode, stage)], (mode, stage, seed, requested_maps)
        assert o.call(0x159c8) == stage  # GA_GetStageNumber
        assert o.call(0x15a14) == 1 and o.call(0x1821c) == 59  # active play after intro
        address = o.call(0x15384, mode, stage)
        assert o.read(address, 108 + 237) == boards[stage], (mode, stage, seed)
    print(f'{len(cases)} original iPad launches selected the exact exported board through the intro and into play')


if __name__ == '__main__':
    main()
