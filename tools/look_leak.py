#!/usr/bin/env python3
"""Find mobile art leaking into the Dreamcast look (and the reverse).

usage: look_leak.py <exe> <dreamcast-only assets> <all-files assets> <out dir> [--look dreamcast|mobile] [--other <mobile-only assets>]

Renders the same screens at the same ticks headlessly from a cache that has only one platform's files and from a cache with every
file, with the presentation forced to that platform's look. Art from the other platform can only appear in the second render, so
any screen whose renders differ is a candidate leak; the script writes both frames and a heat map for each differing case.
The Dreamcast-only and mobile-only caches come from tools/setup-wizard.ps1 (verification.md, 2026-11-24 end-to-end setup).
Headless only: it never shows a window or plays sound.
"""
import os, subprocess, sys, tempfile
from PIL import Image, ImageChops

CASES = [   # name, ccr args, extra environment
    ('startup_200', ['STARTUP'], {'CCR_TICKS': '200'}),
    ('mobile_options_settings', ['OPTIONS'], {'CCR_TICKS': '300', 'CCR_CLICKS': '60:345,289;100:345,289'}),
    ('title', ['DC_TITLE'], {'CCR_TICKS': '60'}),
    ('menu', ['MENU'], {'CCR_TICKS': '60'}),
    ('help', ['HELP'], {'CCR_TICKS': '60'}),
    ('help_page', ['HELP'], {'CCR_TICKS': '120', 'CCR_KEYS': 'E', 'CCR_KEY_TICK': '40'}),
    ('options', ['OPTIONS'], {'CCR_TICKS': '60'}),
    ('options_general', ['OPTIONS'], {'CCR_TICKS': '100', 'CCR_KEYS': 'E', 'CCR_KEY_TICK': '30'}),
    ('stages', ['STAGES'], {'CCR_TICKS': '90'}),
    ('puzzle_ready', ['puzzle', '0'], {'CCR_TICKS': '60'}),
    ('puzzle_run', ['puzzle', '0'], {'CCR_TICKS': '400', 'CCR_KEYS': ' ', 'CCR_KEY_TICK': '30'}),
    ('puzzle_pause', ['puzzle', '0'], {'CCR_TICKS': '120', 'CCR_KEYS': 'P', 'CCR_KEY_TICK': '30'}),
    ('challenge_select', ['CHALLENGE_SELECT'], {'CCR_TICKS': '90'}),
    ('challenge_intro', ['challenge', '0'], {'CCR_TICKS': '30'}),
    ('challenge_play', ['challenge', '0'], {'CCR_TICKS': '600'}),
    ('battle_setup', ['BATTLE'], {'CCR_TICKS': '90'}),
    ('team_setup', ['TEAM_BATTLE'], {'CCR_TICKS': '90'}),
    ('battle_start', ['battle', '0', '1', '3,3,3'], {'CCR_TICKS': '60'}),
    ('battle_play', ['battle', '0', '1', '3,3,3'], {'CCR_TICKS': '1500'}),
    ('battle_late', ['battle', '0', '1', '3,3,3'], {'CCR_TICKS': '5000'}),
    ('team_play', ['TEAM_BATTLE', '0', '1', '3,3,3'], {'CCR_TICKS': '1500'}),
]


def shot(exe, assets, args, env, out, look, saves):
    e = dict(os.environ, CCR_SIZE='640x480', CCR_SHOT=out, CCR_PRESENTATION=look, CCR_TEST_SAVE_DIR=saves, **env)
    if look == 'mobile':
        e['CCR_MODELS'] = '0'   # a mobile-only cache has no model pack; compare the 2D field
    r = subprocess.run([exe, assets] + args, env=e, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=600)
    return r.returncode, r.stdout.decode('latin1', 'replace').strip().splitlines()[-1:] if r.stdout else []


def main():
    argv = sys.argv[1:]
    look = 'dreamcast'
    if '--look' in argv:
        i = argv.index('--look'); look = argv[i + 1]; del argv[i:i + 2]
    only = ''
    if '--only' in argv:
        i = argv.index('--only'); only = argv[i + 1]; del argv[i:i + 2]
    exe, single, full, out = argv[:4]
    os.makedirs(out, exist_ok=True)
    # Both renders must use the same empty save state: cache-local clears and
    # Challenge records are player data, not art from another release.
    saves = tempfile.mkdtemp(prefix='empty-save-', dir=os.path.abspath(out))
    cases = list(CASES)
    if look == 'dreamcast':
        cases += [('staff_cat', ['DC_STAFFROLL'], {'CCR_TICKS': '1246'}),
                  ('staff_flock', ['DC_STAFFROLL'], {'CCR_TICKS': '3046'})]
    cases = [case for case in cases if only in case[0]]
    if not cases: raise SystemExit('no look cases matched')
    leaks = 0
    for name, args, env in cases:
        a, b = os.path.join(out, name + '_single.bmp'), os.path.join(out, name + '_full.bmp')
        ra, la = shot(exe, single, args, env, a, look, saves)
        rb, lb = shot(exe, full, args, env, b, look, saves)
        if not (os.path.exists(a) and os.path.exists(b)):
            leaks += 1
            print(f'{name}: no frame (exit {ra}/{rb}) {la} {lb}'); continue
        ia, ib = Image.open(a).convert('RGB'), Image.open(b).convert('RGB')
        d = ImageChops.difference(ia, ib).convert('L')
        hist = d.histogram(); big = sum(hist[9:])
        mean = sum(i * n for i, n in enumerate(hist)) / max(1, sum(hist))
        status = 'same' if big == 0 else 'DIFF'
        if big:
            leaks += 1
            d.point(lambda v: 255 if v > 8 else 0).save(os.path.join(out, name + '_heat.png'))
            sheet = Image.new('RGB', (ia.width * 2, ia.height)); sheet.paste(ia, (0, 0)); sheet.paste(ib, (ia.width, 0))
            sheet.save(os.path.join(out, name + '_pair.png'))
        print(f'{name}: {status} ({big} px > 8 levels, mean {mean:.2f})')
    print(f'{leaks} of {len(cases)} cases differ')


if __name__ == '__main__':
    main()
