"""Compare the native IRQ divider to ARM instructions and real-loop sample traces."""
import argparse
import csv
import random
import struct
import sys
import wave
from pathlib import Path
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM
from unicorn.arm_const import UC_ARM_REG_PC

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dc_sound_pitch import PitchTable
from dc_sound_clock import DriverSampleClock
from arm7_bus import Arm7Bus
from dc_aica_state import inspect


def verify_irq(driver):
    PitchTable(driver)
    image = driver[32:]
    ram = bytearray(0x200000); ram[:len(image)] = image
    phase_at, clock_at = struct.unpack_from('<2I', image, 0xc94)
    uc = Uc(UC_ARCH_ARM, UC_MODE_ARM); uc.mem_map(0, 0x200000); uc.mem_write(0, bytes(ram))
    bus = Arm7Bus(uc)
    native = DriverSampleClock(driver, ram, 0)
    rng = random.Random(0x2b40300)
    for case in range(512):
        phase = case & 255
        remaining = (0, 1, 2, 440, 441, 0xffffffff, rng.getrandbits(32))[case % 7]
        clock = rng.getrandbits(32) if case % 2 else 0xffffffff
        native.phase, native.skip_remaining, native.clock = phase, remaining, clock
        uc.mem_write(phase_at, bytes([phase])); uc.mem_write(0x30c, struct.pack('<I', remaining))
        uc.mem_write(clock_at, struct.pack('<I', clock))
        native.interrupt(); uc.emu_start(0x2b4, 0x338, count=1000); bus.flush()
        actual = (uc.mem_read(phase_at, 1)[0], struct.unpack('<I', uc.mem_read(0x30c, 4))[0],
                  struct.unpack('<I', uc.mem_read(clock_at, 4))[0])
        if uc.reg_read(UC_ARM_REG_PC) != 0x338 or actual != (native.phase, native.skip_remaining, native.clock):
            raise AssertionError(('IRQ divider', case, actual, native.phase, native.skip_remaining, native.clock))
    print('Original ARM IRQ divider matches: 512 cases')


def verify_trace(driver, state, mlt, trace, audio):
    report = inspect(state, mlt)
    ram = state[report['sound_ram_offset']:report['sound_ram_offset'] + 0x200000]
    if ram[0x294:0x304] != driver[32 + 0x294:32 + 0x304]:
        raise ValueError('Captured driver IRQ code differs from pinned source')
    timer = struct.unpack_from('<I', state, report['register_offset'] + 0x2890)[0]
    native = DriverSampleClock(driver, ram, timer)
    with trace.open(newline='', encoding='utf-8') as stream:
        rows = list(csv.DictReader(stream))
    actual = [(int(r['sample']), int(r['driver_tick'])) for r in rows]
    if len(actual) < 2 or actual[0][0] != 0 or any(a[0] >= b[0] for a, b in zip(actual, actual[1:])):
        raise ValueError('Expected a sample-zero baseline and strictly ordered clock observations')
    with wave.open(str(audio), 'rb') as stream:
        if (stream.getnchannels(), stream.getsampwidth(), stream.getframerate()) != (2, 2, 44100):
            raise ValueError('Expected the matching stereo PCM16 / 44100 Hz reference')
        count = stream.getnframes()
    if actual[-1][0] >= count:
        raise ValueError('Clock observations exceed the reference audio range')
    expected = native.advance(count)
    if actual != expected:
        first = next((i for i, (a, b) in enumerate(zip(actual, expected)) if a != b), min(len(actual), len(expected)))
        raise AssertionError(('Clock/sample trace differs', first, actual[first:first + 2], expected[first:first + 2]))
    print('Original-loop sample clock matches:', len(actual) - 1, 'transitions;',
          count, 'samples; IRQ period', native.irq_period, 'samples; skip reload', native.skip_reload)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('driver', type=Path); parser.add_argument('--state', type=Path)
    parser.add_argument('--mlt', type=Path); parser.add_argument('--trace', type=Path)
    parser.add_argument('--wav', type=Path)
    args = parser.parse_args()
    if args.state and (args.mlt is None or args.trace is None or args.wav is None):
        parser.error('--state requires --mlt, --trace and --wav')
    driver = args.driver.read_bytes(); verify_irq(driver)
    if args.state:
        verify_trace(driver, args.state.read_bytes(), args.mlt.read_bytes(), args.trace, args.wav)
