"""Compare a full port demo JSONL with synchronous USA Flycast memory watches.

Capture each watch with a fresh prefix, frames 1909..3587:
 tasks: 1d9a80:32768:1909; arrows: 186178:304:1909; scores: 1af500:16:1909.
Port JSONL: set DC_BATTLE_DUMP and run dc_battle_probe with KEY_STAGE000.BIN.
Only X/Z, movement direction, mouse type, scores, and live arrow data are compared.
Render angle, height, pose, effects and visual parity are deliberately separate checks.
"""
import argparse
import collections
import json
import struct
from pathlib import Path

TASK_BASE = 0x8c1d9a80


def watches(path, size):
    data = Path(path).read_bytes()
    stride = size + 4
    if len(data) % stride:
        raise ValueError(f'truncated watch: {path}')
    rows = {}
    previous = None
    for offset in range(0, len(data), stride):
        frame = struct.unpack_from('<i', data, offset)[0]
        if previous is not None and frame != previous + 1:
            raise ValueError(f'nonconsecutive watch: {path}')
        rows[frame] = data[offset + 4:offset + stride]
        previous = frame
    return rows


def entities(data):
    def at(address, fmt):
        offset = address - TASK_BASE
        if offset < 0 or offset + struct.calcsize(fmt) > len(data):
            raise ValueError(f'task outside capture: {address:x}')
        return struct.unpack_from(fmt, data, offset)
    node = TASK_BASE
    seen, found = set(), []
    while node and node not in seen:
        seen.add(node)
        kind = at(node + 2, '<B')[0]
        draw = at(node + 0x44, '<I')[0]
        if kind in (1, 2) and draw:
            mouse = kind == 1
            found.append((int(mouse), at(node + 8, '<I')[0] if mouse else 0,
                          at(node + 20, '<f')[0], at(node + 28, '<f')[0],
                          (at(node + 36, '<I')[0] & 0xffff) >> 14))
        node = at(node + 0x54, '<I')[0]
    if node and node != TASK_BASE:
        raise ValueError('task list cycle away from head')
    return collections.Counter(found)


def arrows(data):
    found = []
    for player in range(4):
        for slot in range(3):
            direction, hits, life, x, y = struct.unpack_from('<BB2xihh', data, player * 76 + slot * 24)
            if life > 0:
                found.append((player, x, y, direction, life, hits))
    return collections.Counter(found)


def wheel(data):
    node, seen = TASK_BASE, set()
    while node and node not in seen:
        seen.add(node)
        offset = node - TASK_BASE
        if offset < 0 or offset + 0x58 > len(data):
            raise ValueError('wheel task outside capture')
        if struct.unpack_from('<I', data, offset + 0x44)[0] == 0x8c01d9a0 and data[offset]:
            return (*struct.unpack_from('<3f', data, offset + 20),
                    struct.unpack_from('<f', data, offset + 44)[0],
                    struct.unpack_from('<I', data, offset + 32)[0] & 0xffff)
        node = struct.unpack_from('<I', data, offset + 0x54)[0]
    return None


def f32(value):
    return struct.unpack('<f', struct.pack('<f', value))[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('port', 'tasks', 'arrows', 'scores'):
        parser.add_argument('--' + key, required=True)
    args = parser.parse_args()
    tasks = watches(args.tasks, 32768)
    arrow_rows = watches(args.arrows, 304)
    score_rows = watches(args.scores, 16)
    checked = 0
    for line in Path(args.port).read_text().splitlines():
        port = json.loads(line)
        frame = port['watch_frame']
        if frame not in tasks or frame not in arrow_rows or frame not in score_rows:
            raise ValueError(f'missing original frame {frame}')
        pairs = {
            'entities': (entities(tasks[frame]), collections.Counter(
                (m, t, f32(x), f32(y), d) for m, t, x, y, d in port['entities'])),
            'arrows': (arrows(arrow_rows[frame]), collections.Counter(map(tuple, port['arrows']))),
            'scores': (struct.unpack('<4i', score_rows[frame]), tuple(port['scores'])),
        }
        if 'wheel' in port:
            pose = port['wheel']
            pairs['wheel'] = (wheel(tasks[frame]), (*map(f32, pose[:4]), pose[4]) if pose else None)
        for kind, (original, actual) in pairs.items():
            if original != actual:
                print(f'first {kind} difference: watch frame {frame}, tick {port["tick"]}')
                if isinstance(original, collections.Counter):
                    print('only original:', original - actual)
                    print('only port:', actual - original)
                else:
                    print('original:', original, 'port:', actual)
                print(f'{checked} complete consecutive frames agreed')
                return 1
        checked += 1
    if not checked:
        raise ValueError('empty port trace')
    print(f'Dreamcast demo state: {checked} frames identical in entities, arrows and scores')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
