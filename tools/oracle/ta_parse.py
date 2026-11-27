#!/usr/bin/env python3
"""Decode the PowerVR parameter stream (the game's own draw calls) from a Flycast libretro save state written by flyhost with FLY_DUMP=1.
Prints/returns polygons: header (ctrl, isp, tsp, tex) and vertices (x, y, z=1/w, u, v, base, offset) in 640x480 screen space.
usage: ta_parse.py <file.state> [start_hex end_hex | --auto]"""
import struct, sys

def packets(st):
    """Find viewport polygon packets without assuming a serialized offset or
    alignment. Core versions place TA data on different byte boundaries.
    Require an exact vertex command plus finite viewport coordinates to avoid
    treating texture bytes as a parameter stream. Stale buffers may also be
    returned; callers must match the packet to the live task/mesh.
    """
    seen = set()
    for command in (b'\0\0\0\xe0', b'\0\0\0\xf0'):
        off = 0
        while True:
            vertex = st.find(command, off)
            if vertex < 0: break
            off = vertex + 1; start = vertex - 32
            if start < 0 or start in seen or struct.unpack_from('<I', st, start)[0] >> 29 not in (4, 5): continue
            end = vertex; count = 0
            while end + 32 <= len(st) and struct.unpack_from('<I', st, end)[0] in (0xe0000000, 0xf0000000):
                x, y, depth = struct.unpack_from('<3f', st, end + 4)
                if not (-200 < x < 900 and -200 < y < 700 and 0 < depth < 100): break
                count += 1; end += 32
            if count >= 3:
                seen.add(start)
                yield parse(st, start, end)[0]
def parse(st, start, end):
    polys = []; o = start; cur = None
    while o + 32 <= end:
        w = struct.unpack_from('<8I', st, o); t = w[0] >> 29
        if t == 4 or t == 5:                       # polygon / sprite header (8 words)
            cur = dict(off=o, ctrl=w[0], isp=w[1], tsp=w[2], tex=w[3], verts=[], strips=[], sprite=(t == 5)); polys.append(cur); o += 32
        elif t == 7 and cur is not None:           # vertex (8 words)
            f = struct.unpack_from('<8f', st, o); packed = struct.unpack_from('<I', st, o + 16)[0]
            pu = struct.unpack('<f', struct.pack('<I', packed & 0xFFFF0000))[0]; pv = struct.unpack('<f', struct.pack('<I', (packed << 16) & 0xFFFFFFFF))[0]   # 16-bit UV (ctrl bit 0): U in the high half, V in the low half
            v = (w[0],) + f[1:] + (pu, pv); o += 32
            if not cur['strips'] or cur.get('closed'): cur['strips'].append([]); cur['closed'] = False
            cur['strips'][-1].append(v)
            if len(cur['strips']) == 1: cur['verts'].append(v)    # 'verts' keeps the first strip, as before
            if w[0] & 0x10000000: cur['closed'] = True            # end of strip: the next vertices start a new strip under the SAME header (the TA keeps the last global parameter)
        elif w[0] == 0: o += 32
        else: o += 32
    return polys
if __name__ == '__main__':
    st = open(sys.argv[1], 'rb').read()
    if '--auto' in sys.argv: P = list(packets(st))
    else:
        a = int(sys.argv[2], 16) if len(sys.argv) > 2 else 0x253dc8; b = int(sys.argv[3], 16) if len(sys.argv) > 3 else 0x268600
        P = parse(st, a, b)
    print(len(P), 'polygons')
    for p in P[:60]:
        xs = [v[1] for v in p['verts']] or [0]; ys = [v[2] for v in p['verts']] or [0]
        print(hex(p['off']), 'ctrl %08x tsp %08x tex %08x' % (p['ctrl'], p['tsp'], p['tex']), 'n=%d' % len(p['verts']), 'x %.0f..%.0f y %.0f..%.0f' % (min(xs), max(xs), min(ys), max(ys)))
