"""MANATEE sequence timing arithmetic, in original fixed-point units.

Header setup: ARM 0x89a0..0x89c0. Tempo event: 0x6f60..0x6f80.
Step advancement: 0x711c..0x7140. Multiplication wraps before shifting.
This does not map driver updates to audio samples or allocate voices.
"""
from dataclasses import dataclass
import struct


def word(value):
    if not isinstance(value, int) or not 0 <= value <= 0xffffffff:
        raise ValueError('Expected an unsigned 32-bit timing word')
    return value


def start_inactive_context(context, bank, bank_address, index, priority, clock):
    """Apply successful ARM 0x891c sequence start to an inactive context.

    Active-context replacement invokes cleanup outside this function's scope.
    Untouched context bytes are retained just as in the original routine.
    """
    if len(context) != 0x50 or context[1] & 1:
        raise ValueError('Expected an inactive 0x50-byte context')
    if len(bank) < 16 or bank[:4] != b'SMSB':
        raise ValueError('Expected SMSB bank data')
    _, size, count = struct.unpack_from('<3I', bank, 4)
    if size > len(bank) or 16 + count * 4 > size:
        raise ValueError('Invalid SMSB bounds')
    if not isinstance(index, int) or not 0 <= index < count:
        raise ValueError('Sequence index outside bank')
    offset = struct.unpack_from('<I', bank, 16 + index * 4)[0]
    if offset < 16 + count * 4 or offset + 12 > size or bank[offset:offset + 4] != b'SMSD':
        raise ValueError('Missing or invalid SMSD sequence')
    word(bank_address), word(priority), word(clock)
    resolution, tempo = struct.unpack_from('<2I', bank, offset + 4)
    result = bytearray(context)
    result[0] = priority & 0xf8
    result[1] = (result[1] | 1) & 0xfd
    fields = {4: bank_address + size - 4, 8: resolution,
              12: SequenceTiming(resolution, tempo).scale,
              16: bank_address + offset + 12, 20: bank_address + offset,
              0x34: 0, 0x38: tempo, 0x40: clock}
    for address, value in fields.items():
        struct.pack_into('<I', result, address, value & 0xffffffff)
    return bytes(result)


@dataclass
class SequenceTiming:
    resolution: int
    tempo: int
    time: int = 0
    step_extension: int = 0

    @property
    def scale(self):
        return ((word(self.resolution) * word(self.tempo)) & 0xffffffff) >> 4

    def advance(self, step):
        self.time = (word(self.time) + self.scale * word(step) + word(self.step_extension)) & 0xffffffff
        self.step_extension = 0
        return self.time


class LinearSequenceClock:
    """Schedule parsed, non-looping SMSD events in driver updates.

    Event effects and voice allocation are separate. References already expanded
    by mlt_sequences are accepted; loops and sysex need their original handlers.
    """
    def __init__(self, sequence):
        supported = {'tempo', 'control', 'program', 'pressure', 'pitch', 'note', 'end'}
        if any(event['type'] not in supported for event in sequence['events']):
            raise ValueError('Unsupported non-linear sequence event')
        self.timing = SequenceTiming(*sequence['header'])
        self.events = sequence['events']
        self.position = 0
        self.ended = False

    def update(self, increment=0x4000):
        word(increment)
        if self.ended:
            return []
        previous = self.timing.time
        self.timing.time = (previous - increment) & 0xffffffff
        # SUBS/BHI at 0x6a68: unsigned greater-than before subtraction.
        if previous > increment:
            return []
        due = []
        while self.position < len(self.events):
            event = self.events[self.position]
            self.position += 1
            due.append(event)
            if event['type'] == 'end':
                self.ended = True
                break
            if event['type'] == 'tempo':
                self.timing.tempo = event['value']
            remaining = self.timing.advance(event['step'])
            # CMP/BLE at 0x70c8 uses a signed comparison to zero.
            if 0 < remaining < 0x80000000:
                break
        return due
