#!/usr/bin/env python3
"""Run every game test executable (build/game/*_test.exe) the way they expect and report each exit code.

usage: run_tests.py [--assets local/cache/assets] [--only substring]
The tests open their default inputs at ../local/... and so run from game/; the few that need arguments get them from ARGS below.
A test passes on exit code 0. Build first (build.cmd builds every test)."""
import glob, os, subprocess, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    args = sys.argv[1:]
    opt = lambda f, d: args[args.index(f) + 1] if f in args else d
    assets = os.path.join(ROOT, opt('--assets', 'local/cache/assets'))
    only = opt('--only', '')
    stages = os.path.join(assets, 'battle_stages.bin')
    ARGS = {
        'challenge_battle_game_test': [stages, '0', '1', '600'],
        'challenge_battle_test': [stages, '0', '1', '600'],
        'challenge_game_test': [stages, '0', '600'],
        'challenge_sim_test': [stages, '0'],
        'challenge_controller_test': [assets],
        'input_regression_test': [assets],
    }
    failed = 0
    exes = sorted(glob.glob(os.path.join(ROOT, 'build', 'game', '*_test.exe')))
    for exe in exes:
        name = os.path.splitext(os.path.basename(exe))[0]
        if only not in name: continue
        t0 = time.time()
        try:
            r = subprocess.run([exe] + ARGS.get(name, []), cwd=os.path.join(ROOT, 'game'), capture_output=True, text=True, timeout=900)
            rc, tail = r.returncode, (r.stdout + r.stderr).strip().splitlines()[-1:] or ['']
        except subprocess.TimeoutExpired:
            rc, tail = 'timeout', ['']
        ok = rc == 0
        failed += not ok
        print(f'{"pass" if ok else "FAIL"} {name} ({time.time() - t0:.1f}s){"" if ok else f" rc={rc}: {tail[0][:160]}"}')
    print(f'{len(exes) - failed} passed, {failed} failed')
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
