"""Compare the full HD 1.0 startup sequence with the port."""
import os
from pathlib import Path
import struct
import subprocess
import sys

from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_SP

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools' / 'oracle'))
import hd_env
from ios_oracle import f2u, u2f


def main():
    del hd_env.HOOKS[0xbcc4], hd_env.HOOKS[0xc9b4]
    env = hd_env.make()
    oracle = env.o
    task = oracle.alloc(0xa20)
    state = env.appdata + 0x668
    requested = env.appdata + 0x658
    jingle = []
    logo = []

    def hook(uc, addr, size, data):
        if addr == 0xbcc4:
            oracle.write(state, struct.pack('<I', oracle._r(1)))
        elif addr == 0xc9b4:
            jingle.append(oracle._r(1))
        else:
            sp = uc.reg_read(UC_ARM_REG_SP)
            logo.append(oracle.u32(sp + 28))
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))

    for addr in (0xbcc4, 0xc9b4, 0xa70c):
        oracle.uc.hook_add(UC_HOOK_CODE, hook, begin=addr, end=addr)
    for slot in (3, 4, 5):
        image = oracle.u32(env.appdata + 0x3cc + 4 * slot)
        oracle.call(0xb194, image, 0, 0, f2u(1024), f2u(1024))

    init = [0xe400, 0xe020, 0xe7a0]
    process = [0xe6e0, 0xe27c, 0xe840]
    handle = [0xe3fc, 0xe0dc, 0xe8fc]
    render = [0xe540, 0xe110, 0xe930]
    inputs = []
    expected = []
    for skip in (0, 6, 9):
        oracle.write(task, bytes(0xa20))
        screen = 0
        oracle.write(requested, bytes(4))
        oracle.call(init[screen], task)
        while screen < 3:
            press = int(oracle.u32(state) == skip)
            inputs.append(f'16666.666015625 {press}\n')
            if press:
                oracle.call(handle[screen], task, 10, 10, 0)
            jingle.clear()
            oracle.call(process[screen], task, f2u(16666.666015625))
            new = oracle.u32(requested)
            if new != screen:
                screen = new
                if screen < 3:
                    oracle.call(init[screen], task)
            assert not jingle or jingle == [14]
            env.log.clear()
            logo.clear()
            if screen == 3:
                expected.append((11, 500000.0, 0, 255, 0))
            else:
                oracle.call(render[screen], task)
                assert len(logo) == 1
                blackout = env.log[-1][-1] if len(env.log) == 2 else 0
                expected.append((oracle.u32(state), u2f(oracle.u32(task + 0xa14)), int(bool(jingle)),
                                 logo[0], blackout))
    rows = subprocess.run([ROOT / 'build/game/ccr.exe'], input=''.join(inputs), capture_output=True,
                          text=True, env=dict(os.environ, CCR_STARTUP_FLOW_TRACE='1'),
                          check=True).stdout.splitlines()
    assert len(rows) == len(expected)
    for i, (row, ref) in enumerate(zip(rows, expected)):
        phase, timer, jingle, opacity, fade = row.split()
        assert (int(phase), float.fromhex(timer), int(jingle), int(opacity), int(fade)) == ref, (i, row, ref)
    print(f'{len(rows)} startup ticks matched including both skip paths')


if __name__ == '__main__':
    main()
