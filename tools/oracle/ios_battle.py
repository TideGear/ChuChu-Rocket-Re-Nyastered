"""iOS battle harness: same scenario recording as battle_probe/make_cpu_golden, but on the iOS armv7 code (names from Ghidra's function list)."""
import os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ios_oracle import *
FUNCS = {}
def load_funcs(path):
    for l in open(path):
        p = l.split('\t')
        if len(p) >= 3: FUNCS.setdefault(p[2].strip(), int(p[0], 16))
ROOT = r'C:\Dev\ChuChu Rocket'
BUILD = {'v112': ('CCR_ios_v112', 'ios_v112'), 'hd10': ('CCR_ios_hd10', 'ios_hd10'), '102': ('CCR_ios_102', 'ios_102'), 'v11': ('CCR_ios_v11os30', 'ios_v11os30'), 'orbit': ('CCR_ios_orbit', 'ios_orbit')}
BUILD_NAME = ['v112']
def make(build='v112'):
    BUILD_NAME[0] = build; thin, dec = BUILD[build]
    FUNCS.clear(); load_funcs(r'%s\analysis\decomp\%s\%s.functions.txt' % (ROOT, dec, thin))
    o = IOSOracle(r'%s\analysis\thin\%s' % (ROOT, thin))
    for n in list(FUNCS):                                               # older builds list the same functions without the leading underscore
        if not n.startswith('_') and '_' + n not in FUNCS: FUNCS['_' + n] = FUNCS[n]
    if 'CT_Random' not in FUNCS and '__ZL9CT_Randomv' in FUNCS: FUNCS['CT_Random'] = FUNCS['__ZL9CT_Randomv']
    for alias, names in (('changeGlobalMode', ('MC_ChangeGlobalMode',)), ('GA_SetStageNum', ('GA_SetStageNumber',)), ('FI_GetFIPSptr', ('FI_GetFIPSp',))):     # names differ between builds
        if alias not in FUNCS:
            for n in names:
                if n in FUNCS: FUNCS[alias] = FUNCS[n]
    if 'FI_GetFIPSptr' not in FUNCS:                                    # tail-called by FI_GetFIPNow
        import capstone
        md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB); seg = [x for x in o.m.segs if x[0] == '__TEXT'][0]; a = FUNCS['FI_GetFIPNow'] & ~1
        for i in md.disasm(o.m.d[seg[3] + a - seg[1]: seg[3] + a - seg[1] + 24], a):
            if i.mnemonic in ('b', 'b.w'): FUNCS['FI_GetFIPSptr'] = int(i.op_str.lstrip('#'), 16)
    for n in ('__ZN4Core7vibrateEiii',):                                  # haptics: older builds write straight to a UIKit object that is not mapped; make it a no-op (return immediately)
        if n in FUNCS: o.uc.mem_write(FUNCS[n] & ~1, b'pG')
    return o
def ascii_stage(rec):
    L = [rec[r * 25:(r + 1) * 25] for r in range(19)]
    def tile(ch): return 0x11 if ch == 0x37 else 0 if ch == 0x39 else (ch - 0x40) & 0xff
    tiles = bytes(tile(L[2 * r + 1][2 * c + 1]) for r in range(9) for c in range(12))
    walls = bytearray(237)
    for i in range(10):
        for c in range(12): walls[25 * i + c] = 1 if L[2 * i][2 * c + 1] == 0x31 else 0
    for i in range(9):
        for c in range(13): walls[25 * i + 12 + c] = 1 if L[2 * i + 1][2 * c] == 0x31 else 0
    return tiles, bytes(walls)
def g(o, name, *a):
    if name == 'GA_SetStageNum' and BUILD_NAME[0] != 'v112': return 0     # older builds bump a counter through an app-global pointer; stage 0 is the default
    try: return o.call(FUNCS[name], *a)
    except Exception as e:
        print('FAILED in', name, 'pc=%#x' % o.uc.reg_read(UC_ARM_REG_PC), 'lr=%#x' % o.uc.reg_read(UC_ARM_REG_LR), e); raise
if __name__ == '__main__':
    o = make(sys.argv[1] if len(sys.argv) > 1 else 'v112')
    for n in ('GA_Reset', 'GA_SetGameType', 'GA_SetStageNum', 'SmpTskInit', 'BHLib_SeedRNG', 'GA_SetCharaSpeed', 'GA_OnGameFlag', 'FI_InitFieldCollision', 'AR_StartArrow4Manager', 'RO_StartRocket4Manager',
              'GE_StartGenerator4Manager', 'SmpColLoopInit', 'SmpTskExeServer', 'SmpColAnalyze', 'CT_StartCompThink', 'AR_PutArrow', 'SC_InitScoreBoard', 'FI_GetFIPSptr', 'njRandom', 'MO_PutMouse', 'CA_PutCat'):
        print(n, hex(FUNCS[n]) if n in FUNCS else None)
