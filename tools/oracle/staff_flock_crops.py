"""Emit per-mouse parity crop boxes from original flock RAM and meshes.

Usage: staff_flock_crops.py <1ST_READ.BIN> <frame.ram>
Used for the 84 individual elements in parity case staff_flock_2115.
Positions/poses come from task 0x8c051a60; draw 0x8c051a76 calls
0x8c0193e0 with yaw 0, scale .6, lift 3 and the fast chunk projection.
Each mesh's projected bounds get a 1-pixel border, clipped to the viewport.
"""
import json
import math
from pathlib import Path
import struct
import sys
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from export_dc_models import Pack, MODELS
from dc_fit import FOCAL


def boxes(executable, ram):
    r = Path(ram).read_bytes(); pack = Pack(executable)
    roots = {name: off for name, off, textures in MODELS}
    meshes = [np.array([v[:3] for m, vs in pack.assemble(pack.tree(roots[f'mouse{i}'])) for v in vs]) * .6 for i in range(8)]
    pool = range(0x1d9b30, 0x1efb30, 88)
    cats = [a for a in pool if struct.unpack_from('<I', r, a + 64)[0] == 0x8c051580]
    if len(cats) != 1: raise ValueError('expected one live cat to identify flock birth ages')
    cat_age = struct.unpack_from('<I', r, cats[0] + 4)[0]
    out = {}; c = math.sqrt(.5)
    for a in pool:
        if struct.unpack_from('<I', r, a + 64)[0] != 0x8c051a60: continue
        age = struct.unpack_from('<I', r, a + 4)[0]
        x, y, z = struct.unpack_from('<3f', r, a + 20)
        v = meshes[(age // 4) & 7]
        height = v[:, 1] * c + v[:, 2] * c + y
        zz = -v[:, 1] * c + v[:, 2] * c + z - 85.5 + 3
        sx = 320 + FOCAL * (v[:, 0] + x - 112) / (218 - height)
        sy = 240 + FOCAL * zz / (218 - height)
        box = [max(0, math.floor(sx.min()) - 1), max(0, math.floor(sy.min()) - 1),
               min(640, math.ceil(sx.max()) + 1), min(480, math.ceil(sy.max()) + 1)]
        if box[2] > box[0] and box[3] > box[1]:
            out[f'mouse_{cat_age - age}_{round((x - 135) / 8)}'] = box
    if not out: raise ValueError('no visible flock tasks')
    return out


if __name__ == '__main__': print(json.dumps(boxes(*sys.argv[1:]), indent=2))
