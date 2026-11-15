"""Ground truth for Render::drawBubble (HD 1.0 iOS, 0x1ae80): runs the original under Unicorn with a minimal AppData (frame tables of the bubble sheets, the Latin font, the iPad layout struct)
and logs the Render::drawImage / Render::printString calls it makes. usage: hd_bubble_probe.py <x> <y> <width> <text> <flags> <p6> <alpha> [tex]   (output: one line per call)
Needs the extracted HD 1.0 pack (local/cache/assets/ios/ChuChu_Rocket_HD_v1_0/ccrpad[_en]) and local/cache/assets/hd10_layout.bin."""
import os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ios_oracle import IOSOracle, f2u, u2f, s32, STACK
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import *
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
PACK = os.path.join(ROOT, 'local', 'cache', 'assets', 'ios', 'ChuChu_Rocket_HD_v1_0')
DRAWIMAGE, PRINTSTRING, DRAWBUBBLE = 0x1a250, 0x1a19c, 0x1ae80

def make(path=os.path.join(ROOT, 'analysis', 'thin', 'CCR_ios_hd10'), lang_ja=False):
    o = IOSOracle(path); log = []
    def put(data): p = o.alloc(len(data) + 16); o.write(p, data); return p
    def table(rec, locale=False):
        b = os.path.join(PACK, 'ccrpad_en' if locale else 'ccrpad', '%04d.bin' % rec); return put(open(b, 'rb').read())
    def texobj(frames_ptr, space=0): p = o.alloc(0x40); o.write(p + 8, struct.pack('<I', space)); o.write(p + 0x28, struct.pack('<I', frames_ptr)); return p
    appdata = o.alloc(0x2400)
    layout = put(open(os.path.join(ROOT, 'local', 'cache', 'assets', 'hd10_layout.bin'), 'rb').read())
    # slot 11 (+0x3f8): tex 154 / frames 156 (main pack); slot 156 (+0x63c): tex 852 / frames 855 (language pack record 855 - 885 < 0 -> main pack)
    t3f8 = texobj(table(156)); t63c = texobj(table(855) if 855 < 885 else table(855 - 885, True))
    # font 0 (+0x64c): frames rec 3, widths rec 874, height = short at frame record 91 + 22
    ft = texobj(table(3)); widths = put(open(os.path.join(PACK, 'ccrpad', '0874.bin'), 'rb').read())
    ftab = o.read(o.u32(ft + 0x28), 4 + 36 * 256); lineh = struct.unpack_from('<h', ftab, 4 + 36 * 91 + 22)[0]
    font = o.alloc(0x20); o.write(font, struct.pack('<IIIII', ft, lineh, 0, len(open(os.path.join(PACK, 'ccrpad', '0874.bin'), 'rb').read()), widths)); o.write(font + 8, struct.pack('<I', 255))
    o.write(appdata + 0x3f8, struct.pack('<I', t3f8)); o.write(appdata + 0x63c, struct.pack('<I', t63c)); o.write(appdata + 0x64c, struct.pack('<I', font)); o.write(appdata + 0x664, struct.pack('<I', 5 if lang_ja else 0))
    # the code loads r = [0xeb444]; r = [r] -> AppData*; and the layout the same way from 0xeb4fc
    A = o.alloc(8); o.write(0xeb444, struct.pack('<I', A)); o.write(A, struct.pack('<I', appdata))
    A2 = o.alloc(8); o.write(0xeb4fc, struct.pack('<I', A2)); o.write(A2, struct.pack('<I', layout))
    A3 = o.alloc(8); o.write(0xeb51c, struct.pack('<I', A3)); o.write(A3, struct.pack('<I', 1))
    def hook(uc, addr, size, user):
        a = addr & ~1; sp = uc.reg_read(UC_ARM_REG_SP); r = [uc.reg_read(UC_ARM_REG_R0 + i) for i in range(4)]
        st = lambda k: struct.unpack('<I', bytes(uc.mem_read(sp + 4 * k, 4)))[0]
        if a == DRAWIMAGE:
            log.append(('drawImage', r[0], r[1], u2f(r[2]), u2f(r[3]), st(0), u2f(st(1)), st(2)))
        elif a == PRINTSTRING:
            s = bytearray(); p = r[0]
            while True:
                c = bytes(uc.mem_read(p, 1))[0]
                if not c: break
                s.append(c); p += 1
            log.append(('printString', s.decode('latin-1'), u2f(r[1]), u2f(r[2]), r[3], st(0), st(1), st(2), u2f(st(3)), st(4), st(5), s32(st(6))))
        else: return
        uc.reg_write(UC_ARM_REG_R0, 0); uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
    o.uc.hook_add(UC_HOOK_CODE, hook, begin=0x1a19c, end=0x1a19e); o.uc.hook_add(UC_HOOK_CODE, hook, begin=0x1a250, end=0x1a252)
    return o, log, appdata

def bubble(o, log, x, y, w, text, flags, p6, alpha, tex=-1):
    del log[:]; tp = o.alloc(len(text) + 4); o.write(tp, text.encode('latin-1') + b'\0')
    o.call(DRAWBUBBLE, x, y, w, tp, flags, p6, alpha, tex)     # r0..r3 = x, y, width, text; stack: flags, p6, alpha, tex
    return list(log)

if __name__ == '__main__':
    o, log, _ = make(); a = sys.argv[1:]
    for l in bubble(o, log, int(a[0]), int(a[1]), int(a[2]), a[3], int(a[4]), int(a[5]), int(a[6]), int(a[7]) if len(a) > 7 else -1): print(l)
