"""Compare the port mouse task with the original's live staff-roll RAM.

Usage: staff_mouse_compare.py <FLY_WATCH file> <port stdout>
Flycast: resume local/modecap/m17p/m_00300.state, FLY_WATCH=1d9b88:56:0;
or m_00200.state with FLY_POKE_ONCE=0:cdaa4=0 and B@100-102,
FLY_WATCH=1d9b88:56:110 (ignores the pre-init age-zero payload).
Port: CCR_STAFF_TRACE=1 CCR_TICKS=4600 CCR_SHOT=<path>, DC_STAFFROLL.
The watch is the 56-byte task payload (callback pointer is payload + 64).
Counters align runs independently of screenshot/video callback numbering.
This checks motion, pose inputs and retirement; rendered parity is separate.
"""
import struct
import sys
import math


def compare(watch_path, port_path):
    port = {}
    for line in open(port_path, encoding='utf-8-sig'):
        if not line.startswith('staffmouse '):
            continue
        _, age, row, x, y, z, angle, walk, scale, alive = line.split()
        port[int(age)] = (int(row), float(x), float(y), float(z), int(angle), int(walk), float(scale), int(alive))
    if not port:
        raise ValueError('no port task trace')
    raw = open(watch_path, 'rb').read()
    if not raw or len(raw) % 60:
        raise ValueError('watch must contain frame + 56-byte task records')
    seen, bad = set(), []
    last_age = None
    for off in range(0, len(raw), 60):
        frame, = struct.unpack_from('<I', raw, off)
        b = raw[off + 4:off + 60]
        age, = struct.unpack_from('<I', b, 4)
        if last_age is None and age == 0:
            continue  # allocator payload before the mouse's first update
        # Once the allocator reuses this task's payload the watch is unrelated.
        if last_age is not None and age < last_age:
            break
        last_age = age
        row, walk, angle = struct.unpack_from('<BBh', b, 44)
        scale, = struct.unpack_from('<f', b, 48)
        x, y, z = struct.unpack_from('<3f', b, 20)
        expected = (row, x, y, z, angle, walk, scale)
        actual = port.get(age)
        if actual is None or any(not math.isfinite(a) or not math.isfinite(e) or abs(a - e) > 1e-6 for a, e in zip(actual, expected)):
            bad.append((frame, age, expected, actual))
        seen.add(age)
    if len(seen) < 2:
        raise ValueError('watch does not exercise task updates')
    if len(seen) != max(seen) - min(seen) + 1:
        raise ValueError('watch skips task ages')
    # The final type-4 row sets walk and scale to zero before retirement.
    retired = any(v[-1] == 0 and v[-2] == 0 and v[-3] == 0 for v in port.values())
    if not retired:
        raise ValueError('port trace does not reach retirement')
    print(f'{len(seen)} distinct task ages ({min(seen)}..{max(seen)}), {len(bad)} mismatches; port retirement reached')
    for error in bad[:5]:
        print(error)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(compare(*sys.argv[1:]))
