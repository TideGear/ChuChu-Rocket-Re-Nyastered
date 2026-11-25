"""Pack the Dreamcast character and board models (Ninja chunk objects in 1ST_READ.BIN) and their textures into one binary the app loads: <assets>/dreamcast/models.bin.
Each object tree (NJS_CNK_OBJECT: evalflags, model*, pos, ang, scl, child*, sibling*) is assembled here with its vertex NORMALS (vertex chunk type 41 = position + normal) so the app can
light it the way the Dreamcast does. The cat is animated by two Ninja motions the game plays together (docs/dreamcast_models.md): its 24 poses are stored with positions and normals.
Format 'CCM3' (little endian): u32 nTextures, per texture {u16 w, u16 h, w*h*4 RGBA}; u32 nModels, per model {char name[24], u32 nTris, u32 nMats, u32 matTexture[nMats],
nTris x {u8 material, 3 x {f32 x, y, z, u, v, nx, ny, nz}}, u32 nFrames, nFrames x nTris x 18 f32 (x, y, z, nx, ny, nz of the 3 vertices)}.
usage: export_dc_models.py <assets/dreamcast folder with prs_png/> <1ST_READ.BIN>"""
import math, os, struct, sys
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dc_models as M

BASE = 0x8C010000
CAT_TEX = ['CAT_c_cat01', 'CAT_c_cat02', 'CAT_c_cat03', 'CAT_c_cat04']
MOUSE_TEX = ['MOUSE_c_mouse%02d' % n for n in (1, 2, 3, 5, 4, 6, 7, 8, 9, 10)]
CHAO_TEX = ['CHAO_c_mouse06', 'CHAO_c_mouse08', 'CHAO_c_chao01', 'CHAO_c_chao02', 'CHAO_c_chao03', 'CHAO_c_chao08', 'CHAO_c_chao09', 'CHAO_c_chao10', 'CHAO_c_chao11']
PIAN_TEX = ['PIAN_chu_p%02d' % n for n in range(1, 9)]
# BATTLEMODELS texture list in the executable's order (NJS_TEXNAME array at 0x75a8c; index = material number; checked by the rocket lids using 12..15 = rokefuta01..04 and the four rocket colours)
BATTLE_TEX = ['BATTLEMODELS_' + n for n in ['sphere_tx', 'ins', 'bluemado', 'itablue', 'itaorange', 'orangemado', 'itared', 'redmado', 'greenmado', 'itagreen', 'outs', 'rue729',
              'rokefuta01', 'rokefuta02', 'rokefuta03', 'rokefuta04', 'newk1', 'newk1s', 'newk2', 'newk2s', 'newk3', 'newk3s', 'newk4', 'newk4s', 's01', 'rfire01', 'rfire04', 'rfire03',
              'rfire02', 'yuka01', 'yuka02', 'yuka03', 'yuka04', 'yuka05', 'yuka06', 'kabetx01', 'kabetx02', 'kabetx03']]
# (name, root object file offset, texture list). The board pieces are single models: 0xa21e8 is one 180 x 135 quad (the whole 12 x 9 board floor, yuka01), 0xa20fc a wall piece (kabetx01).
# FOURADV texture list in the executable's order (NJS_TEXNAME array at 0x8c0ba160): the in-game HUD of the four-player modes is a 3D scene of flat models using it
HUD_TEX = ['FOURADV_' + n for n in ['disp01k', 'disp02k', 'disp03', 'tensu'] + ['nums%02d' % i for i in range(10)]]
HUD_OFFS = (0xaa370, 0xaa46c, 0xaa760, 0xaaa54, 0xab03c, 0xab180, 0xab290, 0xab674, 0xabe04, 0xac3e4, 0xade98, 0xb0c7c, 0xb0db4, 0xb0eec, 0xb1024, 0xb1178, 0xb1274, 0xb1370, 0xb146c, 0xb15c0, 0xb16bc)
MODELS = [('cat', 0x778c4, CAT_TEX)] + [('mouse%d' % i, o, MOUSE_TEX) for i, o in enumerate((0x7efb8, 0x7fe38, 0x80cb8, 0x81b38, 0x829b8, 0x83838, 0x846b8, 0x85538))] + [
    ('rocket_blue', 0x9a340, BATTLE_TEX), ('rocket_orange', 0x9b490, BATTLE_TEX), ('rocket_red', 0x9c5e0, BATTLE_TEX), ('rocket_green', 0x9d730, BATTLE_TEX),
    ('lid1', 0x987b8, BATTLE_TEX), ('lid2', 0x98b20, BATTLE_TEX), ('lid3', 0x98e88, BATTLE_TEX), ('lid4', 0x991f0, BATTLE_TEX), ('fire', 0xa0258, BATTLE_TEX),
    # The Flycast stream shows 'outs' at hole tiles in Challenge and 'ins' at
    # generators in Battle and Team Battle. Keep the historical pack names.
    ('wall', 0xa20fc, BATTLE_TEX), ('floor', 0xa21e8, BATTLE_TEX),
    ('hole_out', 0xa2990, BATTLE_TEX), ('hole_in', 0xa2628, BATTLE_TEX),
    ('roulette', 0xa302c, BATTLE_TEX)]  # FUN_8c01d9a0 submits object 0x8c0b302c

# 0x8c01b77c draws bare models from table 0x8c0b4a50. The object nodes
# above add y=9.5 and are different draw inputs; retain them for other callers.
MODELS += [(name, off, BATTLE_TEX) for name, off in (
    ('launch_blue', 0x9a328), ('launch_orange', 0x9b478),
    ('launch_red', 0x9c5c8), ('launch_green', 0x9d718), ('launch_base', 0x98438))]

# Mouse draw dispatcher 0x8c019e26 part trees (roots 0x8c08e138 kind 2, 0x8c0960ec kind 1, 0x8c096be8 chain); texture slots as MOUSE_TEX
MODELS += [('mouse_a', 0x7e138, MOUSE_TEX), ('mouse_b', 0x860ec, MOUSE_TEX), ('mouse_c', 0x86be8, MOUSE_TEX), ('ghost', 0x87e44, MOUSE_TEX)]   # ghost: object 0x8c097e44 + motion 0x8c0988a0 (8 frames), drawn by 0x8c0192e0 with texture list 0x8c085d18
MODELS += [('chao%d' % i, 0x8c818 + 0xb98 * i, CHAO_TEX) for i in range(8)]
MODELS += [('pian%d' % i, 0x93230 + 0xb8c * i, PIAN_TEX) for i in range(8)]
MODELS += [('h_%x' % o, o, HUD_TEX) for o in HUD_OFFS]

def rot(v, a, flags):
    ax, ay, az = [t * 2 * math.pi / 65536.0 for t in a]
    x, y, z = v
    # Node rotation order (measured on Flycast frame 3550: ghost region error 10.35 -> 7.72, cat region 5.86 -> 4.79): X, then Y, then Z by default; the 0x20 flag (ZXY_ANG) selects Z, Y, X.
    for ax_, t in ((('z', az), ('y', ay), ('x', ax)) if flags & 0x20 else (('x', ax), ('y', ay), ('z', az))):
        c, s = math.cos(t), math.sin(t)
        if ax_ == 'x': y, z = y * c - z * s, y * s + z * c
        elif ax_ == 'y': x, z = x * c + z * s, -x * s + z * c
        else: x, y = x * c - y * s, x * s + y * c
    return (x, y, z)

class Pack:
    def __init__(self, exe):
        self.d = open(exe, 'rb').read()
        self.models = {BASE + o: (vl, pl) for (o, vo, po, vl, pl) in M.find_models(self.d, BASE)}
    def node(self, addr):
        d, o = self.d, addr - BASE
        fl, mp = struct.unpack_from('<II', d, o)
        return dict(fl=fl, mp=mp, pos=list(struct.unpack_from('<3f', d, o + 8)), ang=list(struct.unpack_from('<3i', d, o + 20)), scl=struct.unpack_from('<3f', d, o + 32),
                    ch=struct.unpack_from('<I', d, o + 44)[0], sb=struct.unpack_from('<I', d, o + 48)[0])
    def tree(self, root_off):
        if BASE + root_off in self.models:   # a bare model (not an object node): a single identity node
            return [dict(fl=0, mp=BASE + root_off, pos=[0.0, 0.0, 0.0], ang=[0, 0, 0], scl=(1.0, 1.0, 1.0), ch=0, sb=0, parent=None)]
        order = []
        def walk(a, parent):
            while a:
                n = self.node(a); n['parent'] = parent; order.append(n)
                if n['ch']: walk(n['ch'], len(order) - 1)
                a = n['sb']
        walk(BASE + root_off, None); return order
    def assemble(self, order, pos=None, ang=None, head=None, special=False, untextured=0):
        """Triangles of the object tree: list of (material, [(x, y, z, u, v, nx, ny, nz) x 3]). pos/ang: per-node overrides (animation); head: replacement positions of node 0's vertices."""
        pos = pos or [list(n['pos']) for n in order]; ang = ang or [list(n['ang']) for n in order]
        def world(i, v, normal=False):
            while i is not None:
                n = order[i]; fl = n['fl']
                if not normal and not fl & 4: v = (v[0] * n['scl'][0], v[1] * n['scl'][1], v[2] * n['scl'][2])
                if not fl & 2: v = rot(v, ang[i], fl)
                if not normal and not fl & 1: v = (v[0] + pos[i][0], v[1] + pos[i][1], v[2] + pos[i][2])
                i = n['parent']
            return v
        verts = []; tris = []
        for i, n in enumerate(order):
            if n['mp'] == 0 or n['fl'] & 8: continue
            vl, pl = self.models[n['mp']]; keys = sorted(vl); base = len(verts); remap = {k: base + j for j, k in enumerate(keys)}
            for j, k in enumerate(keys):
                p, nr = vl[k]
                if i == 0 and head is not None: p = head[j]
                w = world(i, p); nw = world(i, nr if nr else (0.0, 1.0, 0.0), True)
                l = math.sqrt(nw[0] ** 2 + nw[1] ** 2 + nw[2] ** 2) or 1.0
                verts.append(tuple(w) + (nw[0] / l, nw[1] / l, nw[2] / l))
            for strip, rev, tex, mat, sfl in pl:
                for q in range(len(strip) - 2):
                    t3 = [strip[q], strip[q + 1], strip[q + 2]]
                    if (q & 1) ^ rev: t3[1], t3[2] = t3[2], t3[1]
                    a, b, c = t3[0][0], t3[1][0], t3[2][0]
                    if a in remap and b in remap and c in remap and len({a, b, c}) == 3:
                        tris.append(((10 if special and mat[0] == 17 and tex is not None and (tex & 0x1fff) == 2 else (tex if tex is not None else untextured) & 0x1fff) | (0xc0 if sfl >> 8 == 64 and not sfl & 0x40 else (0x80 if sfl & 8 else 0) | (0x40 if sfl & 0x40 else 0)), [verts[remap[x[0]]][:3] + (x[1], 1.0 - x[2]) + verts[remap[x[0]]][3:] for x in t3]))
        return tris
    def assemble_cached(self, order, pos=None, ang=None):
        """Objects whose polygon lists live apart from their vertex lists (the ghost 0x8c097e44): every node's vertex chunk writes its vertices, transformed by that node's matrix, into one shared
        buffer in tree order; a polygon list that starts with a CachePolygonList chunk (type 4, index in the flags byte) is stored, and a DrawPolygonList chunk (type 5) draws the stored list with
        the buffer as it is at that node; a plain polygon list draws at once. Same triangle format as `assemble`."""
        d = self.d
        pos = pos or [list(n['pos']) for n in order]; ang = ang or [list(n['ang']) for n in order]
        def world(i, v, normal=False):
            while i is not None:
                n = order[i]; fl = n['fl']
                if not normal and not fl & 4: v = (v[0] * n['scl'][0], v[1] * n['scl'][1], v[2] * n['scl'][2])
                if not fl & 2: v = rot(v, ang[i], fl)
                if not normal and not fl & 1: v = (v[0] + pos[i][0], v[1] + pos[i][1], v[2] + pos[i][2])
                i = n['parent']
            return v
        buf = {}; blend = {}; cache = {}; tris = []
        def draw(strips):
            for strip, rev, tex, mat, *_ in strips:
                for q in range(len(strip) - 2):
                    t3 = [strip[q], strip[q + 1], strip[q + 2]]
                    if (q & 1) ^ rev: t3[1], t3[2] = t3[2], t3[1]
                    if all(x[0] in buf for x in t3) and len({x[0] for x in t3}) == 3:
                        tris.append((10 if tex is None else tex & 0x1fff, [buf[x[0]][0] + (x[1], 1.0 - x[2]) + buf[x[0]][1] for x in t3]))
        for i, n in enumerate(order):
            if n['mp'] == 0 or n['fl'] & 8: continue
            va, pa = struct.unpack_from('<II', d, n['mp'] - BASE)
            if va:
                # Vertex chunks: type 41 (position, normal) assign their slots; type 44 (position, normal, Ninja flags) are weighted contributions: slot = chunk start + (flags & 0xffff),
                # weight = (flags >> 16) / 255, and the contributions of the nodes that share a slot add up to one (checked on the ghost's tail and body chunks).
                o = va - BASE
                while d[o] != 0xff:
                    t = d[o]; size = struct.unpack_from('<H', d, o + 2)[0]; idx0, cnt = struct.unpack_from('<HH', d, o + 4); stride = (size - 1) * 4 // cnt
                    for k in range(cnt):
                        q = o + 8 + k * stride; p = struct.unpack_from('<3f', d, q); nr = struct.unpack_from('<3f', d, q + 12) if stride >= 24 else (0.0, 1.0, 0.0)
                        w = world(i, p); nw = world(i, nr, True)
                        if t == 44:
                            fl = struct.unpack_from('<I', d, q + 24)[0]; slot = idx0 + (fl & 0xffff); wt = (fl >> 16) / 255.0
                            if slot in blend: bw, bp, bn = blend[slot]; blend[slot] = (bw + wt, [a + wt * b for a, b in zip(bp, w)], [a + wt * b for a, b in zip(bn, nw)])
                            else: blend[slot] = (wt, [wt * c for c in w], [wt * c for c in nw])
                        else:
                            blend.pop(idx0 + k, None); buf[idx0 + k] = (tuple(w), tuple(c / (math.sqrt(sum(x * x for x in nw)) or 1.0) for c in nw))
                    o += 4 + size * 4
                for slot, (bw, bp, bn) in blend.items():
                    l = math.sqrt(sum(x * x for x in bn)) or 1.0
                    buf[slot] = (tuple(c / (bw or 1.0) for c in bp), tuple(c / l for c in bn))   # divide by the summed weight so a slot that has not collected every share yet is still a point
            if pa:
                kind, idx = d[pa - BASE], d[pa - BASE + 1]
                strips = M.parse_plist(d, pa - BASE if kind != 5 else pa - BASE + 2, 0xffff) if kind != 5 else None
                if kind == 4: cache[idx] = strips
                elif kind == 5: draw(cache.get(idx) or [])
                elif strips: draw(strips)
        return tris
    def cat_frames(self, order):
        """The cat's 24 poses: motion A (skeleton keys of nodes 1, 2, 3, 5) and motion B (head vertex morph, table at 0x7ceb4)."""
        d = self.d
        def keys(ptr, kind): return [struct.unpack_from('<Iiii' if kind == 'ang' else '<Ifff', d, ptr - BASE + 16 * i)[1:] for i in range(24)]
        angk = {1: keys(0x8c0878f8, 'ang'), 2: keys(0x8c087a78, 'ang'), 3: keys(0x8c087d78, 'ang'), 5: keys(0x8c087ef8, 'ang')}
        posk = {3: keys(0x8c087bf8, 'pos')}
        frames = []
        for f in range(24):
            pos = [list(n['pos']) for n in order]; ang = [list(n['ang']) for n in order]
            for i, k in angk.items(): ang[i] = list(k[f])
            for i, k in posk.items(): pos[i] = list(k[f])
            vk = struct.unpack_from('<II', d, 0x7ceb4 + 8 * f)[1] - BASE
            head = [struct.unpack_from('<3f', d, vk + 12 * j) for j in range(69)]
            frames.append(self.assemble(order, pos, ang, head))
        return frames

def motion_frames(pack, order, md, nframes):
    """Poses of an object tree driven by a Ninja motion (NJS_MOTION data at `md`: per node, in tree order, three keyframe tracks (position, angle, scale), each a pointer and a count;
    keyframe = u32 frame + three values; position and scale are floats, angle is a 16-bit-turn integer). Linear interpolation between keyframes, as the ghost task uses (0x8c0988a0)."""
    d = pack.d
    md = struct.unpack_from('<I', d, md - BASE)[0]   # NJS_MOTION { mdata pointer, frame count, type, inp_fn }
    def track(p, n, fmt):
        return [(struct.unpack_from('<I', d, p - BASE + 16 * i)[0], list(struct.unpack_from(fmt, d, p - BASE + 16 * i + 4))) for i in range(n)]
    tracks = []
    for k in range(len(order)):
        e = struct.unpack_from('<6I', d, md - BASE + 24 * k)
        tracks.append([track(e[j], e[3 + j], '<3i' if j == 1 else '<3f') if e[j] and e[3 + j] else None for j in range(3)])
    def sample(kfs, f):
        if f <= kfs[0][0]: return list(kfs[0][1])
        for (f0, v0), (f1, v1) in zip(kfs, kfs[1:]):
            if f <= f1:
                t = (f - f0) / float(f1 - f0)
                return [a + (b - a) * t for a, b in zip(v0, v1)]
        return list(kfs[-1][1])
    frames = []
    for f in range(nframes):
        pos = [list(n['pos']) for n in order]; ang = [list(n['ang']) for n in order]
        for k, (tp, ta, ts) in enumerate(tracks):
            if tp: pos[k] = sample(tp, f)
            if ta: ang[k] = [int(round(x)) for x in sample(ta, f)]
        frames.append(pack.assemble_cached(order, pos, ang))
    return frames

def golden_mouse_frames(pack, order):
    """0x8c019e26 dispatches kind 1 through motion 0x8c09661c (8 frames, POS|ANG).
    Its six node tracks are the five-key tables at 0x8c0963dc..0x8c09656c:
    root position followed by one angle track for each child in tree order.
    """
    d = pack.d
    motion, count, kind = struct.unpack_from('<3I', d, 0x8661c)
    assert motion == 0x8c0965bc and count == 8 and kind == 0x20003 and len(order) == 6
    tracks = []
    for i in range(len(order)):
        pos_address, angle_address, pos_count, angle_count = struct.unpack_from('<4I', d, motion - BASE + 16 * i)
        address, key_count = (pos_address, pos_count) if i == 0 else (angle_address, angle_count)
        assert address and key_count == 5
        fmt = '<3f' if i == 0 else '<3i'
        keys = [struct.unpack_from('<I' + fmt[1:], d, address - BASE + 16 * k) for k in range(key_count)]
        assert [key[0] for key in keys] == [0, 2, 4, 6, 7]
        tracks.append(keys)
    def sample(keys, frame):
        for (f0, *v0), (f1, *v1) in zip(keys, keys[1:]):
            if frame <= f1:
                t = (frame - f0) / float(f1 - f0)
                return [a + (b - a) * t for a, b in zip(v0, v1)]
        return list(keys[-1][1:])
    frames = []
    for frame in range(count):
        pos = [list(n['pos']) for n in order]
        ang = [list(n['ang']) for n in order]
        pos[0] = sample(tracks[0], frame)
        for node in range(1, len(order)):
            ang[node] = [int(round(value)) for value in sample(tracks[node], frame)]
        frames.append(pack.assemble(order, pos, ang))
    return frames

def flame_frames(pack, order):
    """0x8c01b7e4: morph motion 0x8c0b1e08, type 0x30, 16 frames.
    Its normal track is null; nine (frame, vertex-array) keys at 0x8c0b1db0
    deform the 64 vertices, with linear interpolation on odd frames.
    The simultaneous node motion 0x8c0b02a4 has no transform keys.
    """
    data, count = struct.unpack_from('<I4xI', pack.d, 0xa1df8)
    keys = [struct.unpack_from('<2I', pack.d, data - BASE + 8 * i) for i in range(count)]
    n = len(pack.models[order[0]['mp']][0])
    arrays = [[struct.unpack_from('<3f', pack.d, p - BASE + 12 * i) for i in range(n)] for f, p in keys]
    frames = []
    for frame in range(16):
        i = next((i for i in range(len(keys) - 1) if keys[i][0] <= frame < keys[i + 1][0]), len(keys) - 2)
        t = (frame - keys[i][0]) / (keys[i + 1][0] - keys[i][0])
        head = [tuple(a + (b - a) * t for a, b in zip(v0, v1)) for v0, v1 in zip(arrays[i], arrays[i + 1])]
        frames.append(pack.assemble(order, head=head))
    return frames

def main(root, exe):
    pack = Pack(exe); tex_ids, textures = {}, []
    def tex(name):
        if name not in tex_ids:
            im = Image.open(os.path.join(root, 'prs_png', name + '.png')).convert('RGBA'); tex_ids[name] = len(textures); textures.append(im)
        return tex_ids[name]
    out_models = []
    for name, off, texlist in MODELS:
        order = pack.tree(off); special = name.startswith('mouse') and name[5:].isdigit()   # mouse keyframes: the 4-vertex cream run (material flags 17, texture 2) is lit by its own light, so it gets material slot 10 (texture 2 again)
        launch = name.startswith('launch_')
        tris = pack.assemble_cached(order) if name == 'ghost' else pack.assemble(order, special=special, untextured=len(texlist) if launch else 0)
        full = name in ('floor', 'wall', 'hole_out', 'hole_in') or name.startswith('h_') or name.startswith('mouse_') or name == 'ghost'    # the board pieces keep the whole texture list: the game picks the floor (yuka01-06) and wall (kabetx01-03) style by stage
        mats = [tex(texlist[m if m < len(texlist) else 2]) if (m < len(texlist) or special) else 0 for m in range(len(texlist) if full else max(m & 0x3f for m, _ in tris) + 1)]
        if launch:
            if 'WHITE' not in tex_ids: tex_ids['WHITE'] = len(textures); textures.append(Image.new('RGBA', (4, 4), (255, 255, 255, 255)))
            mats[len(texlist)] = tex_ids['WHITE']
        if name == 'ghost':
            if 'WHITE' not in tex_ids: tex_ids['WHITE'] = len(textures); textures.append(Image.new('RGBA', (4, 4), (255, 255, 255, 255)))
            mats.append(tex_ids['WHITE'])
        frames = pack.cat_frames(order) if name == 'cat' else golden_mouse_frames(pack, order) if name == 'mouse_b' else motion_frames(pack, order, 0x8c0988a0, 8) if name == 'ghost' else flame_frames(pack, order) if name == 'fire' else []
        for fr in frames: assert len(fr) == len(tris), (len(fr), len(tris))
        out_models.append((name, tris, mats, frames))
    # Sprite 0x8c0b4ba8 / frame table 0x8c0b4a68: 32x32, pivot
    # (16,16), scale .5; EFFECT slots 40..55. Live stream quads are
    # 16 world units square, camera-facing, with source-alpha blending.
    for frame in range(16):
        def smokev(x, z, u, v): return (x, 0.0, z, u, v, 0.0, 1.0, 0.0)
        a, b, c, d = smokev(-8, -8, 0, 1), smokev(-8, 8, 0, 0), smokev(8, -8, 1, 1), smokev(8, 8, 1, 0)
        out_models.append(('smoke%d' % frame, [(0, [a, b, c]), (0, [c, b, d])],
                           [tex('EFFECT_smoke%02d' % (frame + 1))], []))
    # Mouse marker quads (0x8c056d00): a 13.5-unit plane (half size 6.75) textured with texture 46 + 3 * kind of the CHALLENGECLEAR list: kind 0 = plus50 (golden mouse), kind 1 = hatena (roulette mouse)
    for qname, qtex in (('marker_plus50', 'CHALLENGECLEAR_plus50'), ('marker_hatena', 'CHALLENGECLEAR_hatena')):
        h = 6.75
        def qv(x, y, u, v): return (x, y, 0.0, u, v, 0.0, 0.0, 1.0)
        qtris = [(0, [qv(-h, h, 0, 0), qv(-h, -h, 0, 1), qv(h, h, 1, 0)]), (0, [qv(h, h, 1, 0), qv(-h, -h, 0, 1), qv(h, -h, 1, 1)])]
        out_models.append((qname, qtris, [tex(qtex)], []))
    out = bytearray(b'CCM3' + struct.pack('<I', len(textures)))
    for im in textures: out += struct.pack('<HH', im.width, im.height) + im.tobytes()
    out += struct.pack('<I', len(out_models))
    for name, tris, mats, frames in out_models:
        out += name.encode().ljust(24, b'\0') + struct.pack('<II', len(tris), len(mats)) + struct.pack('<%dI' % len(mats), *mats)
        for m, vs in tris:
            out += struct.pack('<B', m)
            for v in vs: out += struct.pack('<8f', *v)
        out += struct.pack('<I', len(frames))
        for fr in frames:
            for m, vs in fr:
                for v in vs: out += struct.pack('<6f', v[0], v[1], v[2], v[5], v[6], v[7])
    open(os.path.join(root, 'models.bin'), 'wb').write(out)
    print('models', len(out_models), 'textures', len(textures), 'bytes', len(out))

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else os.path.join(sys.argv[1], '..', '..', '..', 'analysis', 'extracted', 'dc_files', '1ST_READ.BIN'))
