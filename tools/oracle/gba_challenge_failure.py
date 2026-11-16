"""Audit death marker, failure, and retry timing in GBA Stage Challenge."""
from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0

from gba_session import GBA, ROM, boot_to_menu, run


def verify(selection, column, failure, row=0, natural_frame=None, input_at=None, retry_at=None):
    gba = GBA(ROM)
    gba.load_state(selection)
    uc = gba.uc
    start = gba.frame
    pending = gba.r32(0x08002ed4)
    frozen = gba.r32(0x08002ca0)
    injected, updates, sounds, writes = [], [], [], []
    collision_callers = {'mouse hole': 0x08002cd7, 'cat hole': 0x080031fb}
    collision_frame = natural_frame if natural_frame is not None else 649

    def inject(uc, address, size, data):
        if injected or gba.frame - start < 190 or gba.r8(frozen):
            return
        if failure == 'catch':
            mouse = uc.reg_read(UC_ARM_REG_R0)
            uc.mem_write(mouse + 3, bytes([gba.r8(mouse + 3) | 0x80]))
        else:
            caller = uc.reg_read(UC_ARM_REG_LR)
            if caller != collision_callers[failure]:
                return
            uc.reg_write(UC_ARM_REG_R0, 0xffffff80)
            uc.reg_write(UC_ARM_REG_PC, caller)
        injected.append(gba.frame - start)

    def trace(uc, address, size, data):
        frame = gba.frame - start
        if address == 0x0800488c:
            updates.append(frame)
        elif frame >= collision_frame:
            sounds.append((frame, uc.reg_read(UC_ARM_REG_R0), uc.reg_read(UC_ARM_REG_LR)))

    def pending_write(uc, access, address, size, value, data):
        frame = gba.frame - start
        if frame >= collision_frame:
            writes.append((frame, value, uc.reg_read(UC_ARM_REG_PC)))

    address = 0x08002c28 if failure == 'catch' else 0x080041ac
    if natural_frame is None:
        uc.hook_add(UC_HOOK_CODE, inject, begin=address, end=address)
    for address in (0x0800488c, 0x08024930, 0x0802495c):
        uc.hook_add(UC_HOOK_CODE, trace, begin=address, end=address)
    uc.hook_add(UC_HOOK_MEM_WRITE, pending_write, begin=pending, end=pending)

    directions = 'D' * row + 'R' * column
    keys = {10 + 20 * index: key for index, key in enumerate(directions)}
    keys[180] = 'A'
    if input_at:
        offset, button = input_at
        keys[collision_frame + offset] = button
    run(gba, collision_frame + 251, keys)

    writer = {'catch': 0x08002e7c, 'mouse hole': 0x08002eac,
              'cat hole': 0x080033e0, 'cat rocket': 0x080035fe}[failure]
    expected_writes = [(collision_frame, 255, writer), (collision_frame + 120, 255, 0x0800823a)]
    expected_sounds = [(collision_frame, 62, 0x0800490b)]
    if failure == 'cat rocket':
        expected_sounds.insert(0, (collision_frame, 36, 0x080046a9))
    last_update = collision_frame + 192
    if retry_at is not None:
        retry_frame = collision_frame + retry_at
        expected_writes.append((retry_frame + 1, 0, 0x08000f00))
        expected_sounds.extend([(retry_frame, 5, 0x080082d3), (retry_frame + 2, 59, 0x08007e95)])
        last_update = min(last_update, retry_frame)
    assert injected == ([collision_frame] if natural_frame is None else []), injected
    assert updates == list(range(collision_frame + 1, last_update + 1)), updates
    assert writes == expected_writes, writes
    assert sounds == expected_sounds, sounds
    assert gba.r8(pending) == (0 if retry_at is not None else 255)


def main():
    gba = boot_to_menu(cache=False)
    run(gba, 240, {10: 'D', 30: 'D', 60: 'A'})
    selection = gba.save_state()
    for column, failure in ((0, 'catch'), (1, 'catch'), (2, 'mouse hole'), (2, 'cat hole')):
        verify(selection, column, failure)
    for button in ('A', 'T'):
        for offset in (11, 119, 120, 134):
            verify(selection, 2, 'cat hole', input_at=(offset, button))
        for offset in (135, 151, 193):
            verify(selection, 2, 'cat hole', input_at=(offset, button), retry_at=offset + 1)
    for offset in (135, 151, 193):
        verify(selection, 2, 'cat hole', input_at=(offset, 'B'))
    verify(selection, 0, 'mouse hole', row=3, natural_frame=792)
    verify(selection, 1, 'cat rocket', row=4, natural_frame=820)
    for column, failure, row, frame in ((0, 'mouse hole', 3, 792), (1, 'cat rocket', 4, 820)):
        verify(selection, column, failure, row, frame, input_at=(134, 'A'))
        verify(selection, column, failure, row, frame, input_at=(135, 'A'), retry_at=136)
    print('27 GBA Stage Challenge cases matched, including natural failures and retry boundaries')


if __name__ == '__main__':
    main()
