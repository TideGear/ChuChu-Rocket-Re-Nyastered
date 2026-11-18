"""MANATEE sequence timing arithmetic, in original fixed-point units.

Header setup: ARM 0x89a0..0x89c0. Tempo event: 0x6f60..0x6f80.
Step advancement: 0x711c..0x7140. Multiplication wraps before shifting.
This does not map driver updates to audio samples or allocate voices.
"""
from dataclasses import dataclass


def word(value):
    if not isinstance(value, int) or not 0 <= value <= 0xffffffff:
        raise ValueError('Expected an unsigned 32-bit timing word')
    return value


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
