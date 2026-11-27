"""Compare staff-roll cat and flock against the original's live scheduler.

Usage: staff_cat_compare.py <FLY_WATCH file> <port stdout>
Flycast: resume m17p/m_00300.state; FLY_WATCH=1d9be0:8192:885.
Port: CCR_STAFF_TRACE=1 CCR_TICKS=4600 CCR_SHOT=<path>, DC_STAFFROLL.
The watched range includes cat + 84 flock task slots (stride 88).
The callback at task+64 is cleared by retirement (0x8c01f130).
Rendered pose parity is a separate check in tools/parity.py.
"""
import math
import struct
import sys


def compare(watch_path, port_path):
    cats, flocks = {}, {}
    for line in open(port_path, encoding='utf-8-sig'):
        v = line.split()
        if not v:
            continue
        if v[0] == 'staffcat':
            age = int(v[1]); cats[age] = tuple(map(float, v[2:])); flocks[age] = []
        elif v[0] == 'staffflock':
            age, born, slot, ticks = map(int, v[1:5])
            flocks[age].append((born, slot, ticks, float(v[5]), float(v[6])))
    raw = open(watch_path, 'rb').read()
    stride = 4 + 8192
    if not raw or len(raw) % stride or not cats:
        raise ValueError('missing or malformed original/port task trace')
    ages, births, bad, samples = set(), set(), [], 0
    for off in range(0, len(raw), stride):
        frame, = struct.unpack_from('<I', raw, off)
        b = raw[off + 4:off + stride]
        age, = struct.unpack_from('<I', b, 4)
        callback, = struct.unpack_from('<I', b, 64)
        if not age or callback not in (0, 0x8c051580):
            continue
        row, walk, angle, roll, wait = struct.unpack_from('<BB3h', b, 44)
        x, y, z = struct.unpack_from('<3f', b, 20)
        scale, = struct.unpack_from('<f', b, 52)
        expected = (row, x, y, z, angle, roll, wait, walk, scale, int(callback != 0))
        actual = cats.get(age)
        if actual is None or any(not math.isfinite(a) or not math.isfinite(e) or abs(a - e) > 1e-6 for a, e in zip(actual, expected)):
            bad.append(('cat', frame, age, expected, actual))
        flock = []
        for base in range(88, len(b) - 88 + 1, 88):
            if struct.unpack_from('<I', b, base + 64)[0] != 0x8c051a60:
                continue
            ticks, = struct.unpack_from('<I', b, base + 4)
            x, y, z = struct.unpack_from('<3f', b, base + 20)
            slot = int((x - 135) / 8)
            if y != 100 or x != 135 + 8 * slot or not 0 <= slot < 6:
                raise ValueError('unexpected flock position/slot')
            born = age - ticks
            flock.append((born, slot, ticks, x, z))
            births.add((born, slot)); samples += 1
        if sorted(flock) != sorted(flocks.get(age, [])):
            bad.append(('flock', frame, age, sorted(flock), sorted(flocks.get(age, []))))
        ages.add(age)
    if not ages or min(ages) != 1 or len(ages) != max(ages):
        raise ValueError('watch must cover every cat update from age 1')
    if cats[max(ages)][-1] != 0 or births != {(age, slot) for age in range(1950, 2048, 7) for slot in range(6)}:
        raise ValueError('retirement or full 84-mouse flock not exercised')
    print(f'{len(ages)} cat update ages (1..{max(ages)}), {len(births)} flock tasks, {samples} live flock observations; {len(bad)} mismatches')
    for error in bad[:5]:
        print(error)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(compare(*sys.argv[1:]))
