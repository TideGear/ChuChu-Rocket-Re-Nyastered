"""Find and export Ninja *chunk* models baked into the Dreamcast executables (no NJCM headers on disc).
Model struct (NJS_CNK_MODEL, 24 bytes): vlist ptr, plist ptr, center xyz, radius. Pointers are SH-4 addresses (base 0x8C010000).
usage: dc_models.py <1ST_READ.BIN or 2_DP.BIN> <outdir> [base=0x8C010000]
Writes <outdir>/model_<fileoffset>.obj (+ index.json). Strips are emitted as triangles with alternating winding."""
import json, os, struct, sys

def u16(d, o): return struct.unpack_from('<H', d, o)[0]
def u32(d, o): return struct.unpack_from('<I', d, o)[0]

def parse_vlist(d, o):
    """returns {absolute index: (pos, normal|None)} or None if not a vertex list"""
    verts = {}; n_chunks = 0
    while True:
        if o + 4 > len(d): return None
        t = d[o]; flags = d[o + 1]
        if t == 0xFF: break
        if not (32 <= t <= 50): return None
        size = u16(d, o + 2)                       # in 32-bit words after the 4-byte header
        if size < 1 or o + 4 + size * 4 > len(d): return None
        idx0, cnt = u16(d, o + 4), u16(d, o + 6)
        if cnt == 0 or (size - 1) * 4 % cnt: return None
        stride = (size - 1) * 4 // cnt
        if stride < 12 or stride > 48: return None
        for i in range(cnt):
            p = o + 8 + i * stride
            pos = struct.unpack_from('<3f', d, p)
            nrm = None
            if stride in (24, 28) and t in (35, 40, 41, 42, 44): nrm = struct.unpack_from('<3f', d, p + 12)
            elif stride == 32 and t in (34, ): nrm = struct.unpack_from('<3f', d, p + 16)
            if any(abs(c) > 5000 or c != c for c in pos): return None
            verts[idx0 + i] = (pos, nrm)
        o += 4 + size * 4; n_chunks += 1
        if n_chunks > 16: return None
    return verts if verts else None

STRIP_UV = {65: 256.0, 66: 1024.0, 69: 256.0, 70: 1024.0, 71: 256.0, 72: 1024.0, 73: 256.0, 74: 1024.0, 75: 1024.0}
def strip_extra(t):                                # number of u16 per vertex after the index
    return {64: 0, 65: 2, 66: 2, 67: 3, 68: 2, 69: 5, 70: 5, 71: 4, 72: 4, 73: 5, 74: 5, 75: 7}.get(t)

def parse_plist(d, o, maxidx):
    """returns list of (strip, texid, material) or None. strip = list of (index, u, v)"""
    strips = []; tex = None; mat = None; steps = 0
    while True:
        if o + 2 > len(d): return None
        t = d[o]; fl = d[o + 1]; steps += 1
        if steps > 400: return None
        if t == 0xFF: break
        if t == 0 or 1 <= t <= 5: o += 2; continue
        if t in (8, 9): tex = u16(d, o + 2); o += 4; continue
        if 16 <= t <= 23:
            size = u16(d, o + 2)
            if size > 12: return None
            mat = (t, fl, d[o + 4:o + 4 + size * 2]); o += 4 + size * 2; continue
        if 56 <= t <= 58:
            o += 4 + u16(d, o + 2) * 2; continue
        if 64 <= t <= 75:
            size = u16(d, o + 2); extra = strip_extra(t)
            if extra is None or size < 1 or o + 4 + size * 2 > len(d): return None
            end = o + 4 + size * 2; p = o + 4
            nstrips = u16(d, p) & 0x3FFF; uflags = u16(d, p) >> 14; p += 2
            for _ in range(nstrips):
                if p + 2 > end: return None
                n = struct.unpack_from('<h', d, p)[0]; p += 2
                rev = n < 0; n = abs(n); s = []
                for k in range(n):
                    if p + 2 + extra * 2 > end: return None
                    idx = u16(d, p); p += 2
                    u = v = 0.0
                    if t in STRIP_UV:
                        u = struct.unpack_from('<h', d, p)[0] / STRIP_UV[t]; v = struct.unpack_from('<h', d, p + 2)[0] / STRIP_UV[t]
                    p += extra * 2
                    if idx > maxidx: return None
                    s.append((idx, u, v))
                    if k >= 2: p += uflags * 2
                strips.append((s, rev, tex, mat, fl | t << 8))   # strip chunk flags (0x08 use alpha, 0x10 double side, 0x01 ignore light, 0x40 environment) | chunk type << 8 (64 = no UVs)
            o = end; continue
        return None
    return strips if strips else None

def find_models(d, base):
    out = []
    n = len(d)
    for o in range(0, n - 23, 4):
        va, pa = u32(d, o), u32(d, o + 4)
        if not (base <= va < base + n and base <= pa < base + n): continue
        vo, po = va - base, pa - base
        if d[vo] < 32 or d[vo] > 50: continue
        rad = struct.unpack_from('<f', d, o + 20)[0]
        if not (0.0 <= rad < 5000) or rad != rad: continue
        vl = parse_vlist(d, vo)
        if not vl: continue
        pl = parse_plist(d, po, max(vl))
        if not pl: continue
        out.append((o, vo, po, vl, pl))
    return out

def write_obj(path, vl, pl):
    keys = sorted(vl); remap = {k: i + 1 for i, k in enumerate(keys)}
    with open(path, 'w') as f:
        for k in keys: f.write('v %f %f %f\n' % vl[k][0])
        for k in keys:
            if vl[k][1]: f.write('vn %f %f %f\n' % vl[k][1])
        tris = 0
        for s, rev, tex, mat, *_ in pl:
            f.write('# strip tex=%s\n' % tex)
            for i in range(len(s) - 2):
                a, b, c = s[i][0], s[i + 1][0], s[i + 2][0]
                if (i & 1) ^ rev: b, c = c, b
                if a in remap and b in remap and c in remap and len({a, b, c}) == 3:
                    f.write('f %d %d %d\n' % (remap[a], remap[b], remap[c])); tris += 1
    return tris

def main(path, out, base=0x8C010000):
    d = open(path, 'rb').read(); os.makedirs(out, exist_ok=True)
    models = find_models(d, base); idx = []
    for (o, vo, po, vl, pl) in models:
        name = 'model_%06x' % o
        tris = write_obj(os.path.join(out, name + '.obj'), vl, pl)
        idx.append({'struct_offset': o, 'vlist': vo, 'plist': po, 'vertices': len(vl), 'strips': len(pl), 'triangles': tris,
                    'textures': sorted({s[2] for s in pl if s[2] is not None})})
    json.dump(idx, open(os.path.join(out, 'index.json'), 'w'), indent=1)
    print(os.path.basename(path), len(models), 'models')

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], int(sys.argv[3], 0) if len(sys.argv) > 3 else 0x8C010000)
