"""Check original Puzzle pause inputs from a paused state, without RAM pokes."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess

from dc_challenge_result_routes import word


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('host', 'core', 'system', 'save', 'disc', 'state', 'out'):
        parser.add_argument('--' + name, required=True, type=Path)
    paths = {k: v.resolve() for k, v in vars(parser.parse_args()).items()}
    paths['out'].mkdir(parents=True, exist_ok=True)
    # Flycast libretro B = DC A; A = DC B. Start and Y map directly.
    for selection in (0, 1):
        for button, key in (('A', 'B'), ('Start', 'START'), ('B', 'A'), ('Y', 'Y')):
            tag = ('quit' if selection else 'resume') + '_dc' + button
            prefix = paths['out'] / (tag + '_')
            save = paths['out'] / (tag + '_save')
            shutil.copytree(paths['save'], save, dirs_exist_ok=True)
            env = {k: v for k, v in os.environ.items()
                   if not (k.startswith('FLY_') or k.startswith('FLYHOST_'))}
            env.update(FLYHOST_STATE=str(paths['state']), FLY_DUMP='1')
            keys = ('RIGHT@10-12;' if selection else '') + key + '@30-32'
            cmd = [str(paths[n]) for n in ('host', 'core', 'system')]
            cmd += [str(save), str(paths['disc']), '120', str(prefix), '2,25,100', keys]
            with (paths['out'] / (tag + '.log')).open('w') as log:
                subprocess.run(cmd, env=env, stdout=log, stderr=log,
                               check=True, timeout=90)
            before = Path(str(prefix) + '00025.ram').read_bytes()
            after = Path(str(prefix) + '00100.ram').read_bytes()
            assert before[0x1af155] == 1, tag
            assert word(before, 0x1af164) == selection, tag
            accept = button in ('A', 'Start')
            expected_mode = 7 if accept and selection else 15
            assert word(after, 0x1af108) == expected_mode, tag
            assert bool(after[0x1af155]) == (not accept), tag
            if not accept:
                assert word(after, 0x1af164) == selection, tag
                assert word(after, 0x22d894) == word(before, 0x22d894), tag
            print(f'{tag}: mode {expected_mode}, paused {not accept}')


if __name__ == '__main__':
    main()
