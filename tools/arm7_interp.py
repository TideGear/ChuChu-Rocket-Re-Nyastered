"""Minimal pure-Python ARM7 (ARMv4, ARM state) interpreter for the Dreamcast sound driver MANATEE.DRV.

Runs the original driver's own code (no Unicorn, stdlib only) so setup can derive driver state from the disc.
Memory is the AICA's 2 MiB sound RAM (accesses wrap at 2 MiB) and the 0x800000 AICA register block (plain bytes;
ARM7 word semantics: stores align down, unaligned loads rotate). Modes, interrupts and coprocessors are not modeled:
unsupported instructions and accesses raise instead of continuing.
Validated against Unicorn at the driver main-loop entry (tools/oracle/dc_arm_init_probe.py).
"""
import struct

RAM_SIZE = 0x200000
REG_BASE = 0x800000
REG_SIZE = 0x8000


class ArmError(Exception):
    pass


class Arm7:
    def __init__(self, ram, registers=None):
        if len(ram) != RAM_SIZE:
            raise ValueError('Expected 2 MiB sound RAM')
        self.ram = ram if isinstance(ram, bytearray) else bytearray(ram)
        self.regs_mem = bytearray(REG_SIZE) if registers is None else bytearray(registers)
        self.r = [0] * 16
        self.n = self.z = self.c = self.v = 0
        self.cpsr_low = 0x13          # supervisor mode; only the interrupt-disable bits are tracked
        self.steps = 0
        self.reads = []               # (address, size) of AICA register reads, for callers that need them

    # ---- memory -----------------------------------------------------------------------------------------------
    def _region(self, address, size):
        if address < RAM_SIZE:
            if address + size > RAM_SIZE:
                raise ArmError('RAM access crosses the end at 0x%x' % address)
            return self.ram, address
        if REG_BASE <= address < REG_BASE + REG_SIZE:
            return self.regs_mem, address - REG_BASE
        raise ArmError('Unmapped ARM access at 0x%x' % address)

    def read(self, address, size):
        address &= 0xffffffff
        if size == 4:
            mem, at = self._region(address & ~3, 4)
            if mem is self.regs_mem:
                self.reads.append((address & ~3, 4))
            word = struct.unpack_from('<I', mem, at)[0]
            shift = (address & 3) * 8
            return ((word >> shift) | (word << (32 - shift))) & 0xffffffff if shift else word
        if size == 2:
            mem, at = self._region(address & ~1, 2)
            if mem is self.regs_mem:
                self.reads.append((address & ~1, 2))
            return struct.unpack_from('<H', mem, at)[0]
        mem, at = self._region(address, 1)
        if mem is self.regs_mem:
            self.reads.append((address, 1))
        return mem[at]

    def write(self, address, size, value):
        address &= 0xffffffff
        if size == 4:
            mem, at = self._region(address & ~3, 4)
            if mem is self.regs_mem:      # arm_mem.cpp writeReg<u32> stores only the low halfword
                struct.pack_into('<H', mem, at, value & 0xffff)
            else:
                struct.pack_into('<I', mem, at, value & 0xffffffff)
        elif size == 2:
            mem, at = self._region(address & ~1, 2)
            struct.pack_into('<H', mem, at, value & 0xffff)
        else:
            mem, at = self._region(address, 1)
            mem[at] = value & 0xff

    # ---- helpers ------------------------------------------------------------------------------------------------
    def _cond(self, cond):
        if cond == 14:
            return True
        n, z, c, v = self.n, self.z, self.c, self.v
        return (z, not z, c, not c, n, not n, v, not v, c and not z, (not c) or z, n == v, n != v,
                (not z) and n == v, z or n != v)[cond]

    def _flags(self, result):
        self.n = result >> 31 & 1
        self.z = int(result & 0xffffffff == 0)

    def _shift(self, value, kind, amount, by_register):
        c = self.c
        if kind == 0:     # LSL
            if amount == 0:
                return value, c
            if amount < 32:
                return (value << amount) & 0xffffffff, value >> (32 - amount) & 1
            return 0, (value & 1) if amount == 32 else 0
        if kind == 1:     # LSR
            if amount == 0 and not by_register:
                amount = 32
            if amount == 0:
                return value, c
            if amount < 32:
                return value >> amount, value >> (amount - 1) & 1
            return 0, (value >> 31) if amount == 32 else 0
        if kind == 2:     # ASR
            if amount == 0 and not by_register:
                amount = 32
            if amount == 0:
                return value, c
            if amount < 32:
                return ((value - (1 << 32) if value >> 31 else value) >> amount) & 0xffffffff, value >> (amount - 1) & 1
            return (0xffffffff if value >> 31 else 0), value >> 31
        if amount == 0 and not by_register:   # RRX
            return (value >> 1) | (c << 31), value & 1
        if amount == 0:
            return value, c
        amount &= 31
        if amount == 0:
            return value, value >> 31
        return ((value >> amount) | (value << (32 - amount))) & 0xffffffff, value >> (amount - 1) & 1

    def _reg(self, index, pc):
        return (pc + 8) & 0xffffffff if index == 15 else self.r[index]

    # ---- execution ----------------------------------------------------------------------------------------------
    def run(self, pc, stop, limit=50_000_000):
        """Execute from pc until pc == stop (a set or int); return the stop address."""
        stops = {stop} if isinstance(stop, int) else set(stop)
        r = self.r
        for _ in range(limit):
            if pc in stops:
                r[15] = pc
                return pc
            pc = self.step(pc)
        raise ArmError('Instruction limit reached at 0x%x' % pc)

    def step(self, pc):
        self.steps += 1
        ins = struct.unpack_from('<I', self.ram, pc)[0]
        cond = ins >> 28
        if cond == 15 or not self._cond(cond):
            return pc + 4
        r = self.r
        kind = ins >> 25 & 7
        if kind == 0 and ins & 0x90 == 0x90:
            if ins & 0x60 == 0:        # multiply / swap
                if ins & 0x0fc000f0 == 0x00000090:
                    rd, rn, rs, rm = ins >> 16 & 15, ins >> 12 & 15, ins >> 8 & 15, ins & 15
                    value = (r[rm] * r[rs] + (r[rn] if ins & 0x200000 else 0)) & 0xffffffff
                    r[rd] = value
                    if ins & 0x100000:
                        self._flags(value)
                    return pc + 4
                if ins & 0x0f8000f0 == 0x00800090:
                    rdhi, rdlo, rs, rm = ins >> 16 & 15, ins >> 12 & 15, ins >> 8 & 15, ins & 15
                    a, b = r[rm], r[rs]
                    if ins & 0x400000:
                        a, b = (a - (1 << 32) if a >> 31 else a), (b - (1 << 32) if b >> 31 else b)
                    value = a * b
                    if ins & 0x200000:
                        value += r[rdhi] << 32 | r[rdlo]
                    value &= (1 << 64) - 1
                    r[rdlo], r[rdhi] = value & 0xffffffff, value >> 32
                    if ins & 0x100000:
                        self.n, self.z = value >> 63, int(value == 0)
                    return pc + 4
                if ins & 0x0fb00ff0 == 0x01000090:     # SWP/SWPB
                    rn, rd, rm = ins >> 16 & 15, ins >> 12 & 15, ins & 15
                    size = 1 if ins & 0x400000 else 4
                    old = self.read(r[rn], size)
                    self.write(r[rn], size, r[rm])
                    r[rd] = old
                    return pc + 4
                raise ArmError('Unsupported multiply/swap 0x%08x at 0x%x' % (ins, pc))
            return self._halfword(ins, pc)
        if kind in (0, 1):
            if ins >> 23 & 3 == 2 and not ins >> 20 & 1:    # MRS / MSR (status registers; only the low byte is kept)
                if ins & 0x0fbf0fff == 0x010f0000:
                    r[ins >> 12 & 15] = self.n << 31 | self.z << 30 | self.c << 29 | self.v << 28 | self.cpsr_low
                    return pc + 4
                if ins & 0x0db0f000 == 0x0120f000 and not ins & 0x400000:
                    if ins & 0x02000000:
                        rot = (ins >> 8 & 15) * 2
                        value = ((ins & 255) >> rot | (ins & 255) << (32 - rot)) & 0xffffffff if rot else ins & 255
                    else:
                        value = r[ins & 15]
                    if ins & 0x80000:
                        self.n, self.z, self.c, self.v = value >> 31 & 1, value >> 30 & 1, value >> 29 & 1, value >> 28 & 1
                    if ins & 0x10000:
                        if value & 0x1f != 0x13:
                            raise ArmError('Mode change needs banked registers at 0x%x' % pc)
                        self.cpsr_low = value & 0xff
                    return pc + 4
                raise ArmError('Unsupported status-register instruction 0x%08x at 0x%x' % (ins, pc))
            return self._data(ins, pc)
        if kind in (2, 3):
            if kind == 3 and ins & 0x10:
                raise ArmError('Undefined instruction 0x%08x at 0x%x' % (ins, pc))
            return self._single(ins, pc)
        if kind == 4:
            return self._block(ins, pc)
        if kind == 5:
            offset = ((ins & 0xffffff) ^ 0x800000) - 0x800000
            if ins & 0x1000000:
                r[14] = pc + 4
            return (pc + 8 + offset * 4) & 0xffffffff
        raise ArmError('Unsupported instruction 0x%08x at 0x%x' % (ins, pc))

    def _data(self, ins, pc):
        r = self.r
        opcode, s = ins >> 21 & 15, ins >> 20 & 1
        rn, rd = ins >> 16 & 15, ins >> 12 & 15
        if ins & 0x02000000:
            rot = (ins >> 8 & 15) * 2
            imm = ins & 255
            op2 = ((imm >> rot) | (imm << (32 - rot))) & 0xffffffff if rot else imm
            shifter_carry = op2 >> 31 if rot else self.c
        else:
            rm = ins & 15
            by_register = bool(ins & 0x10)
            if by_register:
                amount = r[ins >> 8 & 15] & 255
                value = (pc + 12) & 0xffffffff if rm == 15 else r[rm]
            else:
                amount = ins >> 7 & 31
                value = self._reg(rm, pc)
            op2, shifter_carry = self._shift(value, ins >> 5 & 3, amount, by_register)
        if opcode in (13, 15):
            a = 0
        else:
            a = (pc + (12 if (not ins & 0x02000000 and ins & 0x10) else 8)) & 0xffffffff if rn == 15 else r[rn]
        mask = 0xffffffff
        carry_in = self.c
        arith = None
        if opcode in (0, 8):
            result = a & op2
        elif opcode in (1, 9):
            result = a ^ op2
        elif opcode in (2, 10):
            arith = (a, (~op2) & mask, 1)
        elif opcode == 3:
            arith = (op2, (~a) & mask, 1)
        elif opcode in (4, 11):
            arith = (a, op2, 0)
        elif opcode == 5:
            arith = (a, op2, carry_in)
        elif opcode == 6:
            arith = (a, (~op2) & mask, carry_in)
        elif opcode == 7:
            arith = (op2, (~a) & mask, carry_in)
        elif opcode == 12:
            result = a | op2
        elif opcode == 13:
            result = op2
        elif opcode == 14:
            result = a & ~op2 & mask
        else:
            result = (~op2) & mask
        if arith is not None:
            x, y, cin = arith
            total = x + y + cin
            result = total & mask
            carry = total >> 32
            overflow = ((x ^ result) & (y ^ result)) >> 31 & 1
        if s:
            if rd == 15 and opcode not in (8, 9, 10, 11):
                raise ArmError('S-suffixed write to PC needs mode handling at 0x%x' % pc)
            self._flags(result)
            if arith is not None:
                self.c, self.v = carry, overflow
            else:
                self.c = shifter_carry
        if opcode in (8, 9, 10, 11):
            return pc + 4
        if rd == 15:
            return result & 0xfffffffc
        r[rd] = result
        return pc + 4

    def _single(self, ins, pc):
        r = self.r
        rn, rd = ins >> 16 & 15, ins >> 12 & 15
        load, byte, pre, up, wb = ins >> 20 & 1, ins >> 22 & 1, ins >> 24 & 1, ins >> 23 & 1, ins >> 21 & 1
        if ins & 0x02000000:
            offset, _ = self._shift(self._reg(ins & 15, pc), ins >> 5 & 3, ins >> 7 & 31, False)
        else:
            offset = ins & 0xfff
        base = self._reg(rn, pc)
        target = (base + offset if up else base - offset) & 0xffffffff
        address = target if pre else base
        size = 1 if byte else 4
        if load:
            value = self.read(address, size)
        else:
            value = (pc + 12) & 0xffffffff if rd == 15 else r[rd]
            self.write(address, size, value)
        if (not pre) or wb:
            if rn != rd or not load:
                r[rn] = target
        if load:
            if rd == 15:
                return value & 0xfffffffc
            r[rd] = value
        return pc + 4

    def _halfword(self, ins, pc):
        r = self.r
        rn, rd = ins >> 16 & 15, ins >> 12 & 15
        load, pre, up, wb = ins >> 20 & 1, ins >> 24 & 1, ins >> 23 & 1, ins >> 21 & 1
        sh = ins >> 5 & 3
        offset = (ins >> 4 & 0xf0 | ins & 15) if ins & 0x400000 else r[ins & 15]
        base = self._reg(rn, pc)
        target = (base + offset if up else base - offset) & 0xffffffff
        address = target if pre else base
        if not load:
            if sh == 1:
                self.write(address, 2, r[rd])
            elif sh in (2, 3):
                raise ArmError('LDRD/STRD is not ARMv4 at 0x%x' % pc)
        else:
            if sh == 1:
                value = self.read(address, 2)
            elif sh == 2:
                value = self.read(address, 1)
                value = value | 0xffffff00 if value & 0x80 else value
            else:
                value = self.read(address, 2)
                value = value | 0xffff0000 if value & 0x8000 else value
            r[rd] = value
        if (not pre) or wb:
            if not load or rn != rd:
                r[rn] = target
        return pc + 4

    def _block(self, ins, pc):
        r = self.r
        rn = ins >> 16 & 15
        listing = [i for i in range(16) if ins >> i & 1]
        load, pre, up, wb = ins >> 20 & 1, ins >> 24 & 1, ins >> 23 & 1, ins >> 21 & 1
        if ins & 0x400000:
            raise ArmError('S-bit block transfer needs mode handling at 0x%x' % pc)
        count = len(listing)
        base = r[rn]
        low = base if up else base - 4 * count
        if pre == up:
            low += 4
        final = base + 4 * count if up else base - 4 * count
        address = low
        next_pc = pc + 4
        for index in listing:
            if load:
                value = self.read(address, 4)
                if index == 15:
                    next_pc = value & 0xfffffffc
                else:
                    r[index] = value
            else:
                self.write(address, 4, (pc + 12) & 0xffffffff if index == 15 else r[index])
            address += 4
        if wb and not (load and rn in listing):
            r[rn] = final & 0xffffffff
        return next_pc
