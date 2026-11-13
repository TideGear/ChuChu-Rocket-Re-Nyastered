"""Minimal GBA harness (development only): runs the user's own ROM under Unicorn (ARM7TDMI) with just enough hardware for the game logic:
memory map, IO register file, DMA (immediate), BIOS SWI services (HLE), keypad, VBlank IRQ delivered at frame waits. No video/audio output.
usage: g = GBA(rom_path); g.run_frames(n, keys=0)"""
import struct, sys
from unicorn import UC_HOOK_MEM_WRITE_PROT, UC_PROT_READ, UC_PROT_ALL
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_INTR, UC_HOOK_MEM_WRITE, UC_HOOK_MEM_READ, UC_HOOK_CODE, UC_HOOK_MEM_UNMAPPED
from unicorn.arm_const import *

IO = 0x04000000; ROM = 0x08000000; STOPADDR = 0x00000F00
KEY_A, KEY_B, KEY_SELECT, KEY_START, KEY_RIGHT, KEY_LEFT, KEY_UP, KEY_DOWN, KEY_R, KEY_L = [1 << i for i in range(10)]

class GBA:
    def __init__(self, path):
        self.rom = open(path, 'rb').read()
        self.uc = uc = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        uc.mem_map(0x00000000, 0x4000)                    # BIOS area (stub)
        import ctypes
        self._iw = (ctypes.c_char * 0x8000)()                 # IWRAM, aliased at 0x03000000 and at the top mirror 0x03FF8000 (stack/IRQ vector are used through it)
        uc.mem_map_ptr(0x03000000, 0x8000, 7, ctypes.addressof(self._iw)); uc.mem_map_ptr(0x03FF8000, 0x8000, 7, ctypes.addressof(self._iw))
        uc.mem_map(0x02000000, 0x40000); uc.mem_map(IO, 0x1000)
        uc.mem_map(0x05000000, 0x1000); uc.mem_map(0x06000000, 0x20000); uc.mem_map(0x07000000, 0x1000)
        for base in (0x08000000, 0x0A000000, 0x0C000000):
            uc.mem_map(base, 0x2000000)
            uc.mem_write(base, self.rom)
        uc.mem_map(0x0E000000, 0x10000, UC_PROT_READ)               # Flash 64 KB: writes are intercepted by a small command state machine
        uc.mem_write(0x0E000000, bytes([255]) * 0x10000)
        self.flash = bytearray(bytes([255]) * 0x10000); self.fstate = 0; self.fmode = None; self.fid = False
        uc.hook_add(UC_HOOK_MEM_WRITE_PROT, self._flash_write)
        uc.mem_write(STOPADDR, b'\x00' * 4)
        self.keys = 0; self.frame = 0; self.vcount = 0; self.unknown = {}; self.halted = False; self.in_irq = False
        uc.mem_write(IO + 0x130, struct.pack('<H', 0x03ff))
        uc.hook_add(UC_HOOK_INTR, self._intr)
        uc.hook_add(UC_HOOK_CODE, lambda u, a, sz, d: u.emu_stop(), begin=STOPADDR, end=STOPADDR + 3)       # return stub for HLE calls
        uc.hook_add(UC_HOOK_MEM_UNMAPPED, self._unmapped)
        uc.hook_add(UC_HOOK_MEM_WRITE, self._iowrite, begin=IO, end=IO + 0x3ff)
        uc.hook_add(UC_HOOK_MEM_READ, self._ioread, begin=IO, end=IO + 0x3ff)
        # registers at reset: SVC mode, IRQ disabled, stacks
        uc.reg_write(UC_ARM_REG_CPSR, 0xD3); uc.reg_write(UC_ARM_REG_SP, 0x03007FE0); uc.reg_write(UC_ARM_REG_PC, ROM)
        self.pc = ROM
    def _flash_write(self, uc, access, addr, size, value, user):
        if not (0x0E000000 <= addr < 0x0E010000): return False
        a = addr & 0xffff; v = value & 0xff; f = self.flash
        if self.fmode == 'program': f[a] &= v; uc.mem_write(0x0E000000 + a, bytes([f[a]])); self.fmode = None; return True
        if self.fmode == 'bank': self.fmode = None; return True
        if self.fstate == 0 and a == 0x5555 and v == 0xAA: self.fstate = 1
        elif self.fstate == 1 and a == 0x2AAA and v == 0x55: self.fstate = 2
        elif self.fstate == 2:
            self.fstate = 0
            if a == 0x5555:
                if v == 0x90: self.fid = True; uc.mem_write(0x0E000000, bytes([0xC2, 0x1C]))                 # Macronix 64K ID
                elif v == 0xF0: self.fid = False; uc.mem_write(0x0E000000, bytes(f[0:2]))
                elif v == 0x80: self.fmode = 'erase'; self.fstate = 3
                elif v == 0xA0: self.fmode = 'program'
                elif v == 0xB0: self.fmode = 'bank'
            elif self.fmode == 'erase' and v == 0x30: pass
        elif self.fstate == 3:                                   # after 0x80: AA 55 then 0x10 (chip) / 0x30 (sector)
            if a == 0x5555 and v == 0xAA: self.fstate = 4
            else: self.fstate = 0; self.fmode = None
        elif self.fstate == 4:
            self.fstate = 5 if (a == 0x2AAA and v == 0x55) else 0
        elif self.fstate == 5:
            if a == 0x5555 and v == 0x10: f[:] = bytes([255]) * 0x10000; uc.mem_write(0x0E000000, bytes(f))
            elif v == 0x30: base = a & 0xf000; f[base:base + 0x1000] = bytes([255]) * 0x1000; uc.mem_write(0x0E000000 + base, bytes([255]) * 0x1000)
            self.fstate = 0; self.fmode = None
        else: self.fstate = 0
        return True
    def _unmapped(self, uc, access, addr, size, value, user):
        print('unmapped access', access, hex(addr), 'pc', hex(uc.reg_read(UC_ARM_REG_PC))); return False
    # ---- helpers ----
    def r32(self, a): return struct.unpack('<I', self.uc.mem_read(a, 4))[0]
    def r16(self, a): return struct.unpack('<H', self.uc.mem_read(a, 2))[0]
    def r8(self, a): return self.uc.mem_read(a, 1)[0]
    def w32(self, a, v): self.uc.mem_write(a, struct.pack('<I', v & 0xffffffff))
    def w16(self, a, v): self.uc.mem_write(a, struct.pack('<H', v & 0xffff))
    # ---- IO ----
    def _ioread(self, uc, access, addr, size, value, user):
        if addr == IO + 6:                               # VCOUNT: cycles so busy-wait loops terminate
            self.vcount = (self.vcount + 1) % 228; uc.mem_write(IO + 6, struct.pack('<H', self.vcount))
        elif addr == IO + 4:                             # DISPSTAT: toggle vblank flag with vcount
            uc.mem_write(IO + 4, struct.pack('<H', (self.r16(IO + 4) & ~7) | (1 if 160 <= self.vcount < 227 else 0)))
    def _iowrite(self, uc, access, addr, size, value, user):
        if addr == IO + 0x202:                           # IF: write 1 to clear
            cur = self.r16(IO + 0x202)
            uc.mem_write(IO + 0x202, struct.pack('<H', cur))        # emulate below after write completes
            self._if_clear = value & 0xffff; self._if_before = cur
        for ch in range(4):                              # DMA control high halfword (+0xA): start on enable with immediate timing
            ctl = IO + 0xB0 + ch * 12 + 8
            if addr in (ctl, ctl + 2):
                self._dma_pending = ch
    def _post_write(self):
        pass
    def _dma(self, ch):
        b = IO + 0xB0 + ch * 12
        src, dst, cnt, ctl = self.r32(b), self.r32(b + 4), self.r16(b + 8), self.r16(b + 10)
        if not (ctl & 0x8000) or ((ctl >> 12) & 3) != 0: return
        n = cnt if cnt else (0x10000 if ch == 3 else 0x4000); w = 4 if ctl & 0x400 else 2
        dctl, sctl = (ctl >> 5) & 3, (ctl >> 7) & 3
        for i in range(n):
            self.uc.mem_write(dst, bytes(self.uc.mem_read(src, w)))
            dst += (w if dctl in (0, 3) else -w if dctl == 1 else 0); src += (w if sctl == 0 else -w if sctl == 1 else 0)
        self.uc.mem_write(b + 10, struct.pack('<H', ctl & 0x7fff))
    # ---- BIOS HLE ----
    def _intr(self, uc, intno, user):
        pc = uc.reg_read(UC_ARM_REG_PC); cpsr = uc.reg_read(UC_ARM_REG_CPSR); thumb = bool(cpsr & 0x20)
        num = (self.r8(pc - 2) if thumb else self.r8(pc - 4 + 2))          # comment field: low byte (thumb) / bits 16-23 (arm)
        r = [uc.reg_read(UC_ARM_REG_R0 + i) for i in range(4)]
        if num in (2, 4, 5):                             # Halt / IntrWait / VBlankIntrWait: end of frame
            self.frame_end = True; self.pc_after = pc | (1 if thumb else 0); uc.emu_stop(); return
        elif num == 6:
            a, b = self._s32(r[0]), self._s32(r[1]); q = int(a / b) if b else 0
            uc.reg_write(UC_ARM_REG_R0, q & 0xffffffff); uc.reg_write(UC_ARM_REG_R1, (a - q * b) & 0xffffffff); uc.reg_write(UC_ARM_REG_R3, abs(q))
        elif num == 7:
            a, b = self._s32(r[1]), self._s32(r[0]); q = int(a / b) if b else 0
            uc.reg_write(UC_ARM_REG_R0, q & 0xffffffff); uc.reg_write(UC_ARM_REG_R1, (a - q * b) & 0xffffffff); uc.reg_write(UC_ARM_REG_R3, abs(q))
        elif num == 8:
            import math; uc.reg_write(UC_ARM_REG_R0, int(math.isqrt(r[0] & 0xffffffff)))
        elif num in (0x0A,):                             # ArcTan2 (0x0000..0xFFFF over 2pi)
            import math; x, y = self._s32(r[0]), self._s32(r[1]); a = math.atan2(y, x); uc.reg_write(UC_ARM_REG_R0, int((a / (2 * math.pi)) * 0x10000) & 0xffff)
        elif num == 9:
            import math; t = self._s32(r[0]) / 16384.0; uc.reg_write(UC_ARM_REG_R0, int(math.atan(t) / (2 * math.pi) * 0x10000) & 0xffff)
        elif num == 0x0B:                                # CpuSet
            src, dst, ctl = r[0], r[1], r[2]; n = ctl & 0x1fffff; w = 4 if ctl & (1 << 26) else 2; fill = bool(ctl & (1 << 24))
            if fill: v = bytes(uc.mem_read(src, w)); uc.mem_write(dst, v * n)
            else: uc.mem_write(dst, bytes(uc.mem_read(src, n * w)))
        elif num == 0x0C:                                # CpuFastSet
            src, dst, ctl = r[0], r[1], r[2]; n = (ctl & 0x1fffff + 7) & ~7 if False else ((ctl & 0x1fffff) + 7) & ~7
            if ctl & (1 << 24): uc.mem_write(dst, bytes(uc.mem_read(src, 4)) * n)
            else: uc.mem_write(dst, bytes(uc.mem_read(src, n * 4)))
        elif num in (0x11, 0x12):                        # LZ77UnComp
            self._lz77(r[0], r[1])
        elif num in (0x14, 0x15):                        # RLUnComp
            self._rl(r[0], r[1])
        elif num in (0x00, 0x01, 0x03, 0x1F, 0x19, 0x1A, 0x1B, 0x1C, 0x1D, 0x1E, 0x10, 0x13, 0x16, 0x17, 0x18, 0x0D, 0x0E, 0x0F): self.unknown[num] = self.unknown.get(num, 0) + 1
        else: self.unknown[num] = self.unknown.get(num, 0) + 1
    @staticmethod
    def _s32(u): u &= 0xffffffff; return u - (1 << 32) if u & 0x80000000 else u
    def _lz77(self, src, dst):
        hdr = self.r32(src); size = hdr >> 8; src += 4; out = bytearray()
        while len(out) < size:
            flags = self.r8(src); src += 1
            for i in range(8):
                if len(out) >= size: break
                if flags & (0x80 >> i):
                    b1, b2 = self.r8(src), self.r8(src + 1); src += 2; ln = (b1 >> 4) + 3; disp = (((b1 & 15) << 8) | b2) + 1
                    for _ in range(ln): out.append(out[-disp])
                else: out.append(self.r8(src)); src += 1
        self.uc.mem_write(dst, bytes(out[:size]))
    def _rl(self, src, dst):
        hdr = self.r32(src); size = hdr >> 8; src += 4; out = bytearray()
        while len(out) < size:
            f = self.r8(src); src += 1
            if f & 0x80: n = (f & 0x7f) + 3; out += bytes([self.r8(src)]) * n; src += 1
            else: n = (f & 0x7f) + 1; out += bytes(self.uc.mem_read(src, n)); src += n
        self.uc.mem_write(dst, bytes(out[:size]))
    # ---- running ----
    def _run_to_frame_end(self):
        self.frame_end = False; self._dma_pending = None
        pc = self.pc
        while True:
            cpsr = self.uc.reg_read(UC_ARM_REG_CPSR)
            self.uc.emu_start(pc, 0xFFFFFFF0, count=20_000_000)
            if self._dma_pending is not None: ch = self._dma_pending; self._dma_pending = None; self._dma(ch); pc = self.uc.reg_read(UC_ARM_REG_PC) | (1 if self.uc.reg_read(UC_ARM_REG_CPSR) & 0x20 else 0); continue
            break
        if self.frame_end: self.pc = self.pc_after
        else: self.pc = self.uc.reg_read(UC_ARM_REG_PC) | (1 if self.uc.reg_read(UC_ARM_REG_CPSR) & 0x20 else 0)
    def _vblank_irq(self):
        ime = self.r16(IO + 0x208) & 1; ie = self.r16(IO + 0x200); dispstat = self.r16(IO + 4)
        self.w16(IO + 0x202, self.r16(IO + 0x202) | 1)
        if not (ime and (ie & 1) and (dispstat & 8)): return
        handler = self.r32(0x03007FFC)
        if handler < 0x02000000: return
        uc = self.uc; REGS = [UC_ARM_REG_R0 + i for i in range(13)] + [UC_ARM_REG_SP, UC_ARM_REG_LR]; saved = [uc.reg_read(r) for r in REGS]; scpsr = uc.reg_read(UC_ARM_REG_CPSR)
        uc.reg_write(UC_ARM_REG_CPSR, 0xD2 if False else (scpsr & ~0x3f) | 0x1f | 0x80); uc.reg_write(UC_ARM_REG_SP, 0x03007F00 - 0x400)
        uc.reg_write(UC_ARM_REG_R0, IO); uc.reg_write(UC_ARM_REG_LR, STOPADDR)
        uc.emu_start(handler, 0xFFFFFFF0, count=2_000_000)
        for r, v in zip(REGS, saved): uc.reg_write(r, v)
        uc.reg_write(UC_ARM_REG_CPSR, scpsr)
    def run_frames(self, n, keys=None):
        for _ in range(n):
            if keys is not None: self.keys = keys
            self.uc.mem_write(IO + 0x130, struct.pack('<H', (~self.keys) & 0x3ff))
            self._run_to_frame_end()
            self.vcount = 160; self.w16(IO + 4, self.r16(IO + 4) | 1)
            self._vblank_irq(); self.frame += 1
            self.vcount = 0

if __name__ == '__main__':
    g = GBA(sys.argv[1]); g.run_frames(int(sys.argv[2]) if len(sys.argv) > 2 else 120)
    print('frames', g.frame, 'pc', hex(g.pc), 'DISPCNT', hex(g.r16(IO)), 'unknown SWIs', g.unknown)
