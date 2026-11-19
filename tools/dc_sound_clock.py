"""MANATEE Timer-A divider, ARM IRQ block 0x2b4..0x300.

Maps an already-running, unprescaled Timer A to driver clock changes. CPU IRQ
latency, pending/in-flight IRQ starts and main-loop worker dispatch are separate
concerns; this is not a complete sequence-to-sample scheduler.
"""
import struct
from dc_sound_pitch import PitchTable


class DriverSampleClock:
    def __init__(self, driver, ram, timer_control):
        PitchTable(driver)
        image = driver[32:]
        if timer_control & 0x700:
            raise NotImplementedError('Prescaled starting Timer A requires its captured prescaler phase')
        reload_word = struct.unpack_from('<I', image, 0x308)[0]
        if reload_word & 0x700:
            raise ValueError('Unverified driver timer prescaler')
        phase_at, clock_at = struct.unpack_from('<2I', image, 0xc94)
        self.phase = ram[phase_at]
        self.clock = struct.unpack_from('<I', ram, clock_at)[0]
        self.skip_remaining = struct.unpack_from('<I', ram, 0x30c)[0]
        self.skip_reload = struct.unpack_from('<I', image, 0x310)[0]
        self.irq_period = 256 - (reload_word & 255)
        self.next_irq = 256 - (timer_control & 255)
        self.sample = 0

    def interrupt(self):
        self.skip_remaining = (self.skip_remaining - 1) & 0xffffffff
        if self.skip_remaining == 0:
            self.skip_remaining = self.skip_reload
            return False
        self.phase = (self.phase + 1) & 3
        if self.phase:
            return False
        self.clock = (self.clock + 1) & 0xffffffff
        return True

    def advance(self, count):
        """Return (sample, driver_clock) observations, including sample-zero baseline."""
        if not isinstance(count, int) or count < 0:
            raise ValueError('Expected a nonnegative sample count')
        events = [(0, self.clock)] if self.sample == 0 and count else []
        for _ in range(count):
            if self.sample == self.next_irq:
                if self.interrupt():
                    events.append((self.sample, self.clock))
                self.next_irq += self.irq_period
            self.sample += 1
        return events
