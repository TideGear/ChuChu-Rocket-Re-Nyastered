import sys, struct
sys.path.insert(0, '.')
from ios_cpu_run import *
idx, seed, frames = int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
o, puts, frame = run(sys.argv[1], idx, seed, frames, [])
sp = []
def hk(name, kind):
    a = FUNCS[name] & ~1
    def cb(uc, ad, s, u):
        p = uc.reg_read(UC_ARM_REG_R0); x, y = struct.unpack('<hh', o.read(p, 4))
        sp.append((frame[0], kind, x, y, uc.reg_read(UC_ARM_REG_R1) & 3, uc.reg_read(UC_ARM_REG_R2) & 0xff if kind == 'mouse' else 0))
    o.uc.hook_add(UC_HOOK_CODE, cb, begin=a, end=a + 2)
hk('MO_PutMouse', 'mouse'); hk('CA_PutCat', 'cat')
g(o, 'changeGlobalMode', 0xc); g(o, 'GA_ResetGameParamStr'); g(o, 'GA_SetGameType', 0); g(o, 'GA_SetStageNum', 0, 0, 1); g(o, 'SmpTskInit')
g(o, '_BHLib_SeedRNG', seed); g(o, 'GA_SetCharaSpeed', 0x3f800000); g(o, 'GA_OnGameFlag'); g(o, 'FI_InitFieldCollision')
g(o, 'AR_StartArrow4Manager'); g(o, 'RO_StartRocket4Manager'); g(o, 'GE_StartGenerator4Manager')
for f in range(1, frames + 1):
    frame[0] = f; g(o, 'SmpColLoopInit'); g(o, 'SmpTskExeServer'); g(o, 'SmpColAnalyze')
ev = []
for s in sp:
    if not ev or ev[-1] != s: ev.append(s)
print(len(ev), ev[:10])
