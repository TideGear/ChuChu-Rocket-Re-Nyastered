"""Observe Puzzle clear/save pending values through the original scheduler.

Resume a state shortly before its last mice arrive. Only stage index and progress
are injected; arrivals and the clear/result/save handlers run in the frame loop.
The board remains the saved board, so this is not other-stage gameplay evidence.
"""
import argparse
import os
from pathlib import Path
import shutil
import struct
import subprocess

from dc_challenge_result_routes import word


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('host', 'core', 'system', 'save', 'disc', 'state', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    paths = {k: v.resolve() for k, v in vars(parser.parse_args()).items()}
    paths['out'].mkdir(parents=True, exist_ok=True)
    full, last = 0x1ffffff, 0x1fffffe
    cases = (
        ('ordinary', 0, (0, 0, 0, 0), -2),
        ('normal_last', 0, (last, 0, 0, 0), 0),
        ('hard_last', 25, (full, last, 0, 0), 0),
        ('special_mania_last', 50, (full, full, last, last), -1),
        ('normal_repeat', 0, (full, 0, 0, 0), -2),
    )
    for tag, stage, masks, pending in cases:
        prefix = paths['out'] / (tag + '_')
        save = paths['out'] / (tag + '_save')
        shutil.copytree(paths['save'], save, dirs_exist_ok=True)
        watch = Path(str(prefix) + 'watch.bin')
        if watch.exists():
            watch.unlink()
        env = {k: v for k, v in os.environ.items()
               if not (k.startswith('FLY_') or k.startswith('FLYHOST_'))}
        pokes = ','.join(f'{0x22d8a4 + 4 * i:x}={m:x}' for i, m in enumerate(masks))
        env.update(FLYHOST_STATE=str(paths['state']), FLY_DUMP='1',
                   FLY_WATCH='22d894:32:0',
                   FLY_POKE_ONCE=f'0:1ae8bc={stage:x},cdaa4=fffffffe,' + pokes)
        cmd = [str(paths[n]) for n in ('host', 'core', 'system')]
        cmd += [str(save), str(paths['disc']), '450', str(prefix), '1,30,240,430', 'A@260-262']
        with (paths['out'] / (tag + '.log')).open('w') as log:
            subprocess.run(cmd, env=env, stdout=log, stderr=log,
                           check=True, timeout=90)
        before = Path(str(prefix) + '00001.ram').read_bytes()
        clear = Path(str(prefix) + '00030.ram').read_bytes()
        result = Path(str(prefix) + '00240.ram').read_bytes()
        assert word(before, 0x22d898) == 3, tag
        assert word(clear, 0x22d898) == 4, tag
        assert word(clear, 0xcdaa4) == pending, tag
        assert word(result, 0x22d898) == 5, tag
        assert word(result, 0xcdaa4) == pending, tag
        after = Path(str(prefix) + '00430.ram').read_bytes()
        destination = 17 if pending == 0 else 7
        assert word(after, 0x1af108) == destination, tag
        expected = list(masks)
        expected[stage // 25] |= 1 << (stage % 25)
        assert list(struct.unpack_from('<4I', result, 0x22d8a4)) == expected, tag
        records = list(struct.iter_unpack('<9I', watch.read_bytes()))
        phases = [(r[0], r[2]) for i, r in enumerate(records)
                  if not i or r[2] != records[i - 1][2]]
        print(f'{tag}: phases {phases}, pending {pending}, saved mask matches, DC B -> mode {destination}')


if __name__ == '__main__':
    main()
