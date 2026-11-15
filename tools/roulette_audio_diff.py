"""Compare original iPad roulette cues with headless live battles."""
import os
from pathlib import Path
import struct
import subprocess
import sys

from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools' / 'oracle'))
import hd_env


def original_cues():
    oracle = hd_env.make().o
    oracle.call(0x15188)
    manager = oracle.u32(0x1d6d0)
    task = oracle.alloc(0x58)
    created = oracle.alloc(0x58)
    cues = []
    dispatch = []

    def record(uc, address, size, user):
        if address == 0x17dd0:
            cues.append((tick, oracle._r(0)))
            assert oracle._r(1) == 0
        elif address == 0x18084:
            dispatch.append((tick, oracle._r(0), oracle._r(1), oracle._r(2)))
            uc.reg_write(UC_ARM_REG_R0, created)
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))

    for address in (0x17dd0, 0x18084, 0x17fb8, 0x13be8, 0x15bb0):
        oracle.uc.hook_add(UC_HOOK_CODE, record, begin=address, end=address)
    results = {}
    for outcome in range(8):
        oracle.write(manager + 4, struct.pack('<2i', 2, outcome))
        oracle.write(task, bytes(0x58))
        cues.clear()
        dispatch.clear()
        for tick in range(121):
            oracle.call(0x1d4dc, task)
        assert len(dispatch) == 1 and dispatch[0][0] == 120
        assert dispatch[0][2:] == (0, 0)  # No constructor or draw callback.
        assert len(cues) == 3 and cues[-1][1] not in results
        results[cues[-1][1]] = list(cues)
    tick = 121
    cues.clear()
    oracle.write(created, bytes(0x58))
    oracle.call(0x1daec, created)  # RL_Eve_Replace
    assert len(cues) == 1
    return results, cues[0]


def main():
    expected, replace_cue = original_cues()
    executable = ROOT / 'build/game/ccr.exe'
    output = ROOT / 'local/roulette-audio-check.bmp'
    env = dict(os.environ, CCR_SHOT=str(output), CCR_TICKS='10000', CCR_AUDIO_TEST='1',
               CCR_ROULETTE_AUDIO_TRACE='1', CCR_LANG='en')
    seen = set()
    checked = 0
    checked_replace = 0
    for seed in range(1, 25):
        result = subprocess.run([executable, 'battle', '0', str(seed)], cwd=ROOT,
                                env=env, check=True, capture_output=True, text=True)
        cues = []
        last_voice = None
        for line in result.stdout.splitlines():
            fields = line.split()
            if fields[:2] == ['roulette', 'cue']:
                frame, sound = map(int, fields[2:])
                if sound == replace_cue[1]:
                    assert last_voice == 122 and frame - start == replace_cue[0]
                    checked_replace += 1
                else:
                    cues.append((frame, sound))
            elif fields[:2] == ['roulette', 'clip']:
                _, last_voice = cues[-1]
                assert fields[2] == f'{last_voice:03d}.ogg' and int(fields[3]) > 0
                start = cues[0][0]
                assert [(frame - start, sound) for frame, sound in cues] == expected[last_voice]
                cues.clear()
                seen.add(last_voice)
                checked += 1
        assert len(cues) < 3, 'Voice requested but the clip did not load'
        if seen == expected.keys():
            break
    assert seen == expected.keys(), (seen, expected.keys())
    assert checked_replace
    print(f'{checked} live rolls matched original cue IDs and timing across eight outcomes, '
          f'with {checked_replace} matching Place Arrows Again effects')


if __name__ == '__main__':
    main()
