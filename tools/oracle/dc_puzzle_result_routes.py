"""Original-loop Puzzle result navigation with injected progress/stage fixtures.

Resume a clear-state snapshot; the scheduler and input handlers run normally.
This tests navigation, not natural completion of the injected stage index.
"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess

from dc_challenge_result_routes import word


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('host', 'core', 'system', 'save', 'disc', 'state', 'out'):
        p.add_argument('--' + name, required=True, type=Path)
    p.add_argument('--pending', type=int, choices=(-2, -1), default=-2)
    args = p.parse_args()
    paths = {k: v.resolve() for k, v in vars(args).items() if isinstance(v, Path)}
    paths['out'].mkdir(parents=True, exist_ok=True)
    for all_groups in (False, True):
        for button, key in (('A', 'B'), ('B', 'A'), ('Start', 'START')):
            tag = ('all' if all_groups else 'normal') + '_dc' + button
            prefix = paths['out'] / (tag + '_')
            save = paths['out'] / (tag + '_save')
            shutil.copytree(paths['save'], save, dirs_exist_ok=True)
            env = {k: v for k, v in os.environ.items()
                   if not (k.startswith('FLY_') or k.startswith('FLYHOST_'))}
            masks = ','.join(f'{0x22d8a4 + 4 * i:x}=' +
                             ('1ffffff' if all_groups or i == 0 else '0')
                             for i in range(4))
            env.update(FLYHOST_STATE=str(paths['state']), FLY_DUMP='1',
                       FLY_POKE_ONCE=f'0:1ae8bc=18,cdaa4={args.pending & 0xffffffff:x},' + masks)
            cmd = [str(paths[n]) for n in ('host', 'core', 'system')]
            cmd += [str(save), str(paths['disc']), '650', str(prefix),
                    '100,600', key + '@350-352']
            with (paths['out'] / (tag + '.log')).open('w') as log:
                subprocess.run(cmd, env=env, stdout=log, stderr=log,
                               check=True, timeout=90)
            before = Path(str(prefix) + '00100.ram').read_bytes()
            after = Path(str(prefix) + '00600.ram').read_bytes()
            assert word(before, 0x1af108) == 15, tag
            assert word(before, 0x1ae8bc) == 24, tag
            assert word(before, 0xcdaa4) == args.pending, tag
            expected = 17 if all_groups and button != 'B' else 7
            assert word(after, 0x1af108) == expected, tag
            print(f'{tag}: pending {args.pending}, stage 24, destination mode {expected}')


if __name__ == '__main__':
    main()
