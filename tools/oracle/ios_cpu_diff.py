"""Differential test: iOS build vs the Android goldens (CASE idx seed frames l0 l1 l2 l3 n / P frame player x y dir).
usage: ios_cpu_diff.py <build> <golden file> [first case] [count]"""
import sys, time
sys.path.insert(0, '.')
from ios_cpu_run import *
build, gold = sys.argv[1], sys.argv[2]
first = int(sys.argv[3]) if len(sys.argv) > 3 else 0; count = int(sys.argv[4]) if len(sys.argv) > 4 else 10**9
cases = []; cur = None
for l in open(gold):
    k = l.split()
    if not k: continue
    if k[0] == 'CASE': cur = dict(idx=int(k[1]), seed=int(k[2]), frames=int(k[3]), levels=[int(x) for x in k[4:8]], want=[]); cases.append(cur)
    elif k[0] == 'P': cur['want'].append(tuple(int(x) for x in k[1:6]))
ok = 0; tot = 0
for c in cases[first:first + count]:
    t0 = time.time()
    o, puts, frame = run(build, c['idx'], c['seed'], c['frames'], c['levels'])
    g(o, 'changeGlobalMode', 0xc); g(o, 'GA_ResetGameParamStr'); g(o, 'GA_SetGameType', 0); g(o, 'GA_SetStageNum', 0, 0, 1); g(o, 'SmpTskInit')
    g(o, '_BHLib_SeedRNG', c['seed']); g(o, 'GA_SetCharaSpeed', 0x3f800000); g(o, 'GA_OnGameFlag'); g(o, 'FI_InitFieldCollision')
    g(o, 'AR_StartArrow4Manager'); g(o, 'RO_StartRocket4Manager'); g(o, 'GE_StartGenerator4Manager'); g(o, 'SC_InitScoreBoard')
    for p, lv in enumerate(c['levels']):
        if lv >= 0: g(o, 'CT_StartCompThink', p, lv)
    for f in range(1, c['frames'] + 1):
        frame[0] = f
        try: g(o, 'SmpColLoopInit'); g(o, 'SmpTskExeServer'); g(o, 'SmpColAnalyze')
        except Exception: print('failed at frame', f); raise
    ev = []
    for p in puts:
        if not ev or ev[-1] != p: ev.append(p)
    m = 0
    while m < len(ev) and m < len(c['want']) and ev[m] == c['want'][m]: m += 1
    same = m == len(ev) == len(c['want']); tot += 1; ok += same
    print('case stage %d seed %d levels %s: %s matched %d/%d (iOS %d) %.0fs' % (c['idx'], c['seed'], c['levels'], 'IDENTICAL' if same else 'DIFF', m, len(c['want']), len(ev), time.time() - t0)
          + ('' if same or m >= len(ev) or m >= len(c['want']) else ' first: want %s got %s' % (c['want'][m], ev[m])), flush=True)
print('identical %d of %d' % (ok, tot))
