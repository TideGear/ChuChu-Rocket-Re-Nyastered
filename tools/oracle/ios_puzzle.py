"""Puzzle-stage differential on the iOS builds: save-tick timelines of the original code vs the C++ simulation dump (local/testdata/sim_dump.txt).
usage: ios_puzzle.py <build> <n main> <n user> [seed] [horizon]"""
import random, struct, sys, time
sys.path.insert(0, '.')
from ios_cpu_run import *
from oracle_batch import iter_stages, sim_dump
def run_stage(o, tiles, walls, counts, arrows, horizon, frame):
    stage = bytearray(380); stage[0:108] = tiles; stage[0x6c:0x6c + 237] = walls; stage[0x15c:0x160] = bytes(counts)
    g(o, 'GA_ResetGameParamStr'); g(o, 'GA_SetGameType', 3); g(o, 'GA_SetStageNum', 0, 0, 1); g(o, 'SmpTskInit')
    ptr = g(o, 'FI_GetFIPSptr', 3, 0); o.write(ptr, bytes(stage))      # original stage array slot, as in the Android harness
    g(o, 'GA_SetCharaSpeed', 0x3f800000); g(o, 'GA_OnGameFlag'); g(o, 'FI_InitFieldCollision')
    g(o, 'AR_StartArrowPzManager'); g(o, 'RO_StartRocketPzManager'); mice = g(o, 'MO_PutMousePuzzle'); g(o, 'CA_PutCatPuzzle')
    pt = o.alloc(16)
    for (x, y, d) in arrows: o.write(pt, struct.pack('<hh', x, y)); g(o, 'AR_PutArrowPzSp', pt, d)
    ticks = []; prev = 0
    for f in range(1, horizon + 1):
        g(o, 'SmpColLoopInit'); g(o, 'SmpTskExeServer'); g(o, 'SmpColAnalyze')
        v = g(o, 'MO_GetRocketMouse')
        while prev < v: ticks.append(f); prev += 1
    return ticks
if __name__ == '__main__':
    build, nmain, nuser = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]); seed = int(sys.argv[4]) if len(sys.argv) > 4 else 11; horizon = int(sys.argv[5]) if len(sys.argv) > 5 else 1500
    sd = sim_dump(); rng = random.Random(seed); stages = [s for s in iter_stages() if s[4]]
    mainl = [s for s in stages if s[0] == 0][:nmain]; userl = [s for s in stages if s[0] == 1]; rng.shuffle(userl); sample = mainl + userl[:nuser]
    same = 0; diffs = []; t0 = time.time()
    for (src, idx, tiles, walls, sol, title) in sample:
        counts = [0, 0, 0, 0]
        for (x, y, d) in sol: counts[d] += 1
        o = make(build); o.m  # fresh process image per stage keeps state clean
        for nm in ('ChuSEStopAll', 'BGM_Pause', 'BGM_Release', 'BGM_Fadeout', 'BGM_SetVolume', 'BGM_Change', 'BGM_Play', 'BGM_Stop2V', 'BGM_Stop', 'SECallForMouse', 'ChuSECall', 'vibrate', 'VS_EasyVibRo'):
            if nm in FUNCS: patch_const_ret(o, FUNCS[nm] & ~1, 0)
        init_trig(o)
        try: got = run_stage(o, tiles, walls, counts, sol, horizon, None)
        except Exception as e: diffs.append((src, idx, 'error %s' % e)); continue
        want = [t for t in sd[(src, idx)] if t <= horizon]
        if got == want: same += 1
        else: diffs.append((src, idx, len(want), len(got), want[:5], got[:5]))
    print('%s: stages %d identical %d different %d (%.0fs)' % (build, len(sample), same, len(diffs), time.time() - t0))
    for d in diffs[:8]: print('  ', d)
