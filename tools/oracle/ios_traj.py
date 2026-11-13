import sys, struct
sys.path.insert(0, '.')
from ios_cpu_run import *
build, idx, seed, upto, outp = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]; levels = [int(x) for x in sys.argv[6].split(',')] if len(sys.argv) > 6 else []
o, puts, frame = run(build, idx, seed, upto, levels); ids = {}; rows = []
a = FUNCS['FI_CheckWarp'] & ~1
def cb(uc, ad, s, u):
    r0 = uc.reg_read(UC_ARM_REG_R0)
    try: x, _, z = struct.unpack('<fff', o.read(r0, 12))
    except Exception: return
    k = ids.setdefault(r0, len(ids)); rows.append((frame[0], k, x, z))
o.uc.hook_add(UC_HOOK_CODE, cb, begin=a, end=a + 2)
g(o, 'changeGlobalMode', 0xc); g(o, 'GA_ResetGameParamStr'); g(o, 'GA_SetGameType', 0); g(o, 'GA_SetStageNum', 0, 0, 1); g(o, 'SmpTskInit')
g(o, '_BHLib_SeedRNG', seed); g(o, 'GA_SetCharaSpeed', 0x3f800000); g(o, 'GA_OnGameFlag'); g(o, 'FI_InitFieldCollision')
g(o, 'AR_StartArrow4Manager'); g(o, 'RO_StartRocket4Manager'); g(o, 'GE_StartGenerator4Manager'); g(o, 'SC_InitScoreBoard')
for p, lv in enumerate(levels):
    if lv >= 0: g(o, 'CT_StartCompThink', p, lv)
for f in range(1, upto + 1):
    frame[0] = f; g(o, 'SmpColLoopInit'); g(o, 'SmpTskExeServer'); g(o, 'SmpColAnalyze')
with open(outp, 'w') as fo:
    for r in rows: fo.write('%d %d %.3f %.3f\n' % r)
print(len(ids), 'entities', len(rows), 'rows')
