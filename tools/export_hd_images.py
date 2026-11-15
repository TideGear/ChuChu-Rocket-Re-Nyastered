"""Exports HD 1.0 `Render::drawImage` images by id (AppData::loadResources: texture tex[id] / frames frm[id] through the pad resource table) to <ret_all>/img/hd_<id>.{tex,frames}.bin;
images whose records live in the language pack (resource id >= 885) go to <ret_all>/loc_<lang>/img_<id> for every Latin language.
usage: export_hd_images.py <thin armv7> <extracted ccrpad dir> <ret_all dir> [ids ...]   (default: tools/hd_image_ids.txt)"""
import os, shutil, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from macho import Macho
import textures as T
LANGS = ['en', 'fr', 'it', 'de', 'es']
def main(thin, pack, out, ids, count=885):
    m = Macho(thin)
    def rd(a, n):
        for s in m.segs:
            if s[1] <= a < s[1] + s[2]: o = s[3] + a - s[1]; return m.d[o:o + n]
    u = lambda a: struct.unpack('<I', rd(a, 4))[0]
    tex = struct.unpack('<175i', rd(0xe6704, 700)); frm = struct.unpack('<175i', rd(0xe6984, 700)); Tb = struct.unpack('<1200i', rd(u(0xeb548), 4800))
    main_ts = {t['rec']: t for t in T.textures(pack)}; os.makedirs(os.path.join(out, 'img'), exist_ok=True); loc_ts = {}
    def write(dst, name, t, frames_path):
        im = T.to_image(t).convert('RGBA')
        with open(os.path.join(dst, name + '.tex.bin'), 'wb') as f: f.write(struct.pack('<2I', t['w'], t['h'])); f.write(im.tobytes())
        shutil.copyfile(frames_path, os.path.join(dst, name + '.frames.bin'))
    for i in ids:
        t, f = Tb[tex[i]], Tb[frm[i]]
        if t < count:
            write(os.path.join(out, 'img'), 'hd_%d' % i, main_ts[t], os.path.join(pack, '%04d.bin' % f))
        else:
            for lg in LANGS:
                lp = pack + '_' + lg
                if lg not in loc_ts: loc_ts[lg] = {x['rec']: x for x in T.textures(lp)}
                dst = os.path.join(out, 'loc_' + lg); os.makedirs(dst, exist_ok=True)
                write(dst, 'img_%d' % i, loc_ts[lg][t - count], os.path.join(lp, '%04d.bin' % (f - count)))
        print('image', i, 'tex', t, 'frames', f)
if __name__ == '__main__':
    a = sys.argv[1:]; ids = [int(x) for x in a[3:]] or [int(x) for x in open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'hd_image_ids.txt')).read().split()]
    main(a[0], a[1], a[2], ids)
