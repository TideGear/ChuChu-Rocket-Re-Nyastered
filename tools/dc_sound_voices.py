"""MANATEE voice allocation, original ARM 0x16f0..0x1804.

Records are the driver's 64-byte voice records, not AICA channel registers.
Selection does not mutate records; subsequent note setup owns that work.
"""
from dataclasses import dataclass
import struct


@dataclass(frozen=True)
class Allocation:
    status: int
    voice_address: int
    register_address: int

    def index(self, count):
        offset = self.voice_address - 0x10000
        if self.status or offset < 0 or offset % 64 or offset // 64 >= count:
            return None
        index = offset // 64
        return index if self.register_address == 0x800000 + index * 128 else None


def allocate_voice(records, priority, low_ram):
    if not 1 <= len(records) <= 64 or any(len(record) != 64 for record in records):
        raise ValueError('Expected 1..64 complete driver voice records')
    if not isinstance(priority, int) or not 0 <= priority <= 255:
        raise ValueError('Priority must be a byte')
    if len(low_ram) < 264:
        raise ValueError('Allocator needs the original low-RAM words for raw return behavior')
    candidate = None
    for index, voice in enumerate(records):
        if voice[:4] == bytes(4):
            return Allocation(0, 0x10000 + index * 64, 0x800000 + index * 128)
        if priority < voice[0x3e]:
            continue
        if candidate is not None:
            previous = records[candidate]
            if previous[0x3f]:
                if voice[0] & 0xe0:
                    if previous[0x3e] < voice[0x3e] or voice[0x3f] < previous[0x3f]:
                        continue
            else:
                if voice[0] & 0xe0:
                    continue
                if previous[3] < voice[3]:
                    continue
                if previous[3] == voice[3] and voice[0x3e] < previous[0x3e]:
                    continue
        candidate = index
    if priority < records[-1][0x3e]:
        # At 0x1734 BMI skips restoration of r1 to the candidate scratch record.
        # 0x17f0/0x17f4 then load from r1=priority, with ARM7 word rotation.
        def read(address):
            value = struct.unpack_from('<I', low_ram, address & ~3)[0]
            shift = (address & 3) * 8
            return ((value >> shift) | (value << ((32 - shift) & 31))) & 0xffffffff
        voice, registers = read(priority), read(priority + 4)
        return Allocation(0 if voice else 255, voice, registers)
    if candidate is None:
        return Allocation(255, 0, 0)
    return Allocation(0, 0x10000 + candidate * 64, 0x800000 + candidate * 128)
