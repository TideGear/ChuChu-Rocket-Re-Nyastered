#!/usr/bin/env python3
"""Decode the PowerVR parameter stream (the game's own draw calls) from a Flycast libretro save state written by flyhost with FLY_DUMP=1.
Prints/returns polygons: header (ctrl, isp, tsp, tex) and vertices (x, y, z=1/w, u, v, base, offset) in 640x480 screen space.
usage: ta_parse.py <file.state> [start_hex end_hex]"""
import struct, sys
def parse(st, start, end):
    polys = []; o = start; cur = None
    while o + 32 <= end:
        w = struct.unpack_from('<8I', st, o); t = w[0] >> 29
        if t == 4 or t == 5:                       # polygon / sprite header (8 words)
            cur = dict(off=o, ctrl=w[0], isp=w[1], tsp=w[2], tex=w[3], verts=[], sprite=(t == 5)); polys.append(cur); o += 32
        elif t == 7 and cur is not None:           # vertex (8 words)
            f = struct.unpack_from('<8f', st, o); cur['verts'].append((w[0],) + f[1:]); o += 32
            if w[0] & 0x10000000: cur = None
        elif w[0] == 0: o += 32
        else: o += 32
    return polys
if __name__ == '__main__':
    st = open(sys.argv[1], 'rb').read()
    a = int(sys.argv[2], 16) if len(sys.argv) > 2 else 0x253dc8; b = int(sys.argv[3], 16) if len(sys.argv) > 3 else 0x268600
    P = parse(st, a, b); print(len(P), 'polygons')
    for p in P[:60]:
        xs = [v[1] for v in p['verts']] or [0]; ys = [v[2] for v in p['verts']] or [0]
        print(hex(p['off']), 'ctrl %08x tsp %08x tex %08x' % (p['ctrl'], p['tsp'], p['tex']), 'n=%d' % len(p['verts']), 'x %.0f..%.0f y %.0f..%.0f' % (min(xs), max(xs), min(ys), max(ys)))
