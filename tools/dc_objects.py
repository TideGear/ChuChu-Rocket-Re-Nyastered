"""Assemble Dreamcast Ninja chunk object hierarchies (NJS_CNK_OBJECT, 52 bytes: evalflags, model*, pos[3], ang[3], scl[3], child*, sibling*)
from 1ST_READ.BIN using the models found by dc_models.py. Writes <outdir>/obj_<offset>.obj for every root (multi-part) object.
usage: dc_objects.py <1ST_READ.BIN> <outdir>"""
import math, os, struct, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dc_models as M

BASE = 0x8C010000

def main(path, out):
    d = open(path, 'rb').read(); os.makedirs(out, exist_ok=True)
    models = {o: (vl, pl) for (o, vo, po, vl, pl) in M.find_models(d, BASE)}
    maddr = {BASE + o: o for o in models}
    objs = {}
    for o in range(0, len(d) - 51, 4):
        flags, mp = struct.unpack_from('<II', d, o)
        if flags > 0xFFF: continue
        if mp != 0 and mp not in maddr: continue
        pos = struct.unpack_from('<3f', d, o + 8); scl = struct.unpack_from('<3f', d, o + 32)
        ang = struct.unpack_from('<3i', d, o + 20)
        ch, sb = struct.unpack_from('<II', d, o + 44)
        if any(abs(v) > 3000 or v != v for v in pos) or any(abs(v) > 100 or v != v for v in scl): continue
        if ch and not (BASE <= ch < BASE + len(d)): continue
        if sb and not (BASE <= sb < BASE + len(d)): continue
        objs[o] = dict(flags=flags, model=maddr.get(mp), pos=pos, ang=ang, scl=scl, child=(ch - BASE) if ch else None, sib=(sb - BASE) if sb else None)
    # keep only objects whose child/sibling links stay inside the candidate set
    changed = True
    while changed:
        changed = False
        for o in list(objs):
            x = objs[o]
            if (x['child'] is not None and x['child'] not in objs) or (x['sib'] is not None and x['sib'] not in objs):
                del objs[o]; changed = True
    referenced = set()
    for x in objs.values():
        if x['child'] is not None: referenced.add(x['child'])
        if x['sib'] is not None: referenced.add(x['sib'])
    roots = [o for o in objs if o not in referenced and (objs[o]['child'] is not None or objs[o]['model'] is not None)]
    def rot(v, a, flags):
        ax, ay, az = [t * 2 * math.pi / 65536.0 for t in a]
        x, y, z = v
        if flags & 0x20:   # ZYX order
            ops = (('x', ax), ('y', ay), ('z', az))
        else:              # XYZ order
            ops = (('z', az), ('y', ay), ('x', ax))
        for ax_, t in ops:
            c, s = math.cos(t), math.sin(t)
            if ax_ == 'x': y, z = y * c - z * s, y * s + z * c
            elif ax_ == 'y': x, z = x * c + z * s, -x * s + z * c
            else: x, y = x * c - y * s, x * s + y * c
        return (x, y, z)
    index = []
    for r in roots:
        verts = []; faces = []; uvs = []
        def walk(o, parent):
            while o is not None:
                x = objs[o]; fl = x['flags']
                def xf(v, x=x, fl=fl, parent=parent):
                    if not fl & 4: v = (v[0] * x['scl'][0], v[1] * x['scl'][1], v[2] * x['scl'][2])
                    if not fl & 2: v = rot(v, x['ang'], fl)
                    if not fl & 1: v = (v[0] + x['pos'][0], v[1] + x['pos'][1], v[2] + x['pos'][2])
                    return parent(v)
                if x['model'] is not None and not fl & 8:
                    vl, pl = models[x['model']]; base = len(verts); keys = sorted(vl); remap = {k: base + i + 1 for i, k in enumerate(keys)}
                    for k in keys: verts.append(xf(vl[k][0]))
                    for s, rev, tex, mat, *_ in pl:
                        for i in range(len(s) - 2):
                            t3 = [s[i], s[i + 1], s[i + 2]]
                            if (i & 1) ^ rev: t3[1], t3[2] = t3[2], t3[1]
                            a, b, c = t3[0][0], t3[1][0], t3[2][0]
                            if a in remap and b in remap and c in remap and len({a, b, c}) == 3:
                                faces.append((remap[a], remap[b], remap[c]))
                                uvs.append(((t3[0][1], t3[0][2]), (t3[1][1], t3[1][2]), (t3[2][1], t3[2][2]), (tex if tex is not None else 0) & 0x1fff))
                if x['child'] is not None: walk(x['child'], xf)
                o = x['sib']; 
        walk(r, lambda v: v)
        if len(faces) < 4: continue
        with open(os.path.join(out, 'obj_%06x.obj' % r), 'w') as f:
            f.write('mtllib obj_%06x.mtl' % r + chr(10))
            for v in verts: f.write('v %f %f %f' % v + chr(10))
            for u3 in uvs:
                for (u, v) in u3[:3]: f.write('vt %f %f' % (u, 1.0 - v) + chr(10))
            cur = None
            for n, t in enumerate(faces):
                tex = uvs[n][3]
                if tex != cur: f.write('usemtl tex%d' % tex + chr(10)); cur = tex
                f.write('f %d/%d %d/%d %d/%d' % (t[0], 3 * n + 1, t[1], 3 * n + 2, t[2], 3 * n + 3) + chr(10))
        with open(os.path.join(out, 'obj_%06x.mtl' % r), 'w') as f:
            for tex in sorted({u[3] for u in uvs}): f.write('newmtl tex%d' % tex + chr(10) + 'map_Kd tex%d.png' % tex + chr(10))
        index.append({'offset': r, 'vertices': len(verts), 'triangles': len(faces)})
    json.dump(index, open(os.path.join(out, 'index.json'), 'w'), indent=1)
    print(len(objs), 'objects', len(roots), 'roots', len(index), 'assembled')

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
