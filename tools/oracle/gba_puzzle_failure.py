"""Trace a forced catch and retry from a local GBA Puzzle planning snapshot."""
import argparse
import pickle
from pathlib import Path

from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0

from gba_session import GBA, ROM, run


def probe(state, force_catch, retry):
    gba = GBA(ROM)
    gba.load_state(state)
    uc = gba.uc
    start = gba.frame
    pending = gba.r32(0x08002ed4)
    frozen = gba.r32(0x08002ca0)
    assert gba.r8(gba.r32(0x08002e20)) == 8 and gba.r8(frozen) and not gba.r8(pending)
    sounds, marker_updates, writes, catches = [], [], [], []

    def catch(uc, address, size, data):
        if not catches and not gba.r8(frozen):
            mouse = uc.reg_read(UC_ARM_REG_R0)
            uc.mem_write(mouse + 3, bytes([gba.r8(mouse + 3) | 128]))
            catches.append(gba.frame - start)

    def trace(uc, address, size, data):
        if address == 0x0800488c:
            marker_updates.append(gba.frame - start)
        else:
            sounds.append((gba.frame - start, uc.reg_read(UC_ARM_REG_R0), uc.reg_read(UC_ARM_REG_LR)))

    def pending_write(uc, access, address, size, value, data):
        writes.append((gba.frame - start, value, uc.reg_read(UC_ARM_REG_PC)))

    if force_catch:
        uc.hook_add(UC_HOOK_CODE, catch, begin=0x08002c28, end=0x08002c28)
    for address in (0x08024930, 0x0802495c, 0x0800488c):
        uc.hook_add(UC_HOOK_CODE, trace, begin=address, end=address)
    uc.hook_add(UC_HOOK_MEM_WRITE, pending_write, begin=pending, end=pending)

    keys = {10: 'r'}
    if retry:
        keys[260] = retry
    run(gba, 300, keys)

    expected_sounds = [(11, 5, 0x0800b13d)]
    if force_catch:
        expected_sounds.append((12, 62, 0x0800490b))
        assert catches == [12]
        assert marker_updates == list(range(13, 133))
        assert writes == [(12, 255, 0x08002e7c), (133, 0, 0x08000f00)]
        if retry:
            expected_sounds.append((261, 6, 0x0800c0b3))
    else:
        assert not marker_updates and not writes
        expected_sounds.extend((frame, 37, 0x08003079)
                               for frame in (72, 82, 92, 102, 112, 192, 202, 212, 222, 232))
    assert sounds == expected_sounds, sounds


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('snapshot', type=Path, help='local gba_session Puzzle planning fixture')
    args = parser.parse_args()
    with args.snapshot.open('rb') as stream:
        state = pickle.load(stream)
    for force_catch, retry in ((False, None), (True, None), (True, 'A'), (True, 'B')):
        probe(state, force_catch, retry)
    print('GBA Puzzle: natural control plus forced catch with no input, A, and B matched')


if __name__ == '__main__':
    main()
