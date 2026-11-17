"""Run the original Android ChallengeLoop (0x30388) for one Challenge stage with no input and log the mode block phase changes.
usage: challenge_probe.py <stage 0-24> [frames]
The mode block is at ghidra 0x17b614 (+0xc = phase); ChallengeInit (0x30a6c) clears it. The screen's process calls ChallengeLoop once per frame."""
import struct, sys
sys.path.insert(0, '.')
from cat_probe import *
init_tables()
BX_LR = b'\x70\x47'
for ga in (0x3d434, 0x3d438, 0x3d444, 0x3d448, 0x3d44c, 0x3d450, 0x3d454, 0x3d458, 0x3d45c, 0x3d464, 0x3d480, 0x3d49c, 0x3d4b4, 0x3d4cc, 0x3d4e4, 0x3d508,
           0x69b04, 0x69b0c, 0x69b18, 0x69b3c, 0x69b48, 0x69b54, 0x69b60, 0x69b74, 0x2bb28, 0x383c0):          # sound/BGM entry points call into JNI: no-ops
    o.write(BASE + ga - G, BX_LR)
MB = 0x17b614
PATCHES = 'challenge_patches.txt'   # render/sound/draw functions the harness stubs (one ghidra address per line); a fault appends one and exits with status 3 so the caller re-runs (Unicorn caches translated blocks, so patches must be in place before execution)
import os
if os.path.exists(PATCHES):
    for line in open(PATCHES):
        if line.strip():
            o.write(BASE + int(line, 16) - G, BX_LR)


def block(n=16):
    return struct.unpack('<%di' % n, o.read(BASE + MB - G, 4 * n))


FUNCS = []
for line in open('../../analysis/decomp/android_arm/libccrjni.so.functions.txt', encoding='utf8'):
    parts = line.split()
    if len(parts) >= 3:
        try: FUNCS.append((int(parts[0], 16), parts[2]))
        except ValueError: pass


def func_at(ga):
    best = None
    for a, n in FUNCS:
        if a <= ga: best = (a, n)
    return best


def main(stage, frames):
    run(stage, frames)


def run(stage, frames):
    gcall(0x30a6c)                                  # ChallengeInit: GA_Reset, game type 2, mode 0xe, clears the block
    from battle_probe import ascii_stage
    d = open('../../analysis/extracted/dc_files/ENGLISH/CHSTAGE25.DAT', 'rb').read()
    tiles, walls = ascii_stage(d[stage * 477:stage * 477 + 475])
    st = bytearray(380); st[0:108] = tiles; st[0x6c:0x6c + 237] = walls
    o.write(gcall(0x2ddd0, 2, stage), bytes(st))    # FI_GetFIPSptr(2, stage): the challenge stage array
    gcall(0x2ed7c, stage, 0, 1)
    if os.environ.get('SEED'): gcall(0x25660, int(os.environ['SEED']))   # BHLib_SeedRNG: a fixed random stream so a port run can be compared                     # GA_SetStageNum(level, stage, flag): stored at +4 / +8 of the game parameter block
    last = None
    if os.environ.get('CALLS'):   # log the named functions entered during frame 0 (the set-up phase)
        names = {a: n for a, n in FUNCS}
        seen = []

        def hk(uc, a, sz, u):
            ga = a - BASE + G
            if ga in names and (not seen or seen[-1] != names[ga]):
                seen.append(names[ga])
        from unicorn import UC_HOOK_CODE
        o.uc.hook_add(UC_HOOK_CODE, hk, begin=BASE, end=BASE + 0x90000)
        gcall(0x30388)
        print('CALLS', ' > '.join(seen))
        return
    if os.environ.get('MPOS'):   # MPOS=lo,hi (ticks): positions of every mouse task at the entry of MO_MouseExe (0x3501c), tick = frame - 469
        mlo, mhi = [int(v) for v in os.environ['MPOS'].split(',')]
        from unicorn import UC_HOOK_CODE as _H
        def mcb(uc, a_, sz, u):
            t = cur_frame[0] - 469
            if mlo <= t <= mhi:
                pr = uc.reg_read(UC_ARM_REG_R0); x, z = struct.unpack('<ff', o.read(pr + 0x14, 4) + o.read(pr + 0x1c, 4)); print('MPOS t%d %.3f %.3f' % (t, x, z))
        cur_frame = [0]
        o.uc.hook_add(_H, mcb, begin=BASE + 0x3501c - G, end=BASE + 0x3501c - G + 2)
    else:
        cur_frame = [0]
    if os.environ.get('COMPSEED'):   # CT_StartCompThink (0x29d50): player, level and the value read by 0x2ef3c (the seed of the computer player's generator)
        from unicorn import UC_HOOK_CODE as _HS
        def scb(uc, a_, sz, u): print('COMPSEED r0 %#x r5(player) %d r6(level) %d f%d' % (uc.reg_read(UC_ARM_REG_R0), uc.reg_read(UC_ARM_REG_R5), uc.reg_read(UC_ARM_REG_R6), cur_frame[0]))
        o.uc.hook_add(_HS, scb, begin=BASE + 0x29d5a - G, end=BASE + 0x29d5a - G + 2)
    if os.environ.get('TRACKARR'):   # every call of the arrow placement function 0x286ac: frame, player, cell, direction (each call is seen twice)
        from unicorn import UC_HOOK_CODE as _HA
        def acb(uc, a_, sz, u):
            pr = uc.reg_read(UC_ARM_REG_R1); x, y = struct.unpack('<hh', o.read(pr, 4))
            print('ARRPUT f%d player %d cell %d %d dir %d' % (cur_frame[0], uc.reg_read(UC_ARM_REG_R0), x, y, uc.reg_read(UC_ARM_REG_R2)))
        o.uc.hook_add(_HA, acb, begin=BASE + 0x286ac - G, end=BASE + 0x286ac - G + 2)
    if os.environ.get('CPOS'):   # CPOS=lo,hi (ticks): cat positions at the entry of the cat task function (FUN_00028ffc)
        clo, chi = [int(v) for v in os.environ['CPOS'].split(',')]
        from unicorn import UC_HOOK_CODE as _HC2
        def ccb(uc, a_, sz, u):
            t = cur_frame[0] - 469
            if clo <= t <= chi:
                pr = uc.reg_read(UC_ARM_REG_R0); x, z = struct.unpack('<ff', o.read(pr + 0x14, 4) + o.read(pr + 0x1c, 4)); print('CPOS t%d %.3f %.3f' % (t, x, z))
        o.uc.hook_add(_HC2, ccb, begin=BASE + 0x28ffc - G, end=BASE + 0x28ffc - G + 2)
    if os.environ.get('EXEFUNCS'):   # SmpTskSetExe (0x3db88) arguments from CA_PutCat and the mouse creation: which task function each kind of task runs
        from unicorn import UC_HOOK_CODE as _HX
        seen_exe = set()
        def xcb(uc, a_, sz, u):
            r1 = uc.reg_read(UC_ARM_REG_R1); lr = uc.reg_read(UC_ARM_REG_LR) - BASE + G
            if (r1, lr) not in seen_exe and len(seen_exe) < 40:
                seen_exe.add((r1, lr)); print('EXE func %#x caller %#x' % (r1 - BASE + G, lr))
        o.uc.hook_add(_HX, xcb, begin=BASE + 0x3db88 - G, end=BASE + 0x3db88 - G + 2)
    if os.environ.get('FORCE'):   # FORCE=<0-7>: the roulette selector (FUN_0003c2bc) returns this outcome, as make_battle_forced_golden.py
        from unicorn import UC_HOOK_CODE as _HF
        def fcb(uc, a_, sz, u): uc.reg_write(UC_ARM_REG_R0, int(os.environ['FORCE'])); uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
        o.uc.hook_add(_HF, fcb, begin=BASE + 0x3c2bc - G, end=BASE + 0x3c2bc - G + 2)
    if os.environ.get('RNGDRAWS'):   # per-frame count of BHLib_GetRandomNumber calls, printed when it changes: 'RNG f<frame> <n>'
        from unicorn import UC_HOOK_CODE as _HR
        rngc = [0]
        def rcb(uc, a_, sz, u):
            rngc[0] += 1
            if os.environ.get('RNGCALLERS') and globals().get('_curf') in (995, 996): print('RNGCALL f%d lr %#x' % (globals()['_curf'], uc.reg_read(UC_ARM_REG_LR) - BASE + G))
        o.uc.hook_add(_HR, rcb, begin=BASE + 0x360a8 - G, end=BASE + 0x360a8 - G + 2)
        globals()['_rngc'] = rngc
    if os.environ.get('TRACKCPU'):   # TRACKCPU=lo,hi frames: computer think task state at each entry of FUN_00029fa8: player, state, timer, cursor (x,y), target (x,y), dir
        clo_, chi_ = [int(v) for v in os.environ['TRACKCPU'].split(',')]
        from unicorn import UC_HOOK_CODE as _HK
        def kcb(uc, a_, sz, u):
            f_ = globals().get('_curf', 0)
            if clo_ <= f_ <= chi_:
                r0 = uc.reg_read(UC_ARM_REG_R0); raw = o.read(r0, 0x34)
                print('CPU f%d p%d state %d timer %d flags %#x cur %d,%d tgt %d,%d dir %d' % (f_, raw[0x2c], struct.unpack_from('<i', raw, 0)[0] & 0xff, struct.unpack_from('<i', raw, 4)[0], struct.unpack_from('<I', raw, 8)[0], struct.unpack_from('<h', raw, 0x10)[0], struct.unpack_from('<h', raw, 0x12)[0], raw[0x2d], raw[0x2e], raw[0x2f]))
        o.uc.hook_add(_HK, kcb, begin=BASE + 0x29fa8 - G, end=BASE + 0x29fa8 - G + 2)
    if os.environ.get('TASKFLAGS'):   # the char ID byte (task + 2) and the exec function of every task the server visits, for the frame window lo,hi
        tlo, thi = [int(v) for v in os.environ['TASKFLAGS'].split(',')]
        from unicorn import UC_HOOK_CODE as _HT
        seen_t = {}
        def tcb(uc, a_, sz, u):
            f_ = globals().get('_curf', 0)
            if tlo <= f_ <= thi:
                r4 = uc.reg_read(UC_ARM_REG_R4); fn = struct.unpack('<I', o.read(r4 + 0x40, 4))[0] - BASE + G; fl = uc.reg_read(UC_ARM_REG_R2) & 0xff
                seen_t[(fn, fl)] = seen_t.get((fn, fl), 0) + 1
        o.uc.hook_add(_HT, tcb, begin=BASE + 0x3d9c4 - G, end=BASE + 0x3d9c4 - G + 2)
        globals()['_seen_t'] = seen_t
    if os.environ.get('TRACKPUT'):   # MO_PutMouse (0x34ee4) and CA_PutCat (0x28f14): frame, kind, cell, heading, type (each call is seen twice)
        from unicorn import UC_HOOK_CODE as _HP
        def pcb(kind):
            def cb(uc, a_, sz, u):
                pr = uc.reg_read(UC_ARM_REG_R0); x, y = struct.unpack('<hh', o.read(pr, 4))
                print('PUT f%d %s %d %d d%d t%d' % (cur_frame[0], kind, x, y, uc.reg_read(UC_ARM_REG_R1) & 3, uc.reg_read(UC_ARM_REG_R2) & 0xff))
            return cb
        o.uc.hook_add(_HP, pcb('mouse'), begin=BASE + 0x34ee4 - G, end=BASE + 0x34ee4 - G + 2)
        o.uc.hook_add(_HP, pcb('cat'), begin=BASE + 0x28f14 - G, end=BASE + 0x28f14 - G + 2)
    if os.environ.get('TRACKUP'):   # log GE_MouseCountUp (0x34a6c) calls: frame and mouse type (each call is seen twice)
        from unicorn import UC_HOOK_CODE as _HU
        def ucb(uc, a_, sz, u): print('UP f%d type %d' % (cur_frame[0], uc.reg_read(UC_ARM_REG_R0)))
        o.uc.hook_add(_HU, ucb, begin=BASE + 0x34a6c - G, end=BASE + 0x34a6c - G + 2)
    if os.environ.get('HOOKCLEAR'):   # log the arguments of Data::clearChallenge (0x3e894) and return
        from unicorn import UC_HOOK_CODE as _HC
        def hcb(uc, a_, sz, u):
            print('CLEAR stage %d bcd %#x at frame %d' % (uc.reg_read(UC_ARM_REG_R0), uc.reg_read(UC_ARM_REG_R1), cur_frame[0]))
            uc.reg_write(UC_ARM_REG_R0, 1); uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
        o.uc.hook_add(_HC, hcb, begin=BASE + 0x3e894 - G, end=BASE + 0x3e894 - G + 2)
    for f in range(frames):
        cur_frame[0] = f; globals()["_curf"] = f
        try:
            gcall(0x30388)                          # ChallengeLoop
        except Exception as e:
            pc = o.uc.reg_read(UC_ARM_REG_PC) - BASE + G
            fn = func_at(pc)
            print('FAILED at frame', f, e, 'pc ghidra %#x in %s' % (pc, fn))
            if fn and any(k in fn[1].lower() for k in ('render', 'draw', 'deform', 'sound', 'bgm', 'texture', 'model', 'effect')):
                open(PATCHES, 'a').write('%x\n' % fn[0])
                raise SystemExit(3)
            return
        if os.environ.get('ARROWS') and f >= 480 and (f - 480) % 40 == 0:   # scripted arrows for player 0 (battle arrow manager, as battle_probe.py): k-th arrow at cell ((7k+3) mod 12, (5k+1) mod 9), direction k mod 4
            k = (f - 480) // 40
            pt = o.heap_ptr; o.heap_ptr += 16
            if os.environ['ARROWS'] == '1':
                x_, y_, d_ = (7 * k + 3) % 12, (5 * k + 1) % 9, k % 4
            else:   # ARROWS=<seed>: the hashed schedule shared with challenge_battle_test
                h_ = ((int(os.environ['ARROWS']) * 1000003 + k * 7919) * 2654435761) & 0xffffffff
                x_, y_, d_ = h_ % 12, (h_ >> 8) % 9, (h_ >> 16) % 4
            o.write(pt, struct.pack('<hh', x_, y_)); gcall(0x286ac, 0, pt, d_)
        if os.environ.get('ARRSLOTS') and int(os.environ['ARRSLOTS'].split(',')[0]) <= f <= int(os.environ['ARRSLOTS'].split(',')[1]):   # ARRSLOTS=lo,hi: the arrow ring of players 0..3 (FUN_0002859c): ring index and per slot (ttl, x, y)
            t_ = (lit(0x286a8) + 0x28614 - G) & 0xffffffff
            for pl_ in range(4):
                P_ = BASE + t_ + pl_ * 0x4c; ring_ = o.read(P_ + 0x2d, 1)[0]
                sl_ = [(struct.unpack('<i', o.read(P_ + i * 0x18 + 0x34, 4))[0], struct.unpack('<hh', o.read(P_ + i * 0x18 + 0x38, 4))) for i in range(3)]
                print('RING f%d p%d idx %d %s' % (f, pl_, ring_, sl_))
        if os.environ.get('COLLROW') and int(os.environ['COLLROW'].split(',')[0]) <= f <= int(os.environ['COLLROW'].split(',')[1]):   # COLLROW=lo,hi[,row]: the collision words of one row (12 cells) after the frame
            base_ = (lit(0x2de50) + 0x2de74 - G) & 0xffffffff; row_ = int((os.environ['COLLROW'].split(',') + ['1'])[2])
            ws_ = struct.unpack('<12I', o.read(BASE + base_ + 48 * row_, 48)); print('COLL f%d row%d' % (f, row_), ' '.join('%x' % w for w in ws_))
        if os.environ.get('ARRCELLS') and f >= 480 and (f - 480) % 40 == 1:   # cells whose collision word has the arrow bit
            base = (lit(0x2de50) + 0x2de74 - G) & 0xffffffff
            words = struct.unpack('<108I', o.read(BASE + base, 432))
            print('ARR t%d' % (f - 469), [(i % 12, i // 12, hex(w & 0xfff)) for i, w in enumerate(words) if w & 0x800])
        for spec in os.environ.get('POKE', '').split(';'):   # POKE="ghidra_addr,value,frame;..." writes a 32-bit value at that frame (rule checks)
            if spec:
                ga, val, at = spec.split(',')
                if f == int(at): o.write(BASE + int(ga, 16) - G, struct.pack('<i', int(val)))
        for spec in os.environ.get('POKEARR', '').split(';'):   # POKEARR="word_index,value,frame": writes into the score array (SC_InitScoreBoard's object) at that frame
            if spec:
                wi, val, at = spec.split(',')
                if f == int(at):
                    pa = (lit(0x3d3d8) + 0x3d366 + lit(0x3d3dc) - G) & 0xffffffff
                    arr = o.u32(BASE + pa)
                    o.write(arr + 4 * int(wi), struct.pack('<i', int(val)))
                    print('poked score array at %#x word %s' % (arr, wi))
        if os.environ.get('DUMPARR') and f in [int(x) for x in os.environ['DUMPARR'].split(',')]:
            pa = (lit(0x3d3d8) + 0x3d366 + lit(0x3d3dc) - G) & 0xffffffff
            print('ARR f%d' % f, struct.unpack('<24i', o.read(o.u32(BASE + pa), 96)))
        if os.environ.get('COLLDUMP') and f == int(os.environ['COLLDUMP']):   # the original's field collision words (12 x 9), index = 12 * row + column
            base_ = (lit(0x2de50) + 0x2de74 - G) & 0xffffffff
            ws_ = struct.unpack('<108I', o.read(BASE + base_, 432))
            for r_ in range(9): print('COLL row', r_, ' '.join('%03x' % (ws_[12 * r_ + c_] & 0xfff) for c_ in range(12)))
        if os.environ.get('BCDTIME') and f in (1, 400, 470, 471, 600, 1000, 1500):   # the BCD timer block (0x17b5f8 + 8) and the game time (+0xc) as TI_GetBCDTime / TI_GetGameTime read them
            print('BCDTIME f%d bcd %#x game %d' % (f, struct.unpack('<i', o.read(BASE + 0x17b5f8 - G + 8, 4))[0], struct.unpack('<i', o.read(BASE + 0x17b5f8 - G + 0xc, 4))[0]))
        if os.environ.get('GTIME') and (f in (1, 2, 3, 100, 361, 362, 469, 470, 471, 472, 473, 480)):   # TI_GetGlobalTime (0x17b5f8) at chosen frames
            print('GTIME f%d %d' % (f, struct.unpack('<i', o.read(BASE + 0x17b5f8 - G, 4))[0]))
        if os.environ.get('TRACKWORDS'):   # log changes of the score array words 8, 9, 12, 13 (type 4 counters and the stage 24 words)
            pa2 = (lit(0x3d3d8) + 0x3d366 + lit(0x3d3dc) - G) & 0xffffffff
            w_ = struct.unpack('<24i', o.read(o.u32(BASE + pa2), 96))
            cur_ = (w_[0], w_[1], w_[2], w_[3], w_[8], w_[9], w_[12], w_[13])
            if cur_ != globals().get('_lastw'):
                print('WORDS f%d w0-3 %s w8 %d w9 %d w12 %d w13 %d' % (f, cur_[:4], cur_[4], cur_[5], cur_[6], cur_[7])); globals()['_lastw'] = cur_
        if os.environ.get('TRACKSCORE'):   # log every change of score word 0 (the player's score, the type 3 win counter)
            pa_ = (lit(0x3d3d8) + 0x3d366 + lit(0x3d3dc) - G) & 0xffffffff
            sc_ = struct.unpack('<i', o.read(o.u32(BASE + pa_), 4))[0]
            if sc_ != globals().get('_lastscore'):
                print('SCORE f%d %d' % (f, sc_)); globals()['_lastscore'] = sc_
        if os.environ.get('TRACKCNT'):   # log every change of the rocket / eaten counters (frame, value)
            cur = (struct.unpack('<i', o.read(BASE + 0x17bbb4 - G, 4))[0], struct.unpack('<i', o.read(BASE + 0x17bbc0 - G, 4))[0])
            if cur != globals().get('_lastcnt'):
                print('CNT f%d rocket %d eaten %d' % (f, cur[0], cur[1])); globals()['_lastcnt'] = cur
        if os.environ.get('GENBLOCK') and f == 471:   # the generator manager block (ghidra 0x17b810): count, flags, entries (x, y word pairs from +0x24, 8 bytes each)
            raw = o.read(BASE + 0x17b810 - G, 0x24 + 8 * 8)
            cnt = struct.unpack_from('<i', raw, 0)[0]
            print('GENBLOCK count', cnt, [struct.unpack_from('<hhi', raw, 0x24 + 8 * i) for i in range(min(cnt, 8))])
        if os.environ.get('RNGDRAWS') and globals()['_rngc'][0]: print('RNG f%d %d' % (f, globals()['_rngc'][0])); globals()['_rngc'][0] = 0
        if os.environ.get('HEATW'):   # HEATW=lo,hi: the CPU heat map (108 int16, 12 columns) at the end of each frame; 'HEAT f<frame> <row 5 cols 3..7>' plus the nonzero count
            hlo, hhi = [int(v) for v in os.environ['HEATW'].split(',')]
            if hlo <= f <= hhi:
                if os.environ.get('HEATFULL'): print('HFULL f%d' % f, ' '.join(str(v) for v in struct.unpack('<108h', o.read(o.u32(BASE + 0x79498 + 0x564 - G), 216))))
                hp = o.u32(BASE + 0x79498 + 0x564 - G); hh = struct.unpack('<108h', o.read(hp, 216))
                print('HEAT f%d' % f + ''.join(' (%d,5)=%d' % (x, hh[5 * 12 + x]) for x in range(3, 8)) + ' nz=%d sum=%d' % (sum(1 for v in hh if v), sum(hh)))
        b = block()
        if os.environ.get('TRACKW4'):
            st_ = struct.unpack('<i', o.read(BASE + 0x184c8c - G, 4))[0]
            if st_ != globals().get('_rl', 0): print('RLSTATUS f%d %d' % (f, st_)); globals()['_rl'] = st_
        if os.environ.get('TRACKW4') and b[4] != globals().get('_w4', 0): print('W4 f%d %d (phase %d)' % (f, b[4], b[3])); globals()['_w4'] = b[4]
        if b[3] != last:
            print('f%d phase %d block %s' % (f, b[3], b))
            last = b[3]
    if os.environ.get('TASKFLAGS'):
        for (fn_, fl_), n_ in sorted(globals()['_seen_t'].items()): print('TASK func %#x flag %#x visits %d' % (fn_, fl_, n_))
    print('counters rocket %d eaten %d' % (struct.unpack('<i', o.read(BASE + 0x17bbb4 - G, 4))[0], struct.unpack('<i', o.read(BASE + 0x17bbc0 - G, 4))[0]))
    print('end block', block(), 'unhandled', o.unhandled)


if __name__ == '__main__':
    main(int(sys.argv[1]), int(sys.argv[2]) if len(sys.argv) > 2 else 600)
