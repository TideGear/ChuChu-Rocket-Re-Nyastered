"""Development-time oracle for the user's own iOS armv7 build (thinned Mach-O): runs functions under Unicorn by symbol name.
usage: o = IOSOracle(path); o.call('_FI_CheckAndCorrectAngle', r0, r1...)"""
import math, os, struct, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from macho import Macho
from unicorn import UcError
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_HOOK_CODE, UC_HOOK_MEM_UNMAPPED
from unicorn.arm_const import *

STUB = 0x70000000; STACK = 0x60000000; HEAP = 0x50000000
def f2u(f): return struct.unpack('<I', struct.pack('<f', f))[0]
def u2f(u): return struct.unpack('<f', struct.pack('<I', u & 0xffffffff))[0]
def s32(u): u &= 0xffffffff; return u - (1 << 32) if u & 0x80000000 else u

class IOSOracle:
    def __init__(self, path):
        self.m = Macho(path); self.uc = Uc(UC_ARCH_ARM, UC_MODE_THUMB); self.stubs = {}; self.unhandled = {}
        for name, vm, vs, fo, fs in self.m.segs:
            if name in ('__PAGEZERO', '__LINKEDIT'): continue
            self.uc.mem_map(vm, (vs + 0xfff) & ~0xfff); self.uc.mem_write(vm, self.m.d[fo:fo + fs])
        self.uc.mem_map(STUB, 0x10000); self.uc.mem_write(STUB, b'\x70\x47' * 0x8000)
        self.uc.mem_map(STACK, 0x100000); self.uc.mem_map(HEAP, 0x1000000); self.heap_ptr = HEAP
        for i, (ptr, name) in enumerate(sorted(self.m.imports().items())):
            a = STUB + 2 * i * 2; self.stubs[a] = name
            self.uc.mem_write(ptr, struct.pack('<I', a | 1))
        self.uc.reg_write(UC_ARM_REG_C1_C0_2, self.uc.reg_read(UC_ARM_REG_C1_C0_2) | (0xf << 20))      # enable VFP/NEON access
        self.uc.reg_write(UC_ARM_REG_FPEXC, 0x40000000)
        self.uc.hook_add(UC_HOOK_CODE, self._hook, begin=STUB, end=STUB + 0x10000)
    def u32(self, a): return struct.unpack('<I', self.uc.mem_read(a, 4))[0]
    def read(self, a, n): return bytes(self.uc.mem_read(a, n))
    def write(self, a, b): self.uc.mem_write(a, b)
    def alloc(self, n): p = self.heap_ptr; self.heap_ptr += (n + 15) & ~15; return p
    def _r(self, k): return self.uc.reg_read(UC_ARM_REG_R0 + k)
    def _hook(self, uc, addr, size, user):
        name = self.stubs.get(addr & ~1)
        if name is None: return
        r = [self._r(i) for i in range(4)]; ret = 0
        f = lambda i: u2f(r[i])
        if name == '_sinf': ret = f2u(math.sin(f(0)))
        elif name == '_cosf': ret = f2u(math.cos(f(0)))
        elif name == '_atan2f': ret = f2u(math.atan2(f(0), f(1)))
        elif name == '_sqrtf': ret = f2u(math.sqrt(f(0)))
        elif name == '_fabsf': ret = f2u(abs(f(0)))
        elif name == '_floorf': ret = f2u(math.floor(f(0)))
        elif name in ('_memset', '_memset_pattern4'): self.write(r[0], bytes([r[1] & 255]) * r[2]); ret = r[0]
        elif name in ('_memcpy', '_memmove'): self.write(r[0], self.read(r[1], r[2])); ret = r[0]
        elif name == '_strlen':
            n = 0
            while self.read(r[0] + n, 1) != bytes(1): n += 1
            ret = n
        elif name == '_strcpy':
            n = 0
            while self.read(r[1] + n, 1) != bytes(1): n += 1
            self.write(r[0], self.read(r[1], n + 1)); ret = r[0]
        elif name == '_strncpy':
            src = b''
            for k in range(r[2]):
                c = self.read(r[1] + k, 1)
                src += c
                if c == bytes(1): break
            self.write(r[0], src.ljust(r[2], bytes(1))); ret = r[0]
        elif name == '_malloc': ret = self.alloc(r[0])
        elif name == '_calloc': ret = self.alloc(r[0] * r[1])
        elif name == '_free': ret = 0
        elif name == '___divsi3': ret = int(s32(r[0]) / s32(r[1])) & 0xffffffff if s32(r[1]) else 0
        elif name == '___modsi3': ret = (s32(r[0]) - int(s32(r[0]) / s32(r[1])) * s32(r[1])) & 0xffffffff if s32(r[1]) else 0
        elif name == '___udivsi3': ret = (r[0] // r[1]) & 0xffffffff if r[1] else 0
        else: self.unhandled[name] = self.unhandled.get(name, 0) + 1
        uc.reg_write(UC_ARM_REG_R0, ret & 0xffffffff)
    def sym(self, name):
        a = self.m.sym_addr(name)
        if a is None: raise KeyError(name)
        return a
    def call(self, name_or_addr, *args, max_insn=5000000):
        a = self.sym(name_or_addr) if isinstance(name_or_addr, str) else name_or_addr
        sp = STACK + 0xf0000; uc = self.uc
        for i, v in enumerate(args[:4]): uc.reg_write(UC_ARM_REG_R0 + i, v & 0xffffffff)
        extra = args[4:]; sp -= 4 * len(extra)
        for i, v in enumerate(extra): uc.mem_write(sp + 4 * i, struct.pack('<I', v & 0xffffffff))
        uc.reg_write(UC_ARM_REG_SP, sp); uc.reg_write(UC_ARM_REG_LR, STUB + 0x7ff0 | 1)
        try: uc.emu_start(a | 1, STUB + 0x7ff0, count=max_insn)
        except UcError as e:
            print('emulation fault: %s pc=%#x  r0-r7 = %s' % (e, uc.reg_read(UC_ARM_REG_PC), ' '.join('%#x' % uc.reg_read(UC_ARM_REG_R0 + i) for i in range(8)))); raise
        return uc.reg_read(UC_ARM_REG_R0)
