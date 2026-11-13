"""Development-time oracle: runs functions of the user's own Android libccrjni.so under Unicorn (ARM Thumb)
so the reimplementation can be differential-tested tick by tick. Nothing from the library is shipped or committed.
usage as module: o = Oracle(path_to_so); o.call(addr, r0, r1, ...)."""
import struct, math, sys
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_HOOK_CODE, UC_PROT_ALL
from unicorn.arm_const import *

BASE = 0x10000000          # load address of the library
STUB = 0x70000000          # import stubs (hooked)
STACK = 0x60000000
HEAP = 0x50000000

def f2u(f): return struct.unpack('<I', struct.pack('<f', f))[0]
def u2f(u): return struct.unpack('<f', struct.pack('<I', u & 0xffffffff))[0]
def s32(u): u &= 0xffffffff; return u - (1 << 32) if u & 0x80000000 else u

class Oracle:
    def __init__(self, path):
        self.d = open(path, 'rb').read()
        self.uc = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
        self.imports = {}          # stub addr -> name
        self.unhandled = {}
        self.calls = []
        self._load()
        self.uc.mem_map(STACK, 0x100000); self.uc.mem_map(HEAP, 0x400000); self.uc.mem_map(STUB, 0x10000)
        self.uc.mem_write(STUB, b'\x70\x47' * 0x2000)       # bx lr
        self.heap_ptr = HEAP
        self.uc.hook_add(UC_HOOK_CODE, self._hook, begin=STUB, end=STUB + 0x10000)

    # ---- ELF loading -------------------------------------------------
    def _load(self):
        d = self.d
        phoff, = struct.unpack_from('<I', d, 0x1c); phentsize, phnum = struct.unpack_from('<2H', d, 0x2a)
        dyn = None; hi = 0
        for i in range(phnum):
            t, off, va, pa, fs, ms, fl, al = struct.unpack_from('<8I', d, phoff + i * phentsize)
            if t == 1: hi = max(hi, va + ms)
            if t == 2: dyn = (va, ms)
        size = (hi + 0xfff) & ~0xfff
        self.uc.mem_map(BASE, size)
        for i in range(phnum):
            t, off, va, pa, fs, ms, fl, al = struct.unpack_from('<8I', d, phoff + i * phentsize)
            if t == 1: self.uc.mem_write(BASE + va, d[off:off + fs])
        # dynamic section
        tags = {}
        dva, dsz = dyn
        for k in range(0, dsz, 8):
            tag, val = struct.unpack('<iI', bytes(self.uc.mem_read(BASE + dva + k, 8)))
            if tag == 0: break
            tags.setdefault(tag, []).append(val)
        symtab, strtab = tags[6][0], tags[5][0]
        def sym(i):
            nm, val, sz, info, oth, shn = struct.unpack('<IIIBBH', bytes(self.uc.mem_read(BASE + symtab + i * 16, 16)))
            end = bytes(self.uc.mem_read(BASE + strtab + nm, 64)).split(b'\0')[0]
            return end.decode(), val, shn
        self.sym = sym
        stubs = {}
        def stub_for(name):
            if name not in stubs:
                a = STUB + 2 * len(stubs); stubs[name] = a; self.imports[a] = name
            return a if (a := stubs[name]) else 0
        rels = []
        if 17 in tags: rels.append((tags[17][0], tags[18][0]))          # DT_REL, DT_RELSZ
        if 23 in tags: rels.append((tags[23][0], tags[2][0]))           # DT_JMPREL, DT_PLTRELSZ
        for rva, rsz in rels:
            for k in range(0, rsz, 8):
                off, info = struct.unpack('<II', bytes(self.uc.mem_read(BASE + rva + k, 8)))
                typ, si = info & 0xff, info >> 8
                at = BASE + off
                if typ == 23:       # R_ARM_RELATIVE
                    v, = struct.unpack('<I', bytes(self.uc.mem_read(at, 4))); self.uc.mem_write(at, struct.pack('<I', BASE + v))
                elif typ in (21, 22, 2):   # GLOB_DAT, JUMP_SLOT, ABS32
                    name, val, shn = sym(si)
                    if shn != 0: self.uc.mem_write(at, struct.pack('<I', BASE + val + (0 if typ != 2 else struct.unpack('<I', bytes(self.uc.mem_read(at, 4)))[0])))
                    else: self.uc.mem_write(at, struct.pack('<I', stub_for(name) | 1))
    def symaddr(self, name):
        # linear search of the dynamic symbol table for exported/defined names
        nsyms = None
        for i in range(1, 4000):
            try: n, v, shn = self.sym(i)
            except Exception: break
            if n == name and shn != 0: return BASE + v
        return None

    # ---- import stubs -------------------------------------------------
    def _hook(self, uc, addr, size, user):
        name = self.imports.get(addr & ~1)
        if name is None: return
        r0, r1 = uc.reg_read(UC_ARM_REG_R0), uc.reg_read(UC_ARM_REG_R1)
        a, b = u2f(r0), u2f(r1); res = None
        if name == '__aeabi_fmul': res = f2u(a * b)
        elif name == '__aeabi_fadd': res = f2u(a + b)
        elif name == '__aeabi_fsub': res = f2u(a - b)
        elif name == '__aeabi_fdiv': res = f2u(a / b if b else math.copysign(float('inf'), a))
        elif name == '__aeabi_i2f': res = f2u(float(s32(r0)))
        elif name == '__aeabi_ui2f': res = f2u(float(r0))
        elif name in ('__aeabi_f2iz',): res = int(a) & 0xffffffff if abs(a) < 2**31 else 0
        elif name == '__aeabi_f2uiz': res = int(a) & 0xffffffff if a >= 0 else 0
        elif name == '__aeabi_fcmplt': res = 1 if a < b else 0
        elif name == '__aeabi_fcmple': res = 1 if a <= b else 0
        elif name == '__aeabi_fcmpgt': res = 1 if a > b else 0
        elif name == '__aeabi_fcmpge': res = 1 if a >= b else 0
        elif name == '__aeabi_fcmpeq': res = 1 if a == b else 0
        elif name in ('sqrt', 'sin', 'cos', 'atan2', 'floor', 'ceil'):      # double precision, soft-float ABI: args in r0:r1 (and r2:r3), result r0:r1
            da = struct.unpack('<d', struct.pack('<II', r0, r1))[0]
            db = struct.unpack('<d', struct.pack('<II', uc.reg_read(UC_ARM_REG_R2), uc.reg_read(UC_ARM_REG_R3)))[0]
            fn = {'sqrt': lambda: math.sqrt(da) if da >= 0 else float('nan'), 'sin': lambda: math.sin(da), 'cos': lambda: math.cos(da),
                  'atan2': lambda: math.atan2(da, db), 'floor': lambda: math.floor(da), 'ceil': lambda: math.ceil(da)}[name]()
            lo, hi = struct.unpack('<II', struct.pack('<d', fn))
            uc.reg_write(UC_ARM_REG_R1, hi); res = lo
        elif name == 'sqrtf': res = f2u(math.sqrt(a)) if a >= 0 else 0
        elif name == 'sinf': res = f2u(math.sin(a))
        elif name == 'cosf': res = f2u(math.cos(a))
        elif name == 'atan2f': res = f2u(math.atan2(a, b))
        elif name == 'ceilf': res = f2u(math.ceil(a))
        elif name == 'floorf': res = f2u(math.floor(a))
        elif name == 'malloc':
            res = self.heap_ptr; self.heap_ptr = (self.heap_ptr + r0 + 15) & ~15
        elif name in ('free', '__stack_chk_fail', 'abort'): res = 0
        elif name == 'memset':
            uc.mem_write(r0, bytes([r1 & 0xff]) * uc.reg_read(UC_ARM_REG_R2)); res = r0
        elif name == 'memcpy':
            n = uc.reg_read(UC_ARM_REG_R2); uc.mem_write(r0, bytes(uc.mem_read(r1, n))); res = r0
        else:
            self.unhandled[name] = self.unhandled.get(name, 0) + 1; res = 0
        self.calls.append(name)
        uc.reg_write(UC_ARM_REG_R0, res & 0xffffffff)
        lr = uc.reg_read(UC_ARM_REG_LR)
        uc.reg_write(UC_ARM_REG_PC, lr)

    # ---- helpers -------------------------------------------------------
    def read(self, addr, n): return bytes(self.uc.mem_read(addr, n))
    def write(self, addr, data): self.uc.mem_write(addr, data)
    def u32(self, a): return struct.unpack('<I', self.read(a, 4))[0]
    def call(self, fn_offset, *args, maxinsn=2000000):
        uc = self.uc
        regs = [UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3]
        for r, v in zip(regs, args): uc.reg_write(r, v & 0xffffffff)
        uc.reg_write(UC_ARM_REG_SP, STACK + 0xf0000)
        ret = STUB + 0x8000            # return trampoline (bx lr loop avoided: stop at this address)
        uc.reg_write(UC_ARM_REG_LR, ret | 1)
        uc.emu_start((BASE + fn_offset) | 1, ret, count=maxinsn)
        return uc.reg_read(UC_ARM_REG_R0)

if __name__ == '__main__':
    o = Oracle(sys.argv[1])
    print('imports:', sorted(set(o.imports.values())))
