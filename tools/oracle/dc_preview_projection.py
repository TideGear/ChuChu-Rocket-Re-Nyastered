"""Check the preview's projection centre against original TA wall vertices.

Uses the original wall model's strip order and UVs, the floor packet and reciprocal
depth. No screenshots or fitted screen offsets are used to select geometry.
"""
import argparse
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import export_dc_models as models
import ta_dump


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('states', nargs='+', type=Path)
    parser.add_argument('--exe', type=Path,
                        default=Path('local/cache/assets/dreamcast/files/1ST_READ.BIN'))
    args = parser.parse_args()
    pack = models.Pack(args.exe)
    node = pack.tree(0xa20fc)[0]  # original board wall object 0x8c0b20fc
    assert node['pos'] == [0, 0, 0] and node['ang'] == [0, 0, 0]
    verts, strips = pack.models[node['mp']]
    order = [v for strip, *_ in strips for v in strip]
    points = np.array([verts[i][0] for i, u, v in order])
    uvs = np.array([(u, v) for i, u, v in order])
    for path in args.states:
        _, _, _, polys = ta_dump.load(path)
        floor = [v for strip in polys[0]['strips'] for v in strip]
        wall = [v for strip in polys[1]['strips'] for v in strip]
        real = np.array(wall)
        assert len(floor) == 4 and len(wall) == len(order), path
        assert np.max(np.abs(real[:, 4:6] - uvs)) < 0.004, path
        distance = 1.0 / floor[0][3]
        assert abs(distance - 410) < 0.001, path
        assert np.max(np.abs(1.0 / real[:, 3] - (distance - points[:, 1]))) < 0.001, path
        x0, y0 = min(v[1] for v in floor), min(v[2] for v in floor)
        scale = (max(v[1] for v in floor) - x0) / 180.0
        plane = np.column_stack((x0 + (7.5 + points[:, 0]) * scale,
                                 y0 + points[:, 2] * scale))
        perspective = (distance * real[:, 3])[:, None]
        raised = points[:, 1] > 0.01
        centres = ((real[:, 1:3] - plane * perspective) / (1 - perspective))[raised]
        centre = np.array([320.0, 240.0])
        projected = centre + (plane - centre) * perspective
        error = float(np.max(np.abs(projected - real[:, 1:3])))
        old = np.array([x0 + 72 * scale, y0 + 85.5 * scale])
        old_error = float(np.max(np.abs(old + (plane - old) * perspective - real[:, 1:3])))
        assert error < 0.001, (path, error)
        print(f'{path}: centre {centres.mean(axis=0)}, '
              f'wall max error {error:.8f} px (old {old_error:.6f} px)')


if __name__ == '__main__':
    main()
