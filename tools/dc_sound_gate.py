"""MANATEE ordinary note-gate countdown (ARM 0x6948..0x69dc).

One call represents a driver scheduler update, not an audio sample. Special
bit-24 continuation records and FIFO backpressure require separate handling.
"""
from dataclasses import dataclass


@dataclass
class NoteGate:
    command: int
    elapsed: int
    remaining: int

    @classmethod
    def from_note(cls, base, group, channel, note, velocity, gate, scale,
                  gate_extension=0, sequence_time=0):
        """Ordinary free-slot insertion, ARM 0x6b34..0x6bd8.

        Timing operands are captured fixed-point driver fields, not milliseconds.
        Allocation, full-table stealing and FIFO submission belong to the caller.
        """
        for name, value, maximum in (
            ('base', base, 255), ('group', group, 7), ('channel', channel, 15),
            ('note', note, 255), ('velocity', velocity, 255),
            ('gate', gate, 0xffffffff), ('scale', scale, 0xffffffff),
            ('gate_extension', gate_extension, 0xffffffff),
            ('sequence_time', sequence_time, 0xffffffff)):
            if not isinstance(value, int) or not 0 <= value <= maximum:
                raise ValueError(f'Invalid {name}')
        command = ((base | 1) << 24 | group << 20 | channel << 16 |
                   note << 8 | velocity) & 0xfeffffff
        return cls(command, 1, (gate * scale + gate_extension + sequence_time) & 0xffffffff)

    def advance(self, increment, paused=False):
        """Return the expired command, or None; clear an expired record."""
        if any(not isinstance(v, int) or not 0 <= v <= 0xffffffff
               for v in (self.command, self.elapsed, self.remaining, increment)):
            raise ValueError('Gate fields must be unsigned 32-bit integers')
        if not self.command or paused:
            return None
        if self.command & 0x1000000:
            raise ValueError('Continuation gate records are not yet supported')
        # SUBS/BLE uses the signed, wrapped result, including overflow flags.
        remaining = (self.remaining - increment) & 0xffffffff
        signed_remaining = self.remaining - (0x100000000 if self.remaining & 0x80000000 else 0)
        signed_increment = increment - (0x100000000 if increment & 0x80000000 else 0)
        if signed_remaining <= signed_increment:
            command = self.command
            self.command = self.elapsed = self.remaining = 0
            return command
        self.remaining = remaining
        self.elapsed = (self.elapsed + 1) & 0xffffffff
        return None
