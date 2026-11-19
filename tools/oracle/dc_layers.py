#!/usr/bin/env python3
"""List every PowerVR primitive of a Flycast state in submission order with its texture word, TSP blend bits, depth and screen box.

usage: dc_layers.py <file.state> [--list opaque|2d|all]

Submission order inside a list is the game's own draw order (opaque 3D list at 0x253e10 for the board, then the 2D list near 0x1900003), so comparing it
with the port's call order shows which element is drawn over which. Blend source/dest come from TSP bits 29-31 / 26-28 and the depth 1/w from the first vertex.
Consecutive primitives with the same texture word and TSP are collapsed into one row with a count."""
import struct, sys

SRC = ['0', '1', 'dst', '1-dst', 'srcA', '1-srcA', 'dstA', '1-dstA']


def parse(st, start, end):
    out = []
    o = start
    while o + 32 <= end:
        w = struct.unpack_from('<4I', st, o)
        t = w[0] >> 29
        if t in (4, 5) and w[0] & 0xffffff:  # polygon / sprite header
            verts = []
            k = o + 32
            while k + 32 <= end and (struct.unpack_from('<I', st, k)[0] >> 29) == 7:
                f = struct.unpack_from('<8f', st, k)
                verts.append(f)
                k += 32
            if not verts:   # sprite headers carry their vertices right after in a 4 x 32 block
                for j in range(4):
                    f = struct.unpack_from('<8f', st, o + 32 + 32 * j)
                    verts.append(f)
            xs = [v[1] for v in verts]
            ys = [v[2] for v in verts]
            if all(abs(x) < 4000 for x in xs) and all(abs(y) < 4000 for y in ys) and verts and 0 < verts[0][3] < 1:
                out.append(dict(off=o, ctrl=w[0], tsp=w[2], tex=w[3], sprite=(t == 5), n=len(verts), z=verts[0][3],
                                box=(min(xs), min(ys), max(xs), max(ys))))
            o = k if k > o + 32 else o + 32
        else:
            o += 32
    return out


def main():
    st = open(sys.argv[1], 'rb').read()
    which = sys.argv[sys.argv.index('--list') + 1] if '--list' in sys.argv else 'all'
    rngs = {'opaque': [(0x253e10, 0x2a0000)], '2d': [(0x1500003, 0x1c00003)], 'all': [(0x253e10, 0x2a0000), (0x1500003, 0x1c00003)]}[which]
    for a, b in rngs:
        print('== list %#x..%#x' % (a, b))
        rows = parse(st, a, b)
        prev = None
        for r in rows:
            key = (r['tex'], r['tsp'], r['sprite'])
            sb, db = (r['tsp'] >> 29) & 7, (r['tsp'] >> 26) & 7
            if prev and prev[0] == key:
                prev[1]['cnt'] += 1
                prev[1]['zmin'] = min(prev[1]['zmin'], r['z'])
                continue
            r['cnt'] = 1
            r['zmin'] = r['z']
            prev = (key, r)
            r['blend'] = '%s->%s' % (SRC[sb], SRC[db])
            print('%#9x %s tex %08x tsp %08x %-9s z %.4f..  box (%4.0f,%4.0f)-(%4.0f,%4.0f) x1' % (
                r['off'], 'spr' if r['sprite'] else 'ply', r['tex'], r['tsp'], r['blend'], r['z'], *r['box']))


if __name__ == '__main__':
    main()
