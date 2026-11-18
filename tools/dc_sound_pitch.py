"""Exact pitch-word calculation for the tested Dreamcast MANATEE.DRV.

Derived from ARM routine 0x1c30, with tables addressed by literals at
0x2144/0x2148, thresholds at 0x1cc8..0x1cd0. Driver ARM image starts at file +32.
No sample rate or equal-temperament approximation is substituted for the tables.
"""
import hashlib
import struct


DRIVER_SHA256 = '11c89eaa2b207c178495a2789363bcbbc15cf0d67c00557b9a2bdf4c2cf8de06'


class PitchTable:
    def __init__(self, driver):
        if hashlib.sha256(driver).hexdigest() != DRIVER_SHA256:
            raise ValueError('Unsupported MANATEE driver; verify its pitch routine first')
        image = driver[32:]
        coarse, fractional = struct.unpack_from('<2I', image, 0x2144)
        self.coarse = image[coarse:coarse + 256]
        self.fractional = image[fractional:fractional + 2048]
        self.thresholds = struct.unpack_from('<3I', image, 0x1cc8)

    def word(self, note, root, fine_tune=0, bend=0):
        """bend is the routine's signed raw 1/256-semitone r7 input."""
        if not 0 <= note <= 127 or not 0 <= root <= 127 or not -128 <= fine_tune <= 127:
            raise ValueError('Invalid note, root key or fine-tune byte')
        combined = (bend + fine_tune) & 0xffffffff
        coarse = self.coarse[((combined >> 8) + note + 0x60 - root) & 255]
        index = (((coarse & 15) << 8) | (combined & 0xfe)) >> 1
        fraction = self.fractional[index] + 256 * sum(index >= bound for bound in self.thresholds)
        return ((coarse & 0xf0) << 7) | fraction
