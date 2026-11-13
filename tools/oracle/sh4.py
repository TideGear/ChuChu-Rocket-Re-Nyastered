"""Small SH-4 interpreter for development-time differential tests of the user's own Dreamcast executable (no graphics, no audio, no BIOS).
Integer core + single-precision FPU subset used by game logic; 16 MB RAM at 0x0C000000 (mirrors 0x8C.. / 0xAC..), Python hooks at chosen addresses.
usage: m = SH4(); m.load(addr, bytes); m.call(addr, r4, r5, ...) -> r0"""
import struct
import numpy as np

RAM_BASE = 0x0C000000; RAM_SIZE = 0x01000000
SENTINEL = 0x0C0FFFF0
f32 = np.float32

def u2f(u): return struct.unpack('<f', struct.pack('<I', u & 0xffffffff))[0]
def f2u(f): return struct.unpack('<I', struct.pack('<f', float(f)))[0]
def s32(v):
    v &= 0xffffffff
    return v - (1 << 32) if v & 0x80000000 else v
def s8(v): return v - 256 if v & 128 else v
def s16(v): return v - 65536 if v & 0x8000 else v

class SH4:
    def __init__(self):
        self.ram = bytearray(RAM_SIZE); self.r = [0] * 16; self.pc = 0; self.pr = 0; self.gbr = 0; self.mach = 0; self.macl = 0; self.sr = 0x700000F0
        self.fpul = 0; self.fpscr = 0; self.fr = [0] * 16; self.xf = [0] * 16; self.hooks = {}; self.icount = 0; self.trace = None
    # ---- memory ----
    def _off(self, a):
        a &= 0x1fffffff
        if RAM_BASE <= a < RAM_BASE + RAM_SIZE: return a - RAM_BASE
        raise MemoryError('access %#x pc=%#x' % (a, self.pc))
    def load(self, addr, data): o = self._off(addr); self.ram[o:o + len(data)] = data
    def rd8(self, a): return self.ram[self._off(a)]
    def rd16(self, a): o = self._off(a); return self.ram[o] | (self.ram[o + 1] << 8)
    def rd32(self, a): o = self._off(a); return struct.unpack_from('<I', self.ram, o)[0]
    def wr8(self, a, v): self.ram[self._off(a)] = v & 255
    def wr16(self, a, v): o = self._off(a); struct.pack_into('<H', self.ram, o, v & 0xffff)
    def wr32(self, a, v): o = self._off(a); struct.pack_into('<I', self.ram, o, v & 0xffffffff)
    # ---- flags / registers ----
    @property
    def T(self): return self.sr & 1
    def setT(self, v): self.sr = (self.sr & ~1) | (1 if v else 0)
    def FR(self, n): return self.fr[n] if not (self.fpscr & 0x200000) else self.xf[n]
    def setFR(self, n, v):
        if not (self.fpscr & 0x200000): self.fr[n] = v & 0xffffffff
        else: self.xf[n] = v & 0xffffffff
    def fget(self, n): return f32(u2f(self.FR(n)))
    def fset(self, n, v): self.setFR(n, f2u(f32(v)))
    # ---- execution ----
    def call(self, addr, *args, max_insn=50_000_000):
        for i, v in enumerate(args[:4]): self.r[4 + i] = v & 0xffffffff
        self.r[15] = (RAM_BASE + RAM_SIZE - 0x1000) | 0x80000000; self.pr = SENTINEL | 0x80000000; self.pc = addr; n = 0
        while (self.pc & 0x1fffffff) != SENTINEL:
            h = self.hooks.get(self.pc & 0x1fffffff)
            if h is not None: h(self); self.pc = self.pr; continue
            self.step(); n += 1
            if n > max_insn: raise RuntimeError('instruction limit at pc=%#x' % self.pc)
        self.icount += n
        return self.r[0]
    def step(self):
        pc = self.pc; op = self.rd16(pc)
        if self.trace is not None: self.trace(self, pc, op)
        self.pc = pc + 2; self.exec(op, pc)
    def delay(self, target):
        pc = self.pc; op = self.rd16(pc); self.pc = pc + 2; self.exec(op, pc); self.pc = target
    def bad(self, op, pc): raise RuntimeError('unhandled opcode %04x at %#x' % (op, pc))
    def exec(self, op, pc):
        r = self.r; n = (op >> 8) & 15; m = (op >> 4) & 15; hi = op >> 12
        if hi == 0xE: r[n] = ((op & 0xff) - 256) & 0xffffffff if op & 0x80 else op & 0xff; return
        if hi == 0x6: return self.op6(op, n, m)
        if hi == 0x7: r[n] = (r[n] + s8(op & 0xff)) & 0xffffffff; return
        if hi == 0xD: r[n] = self.rd32(((pc + 4) & ~3) + (op & 0xff) * 4); return
        if hi == 0x9: r[n] = s16(self.rd16(pc + 4 + (op & 0xff) * 2)) & 0xffffffff; return
        if hi == 0x1: self.wr32(r[n] + (op & 15) * 4, r[m]); return
        if hi == 0x5: r[n] = self.rd32(r[m] + (op & 15) * 4); return
        if hi == 0x2: return self.op2(op, pc, n, m)
        if hi == 0x3: return self.op3(op, pc, n, m)
        if hi == 0x4: return self.op4(op, pc, n, m)
        if hi == 0x0: return self.op0(op, pc, n, m)
        if hi == 0x8: return self.op8(op, pc, n, m)
        if hi == 0xA:
            d = op & 0xfff; d = d - 4096 if d & 0x800 else d; self.delay(pc + 4 + d * 2); return
        if hi == 0xB:
            d = op & 0xfff; d = d - 4096 if d & 0x800 else d; self.pr = pc + 4; self.delay(pc + 4 + d * 2); return
        if hi == 0xC: return self.opc(op, pc)
        if hi == 0xF: return self.opf(op, pc, n, m)
        self.bad(op, pc)
    def op6(self, op, n, m):
        r = self.r; k = op & 15
        if k == 3: r[n] = r[m]
        elif k == 2: r[n] = self.rd32(r[m])
        elif k == 0: r[n] = s8(self.rd8(r[m])) & 0xffffffff
        elif k == 1: r[n] = s16(self.rd16(r[m])) & 0xffffffff
        elif k == 6:
            v = self.rd32(r[m])
            if n != m: r[m] = (r[m] + 4) & 0xffffffff
            r[n] = v
        elif k == 4:
            v = s8(self.rd8(r[m])) & 0xffffffff
            if n != m: r[m] = (r[m] + 1) & 0xffffffff
            r[n] = v
        elif k == 5:
            v = s16(self.rd16(r[m])) & 0xffffffff
            if n != m: r[m] = (r[m] + 2) & 0xffffffff
            r[n] = v
        elif k == 7: r[n] = ~r[m] & 0xffffffff
        elif k == 8: v = r[m]; r[n] = (v & 0xffff0000) | ((v & 0xff) << 8) | ((v >> 8) & 0xff)
        elif k == 9: v = r[m]; r[n] = ((v & 0xffff) << 16) | (v >> 16)
        elif k == 0xA:
            tmp = (0 - r[m]) & 0xffffffff; res = (tmp - self.T) & 0xffffffff; self.setT((0 < tmp) or (tmp < res)); r[n] = res
        elif k == 0xB: r[n] = (-r[m]) & 0xffffffff
        elif k == 0xC: r[n] = r[m] & 0xff
        elif k == 0xD: r[n] = r[m] & 0xffff
        elif k == 0xE: r[n] = s8(r[m] & 0xff) & 0xffffffff
        elif k == 0xF: r[n] = s16(r[m] & 0xffff) & 0xffffffff
    def op2(self, op, pc, n, m):
        r = self.r; k = op & 15
        if k == 2: self.wr32(r[n], r[m])
        elif k == 0: self.wr8(r[n], r[m])
        elif k == 1: self.wr16(r[n], r[m])
        elif k == 6: r[n] = (r[n] - 4) & 0xffffffff; self.wr32(r[n], r[m])
        elif k == 4: r[n] = (r[n] - 1) & 0xffffffff; self.wr8(r[n], r[m])
        elif k == 5: r[n] = (r[n] - 2) & 0xffffffff; self.wr16(r[n], r[m])
        elif k == 7:
            self.sr = (self.sr & ~0x300) | ((r[n] >> 31) << 8) | ((r[m] >> 31) << 9); self.setT(((r[n] >> 31) ^ (r[m] >> 31)) & 1)
        elif k == 8: self.setT((r[n] & r[m]) == 0)
        elif k == 9: r[n] &= r[m]
        elif k == 0xA: r[n] ^= r[m]
        elif k == 0xB: r[n] |= r[m]
        elif k == 0xC:
            a = r[n] ^ r[m]; self.setT(any(((a >> (8 * i)) & 255) == 0 for i in range(4)))
        elif k == 0xD: r[n] = ((r[m] & 0xffff) << 16) | ((r[n] >> 16) & 0xffff)
        elif k == 0xE: self.macl = ((r[n] & 0xffff) * (r[m] & 0xffff)) & 0xffffffff
        elif k == 0xF: self.macl = (s16(r[n] & 0xffff) * s16(r[m] & 0xffff)) & 0xffffffff
        else: self.bad(op, pc)
    def op3(self, op, pc, n, m):
        r = self.r; k = op & 15; a, b = r[n], r[m]
        if k == 0: self.setT(a == b)
        elif k == 2: self.setT(a >= b)
        elif k == 3: self.setT(s32(a) >= s32(b))
        elif k == 6: self.setT(a > b)
        elif k == 7: self.setT(s32(a) > s32(b))
        elif k == 8: r[n] = (a - b) & 0xffffffff
        elif k == 0xC: r[n] = (a + b) & 0xffffffff
        elif k == 0xE: v = a + b + self.T; self.setT(v > 0xffffffff); r[n] = v & 0xffffffff
        elif k == 0xA: v = a - b - self.T; self.setT(v < 0); r[n] = v & 0xffffffff
        elif k == 0xF: v = s32(a) + s32(b); self.setT(v > 0x7fffffff or v < -0x80000000); r[n] = v & 0xffffffff
        elif k == 0xB: v = s32(a) - s32(b); self.setT(v > 0x7fffffff or v < -0x80000000); r[n] = v & 0xffffffff
        elif k == 5: v = a * b; self.macl = v & 0xffffffff; self.mach = (v >> 32) & 0xffffffff
        elif k == 0xD: v = s32(a) * s32(b); self.macl = v & 0xffffffff; self.mach = (v >> 32) & 0xffffffff
        elif k == 4: self.div1(n, m)
        else: self.bad(op, pc)
    def div1(self, n, m):
        r = self.r; old_q = (self.sr >> 8) & 1; M = (self.sr >> 9) & 1; T = self.T
        q = (r[n] >> 31) & 1; r[n] = ((r[n] << 1) | T) & 0xffffffff; tmp0 = r[n]
        sub = (old_q == M)
        if sub: r[n] = (r[n] - r[m]) & 0xffffffff; tmp1 = 1 if r[n] > tmp0 else 0
        else: r[n] = (r[n] + r[m]) & 0xffffffff; tmp1 = 1 if r[n] < tmp0 else 0
        q = ((1 - tmp1) if q else tmp1) if M == 0 else (tmp1 if q else (1 - tmp1))
        self.sr = (self.sr & ~0x100) | (q << 8); self.setT(1 if q == M else 0)
    def op4(self, op, pc, n, m):
        r = self.r; lo = op & 0xff
        if lo == 0x00: self.setT(r[n] >> 31); r[n] = (r[n] << 1) & 0xffffffff
        elif lo == 0x01: self.setT(r[n] & 1); r[n] >>= 1
        elif lo == 0x04: self.setT(r[n] >> 31); r[n] = ((r[n] << 1) | (r[n] >> 31)) & 0xffffffff
        elif lo == 0x05: self.setT(r[n] & 1); r[n] = (r[n] >> 1) | ((r[n] & 1) << 31)
        elif lo == 0x08: r[n] = (r[n] << 2) & 0xffffffff
        elif lo == 0x09: r[n] >>= 2
        elif lo == 0x18: r[n] = (r[n] << 8) & 0xffffffff
        elif lo == 0x19: r[n] >>= 8
        elif lo == 0x28: r[n] = (r[n] << 16) & 0xffffffff
        elif lo == 0x29: r[n] >>= 16
        elif lo == 0x20: self.setT(r[n] >> 31); r[n] = (r[n] << 1) & 0xffffffff
        elif lo == 0x21: self.setT(r[n] & 1); r[n] = (r[n] >> 1) | (r[n] & 0x80000000)
        elif lo == 0x24: t = self.T; self.setT(r[n] >> 31); r[n] = ((r[n] << 1) | t) & 0xffffffff
        elif lo == 0x25: t = self.T; self.setT(r[n] & 1); r[n] = (r[n] >> 1) | (t << 31)
        elif lo == 0x10: r[n] = (r[n] - 1) & 0xffffffff; self.setT(r[n] == 0)
        elif lo == 0x11: self.setT(s32(r[n]) >= 0)
        elif lo == 0x15: self.setT(s32(r[n]) > 0)
        elif lo == 0x0B: self.pr = pc + 4; self.delay(r[n])
        elif lo == 0x2B: self.delay(r[n])
        elif lo == 0x0E: self.sr = r[n]
        elif lo == 0x1E: self.gbr = r[n]
        elif lo == 0x0A: self.mach = r[n]
        elif lo == 0x1A: self.macl = r[n]
        elif lo == 0x2A: self.pr = r[n]
        elif lo == 0x5A: self.fpul = r[n]
        elif lo == 0x6A: self.fpscr = r[n]
        elif lo == 0x22: r[n] = (r[n] - 4) & 0xffffffff; self.wr32(r[n], self.pr)
        elif lo == 0x02: r[n] = (r[n] - 4) & 0xffffffff; self.wr32(r[n], self.mach)
        elif lo == 0x12: r[n] = (r[n] - 4) & 0xffffffff; self.wr32(r[n], self.macl)
        elif lo == 0x13: r[n] = (r[n] - 4) & 0xffffffff; self.wr32(r[n], self.gbr)
        elif lo == 0x03: r[n] = (r[n] - 4) & 0xffffffff; self.wr32(r[n], self.sr)
        elif lo == 0x52: r[n] = (r[n] - 4) & 0xffffffff; self.wr32(r[n], self.fpul)
        elif lo == 0x62: r[n] = (r[n] - 4) & 0xffffffff; self.wr32(r[n], self.fpscr)
        elif lo == 0x26: self.pr = self.rd32(r[n]); r[n] = (r[n] + 4) & 0xffffffff
        elif lo == 0x06: self.mach = self.rd32(r[n]); r[n] = (r[n] + 4) & 0xffffffff
        elif lo == 0x16: self.macl = self.rd32(r[n]); r[n] = (r[n] + 4) & 0xffffffff
        elif lo == 0x17: self.gbr = self.rd32(r[n]); r[n] = (r[n] + 4) & 0xffffffff
        elif lo == 0x07: self.sr = self.rd32(r[n]); r[n] = (r[n] + 4) & 0xffffffff
        elif lo == 0x56: self.fpul = self.rd32(r[n]); r[n] = (r[n] + 4) & 0xffffffff
        elif lo == 0x66: self.fpscr = self.rd32(r[n]); r[n] = (r[n] + 4) & 0xffffffff
        elif lo == 0x1B: v = self.rd8(r[n]); self.setT(v == 0); self.wr8(r[n], v | 0x80)
        elif (lo & 15) == 0xC:
            sh = r[m]; v = s32(r[n])
            if not (sh & 0x80000000): r[n] = (v << (sh & 31)) & 0xffffffff
            else:
                sh = (-s32(sh)) & 31; r[n] = ((v >> sh) & 0xffffffff) if sh else (0xffffffff if v < 0 else 0)
        elif (lo & 15) == 0xD:
            sh = r[m]; v = r[n]
            if not (sh & 0x80000000): r[n] = (v << (sh & 31)) & 0xffffffff
            else:
                sh = (-s32(sh)) & 31; r[n] = (v >> sh) if sh else 0
        else: self.bad(op, pc)
    def op0(self, op, pc, n, m):
        r = self.r; lo = op & 0xff; k = op & 15
        if k == 4: self.wr8(r[0] + r[n], r[m]); return
        if k == 5: self.wr16(r[0] + r[n], r[m]); return
        if k == 6: self.wr32(r[0] + r[n], r[m]); return
        if k == 7: self.macl = (r[n] * r[m]) & 0xffffffff; return
        if k == 0xC: r[n] = s8(self.rd8(r[0] + r[m])) & 0xffffffff; return
        if k == 0xD: r[n] = s16(self.rd16(r[0] + r[m])) & 0xffffffff; return
        if k == 0xE: r[n] = self.rd32(r[0] + r[m]); return
        if lo == 0x09: return
        if lo == 0x08: self.setT(0); return
        if lo == 0x18: self.setT(1); return
        if lo == 0x28: self.mach = self.macl = 0; return
        if lo == 0x19: self.sr &= ~0x301; return
        if lo == 0x29: r[n] = self.T; return
        if lo == 0x0B: self.delay(self.pr); return
        if lo == 0x02: r[n] = self.sr; return
        if lo == 0x12: r[n] = self.gbr; return
        if lo == 0x0A: r[n] = self.mach; return
        if lo == 0x1A: r[n] = self.macl; return
        if lo == 0x2A: r[n] = self.pr; return
        if lo == 0x5A: r[n] = self.fpul; return
        if lo == 0x6A: r[n] = self.fpscr; return
        if lo == 0x03: self.pr = pc + 4; self.delay(pc + 4 + r[n]); return
        if lo == 0x23: self.delay(pc + 4 + r[n]); return
        if lo in (0x83, 0x93, 0xA3, 0xB3, 0x48, 0x58): return
        if lo == 0xC3: self.wr32(r[n], r[0]); return
        self.bad(op, pc)
    def op8(self, op, pc, n, m):
        r = self.r; sub = (op >> 8) & 15; d = op & 0xff
        if sub == 0x0: self.wr8(r[m] + (op & 15), r[0])
        elif sub == 0x1: self.wr16(r[m] + (op & 15) * 2, r[0])
        elif sub == 0x4: r[0] = s8(self.rd8(r[m] + (op & 15))) & 0xffffffff
        elif sub == 0x5: r[0] = s16(self.rd16(r[m] + (op & 15) * 2)) & 0xffffffff
        elif sub == 0x8: self.setT(s32(r[0]) == s8(d))
        elif sub == 0x9:
            if self.T: self.pc = pc + 4 + s8(d) * 2
        elif sub == 0xB:
            if not self.T: self.pc = pc + 4 + s8(d) * 2
        elif sub == 0xD:
            if self.T: self.delay(pc + 4 + s8(d) * 2)
        elif sub == 0xF:
            if not self.T: self.delay(pc + 4 + s8(d) * 2)
        else: self.bad(op, pc)
    def opc(self, op, pc):
        r = self.r; sub = (op >> 8) & 15; d = op & 0xff
        if sub == 0x0: self.wr8(self.gbr + d, r[0])
        elif sub == 0x1: self.wr16(self.gbr + d * 2, r[0])
        elif sub == 0x2: self.wr32(self.gbr + d * 4, r[0])
        elif sub == 0x4: r[0] = s8(self.rd8(self.gbr + d)) & 0xffffffff
        elif sub == 0x5: r[0] = s16(self.rd16(self.gbr + d * 2)) & 0xffffffff
        elif sub == 0x6: r[0] = self.rd32(self.gbr + d * 4)
        elif sub == 0x7: r[0] = ((pc + 4) & ~3) + d * 4
        elif sub == 0x8: self.setT((r[0] & d) == 0)
        elif sub == 0x9: r[0] &= d
        elif sub == 0xA: r[0] ^= d
        elif sub == 0xB: r[0] |= d
        elif sub == 0xC: self.setT((self.rd8(self.gbr + r[0]) & d) == 0)
        elif sub == 0xD: self.wr8(self.gbr + r[0], self.rd8(self.gbr + r[0]) & d)
        elif sub == 0xE: self.wr8(self.gbr + r[0], self.rd8(self.gbr + r[0]) ^ d)
        elif sub == 0xF: self.wr8(self.gbr + r[0], self.rd8(self.gbr + r[0]) | d)
        else: self.bad(op, pc)
    def opf(self, op, pc, n, m):
        lo = op & 15; sz = bool(self.fpscr & 0x100); r = self.r
        if lo == 0xC:
            if sz: self.setFR(n & ~1, self.FR(m & ~1)); self.setFR(n | 1, self.FR(m | 1))
            else: self.setFR(n, self.FR(m))
            return
        if lo == 8:
            if sz: self.setFR(n & ~1, self.rd32(r[m])); self.setFR(n | 1, self.rd32(r[m] + 4))
            else: self.setFR(n, self.rd32(r[m]))
            return
        if lo == 9:
            if sz: self.setFR(n & ~1, self.rd32(r[m])); self.setFR(n | 1, self.rd32(r[m] + 4)); r[m] = (r[m] + 8) & 0xffffffff
            else: self.setFR(n, self.rd32(r[m])); r[m] = (r[m] + 4) & 0xffffffff
            return
        if lo == 0xA:
            if sz: self.wr32(r[n], self.FR(m & ~1)); self.wr32(r[n] + 4, self.FR(m | 1))
            else: self.wr32(r[n], self.FR(m))
            return
        if lo == 0xB:
            if sz: r[n] = (r[n] - 8) & 0xffffffff; self.wr32(r[n], self.FR(m & ~1)); self.wr32(r[n] + 4, self.FR(m | 1))
            else: r[n] = (r[n] - 4) & 0xffffffff; self.wr32(r[n], self.FR(m))
            return
        if lo == 6:
            a = r[0] + r[m]
            if sz: self.setFR(n & ~1, self.rd32(a)); self.setFR(n | 1, self.rd32(a + 4))
            else: self.setFR(n, self.rd32(a))
            return
        if lo == 7:
            a = r[0] + r[n]
            if sz: self.wr32(a, self.FR(m & ~1)); self.wr32(a + 4, self.FR(m | 1))
            else: self.wr32(a, self.FR(m))
            return
        a, b = self.fget(n), self.fget(m)
        with np.errstate(all='ignore'):
            if lo == 0: self.fset(n, a + b)
            elif lo == 1: self.fset(n, a - b)
            elif lo == 2: self.fset(n, a * b)
            elif lo == 3: self.fset(n, a / b)
            elif lo == 4: self.setT(a == b)
            elif lo == 5: self.setT(a > b)
            elif lo == 0xE: self.fset(n, f32(self.fget(0) * b) + a)
            elif lo == 0xD:
                sub = (op >> 4) & 15
                if sub == 0: self.setFR(n, self.fpul)
                elif sub == 1: self.fpul = self.FR(n)
                elif sub == 2: self.fset(n, f32(s32(self.fpul)))
                elif sub == 3:
                    v = float(a)
                    if v != v: iv = 0x80000000
                    elif v >= 2147483648.0: iv = 0x7fffffff
                    elif v <= -2147483648.0: iv = 0x80000000
                    else: iv = int(v) & 0xffffffff
                    self.fpul = iv
                elif sub == 4: self.setFR(n, self.FR(n) ^ 0x80000000)
                elif sub == 5: self.setFR(n, self.FR(n) & 0x7fffffff)
                elif sub == 6: self.fset(n, np.sqrt(a))
                elif sub == 7: self.fset(n, f32(1.0) / np.sqrt(a))
                elif sub == 8: self.setFR(n, 0)
                elif sub == 9: self.setFR(n, 0x3f800000)
                else: self.bad(op, pc)
            else: self.bad(op, pc)
