"""Check complete raw TA preview lid strips against the original model.

Capture with patch_flycast_ta_capture.py. --quarter checks Battle/Challenge's
0x4000/0xc000 branch; default checks Puzzle's 0/0x8000 branch. The RAM snapshot
supplies Ninja's original screen block; no port transform is used as evidence.
"""
import argparse
import math
from pathlib import Path
import struct
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import export_dc_models as models
import ta_parse
from dc_fit import uv_of


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('stream', type=Path)
    p.add_argument('ram', type=Path)
    p.add_argument('--exe', type=Path, default=Path('local/cache/assets/dreamcast/files/1ST_READ.BIN'))
    p.add_argument('--quarter', action='store_true')
    p.add_argument('--halves', type=int, default=12)
    args = p.parse_args()
    pack = models.Pack(args.exe)
    verts, strips = pack.models[pack.tree(0x987b8)[0]['mp']]
    flat = [v for strip, *_ in strips for v in strip]
    src = np.array([verts[i][0] for i, u, v in flat])
    normals = np.array([verts[i][1] for i, u, v in flat])
    uvs = np.array([(u, v) for i, u, v in flat])
    data = args.stream.read_bytes()
    fx, fy, cx, cy = struct.unpack_from('<4f', args.ram.read_bytes(), 0x2c8294)
    polys = ta_parse.parse(data, 0, len(data))
    floor = [v for strip in polys[0]['strips'] for v in strip]
    distance = 1.0 / floor[0][3]
    assert abs(distance - 410) < 0.001
    count, max_geometry, max_light = 0, 0.0, 0.0
    boxes = []
    for poly in polys:
        run = [v for strip in poly['strips'] for v in strip]
        if len(run) != len(flat) or np.max(np.abs(np.array([uv_of(poly, v) for v in run]) - uvs)) > 0.004:
            continue
        actual = np.array(run)
        depth = 1.0 / actual[:, 3]
        world = np.column_stack(((actual[:, 1] - cx) * depth / fx,
                                 distance - depth,
                                 (actual[:, 2] - cy) * depth / fy))
        side = 1 if count % 2 == 0 else -1
        rotation = np.array([[0, 0, side], [0, 1, 0], [-side, 0, 0]]) if args.quarter else np.diag([side, 1, side])
        rotated = src @ rotation.T
        translation = (world - rotated).mean(axis=0)
        geometry = float(np.max(np.abs(rotated + translation - world)))
        light = 0.3 + np.maximum(0, (normals @ rotation.T) @ np.array([0, 0.5, -0.25]))
        lighting = float(np.max(np.abs(light - actual[:, 6])))
        assert geometry < 0.0001, (hex(poly['off']), geometry)
        assert lighting < 0.000001, (hex(poly['off']), lighting)
        max_geometry, max_light = max(max_geometry, geometry), max(max_light, lighting)
        box = (actual[:, 1].min(), actual[:, 2].min(), actual[:, 1].max(), actual[:, 2].max())
        if count % 2 == 0:
            boxes.append(box)
        else:
            first = boxes[-1]
            boxes[-1] = (min(first[0], box[0]), min(first[1], box[1]), max(first[2], box[2]), max(first[3], box[3]))
        count += 1
    assert count == args.halves, (count, args.halves)
    print(f'{count} halves: max geometry {max_geometry:.9f} world units, light {max_light:.9g}')
    for i, box in enumerate(boxes):
        print(f'rocket_{i}: {[math.floor(box[0]) - 1, math.floor(box[1]) - 1, math.ceil(box[2]) + 1, math.ceil(box[3]) + 1]}')


if __name__ == '__main__':
    main()
