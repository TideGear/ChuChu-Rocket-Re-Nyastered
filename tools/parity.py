#!/usr/bin/env python3
"""Run every port-vs-Flycast parity case in tools/parity_manifest.json and report the errors.

usage: parity.py <assets dir> [--out local/parity] [--only substring] [--exe build/game/ccr.exe]

For each case: renders the port headlessly (accelerated renderer on a hidden window, never the user's screen or audio),
compares it with the local Flycast reference, writes a reference|port|heatmap sheet (tools/diff_heatmap.py colours) and
appends a CSV row: full-frame mean RGB error, pixels off by more than 1 and by more than 8 levels, and per-element crops
(mean, pixels >8, best integer alignment shift within +-2 px). Cases whose reference is missing are reported as skipped."""
import csv, json, os, subprocess, sys
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def heat(err):
    h = np.zeros(err.shape + (3,), np.uint8)
    h[err == 1] = (0, 0, 90)
    h[(err > 1) & (err <= 8)] = (0, 90, 255)
    h[(err > 8) & (err <= 32)] = (255, 220, 0)
    h[(err > 32) & (err <= 96)] = (255, 60, 0)
    h[err > 96] = (255, 255, 255)
    return h


def best_shift(r, p, box, reach=2):
    x0, y0, x1, y1 = box
    ref = r[y0:y1, x0:x1]
    best = None
    for dy in range(-reach, reach + 1):
        for dx in range(-reach, reach + 1):
            if y0 + dy < 0 or x0 + dx < 0 or y1 + dy > p.shape[0] or x1 + dx > p.shape[1]:
                continue
            e = np.abs(ref - p[y0 + dy:y1 + dy, x0 + dx:x1 + dx]).mean()
            if best is None or e < best[0]:
                best = (e, dx, dy)
    return best


def expand(case):
    if 'sweep' not in case:
        yield case
        return
    s = case['sweep']
    for v in range(s['from'], s['to'] + 1):
        env = {k: str(eval(val[1:-1], {s['var']: v})) if val.startswith('{') else val for k, val in case['env'].items()}
        k = eval(case['k'], {s['var']: v}) if 'k' in case else v
        c = dict(case, name=case['name'].format(**{s['var']: v}), ref=case['ref'].format(k=k, **{s['var']: v}), env=env)
        c.pop('sweep')
        yield c


def main():
    args = sys.argv[1:]
    assets = args[0]
    opt = lambda f, d: args[args.index(f) + 1] if f in args else d
    out = os.path.join(ROOT, opt('--out', 'local/parity'))
    only = opt('--only', '')
    exe = os.path.join(ROOT, opt('--exe', 'build/game/ccr.exe'))
    os.makedirs(out, exist_ok=True)
    man = json.load(open(os.path.join(ROOT, 'tools', 'parity_manifest.json')))
    rows = []
    for case in (c for raw in man['cases'] for c in expand(raw)):
        if only not in case['name']:
            continue
        ref_path = os.path.join(ROOT, case['ref'])
        if not os.path.isfile(ref_path):
            rows.append({'case': case['name'], 'status': 'skipped (no reference)'})
            print(case['name'], 'skipped: no reference', case['ref'])
            continue
        shot = os.path.join(out, case['name'] + '.bmp')
        env = dict(os.environ, **man['defaults']['env'], **case.get('env', {}), CCR_SHOT=shot)
        if os.path.exists(shot):
            os.remove(shot)
        subprocess.run([exe, os.path.join(ROOT, case['assets']) if 'assets' in case else assets] + case['args'], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300)
        if not os.path.isfile(shot):
            rows.append({'case': case['name'], 'status': 'port capture failed'})
            print(case['name'], 'port capture failed')
            continue
        r = np.asarray(Image.open(ref_path).convert('RGB')).astype(int)
        p = np.asarray(Image.open(shot).convert('RGB')).astype(int)
        err = np.abs(r - p).max(2)
        row = {'case': case['name'], 'status': 'ok', 'mean': round(float(np.abs(r - p).mean()), 4),
               'px_gt1': int((err > 1).sum()), 'px_gt8': int((err > 8).sum()), 'note': case.get('note', '')}
        for name, box in case.get('elements', {}).items():
            x0, y0, x1, y1 = box
            e, dx, dy = best_shift(r, p, box)
            row[name + '_mean'] = round(float(np.abs(r - p)[y0:y1, x0:x1].mean()), 4)
            row[name + '_px_gt8'] = int((err[y0:y1, x0:x1] > 8).sum())
            # px_gt8 outside a 1 px edge band: errors > 8 that are not within 1 px of a pixel that differs from its own neighbour in the reference (an edge)
            ref_c = r[y0:y1, x0:x1]
            edge = np.zeros(ref_c.shape[:2], bool)
            for ax in (0, 1):
                d = np.abs(np.diff(ref_c, axis=ax)).max(2) > 8
                if ax == 0: edge[:-1] |= d; edge[1:] |= d
                else: edge[:, :-1] |= d; edge[:, 1:] |= d
            band = edge.copy()
            for _ in range(1):
                b2 = band.copy(); b2[1:] |= band[:-1]; b2[:-1] |= band[1:]; b2[:, 1:] |= band[:, :-1]; b2[:, :-1] |= band[:, 1:]; band = b2
            off = int(((err[y0:y1, x0:x1] > 8) & ~band).sum())
            row[name + '_off_edge_gt8'] = off
            row[name + '_pass'] = bool(row[name + '_mean'] <= 1 and (dx, dy) == (0, 0) and off == 0)
            row[name + '_shift'] = '%d,%d' % (dx, dy)
            # goal.md "pass (rounding)": the only residue is a uniform signed offset of at most 2 levels per channel (GPU/emulator rounding):
            # shift (0,0), no off-edge pixel over 8, and once the per-channel offset is removed the mean error is <= 1.
            d = (p - r)[y0:y1, x0:x1].astype(float)
            o = d.reshape(-1, 3).mean(0)
            residual = float(np.abs(d - o).mean())
            row[name + '_offset'] = '%+.2f,%+.2f,%+.2f' % tuple(o)
            row[name + '_residual'] = round(residual, 4)
            rounding = (not row[name + '_pass']) and (dx, dy) == (0, 0) and off == 0 and float(np.abs(o).max()) <= 2 and residual <= 1
            row[name + '_verdict'] = 'pass' if row[name + '_pass'] else 'pass (rounding)' if rounding else 'fail'
        sheet = Image.new('RGB', (r.shape[1] * 3, r.shape[0]))
        sheet.paste(Image.fromarray(r.astype(np.uint8)), (0, 0))
        sheet.paste(Image.fromarray(p.astype(np.uint8)), (r.shape[1], 0))
        sheet.paste(Image.fromarray(heat(err)), (2 * r.shape[1], 0))
        sheet.save(os.path.join(out, case['name'] + '.png'))
        rows.append(row)
        print('%-22s mean %.3f  px>1 %6d  px>8 %6d %s' % (row['case'], row['mean'], row['px_gt1'], row['px_gt8'], row['note']))
    keys = []
    for row in rows:
        keys += [k for k in row if k not in keys]
    with open(os.path.join(out, 'parity.csv'), 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    ok = [r for r in rows if r.get('status') == 'ok']
    print('%d cases, %d measured, %d with full-frame mean <= 3' % (len(rows), len(ok), sum(r['mean'] <= 3 for r in ok)))


if __name__ == '__main__':
    main()
