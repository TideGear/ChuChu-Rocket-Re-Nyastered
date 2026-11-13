"""Differential test of whole puzzle stages: original code (emulated) vs the C++ simulation's dump (save ticks)."""
import struct, sys, time, random
sys.path.insert(0, '.')
import full_stage as F
from full_stage import *
def iter_stages(path=r'C:\Dev\ChuChu Rocket\local\testdata\gba_stages.bin'):
    f = open(path, 'rb'); n, = struct.unpack('<I', f.read(4))
    for i in range(n):
        s, nsol, idx = struct.unpack('<BBH', f.read(4)); tiles = f.read(108); walls = f.read(237); sol = [tuple(f.read(3)) for _ in range(nsol)]; title = f.read(32).rstrip(b'\0')
        yield s, idx, tiles, walls, sol, title
def sim_dump(path=r'C:\Dev\ChuChu Rocket\local\testdata\sim_dump.txt'):
    d = {}
    for line in open(path):
        if not line.startswith('STAGE'): continue
        head, _, rest = line.partition(':'); _, src, idx, n = head.split()
        d[(int(src), int(idx))] = [int(x) for x in rest.split()]
    return d
def oracle_saves(tiles, walls, sol, horizon):
    counts = [0, 0, 0, 0]
    for (x, y, d) in sol: counts[d] += 1
    series = []
    orig = F.gcall
    def patched(ga, *a):
        r = orig(ga, *a)
        if ga == 0x34e54: series.append(r)
        return r
    F.gcall = patched
    try: res = run_stage(tiles, walls, counts, sol, frames=horizon)
    finally: F.gcall = orig
    ticks = []; prev = 0
    for i, v in enumerate(series):
        while prev < v: ticks.append(i + 1); prev += 1
    return ticks, res
if __name__ == '__main__':
    horizon = int(sys.argv[1]); nmain = int(sys.argv[2]); nuser = int(sys.argv[3]); seed = int(sys.argv[4]) if len(sys.argv) > 4 else 1
    sd = sim_dump(); rng = random.Random(seed)
    stages = [s for s in iter_stages() if s[4]]
    mainl = [s for s in stages if s[0] == 0][:nmain]; userl = [s for s in stages if s[0] == 1]; rng.shuffle(userl)
    sample = mainl + userl[:nuser]
    if len(sys.argv) > 6: sample = sample[int(sys.argv[5]):int(sys.argv[5]) + int(sys.argv[6])]   # chunking: fresh process per chunk avoids emulator resource exhaustion
    same = 0; diffs = []; errors = []; t0 = time.time()
    for (src, idx, tiles, walls, sol, title) in sample:
        want = [t for t in sd[(src, idx)] if t <= horizon]
        try:
            got, res = oracle_saves(tiles, walls, sol, horizon)
        except BaseException as e:
            errors.append((src, idx, str(e)[:60])); continue
        got = [t for t in got if t <= horizon]
        if got == want: same += 1
        else: diffs.append((src, idx, title.decode('latin1'), len(want), len(got), want[:6], got[:6]))
    print('stages compared %d identical %d different %d emulation-errors %d (%.0fs)' % (len(sample), same, len(diffs), len(errors), time.time() - t0))
    for e in errors[:5]: print('  error', e)
    for d in diffs[:12]: print('  src %d idx %d %r: sim saved %d, original saved %d | sim %s | orig %s' % d)
