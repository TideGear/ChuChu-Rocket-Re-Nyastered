import sys, struct
sys.path.insert(0, '.')
from ios_cpu_run import *
build, idx, seed, f0, f1 = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]); levels = [int(x) for x in sys.argv[6].split(',')]
o, puts, frame = run(build, idx, seed, f1, levels); tasks = []
a = FUNCS['CT_StartCompThink'] + 0x22 & ~1          # 0x1e216: cbz r0 (r0 = task)
def cb(uc, ad, s, u):
    t = uc.reg_read(UC_ARM_REG_R0)
    if t and t not in tasks: tasks.append(t)
o.uc.hook_add(UC_HOOK_CODE, cb, begin=a, end=a + 2)
g(o, 'changeGlobalMode', 0xc); g(o, 'GA_ResetGameParamStr'); g(o, 'GA_SetGameType', 0); g(o, 'GA_SetStageNum', 0, 0, 1); g(o, 'SmpTskInit')
g(o, '_BHLib_SeedRNG', seed); g(o, 'GA_SetCharaSpeed', 0x3f800000); g(o, 'GA_OnGameFlag'); g(o, 'FI_InitFieldCollision')
g(o, 'AR_StartArrow4Manager'); g(o, 'RO_StartRocket4Manager'); g(o, 'GE_StartGenerator4Manager'); g(o, 'SC_InitScoreBoard')
for p, lv in enumerate(levels):
    if lv >= 0: g(o, 'CT_StartCompThink', p, lv)
def dump(t):
    b = o.read(t, 0x34); return 'st=%d timer=%d flags=%#x cur=(%d,%d) pl=%d tgt=(%d,%d) dir=%d cnt=%d' % (b[0], struct.unpack_from('<i', b, 4)[0], struct.unpack_from('<I', b, 8)[0], *struct.unpack_from('<hh', b, 0x10), b[0x2c], b[0x2d], b[0x2e], b[0x2f], struct.unpack_from('<H', b, 0x30)[0])
for f in range(1, f1 + 1):
    frame[0] = f; g(o, 'SmpColLoopInit'); g(o, 'SmpTskExeServer'); g(o, 'SmpColAnalyze')
    if f >= f0:
        for t in tasks: print('f%d' % f, dump(t))
