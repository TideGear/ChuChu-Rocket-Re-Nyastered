"""Compare all iPad Battle Settings preview pixels with the original."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parent / 'oracle'))
from hd_battle_preview import BattlePreviewOracle


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('executable', type=Path)
    parser.add_argument('assets', type=Path)
    args = parser.parse_args()

    oracle = BattlePreviewOracle()
    with TemporaryDirectory() as temp:
        dump = Path(temp) / 'previews.bin'
        env = dict(os.environ, CCR_HEADLESS='1', CCR_PAD_PREVIEW_DUMP=str(dump))
        subprocess.run([args.executable.resolve(), args.assets.resolve()], env=env, check=True)
        with dump.open('rb') as actual:
            for team in (False, True):
                for stage in range(25):
                    expected = oracle.capture(team, stage)
                    observed = actual.read(len(expected))
                    if len(observed) != len(expected):
                        raise SystemExit(f'Short preview for team={team}, stage={stage}')
                    if observed != expected:
                        first = next(i for i, (a, b) in enumerate(zip(observed, expected)) if a != b) // 2
                        x, y = first % 832, first // 832
                        got = int.from_bytes(observed[first * 2:first * 2 + 2], 'little')
                        want = int.from_bytes(expected[first * 2:first * 2 + 2], 'little')
                        raise SystemExit(f'team={team}, stage={stage}, pixel ({x}, {y}): {got:04x} != {want:04x}')
            if actual.read(1):
                raise SystemExit('Unexpected pixels after the final preview')
    print('50 original iPad preview uploads match byte for byte')


if __name__ == '__main__':
    main()
