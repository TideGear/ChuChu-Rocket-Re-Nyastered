"""Trace cat cue selection and the GBA ROM's song-number dispatcher."""
from pathlib import Path

from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_SP

from gba_oracle import GBA, STOPADDR


def main():
    root = Path(__file__).resolve().parents[2]
    gba = GBA(root / 'analysis/gba/ccr.gba')
    uc = gba.uc
    obj = 0x03000700
    cues = []
    starts = []
    collision = 0
    arrival = 1

    def hook(uc, address, size, data):
        r0 = uc.reg_read(UC_ARM_REG_R0)
        if address == 0x08024930:
            cues.append(r0)
            return  # Keep the ROM dispatcher and its table lookup running.
        if address == 0x08024fac:
            starts.append((r0, uc.reg_read(UC_ARM_REG_R1)))
        elif address == 0x080041ac:
            uc.reg_write(UC_ARM_REG_R0, collision)
        elif address == 0x08003508:
            uc.reg_write(UC_ARM_REG_R0, arrival)
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))

    for address in (0x08024930, 0x08024fac, 0x080041ac, 0x08003508, 0x08004158,
                    0x08004570, 0x08000cf4, 0x080032d8, 0x08004250):
        uc.hook_add(UC_HOOK_CODE, hook, begin=address, end=address)

    def run(count, flags, movement, expected):
        cues.clear()
        starts.clear()
        uc.mem_write(obj, bytes(0x30))
        uc.mem_write(obj + 3, bytes([flags]))
        uc.mem_write(obj + 0x19, bytes([count]))
        gba.w16(obj + 0x20, movement)
        uc.reg_write(UC_ARM_REG_R0, obj)
        uc.reg_write(UC_ARM_REG_SP, 0x03007e00)
        uc.reg_write(UC_ARM_REG_LR, STOPADDR | 1)
        uc.emu_start(0x08003141, STOPADDR, count=10000)
        assert cues == expected, (count, flags, movement, cues, expected)
        table = gba.r32(0x08024958)
        players = gba.r32(0x08024954)
        assert starts == [(gba.r32(players + 12 * gba.r16(table + 8 * i + 4)),
                           gba.r32(table + 8 * i)) for i in expected], starts

    run(0, 0x80, 0, [])     # Ordinary catch below the large-cat threshold.
    run(48, 0x80, 0, [])
    run(49, 0x80, 0, [42])
    run(50, 0x80, 0, [])
    run(0, 0xc0, 0, [42])   # The alternate catch flag adds 50.
    run(99, 0x80, 0, [43])  # The second threshold also selects the large-cat effect.
    for literal, value in ((0x080031c8, 1), (0x080031cc, 2)):
        gate = gba.r32(literal)
        uc.mem_write(gate, bytes([value]))
        run(49, 0x80, 0, [])
        uc.mem_write(gate, bytes(1))
    collision = 0x20
    run(0, 0, 0x1000, [36])
    run(49, 0, 0x1000, [36])
    run(50, 0, 0x1000, [43])
    arrival = 0
    run(50, 0, 0x1000, [])
    for index, program in ((36, 5), (42, 67), (43, 30)):
        header = gba.r32(gba.r32(0x08024958) + 8 * index)
        stream = gba.r32(header + 8)
        assert gba.r8(header) == 1 and bytes(uc.mem_read(stream + 4, 2)) == bytes([0xbd, program])
        print(f'cue {index}: sequence header {header:#010x}, initial program {program}')
    print('12 GBA cat cue and song dispatcher cases matched')


if __name__ == '__main__':
    main()
