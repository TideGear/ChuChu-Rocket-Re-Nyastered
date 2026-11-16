"""Verify the original iPad Puzzle failure timer, task passes and automatic reset."""
import struct

from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0

import hd_env


def main():
    oracle = hd_env.make().o
    state = oracle.u32(0x18684)
    calls = []
    task_pass = [0x14cb8, 0x17f24, 0x14ee0]
    rebuild = [0x15a70, 0x17e0c, 0x18084, 0x15a20, 0x15804, 0x17364, 0x16044, 0x144c0,
               0x1e028, 0x1de1c, 0x140cc, 0x1f404, 0x18084]
    failure = [0x18e48, 0x1f414, 0x15a20, 0x15a08, 0x17dd0]
    mouse_failed = False

    def hook(uc, address, size, data):
        calls.append((address, oracle._r(0)))
        result = int(address == 0x15f24 or address == (0x15f30 if mouse_failed else 0x143fc))
        uc.reg_write(UC_ARM_REG_R0, result)
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))

    monitored = {0x15f24, 0x15f30, 0x143fc, 0x17e38, 0x3baf8, 0x3bcb4, *task_pass, *rebuild, *failure}
    for address in monitored:
        oracle.uc.hook_add(UC_HOOK_CODE, hook, begin=address, end=address)

    for mouse_failed in (False, True):
        for dash in (0, 1):
            oracle.write(state, struct.pack('<8I', 777, 3, dash, 0, 0, 0, 0, 0))
            for frame in range(123):
                calls.clear()
                oracle.call(0x18294)
                addresses = [address for address, _ in calls]
                phase = struct.unpack('<3I', oracle.read(state, 12))
                if frame == 0:
                    checks = [0x15f24, 0x15f30] + ([] if mouse_failed else [0x143fc])
                    assert phase == (1, 6, dash)
                    assert addresses == checks + failure + task_pass * (dash + 1), calls
                    assert (0x17dd0, 27) in calls
                elif frame < 120:
                    assert phase == (frame + 1, 6, dash)
                    assert addresses == task_pass * (dash + 1), calls
                elif frame == 120:
                    assert phase == (121, 1, dash)
                    assert addresses == [0x17e38] + task_pass * (dash + 1), calls
                else:
                    assert phase == (frame - 120, 2, 0)
                    assert addresses == (rebuild if frame == 121 else []) + task_pass, calls
    print('4 iPad Puzzle cases matched, including Dash, task teardown and automatic arrow-preserving reset')


if __name__ == '__main__':
    main()
