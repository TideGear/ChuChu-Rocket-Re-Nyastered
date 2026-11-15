"""Ground truth for the Help & Options sound menu (HD 1.0 iOS): runs HelpOptionsScreen::initSoundMenuItems (0x2398c) and renderSoundMenuItems (0x22dcc) under Unicorn with a minimal AppData
and logs the low-level draw calls (BHLib_RenderTexture 0xac4c, BHLib_RenderFilledRect 0xaae8, BHLib_PrintString 0x9dc0, sprintf).
usage: hd_options_probe.py <music 0..255> <sfx 0..255> <vibration 0/1> <drag state a40 (0 music, 1 sfx, other = none)> [list of item states ...]"""
import os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ios_oracle import IOSOracle, u2f, s32
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import *
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
PACK = os.path.join(ROOT, 'local', 'cache', 'assets', 'ios', 'ChuChu_Rocket_HD_v1_0')
INIT, RENDER = 0x2398c, 0x22dcc
HOOKS = {0xac4c: 'RenderTexture', 0xaae8: 'RenderFilledRect', 0x9dc0: 'PrintString', 0xccd4: 'bind'}

def make(music=128, sfx=128, vib=1, drag=2, lang_ja=False):
    o = IOSOracle(os.path.join(ROOT, 'analysis', 'thin', 'CCR_ios_hd10')); log = []
    def put(data): p = o.alloc(len(data) + 16); o.write(p, data); return p
    def table(rec): return put(open(os.path.join(PACK, 'ccrpad', '%04d.bin' % rec), 'rb').read())
    def texobj(rec, space): p = o.alloc(0x40); o.write(p + 8, struct.pack('<I', space)); o.write(p + 0x28, struct.pack('<I', table(rec))); return p
    appdata = o.alloc(0x2800)
    for off, rec, sp in ((0x400, 165, 1), (0x410, 174, 2), (0x428, 229, 3)): o.write(appdata + off, struct.pack('<I', texobj(rec, sp)))
    ft = texobj(3, 4); w874 = open(os.path.join(PACK, 'ccrpad', '0874.bin'), 'rb').read(); widths = put(w874)
    ftab = o.read(o.u32(ft + 0x28), 4 + 36 * 256); lineh = struct.unpack_from('<h', ftab, 4 + 36 * 91 + 22)[0]
    font = o.alloc(0x20); o.write(font, struct.pack('<IIIII', ft, lineh, 255, len(w874), widths)); o.write(appdata + 0x64c, struct.pack('<I', font))
    o.write(appdata + 0x4d, bytes([vib])); o.write(appdata + 0x54, struct.pack('<I', music)); o.write(appdata + 0x58, struct.pack('<I', sfx)); o.write(appdata + 0x664, struct.pack('<I', 5 if lang_ja else 0))
    o.write(appdata + 0x685, bytes([0])); o.write(appdata + 0x390, struct.pack('<I', 11))
    A = o.alloc(8); o.write(0xeb444, struct.pack('<I', A)); o.write(A, struct.pack('<I', appdata))
    o.write(0x10eb10, struct.pack('<I', 768)); o.write(0x10eb0c, struct.pack('<I', 1024))
    # text table: language pack records -> AppData +0x68c + 4 * (id - first text id); first text id = 965 on the pad; ids come from getActualResourceID (the pad table)
    T = struct.unpack('<1200i', o.read(o.u32(0xeb548), 4800)); texts = {}
    for l in open(os.path.join(ROOT, 'local', 'cache', 'assets', 'ret_all', 'loc_en', 'hd_text.tsv'), encoding='latin-1').read().split('\n'):
        if '\t' in l: k, v = l.split('\t', 1); texts[int(k)] = v
    for rid, s in texts.items(): o.write(appdata + 0x68c + 4 * (rid - 965), struct.pack('<I', put(s.encode('latin-1') + bytes(1))))
    scr = o.alloc(0xd00); o.write(scr + 0xa14, bytes([1])); o.write(scr + 0xa1c, struct.pack('<I', 4)); o.write(scr + 0xa40, struct.pack('<I', drag & 0xffffffff))
    def hook(uc, addr, size, user):
        name = HOOKS.get(addr & ~1)
        if not name: return
        if name == 'bind': uc.reg_write(UC_ARM_REG_R0, 0); uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR)); return
        sp = uc.reg_read(UC_ARM_REG_SP); r = [uc.reg_read(UC_ARM_REG_R0 + i) for i in range(4)]
        st = lambda k: struct.unpack('<I', bytes(uc.mem_read(sp + 4 * k, 4)))[0]
        if name == 'RenderTexture': log.append((name, u2f(r[0]), u2f(r[1]), u2f(r[2]), u2f(r[3]), u2f(st(0)), u2f(st(1)), st(4), st(5), st(6), st(7)))
        elif name == 'RenderFilledRect': log.append((name, u2f(r[0]), u2f(r[1]), u2f(r[2]), u2f(r[3]), st(0), st(1), st(2), st(3)))
        else:
            s = bytearray(); p = r[1]
            while True:
                c = bytes(uc.mem_read(p, 1))[0]
                if not c: break
                s.append(c); p += 1
            log.append((name, s.decode('latin-1'), u2f(r[2]), u2f(r[3]), st(0), st(1), st(2), st(3), u2f(st(4)), st(5) & 0xffff, st(6) & 255))
        uc.reg_write(UC_ARM_REG_R0, 0); uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
    for a in HOOKS: o.uc.hook_add(UC_HOOK_CODE, hook, begin=a, end=a + 2)
    return o, log, scr, appdata

def run(o, log, scr):
    o.call(INIT, scr); del log[:]; o.call(RENDER, scr); return list(log)

if __name__ == '__main__':
    a = [int(x) for x in sys.argv[1:5]]; o, log, scr, ad = make(*a)
    for l in run(o, log, scr): print(l)
