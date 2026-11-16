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
    gcall(0x2ed7c, stage, 0, 1)                     # GA_SetStageNum(level, stage, flag): stored at +4 / +8 of the game parameter block
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
    for f in range(frames):
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
            o.write(pt, struct.pack('<hh', (7 * k + 3) % 12, (5 * k + 1) % 9)); gcall(0x286ac, 0, pt, k % 4)
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
        if os.environ.get('TRACKCNT'):   # log every change of the rocket / eaten counters (frame, value)
            cur = (struct.unpack('<i', o.read(BASE + 0x17bbb4 - G, 4))[0], struct.unpack('<i', o.read(BASE + 0x17bbc0 - G, 4))[0])
            if cur != globals().get('_lastcnt'):
                print('CNT f%d rocket %d eaten %d' % (f, cur[0], cur[1])); globals()['_lastcnt'] = cur
        b = block()
        if b[3] != last:
            print('f%d phase %d block %s' % (f, b[3], b))
            last = b[3]
    print('counters rocket %d eaten %d' % (struct.unpack('<i', o.read(BASE + 0x17bbb4 - G, 4))[0], struct.unpack('<i', o.read(BASE + 0x17bbc0 - G, 4))[0]))
    print('end block', block(), 'unhandled', o.unhandled)


if __name__ == '__main__':
    main(int(sys.argv[1]), int(sys.argv[2]) if len(sys.argv) > 2 else 600)
