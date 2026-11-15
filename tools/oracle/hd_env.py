"""Generic Unicorn environment for HD 1.0 (iPad) screen functions: a fake AppData with the frame table of every image slot (slot k = AppData + 0x3cc + 4 k), both fonts, the English text table,
the pad layout struct and screen size globals; logs the low-level draw calls (BHLib_RenderTexture, RenderFilledRect, PrintString, GetStringPixelWidth results are real) and stubs bindTextureSpace.
usage: env = make(); env.call(addr, *args); env.log"""
import os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ios_oracle import IOSOracle, u2f, s32
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import *
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
PACK = os.path.join(ROOT, 'local', 'cache', 'assets', 'ios', 'ChuChu_Rocket_HD_v1_0')
HOOKS = {0xac4c: 'RenderTexture', 0xaae8: 'RenderFilledRect', 0x9dc0: 'PrintString', 0xccd4: 'bind', 0xae58: 'rawres', 0xbcc4: 'stub0', 0xc9b4: 'stub0', 0xc6e8: 'stub0'}
class Env:
    pass
def make(lang='en'):
    e = Env(); o = IOSOracle(os.path.join(ROOT, 'analysis', 'thin', 'CCR_ios_hd10')); e.o = o; e.log = []
    def put(data): p = o.alloc(len(data) + 16); o.write(p, data); return p
    def rec(r):
        if r < 885: return open(os.path.join(PACK, 'ccrpad', '%04d.bin' % r), 'rb').read()
        return open(os.path.join(PACK, 'ccrpad_' + lang, '%04d.bin' % (r - 885)), 'rb').read()
    ad = o.alloc(0x2800); e.appdata = ad
    tex = struct.unpack('<175i', o.read(0xe6704, 700)); frm = struct.unpack('<175i', o.read(0xe6984, 700)); T = struct.unpack('<1200i', o.read(o.u32(0xeb548), 4800))
    e.T = T
    for k in range(175):
        if not (0 <= frm[k] < 1200): continue
        try: data = rec(T[frm[k]])
        except OSError: continue
        t = o.alloc(0x40); o.write(t + 8, struct.pack('<I', k)); o.write(t + 0x28, struct.pack('<I', put(data))); o.write(ad + 0x3cc + 4 * k, struct.pack('<I', t))
    w874 = open(os.path.join(PACK, 'ccrpad', '0874.bin'), 'rb').read(); w876 = open(os.path.join(PACK, 'ccrpad', '0876.bin'), 'rb').read()
    def font(img, w):
        tb = o.u32(o.u32(ad + 0x3cc + 4 * img) + 0x28); lh = struct.unpack_from('<h', o.read(tb, 4 + 36 * 92), 4 + 36 * 91 + 22)[0]
        f = o.alloc(0x20); o.write(f, struct.pack('<IIIII', o.u32(ad + 0x3cc + 4 * img), lh, 255, len(w), put(w))); return f
    f0 = font(0, w874); f1 = font(2, w876); o.write(ad + 0x64c, struct.pack('<I', f0)); o.write(ad + 0x384, struct.pack('<I', f1)); e.fontname = {f0: 0, f1: 1}
    for sp in range(11):
        t = o.alloc(0x60); o.write(ad + 0x3a0 + 4 * sp, struct.pack('<I', t))
    o.write(ad + 0x44, struct.pack('<I', 36)); o.write(ad + 0x390, struct.pack('<I', 11)); o.write(ad + 0x664, struct.pack('<I', 0))
    A = o.alloc(8); o.write(0xeb444, struct.pack('<I', A)); o.write(A, struct.pack('<I', ad))
    layout = put(open(os.path.join(ROOT, 'local', 'cache', 'assets', 'hd10_layout.bin'), 'rb').read()); A2 = o.alloc(8); o.write(0xeb4fc, struct.pack('<I', A2)); o.write(A2, struct.pack('<I', layout))
    A3 = o.alloc(8); o.write(0xeb51c, struct.pack('<I', A3)); o.write(A3, struct.pack('<I', 1))
    o.write(0x10eb10, struct.pack('<I', 768)); o.write(0x10eb0c, struct.pack('<I', 1024))
    texts = {}
    for l in open(os.path.join(ROOT, 'local', 'cache', 'assets', 'ret_all', 'loc_' + lang, 'hd_text.tsv'), encoding='latin-1').read().split('\n'):
        if '\t' in l: k, v = l.split('\t', 1); texts[int(k)] = v.replace(chr(11), chr(10))
    for rid, s in texts.items(): o.write(ad + 0x68c + 4 * (rid - 965), struct.pack('<I', put(s.encode('latin-1') + bytes(1))))
    def hook(uc, addr, size, user):
        name = HOOKS.get(addr & ~1)
        if not name: return
        if name == 'rawres':
            rid = uc.reg_read(UC_ARM_REG_R1)
            if rid not in e.raw: e.raw[rid] = put(rec(rid))
            uc.reg_write(UC_ARM_REG_R0, e.raw[rid]); uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR)); return
        if name in ('bind', 'stub0'): uc.reg_write(UC_ARM_REG_R0, 0); uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR)); return
        sp = uc.reg_read(UC_ARM_REG_SP); r = [uc.reg_read(UC_ARM_REG_R0 + i) for i in range(4)]; st = lambda k: struct.unpack('<I', bytes(uc.mem_read(sp + 4 * k, 4)))[0]
        if name == 'RenderTexture': e.log.append((name, u2f(r[0]), u2f(r[1]), u2f(r[2]), u2f(r[3]), u2f(st(0)), u2f(st(1)), st(4), st(5), st(6), st(7)))
        elif name == 'RenderFilledRect': e.log.append((name, u2f(r[0]), u2f(r[1]), u2f(r[2]), u2f(r[3]), st(0), st(1), st(2), st(3)))
        else:
            s = bytearray(); p = r[1]
            while True:
                c = bytes(uc.mem_read(p, 1))[0]
                if not c: break
                s.append(c); p += 1
            e.log.append((name, s.decode('latin-1'), u2f(r[2]), u2f(r[3]), st(0), st(1), st(2), st(3), u2f(st(4)), st(5) & 0xffff, st(6) & 255, e.fontname.get(r[0], r[0])))
        uc.reg_write(UC_ARM_REG_R0, 0); uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
    for a in HOOKS: o.uc.hook_add(UC_HOOK_CODE, hook, begin=a, end=a + 2)
    e.raw = {}; e.put = put; e.alloc = o.alloc
    return e
