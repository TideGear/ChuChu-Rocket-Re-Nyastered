"""Compare the port's iPad drum mesh and projection against the original GL calls."""
from itertools import product
import math
import os
from pathlib import Path
import struct
import subprocess
import sys

from unicorn.arm_const import UC_ARM_REG_SP

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools' / 'oracle'))
import hd_env
from ios_oracle import IOSOracle, f2u, u2f


class DrawOracle(IOSOracle):
    calls = None

    def _hook(self, uc, address, size, user):
        name = self.stubs[address]
        r = [self._r(i) for i in range(4)]
        if self.calls is not None:
            if name in ('_glTranslatef', '_glRotatef', '_glScalef'):
                self.calls.append((name, tuple(map(u2f, r[:4 if name == '_glRotatef' else 3]))))
            elif name == '_glMultMatrixf':
                self.calls.append((name, struct.unpack('<16f', self.read(r[0], 64))))
            elif name == '_glFrustumf':
                tail = self.read(uc.reg_read(UC_ARM_REG_SP), 8)
                self.calls.append((name, tuple(map(u2f, r)) + struct.unpack('<2f', tail)))
            elif name in ('_glViewport', '_glCullFace', '_glNormalPointer', '_glDrawElements',
                          '_glVertexPointer', '_glTexCoordPointer'):
                self.calls.append((name, tuple(r)))
        super()._hook(uc, address, size, user)


def original_vertices(oracle, pose):
    oracle.calls = []
    oracle.call(0x1a970, *map(f2u, pose))
    calls = oracle.calls
    oracle.calls = None
    by_name = dict(calls)
    _, _, width, height = by_name['_glViewport']
    assert by_name['_glCullFace'][0] == 0x404
    stride, pointer = by_name['_glNormalPointer'][1:3]
    assert (stride, pointer + 12, pointer + 24) == (
        32, by_name['_glVertexPointer'][3], by_name['_glTexCoordPointer'][3])
    mode, count, scalar, index_pointer = by_name['_glDrawElements']
    assert (mode, count, scalar) == (4, 48, 0x1403)
    indices = struct.unpack('<48H', oracle.read(index_pointer, 96))
    end = next(i for i, (name, _) in enumerate(calls) if name == '_glDrawElements')
    left, right, bottom, top, near, _ = by_name['_glFrustumf']
    rows = []
    for i in range(max(indices) + 1):
        data = struct.unpack('<8f', oracle.read(pointer + i * stride, stride))
        x, y, z = data[3:6]
        for name, a in reversed(calls[:end]):
            if name == '_glTranslatef':
                x, y, z = x + a[0], y + a[1], z + a[2]
            elif name == '_glScalef':
                x, y, z = x * a[0], y * a[1], z * a[2]
            elif name == '_glRotatef':
                c, s = math.cos(math.radians(a[0])), math.sin(math.radians(a[0]))
                if a[1:] == (1, 0, 0):
                    y, z = y * c - z * s, y * s + z * c
                else:
                    assert a[1:] == (0, 0, 1)
                    x, y = x * c - y * s, x * s + y * c
            elif name == '_glMultMatrixf':
                v = (x, y, z, 1)
                x, y, z = (sum(a[j * 4 + i] * v[j] for j in range(4)) for i in range(3))
        depth = -z
        assert depth > near
        portrait_x = width * (near * x / depth - left) / (right - left)
        portrait_y = height * (near * y / depth - bottom) / (top - bottom)
        rows.append((*data, portrait_y, portrait_x, 1 / depth))
    return indices, rows


def main():
    hd_env.IOSOracle = DrawOracle
    env = hd_env.make()
    oracle = env.o
    oracle.call(0x15188)
    image = oracle.u32(env.appdata + 0x3cc + 4 * 99)
    frame = oracle.u32(image + 0x28) + 4
    actual_uv = struct.unpack('<4f', oracle.read(frame, 16))
    poses = list(product((45.5, 557.3334, 970.0), (201.0, 380.0, 653.0),
                         range(0, 360, 45), (1.0, 30.0, 37.5)))
    cases = []
    for uv in (actual_uv, (0.13, 0.19, 0.58, 0.88)):
        oracle.write(frame, struct.pack('<4f', *uv))
        oracle.call(0x1b420, 99, 0)
        cases.extend((pose + uv, original_vertices(oracle, pose)) for pose in poses)
    executable = ROOT / 'build/game/ccr.exe'
    requests = ''.join(' '.join(map(str, case)) + '\n' for case, _ in cases)
    rows = subprocess.run([executable], env=dict(os.environ, CCR_ROULETTE_MESH_TRACE='1'),
                          input=requests, check=True, capture_output=True, text=True).stdout.splitlines()
    assert len(rows) == len(cases) * 19
    max_pixel_error = 0
    for i, (case, (indices, vertices)) in enumerate(cases):
        assert tuple(map(int, rows[i * 19].split())) == indices
        for ref, row in zip(vertices, rows[i * 19 + 1:(i + 1) * 19]):
            actual = tuple(map(float.fromhex, row.split()))
            assert actual[:8] == ref[:8], (case, actual, ref)
            error = max(abs(a - b) for a, b in zip(actual[8:10], ref[8:10]))
            assert error < 0.001 and abs(actual[10] - ref[10]) < 1e-7, (case, actual, ref)
            max_pixel_error = max(max_pixel_error, error)
    print(f'{len(cases)} draws matched: mesh exact, {max_pixel_error:.6f}px maximum projection error')


if __name__ == '__main__':
    main()
