"""Check staff cat head geometry against its source morph and live task.

Usage: staff_cat_projection.py <1ST_READ.BIN> <frame.state> <frame.ram>
The original draw 0x8c051920 -> 0x8c011120 -> 0x8c0119fe uses the
Ninja screen block at 0x8c2c8294 (fx,fy,cx,cy), unlike fast chunk mice.
Finds the exact head UV run across serialized buffers without fixed offsets.
Reports vertex residual in world units; does not verify texture/shading.
"""
import math
import struct
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import dc_models as M
import ta_parse as T
from dc_fit import uv_of


def check(executable, state, ram):
    d, st, r = (Path(p).read_bytes() for p in (executable, state, ram))
    tasks = [a for a in range(0x1d9b30, 0x1efb30, 88) if struct.unpack_from('<I', r, a + 64)[0] == 0x8c051580]
    if len(tasks) != 1: raise ValueError('expected one live staff cat')
    a = tasks[0]; age = struct.unpack_from('<I', r, a + 4)[0]
    walk = r[a + 45]; yaw, roll = struct.unpack_from('<2h', r, a + 46)
    pos = np.array(struct.unpack_from('<3f', r, a + 20)); scale = struct.unpack_from('<f', r, a + 52)[0]
    fx, fy, cx, cy = struct.unpack_from('<4f', r, 0x2c8294)
    phase = ((age * walk) % 192) * .125; f = int(phase); heads = []
    for frame in (f, (f + 1) % 24):
        ptr = struct.unpack_from('<II', d, 0x7ceb4 + 8 * frame)[1] - 0x8c010000
        heads.append(np.array([struct.unpack_from('<3f', d, ptr + 12 * i) for i in range(69)]))
    _, _, _, vl, pl = next(m for m in M.find_models(d, 0x8c010000) if m[0] == 0x778ac)
    flat = [v for strip, rev, tex, mat, *_ in pl if tex == 16384 for v in strip]
    index = {key: i for i, key in enumerate(sorted(vl))}
    h = heads[0] + (heads[1] - heads[0]) * (phase - f)
    src = np.array([h[index[i]] + (0, 14, 0) for i, u, v in flat]) * scale
    def rotation(degrees, axis):
        c, s = math.cos(math.radians(degrees)), math.sin(math.radians(degrees))
        return np.array([[1,0,0],[0,c,-s],[0,s,c]]) if axis == 'x' else np.array([[c,0,s],[0,1,0],[-s,0,c]]) if axis == 'y' else np.array([[c,-s,0],[s,c,0],[0,0,1]])
    # SH-4 truncates degrees * 182.04444885 into a 16-bit turn first.
    turn = lambda deg: (int(np.float32(deg) * np.float32(182.0444488525390625)) & 65535) * 360 / 65536
    R = rotation(-45, 'x') @ rotation(-turn(yaw), 'y') @ rotation(-turn(roll), 'z')
    expected = src @ R.T + pos - (112, 0, 85.5) + (0, 0, 2.5)
    uvs = np.array([(u, v) for i, u, v in flat]); best = None
    for p in T.packets(st):
        verts = [v for strip in p['strips'] for v in strip]
        if len(verts) != len(flat) or np.max(np.abs(np.array([uv_of(p, v) for v in verts]) - uvs)) > .004: continue
        actual = np.array([((v[1] - cx) / (fx * v[3]), 218 - 1 / v[3], (v[2] - cy) / (fy * v[3])) for v in verts])
        residual = float(np.linalg.norm(actual - expected, axis=1).max())
        if best is None or residual < best[0]: best = (residual, p['off'])
    if best is None: raise ValueError('no matching head packet')
    print(f'cat age {age}, phase {phase}, Ninja projection {fx}/{fy}, head packet {best[1]:#x}, max vertex error {best[0]:.8f} world units')
    return 0 if best[0] < .001 else 1


if __name__ == '__main__': sys.exit(check(*sys.argv[1:]))
