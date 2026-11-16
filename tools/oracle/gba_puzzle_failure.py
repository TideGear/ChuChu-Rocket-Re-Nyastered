"""Trace forced mouse catches, hole falls, and post-failure controls in GBA Puzzle."""
import argparse
import pickle
from pathlib import Path

from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0

from gba_session import GBA, ROM, boot_to_menu, run


def probe(state, failure, after_start=None, followup=()):
    gba = GBA(ROM)
    gba.load_state(state)
    uc = gba.uc
    start = gba.frame
    pending = gba.r32(0x08002ed4)
    frozen = gba.r32(0x08002ca0)
    assert gba.r8(gba.r32(0x08002e20)) == 8 and gba.r8(frozen) and not gba.r8(pending)
    sounds, marker_updates, writes, collisions = [], [], [], []

    def catch(uc, address, size, data):
        if not collisions and not gba.r8(frozen):
            mouse = uc.reg_read(UC_ARM_REG_R0)
            uc.mem_write(mouse + 3, bytes([gba.r8(mouse + 3) | 128]))
            collisions.append(gba.frame - start)

    def hole(uc, address, size, data):
        caller = uc.reg_read(UC_ARM_REG_LR)
        if not collisions and caller == 0x08002cd7:
            uc.reg_write(UC_ARM_REG_R0, 0xffffff80)
            uc.reg_write(UC_ARM_REG_PC, caller)
            collisions.append(gba.frame - start)

    def trace(uc, address, size, data):
        if address == 0x0800488c:
            marker_updates.append(gba.frame - start)
        else:
            sounds.append((gba.frame - start, uc.reg_read(UC_ARM_REG_R0), uc.reg_read(UC_ARM_REG_LR)))

    def pending_write(uc, access, address, size, value, data):
        writes.append((gba.frame - start, value, uc.reg_read(UC_ARM_REG_PC)))

    if failure == 'catch':
        uc.hook_add(UC_HOOK_CODE, catch, begin=0x08002c28, end=0x08002c28)
    elif failure == 'hole':
        uc.hook_add(UC_HOOK_CODE, hole, begin=0x080041ac, end=0x080041ac)
    for address in (0x08024930, 0x0802495c, 0x0800488c):
        uc.hook_add(UC_HOOK_CODE, trace, begin=address, end=address)
    uc.hook_add(UC_HOOK_MEM_WRITE, pending_write, begin=pending, end=pending)

    keys = {10: 'r'}
    if after_start:
        frame, key = after_start
        keys[frame] = key
    run(gba, 300, keys)

    expected_sounds = [(11, 5, 0x0800b13d)]
    if failure:
        expected_sounds.append((12, 62, 0x0800490b))
        assert collisions == [12]
        assert marker_updates == list(range(13, 133))
        writer = 0x08002e7c if failure == 'catch' else 0x08002eac
        assert writes == [(12, 255, writer), (133, 0, 0x08000f00)], writes
    else:
        assert not marker_updates and not writes
    expected_sounds.extend(followup)
    assert sounds == expected_sounds, sounds


def verify_stage(state, panel_placed):
    rescue_frames = (72, 82, 92, 102, 112, 192, 202, 212, 222, 232) if panel_placed else ()
    probe(state, None, followup=[(frame, 37, 0x08003079) for frame in rescue_frames])
    panel_cue = (6, 0x0800c0b3) if panel_placed else (4, 0x0800c12f)
    rescue = [(frame + 124, 37, 0x08003079) for frame in rescue_frames if frame < 120]
    for failure in ('catch', 'hole'):
        probe(state, failure)
        for key in ('A', 'B', 'T', 'r'):
            probe(state, failure, (20, key))
        for frame in (125, 131, 132):
            probe(state, failure, (frame, 'A'))
        for frame, response in ((133, 135), (134, 135), (135, 136), (260, 261)):
            for key in ('A', 'B'):
                probe(state, failure, (frame, key), [(response, *panel_cue)])
        probe(state, failure, (133, 'T'), [(136, 35, 0x08001b0f)])
        probe(state, failure, (133, 'r'), [(135, 5, 0x0800b13d), *rescue])
    print(f'37 GBA Puzzle cases matched with the panel {"placed" if panel_placed else "in stock"}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('snapshot', type=Path, nargs='?', help='optional trusted local fixture with a panel placed')
    args = parser.parse_args()
    if args.snapshot:
        with args.snapshot.open('rb') as stream:
            verify_stage(pickle.load(stream), panel_placed=True)
        return

    gba = boot_to_menu(cache=False)
    run(gba, 240, {10: 'U', 30: 'R', 60: 'A'})
    selection = gba.save_state()
    for panel_placed in (False, True):
        gba.load_state(selection)
        keys = {30: 'A'}
        if panel_placed:
            keys[220] = 'A'
        run(gba, 300, keys)
        verify_stage(gba.save_state(), panel_placed)


if __name__ == '__main__':
    main()
