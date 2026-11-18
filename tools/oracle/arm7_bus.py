"""ARM7 word-access semantics missing from Unicorn's ordinary memory accesses.

ARM7 word stores align down; unaligned word loads rotate the aligned word.
Unicorn instead accesses consecutive bytes even with its TI925T CPU model.
These hooks correct data accesses while leaving the original instructions intact.
Used only for mapped sound RAM in the Dreamcast driver probes. Call flush()
after a bounded emulation stop before inspecting memory.
"""
import struct

from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE, UC_MEM_READ, UC_MEM_WRITE


class Arm7Bus:
    def __init__(self, uc):
        self.uc = uc
        self.pending = None
        self.reads = self.writes = 0
        self.hooks = (
            uc.hook_add(UC_HOOK_CODE, self.before_instruction),
            uc.hook_add(UC_HOOK_MEM_READ | UC_HOOK_MEM_WRITE, self.access),
        )

    def flush(self):
        if self.pending is not None:
            address, data = self.pending
            self.pending = None
            self.uc.mem_write(address, data)

    def before_instruction(self, uc, address, size, context):
        self.flush()

    def access(self, uc, operation, address, size, value, context):
        self.flush()
        if size != 4 or not address & 3 or address >= 0x800000:
            return
        aligned = address & ~3
        if operation == UC_MEM_READ:
            original = bytes(uc.mem_read(address, 4))
            word = struct.unpack('<I', uc.mem_read(aligned, 4))[0]
            shift = (address & 3) * 8
            rotated = ((word >> shift) | (word << (32 - shift))) & 0xffffffff
            uc.mem_write(address, struct.pack('<I', rotated))
            self.pending = address, original
            self.reads += 1
        elif operation == UC_MEM_WRITE:
            after = bytes(uc.mem_read(aligned + 4, 4))
            self.pending = aligned, struct.pack('<I', value & 0xffffffff) + after
            self.writes += 1
