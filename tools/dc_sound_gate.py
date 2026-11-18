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
