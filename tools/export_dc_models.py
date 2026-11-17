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
            for fr in cat_morph_frames(root, V):
                frames.append([c for m, idx in F for a, b in idx for c in fr[a]])
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
