"""Pack the assembled Dreamcast character models (tools/dc_objects.py output) and their textures into one binary the app loads: <assets>/dreamcast/models.bin.
Format (little endian): 'CCM2', u32 nTextures, per texture {u16 w, u16 h, w*h*4 RGBA bytes}; u32 nModels, per model {char name[24], u32 nTris, u32 nMats, u32 matTexture[nMats],
nTris x {u8 material, 3 x {f32 x, y, z, u, v}}, u32 nFrames, nFrames x nTris x 9 f32 (x, y, z of the 3 vertices: vertex-morph frames, same triangle order)}.
The cat's head is animated by a 24-frame vertex-morph table (docs/dreamcast_models.md): frame k replaces the 69 head vertices; frames 17 and 23 equal the base pose.
Models and their texture lists (docs/dreamcast_models.md): the cat object 0x778c4 uses c_cat01..04; the basic mouse's eight walk keyframes 0x7efb8.. use the MOUSE archive in the
executable's slot order 01, 02, 03, 05, 04, 06, 07, 08, 09, 10 (material index = slot).
usage: export_dc_models.py <assets/dreamcast folder>"""
import os, struct, sys
from PIL import Image

CAT_TEX = ['CAT_c_cat01', 'CAT_c_cat02', 'CAT_c_cat03', 'CAT_c_cat04']
MOUSE_TEX = ['MOUSE_c_mouse%02d' % n for n in (1, 2, 3, 5, 4, 6, 7, 8, 9, 10)]
# BATTLEMODELS texture list in the executable's order (NJS_TEXNAME array at 0x75a8c; index = the material number in the objects; verified by the 4 rocket-lid objects using 12..15 = rokefuta01..04 and the four rocket colours using the matching ita/mado pairs)
BATTLE_TEX = ['sphere_tx', 'ins', 'bluemado', 'itablue', 'itaorange', 'orangemado', 'itared', 'redmado', 'greenmado', 'itagreen', 'outs', 'rue729', 'rokefuta01', 'rokefuta02', 'rokefuta03', 'rokefuta04',
              'newk1', 'newk1s', 'newk2', 'newk2s', 'newk3', 'newk3s', 'newk4', 'newk4s', 's01', 'rfire01', 'rfire04', 'rfire03', 'rfire02', 'yuka01', 'yuka02', 'yuka03', 'yuka04', 'yuka05', 'yuka06',
              'kabetx01', 'kabetx02', 'kabetx03']
BATTLE_TEX = ['BATTLEMODELS_' + n for n in BATTLE_TEX]
MODELS = [('cat', '0778c4', CAT_TEX)] + [('mouse%d' % i, o, MOUSE_TEX) for i, o in enumerate(('07efb8', '07fe38', '080cb8', '081b38', '0829b8', '083838', '0846b8', '085538'))]     + [('rocket_blue', '09a340', BATTLE_TEX), ('rocket_orange', '09b490', BATTLE_TEX), ('rocket_red', '09c5e0', BATTLE_TEX), ('rocket_green', '09d730', BATTLE_TEX),
       ('lid1', '0987b8', BATTLE_TEX), ('lid2', '098b20', BATTLE_TEX), ('lid3', '098e88', BATTLE_TEX), ('lid4', '0991f0', BATTLE_TEX), ('fire', '0a0258', BATTLE_TEX), ('wall', '0a2114', BATTLE_TEX)]

def load_obj_indexed(path):
    V, T, F = [], [], []
    mat = 0
    for line in open(path):
        k = line.split()
        if not k: continue
        if k[0] == 'v': V.append(tuple(map(float, k[1:4])))
        elif k[0] == 'vt': T.append((float(k[1]), float(k[2])))
        elif k[0] == 'usemtl': mat = int(k[1][3:])
        elif k[0] == 'f': F.append((mat, [(int(p.split('/')[0]) - 1, int(p.split('/')[1]) - 1) for p in k[1:4]]))
    return V, T, F

def cat_morph_frames(root, V):
    """Vertex-morph frames of the cat head (table at 0x7ceb4, 24 frames of 69 xyz floats): returns a list of 24 full vertex arrays (object space)."""
    d = open(os.path.join(root, '..', '..', '..', '..', 'analysis', 'extracted', 'dc_files', '1ST_READ.BIN'), 'rb').read(); base = 0x8C010000
    import sys as _s; _s.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import dc_models as M
    vl = {o: v for (o, vo, po, v, pl) in M.find_models(d, base)}[0x778ac]; keys = sorted(vl); b0 = [vl[k][0] for k in keys]
    delta = [V[i][j] - b0[i][j] for i in range(len(keys)) for j in range(3)]
    dx = [delta[j] for j in range(3)]
    assert all(abs(delta[3 * i + j] - dx[j]) < 1e-3 for i in range(len(keys)) for j in range(3)), 'the head is not a pure translation of its object space'
    frames = []
    for k in range(24):
        p = struct.unpack_from('<II', d, 0x7ceb4 + 8 * k)[1] - base
        fr = [list(v) for v in V]
        for i in range(len(keys)):
            x, y, z = struct.unpack_from('<3f', d, p + 12 * i); fr[i] = [x + dx[0], y + dx[1], z + dx[2]]
        frames.append(fr)
    return frames

def cat_pose_frames(root):
    """Full 24-frame cat animation from the two Ninja motions the game plays together (draw call 0x8c0e673e with 0x8c088108 and 0x8c08cfd4, frame = a float in [0, 24)):
    motion A (type 0x7, 24 keys per animated node: 'ang' and 'pos' key lists) turns/moves the feet and tail nodes 1, 2, 3 and 5; motion B (type 0x30) morphs the head's 69 vertices
    (node 0). Returns 24 flat position arrays in the triangle order of obj_0778c4.obj (3 vertices x xyz per triangle)."""
    import math
    d = open(os.path.join(root, '..', '..', '..', '..', 'analysis', 'extracted', 'dc_files', '1ST_READ.BIN'), 'rb').read(); B = 0x8C010000
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import dc_models as M
    models = {B + o: (vl, pl) for (o, vo, po, vl, pl) in M.find_models(d, B)}
    def node(a):
        o = a - B; fl, mp = struct.unpack_from('<II', d, o)
        return dict(fl=fl, mp=mp, pos=list(struct.unpack_from('<3f', d, o + 8)), ang=list(struct.unpack_from('<3i', d, o + 20)), scl=struct.unpack_from('<3f', d, o + 32), ch=struct.unpack_from('<I', d, o + 44)[0], sb=struct.unpack_from('<I', d, o + 48)[0])
    order = []
    def walk(a, parent):
        while a:
            n = node(a); n['parent'] = parent; order.append(n)
            if n['ch']: walk(n['ch'], len(order) - 1)
            a = n['sb']
    walk(0x8c0878c4, None)
    def keys(ptr, kind):
        o = ptr - B
        return [struct.unpack_from('<Iiii' if kind == 'ang' else '<Ifff', d, o + 16 * i)[1:] for i in range(24)]
    angk = {1: keys(0x8c0878f8, 'ang'), 2: keys(0x8c087a78, 'ang'), 3: keys(0x8c087d78, 'ang'), 5: keys(0x8c087ef8, 'ang')}
    posk = {3: keys(0x8c087bf8, 'pos')}
    vkeys = [struct.unpack_from('<II', d, 0x7ceb4 + 8 * k)[1] - B for k in range(24)]
    def rot(v, a, flags):
        ax, ay, az = [t * 2 * math.pi / 65536.0 for t in a]
        x, y, z = v
        ops = (('x', ax), ('y', ay), ('z', az)) if flags & 0x20 else (('z', az), ('y', ay), ('x', ax))
        for ax_, t in ops:
            c, s_ = math.cos(t), math.sin(t)
            if ax_ == 'x': y, z = y * c - z * s_, y * s_ + z * c
            elif ax_ == 'y': x, z = x * c + z * s_, -x * s_ + z * c
            else: x, y = x * c - y * s_, x * s_ + y * c
        return (x, y, z)
    frames = []
    for f in range(24):
        pos = [list(n['pos']) for n in order]; ang = [list(n['ang']) for n in order]
        for i, k in angk.items(): ang[i] = list(k[f])
        for i, k in posk.items(): pos[i] = list(k[f])
        def world(i, v):
            while i is not None:
                n = order[i]; fl = n['fl']
                if not fl & 4: v = (v[0] * n['scl'][0], v[1] * n['scl'][1], v[2] * n['scl'][2])
                if not fl & 2: v = rot(v, ang[i], fl)
                if not fl & 1: v = (v[0] + pos[i][0], v[1] + pos[i][1], v[2] + pos[i][2])
                i = n['parent']
            return v
        verts = []; tris = []
        for i, n in enumerate(order):
            if n['mp'] == 0 or n['fl'] & 8: continue
            vl, pl = models[n['mp']]; keys_ = sorted(vl); base = len(verts); remap = {k: base + j for j, k in enumerate(keys_)}
            for j, k in enumerate(keys_):
                p = vl[k][0]
                if i == 0: p = struct.unpack_from('<3f', d, vkeys[f] + 12 * j)   # head: motion B replaces the vertex positions
                verts.append(world(i, p))
            for strip, rev, tex, mat in pl:
                for q in range(len(strip) - 2):
                    t3 = [strip[q], strip[q + 1], strip[q + 2]]
                    if (q & 1) ^ rev: t3[1], t3[2] = t3[2], t3[1]
                    a_, b_, c_ = t3[0][0], t3[1][0], t3[2][0]
                    if a_ in remap and b_ in remap and c_ in remap and len({a_, b_, c_}) == 3: tris.append((remap[a_], remap[b_], remap[c_]))
        frames.append([c for t in tris for vi in t for c in verts[vi]])
    return frames

def load_obj(path):
    V, T, tris, mat = [], [], [], 0
    for line in open(path):
        k = line.split()
        if not k: continue
        if k[0] == 'v': V.append(tuple(map(float, k[1:4])))
        elif k[0] == 'vt': T.append((float(k[1]), float(k[2])))
        elif k[0] == 'usemtl': mat = int(k[1][3:])
        elif k[0] == 'f':
            idx = [(int(p.split('/')[0]) - 1, int(p.split('/')[1]) - 1) for p in k[1:4]]
            tris.append((mat, [(V[a], T[b]) for a, b in idx]))
    return tris

def main(root):
    tex_ids, textures = {}, []
    def tex(name):
        if name not in tex_ids:
            im = Image.open(os.path.join(root, 'prs_png', name + '.png')).convert('RGBA')
            tex_ids[name] = len(textures); textures.append(im)
        return tex_ids[name]
    models = []
    for name, off, texlist in MODELS:
        V, T, F = load_obj_indexed(os.path.join(root, 'objects', 'obj_%s.obj' % off))
        tris = [(m, [(V[a], T[b]) for a, b in idx]) for m, idx in F]
        nm = max(m for m, _ in tris) + 1
        mats = [tex(texlist[m]) if m < len(texlist) else 0 for m in range(nm)]
        frames = []
        if name == 'cat':
            frames = cat_pose_frames(root)
            assert all(len(fr) == len(F) * 9 for fr in frames), (len(frames[0]), len(F) * 9)
        models.append((name, tris, mats, frames))
    out = bytearray(b'CCM2' + struct.pack('<I', len(textures)))
    for im in textures:
        out += struct.pack('<HH', im.width, im.height) + im.tobytes()
    out += struct.pack('<I', len(models))
    for name, tris, mats, frames in models:
        out += name.encode().ljust(24, b'\0') + struct.pack('<II', len(tris), len(mats)) + struct.pack('<%dI' % len(mats), *mats)
        for m, vs in tris:
            out += struct.pack('<B', m)
            for (x, y, z), (u, v) in vs: out += struct.pack('<5f', x, y, z, u, v)
        out += struct.pack('<I', len(frames))
        for fr in frames: out += struct.pack('<%df' % len(fr), *fr)
    open(os.path.join(root, 'models.bin'), 'wb').write(out)
    print('models', len(models), 'textures', len(textures), 'bytes', len(out))

if __name__ == '__main__': main(sys.argv[1])
