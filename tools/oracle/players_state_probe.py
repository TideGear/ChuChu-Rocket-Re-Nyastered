"""Ground truth for PlayerSelectScreen::process states 0x26 / 0x27 (HD 1.0 0x34de4; read in docs/roadmap.md 2026-11-14).
process(float dt) takes dt in r1 (vmov s16, r1). Per call it prints the requested screen the original writes (+0x658, unchanged = 0),
the precalcTextures(r0, r2) calls, the texture removal/put calls on the split flag +0xa7d, and the fade timer +0xa38 after the call.
Prerequisites as in settings_press_inited.py (field grids, playfields, texture spaces, constructor).
Usage: py -3 players_state_probe.py [--grid]"""
import os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hd_env
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import *
PROCESS, PRECALC, REMOVE, PUT = 0x34de4, 0x19d38, 0xd2bc, 0xcff0
env = hd_env.make(); o = env.o
hd_env.place_stage_select(env)
o.call(0x15928, 0); o.call(0x1ac88)
scr = env.alloc(0xe00); o.call(0x34a00, scr)
o.write(scr + 0xa7c, bytes([0])); o.write(scr + 0xd35, bytes([0]))
calls = []
FLAG = env.alloc(16); o.write(0xeb450, struct.pack('<I', FLAG))   # the flag cell the app sets up at start
def stub(name):
    def h(uc, a, s, u):   # record the arguments and return to the caller without running the function
        calls.append((name, uc.reg_read(UC_ARM_REG_R0), uc.reg_read(UC_ARM_REG_R1), uc.reg_read(UC_ARM_REG_R2)))
        uc.reg_write(UC_ARM_REG_R0, 1 if name == 'put' else 0); uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
    return h
o.uc.hook_add(UC_HOOK_CODE, stub('precalc'), begin=PRECALC, end=PRECALC + 2)
o.uc.hook_add(UC_HOOK_CODE, stub('remove'), begin=REMOVE, end=REMOVE + 2)
o.uc.hook_add(UC_HOOK_CODE, stub('put'), begin=PUT, end=PUT + 2)
CHANGE, SONG, PPANE, SPANE = 0xbcc4, 0xc9b4, 0x32bbc, 0x32b1c
def stub_change(uc, a, s, u):   # changeGameState(app, state): record it and store the state the way the game does (+0x668, timer +0x66c cleared)
    calls.append(('change', uc.reg_read(UC_ARM_REG_R0), uc.reg_read(UC_ARM_REG_R1), 0))
    uc.mem_write(env.appdata + 0x668, struct.pack('<I', uc.reg_read(UC_ARM_REG_R1))); uc.mem_write(env.appdata + 0x66c, struct.pack('<I', 0))
    uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
o.uc.hook_add(UC_HOOK_CODE, stub_change, begin=CHANGE, end=CHANGE + 2)
o.uc.hook_add(UC_HOOK_CODE, stub('song'), begin=SONG, end=SONG + 2)
o.uc.hook_add(UC_HOOK_CODE, stub('ppane'), begin=PPANE, end=PPANE + 2)
o.uc.hook_add(UC_HOOK_CODE, stub('spane'), begin=SPANE, end=SPANE + 2)
def f2u(x): return struct.unpack('<I', struct.pack('<f', x))[0]
def run(state, a3c, a40, tim=0, net=0, split=0, dt=1.0 / 60, fade=0.0):
    ad = env.appdata
    o.write(ad + 0x668, struct.pack('<I', state)); o.write(ad + 0x658, struct.pack('<I', 0)); o.write(ad + 0x66c, struct.pack('<I', tim))
    netflag = FLAG   # process: ldr r3,[0xeb450]; ldr r0,[r3]; ldrb r5,[r0]: global 0xeb450 holds the address of the network flag byte
    o.write(netflag, bytes([net])); o.write(scr + 0xa7d, bytes([split]))
    o.write(scr + 0xa3c, bytes([a3c])); o.write(scr + 0xa40, struct.pack('<I', a40)); o.write(scr + 0xa38, struct.pack('<f', fade))
    del calls[:]
    o.call(PROCESS, scr, f2u(dt))
    req = struct.unpack('<I', bytes(o.read(ad + 0x658, 4)))[0]
    fade_after = struct.unpack('<f', bytes(o.read(scr + 0xa38, 4)))[0]
    return req, list(calls), fade_after
def line(st, tim, a3c, a40, net, split, dt, fade):
    req, cl, fa = run(st, a3c, a40, tim, net, split, dt, fade)
    ops = ';'.join(('precalc(%d,%d)' % (r0, r2)) if n == 'precalc' else ('change(%d)' % r1 if n == 'change' else ('song(%d)' % r1 if n == 'song' else ('%s(%d,%d)' % (n, r1, r2)))) for n, r0, r1, r2 in cl)   # remove/put: texture id r1, value r2
    return '%#x t%d a3c%d a40=%d net%d split%d dt%.4f fade%.1f -> req=%d ops=[%s] fade=%.4f' % (st, tim, a3c, a40, net, split, dt, fade, req, ops, fa)
def grid():
    out = []
    for st in (0x26, 0x27):
        for tim in (3, 5):
            for a3c in (0, 1):
                for a40 in (0, 1, 2):
                    for net in (0, 1):
                        for split in (0, 1):
                            out.append(line(st, tim, a3c, a40, net, split, 1.0, 499999.5 if st == 0x26 else 0.0))
                            out.append(line(st, tim, a3c, a40, net, split, 1.0 / 60, 0.5))
    return out
def grid24():
    out = []
    for dt in (1.0, 1.0 / 60):
        for fade0 in (0.0, 0.5, 1.5):
            req, cl, fa = run(0x24, 0, 0, 0, 0, 0, dt, fade0)
            ops = ';'.join('%s(%d)' % (n, r1) for n, r0, r1, r2 in cl)
            out.append('0x24 dt%.4f fade%.1f -> req=%d ops=[%s] fade=%.4f' % (dt, fade0, req, ops, fa))
    for a44 in (0, 1, 2):
        o.write(scr + 0xa44, struct.pack('<I', a44))
        req, cl, fa = run(0x25, 0, 0, 0, 0, 0, 1.0 / 60, 0.0)
        ops = ';'.join('%s' % n for n, r0, r1, r2 in cl)
        out.append('0x25 a44=%d -> req=%d ops=[%s]' % (a44, req, ops))
    return out
if __name__ == '__main__':
    if '--grid24' in sys.argv: print('\n'.join(grid24()))
    elif '--grid' in sys.argv: print('\n'.join(grid()))
    else:
        for l in grid()[:4]: print(l)
