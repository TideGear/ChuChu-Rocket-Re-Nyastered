"""Record CPU-player arrow placements of the iOS build for a (stage, seed, levels) case, in the make_cpu_golden.py format."""
import os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ios_battle as B
from ios_battle import *
from unicorn import UC_HOOK_CODE

def patch_const_ret(o, addr, value):
    """Overwrite a function with: return <value> (thumb: ldr r0,[pc,#k]; bx lr; .word value)"""
    lit = (addr + 4 + 3) & ~3 if (addr + 4) % 4 else addr + 4
    imm = (lit - ((addr + 4) & ~3)) // 4
    o.write(addr, struct.pack('<HH', 0x4800 | imm, 0x4770))
    o.write(lit, struct.pack('<I', value))

def trig_slots(o):
    import capstone
    md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB); out = []
    seg = [x for x in o.m.segs if x[0] == '__TEXT'][0]
    for nm in ('njSin', 'njCos'):
        a = FUNCS[nm] & ~1; code = o.m.d[seg[3] + a - seg[1]: seg[3] + a - seg[1] + 24]; lit = add = None
        for i in md.disasm(code, a):
            if i.mnemonic.startswith('ldr') and 'pc' in i.op_str and lit is None:
                imm = int(i.op_str.split('#')[1].rstrip(']'), 0); lit = ((i.address + 4) & ~3) + imm
            if i.mnemonic == 'add' and i.op_str.endswith('pc') and add is None: add = i.address + 4
        out.append((o.u32(lit) + add, True) if add is not None else (o.u32(lit), False))      # (address, is pointer slot); non-PIC (HD): the literal IS the table address
    return out

def init_trig(o):
    import math
    for (slot, is_ptr), fn in zip(trig_slots(o), (math.sin, math.cos)):
        data = b''.join(struct.pack('<f', fn(i * 2 * math.pi / 65536)) for i in range(65536))
        if is_ptr: tbl = o.alloc(65536 * 4); o.write(tbl, data); o.write(slot, struct.pack('<I', tbl))
        else: o.write(slot, data)

def init_trig_old(o, sin_lit=0x4970c, sin_add=0x49704, cos_lit=0x49720, cos_add=0x49718):
    import math
    for lit, add, fn in ((sin_lit, sin_add, math.sin), (cos_lit, cos_add, math.cos)):
        slot = o.u32(lit) + add
        tbl = o.alloc(65536 * 4); o.write(tbl, b''.join(struct.pack('<f', fn(i * 2 * math.pi / 65536)) for i in range(65536))); o.write(slot, struct.pack('<I', tbl))

def run(build, idx, seed, frames, levels, stages_file=r'C:\Dev\ChuChu Rocket\analysis\extracted\dc_files\ENGLISH\BTSTAGE25.DAT'):
    o = make(build)
    d = open(stages_file, 'rb').read(); tiles, walls = ascii_stage(d[idx * 477:idx * 477 + 475])
    st = bytearray(0x15c); st[0:108] = tiles; st[0x6c:0x6c + 237] = walls
    buf = o.alloc(0x400); o.write(buf, bytes(st))
    patch_const_ret(o, FUNCS['FI_GetFIPSptr'], buf)
    init_trig(o)
    for nm in ('ChuSEStopAll', 'BGM_Pause', 'BGM_Release', 'BGM_Fadeout', 'BGM_SetVolume', 'BGM_Change', 'BGM_Play', 'BGM_Stop2V', 'BGM_Stop', 'SECallForMouse', 'ChuSECall', 'vibrate', 'VS_EasyVibRo'):
        if nm in FUNCS: patch_const_ret(o, FUNCS[nm] & ~1, 0)        # sound/vibration entry points (as in the Android harness)
    puts = []; frame = [0]
    def cb(uc, a, s, u):
        pl = uc.reg_read(UC_ARM_REG_R0); p = uc.reg_read(UC_ARM_REG_R1); dd = uc.reg_read(UC_ARM_REG_R2)
        x, y = struct.unpack('<hh', o.read(p, 4)); puts.append((frame[0], pl, x, y, dd & 0xff))
    o.uc.hook_add(UC_HOOK_CODE, cb, begin=FUNCS['AR_PutArrow'] & ~1, end=(FUNCS['AR_PutArrow'] & ~1) + 2)
    return o, puts, frame
if __name__ == '__main__':
    build, idx, seed, frames = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
    levels = [int(x) for x in sys.argv[5].split(',')]
    o, puts, frame = run(build, idx, seed, frames, levels)
    print('setup...')
    g(o, 'changeGlobalMode', 0xc); g(o, 'GA_ResetGameParamStr'); g(o, 'GA_SetGameType', 0); g(o, 'GA_SetStageNum', 0, 0, 1); g(o, 'SmpTskInit')
    g(o, '_BHLib_SeedRNG', seed); g(o, 'GA_SetCharaSpeed', 0x3f800000); g(o, 'GA_OnGameFlag'); g(o, 'FI_InitFieldCollision')
    g(o, 'AR_StartArrow4Manager'); g(o, 'RO_StartRocket4Manager'); g(o, 'GE_StartGenerator4Manager'); g(o, 'SC_InitScoreBoard')
    for p, lv in enumerate(levels):
        if lv >= 0: g(o, 'CT_StartCompThink', p, lv)
    print('frames...')
    for f in range(1, frames + 1):
        frame[0] = f
        g(o, 'SmpColLoopInit'); g(o, 'SmpTskExeServer'); g(o, 'SmpColAnalyze')
    ev = []
    for p in puts:
        if not ev or ev[-1] != p: ev.append(p)
    print(len(ev), 'placements', ev[:8]); print('unhandled', o.unhandled)
