import sys, struct
sys.path.insert(0, '.')
from ios_cpu_run import *
def heat_addr(o): return (o.u32(0x132b4) + 0x13260) & 0xffffffff
if __name__ == '__main__':
    build, idx, seed, upto = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]); levels = [int(x) for x in sys.argv[5].split(',')]
    o, puts, frame = run(build, idx, seed, upto, levels)
    g(o, 'changeGlobalMode', 0xc); g(o, 'GA_ResetGameParamStr'); g(o, 'GA_SetGameType', 0); g(o, 'GA_SetStageNum', 0, 0, 1); g(o, 'SmpTskInit')
    g(o, '_BHLib_SeedRNG', seed); g(o, 'GA_SetCharaSpeed', 0x3f800000); g(o, 'GA_OnGameFlag'); g(o, 'FI_InitFieldCollision')
    g(o, 'AR_StartArrow4Manager'); g(o, 'RO_StartRocket4Manager'); g(o, 'GE_StartGenerator4Manager'); g(o, 'SC_InitScoreBoard')
    for p, lv in enumerate(levels):
        if lv >= 0: g(o, 'CT_StartCompThink', p, lv)
    ha = heat_addr(o); print('heat array at', hex(ha))
    for f in range(1, upto + 1):
        frame[0] = f; g(o, 'SmpColLoopInit'); g(o, 'SmpTskExeServer'); g(o, 'SmpColAnalyze')
    h = struct.unpack('<108h', o.read(ha, 216))
    for y in range(9): print(''.join('%5d' % h[y * 12 + x] for x in range(12)))
