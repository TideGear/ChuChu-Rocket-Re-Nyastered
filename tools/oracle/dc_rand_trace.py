"""Count the USA executable's nine rand() call sites in a local Flycast capture.

make <unmodified RAM dump> <poke.txt>: validate wrappers in SH4 and write FLY_POKE.
Run flyhost with FLYHOST_SYNC=1, FLY_POKE from that file, and
FLY_WATCH=6400:36:1660. Use a fresh output prefix (watch files append).
read <watch.bin>: print per-frame deltas, indexed by literal-pool address.

Only the user's emulated RAM is patched. No executable, BIOS or font data is exported.
Compare an instrumented screenshot and RNG state with an unmodified synchronous run
before treating the trace as evidence. These addresses apply only to the tested USA dump.
"""
import argparse
import struct
import sys
from pathlib import Path

POOLS = (0x11308, 0x17004, 0x1CEE8, 0x1DCE8, 0x239F8,
         0x2696C, 0x277E8, 0x511B8, 0x581E8)
RAND = 0x8C060E2C
CODE = 0x8C006000
COUNTERS = 0x8C006400


def make(ram_path, output):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from sh4 import SH4
    ram = Path(ram_path).read_bytes()
    if len(ram) != 0x1000000 or any(ram[0x6000:0x6500]):
        raise ValueError('expected a 16 MiB RAM dump with unused zero scratch at 0x6000..0x64ff')
    words = {}
    for i, pool in enumerate(POOLS):
        if struct.unpack_from('<I', ram, pool)[0] != RAND:
            raise ValueError(f'unrecognized rand pointer at {pool:x}')
        addr = CODE + i * 32
        counter = COUNTERS + i * 4
        # Preserve r1/r2 and PR, increment this caller's counter, then tail-call rand.
        code = struct.pack('<12H2I', 0x2F16, 0x2F26, 0xD104, 0x6212,
                           0x7201, 0x2122, 0x62F6, 0x61F6,
                           0xD002, 0x402B, 0x0009, 0x0009, counter, RAND)
        m = SH4()
        m.ram[:] = ram
        m.load(addr, code)
        m.wr32(0x8C0D2184, 0xDEAD0CAB)
        expected_state = (0xDEAD0CAB * 1103515245 + 12345) & 0xFFFFFFFF
        result = m.call(addr)
        if (result != ((expected_state >> 16) & 0x7FFF) or
                m.rd32(0x8C0D2184) != expected_state or m.rd32(counter) != 1):
            raise ValueError('wrapper differs from original rand()')
        words[pool] = addr
        for j in range(0, len(code), 4):
            words[(addr & 0xFFFFFF) + j] = struct.unpack_from('<I', code, j)[0]
    Path(output).write_text('1660:' + ','.join(f'{k:x}={v:x}' for k, v in words.items()), encoding='ascii')
    print('9 wrappers validated; watch 6400:36:1660 with synchronous rendering')


def read(path):
    data = Path(path).read_bytes()
    if len(data) % 40:
        raise ValueError('truncated watch record')
    previous = None
    last_frame = None
    for frame, *counts in struct.iter_unpack('<10I', data):
        if last_frame is not None and frame != last_frame + 1:
            raise ValueError('nonconsecutive watch frames (use a fresh prefix)')
        if previous is not None:
            deltas = [(a - b) & 0xFFFFFFFF for a, b in zip(counts, previous)]
            changes = [f'{pool:05x}:{n}' for pool, n in zip(POOLS, deltas) if n]
            if changes:
                print(frame, ' '.join(changes))
        previous, last_frame = counts, frame


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('make')
    p.add_argument('ram')
    p.add_argument('output')
    p = sub.add_parser('read')
    p.add_argument('watch')
    args = parser.parse_args()
    if args.command == 'make':
        make(args.ram, args.output)
    else:
        read(args.watch)
