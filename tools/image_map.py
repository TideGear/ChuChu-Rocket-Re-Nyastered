"""Image id -> texture record map of iOS 1.1.2, read from the code (AppData::loadResources 0xb1f4: for image id i (0..174) the texture is
BHLib_CreateTexture(pack, getActualResourceID(tex[i]), getActualResourceID(frm[i])); getActualResourceID 0x8990 picks the table by the device
class: < 6 `_ccrphn_res`, 6..9 `_ccrret_res`, >= 10 a third table). Resource ids at or past the main pack's record count address the
language pack (_<pack>0_<lang>) at id - count. Verified: arrows 0x5f -> ccrret 645, digits 0x6a -> 729, cursors 0x6b -> 732, crowns 0x69 -> 726.
usage: image_map.py <out.json>   -> {"<id>": [pack, texture record, frame record]} for the retina (ccrret) build"""
import json, os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from macho import Macho
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'analysis')
def main(out):
    m = Macho(os.path.join(ROOT, 'thin', 'CCR_ios_v112'))
    def rd(a, n):
        for s in m.segs:
            if s[1] <= a < s[1] + s[2]: o = s[3] + a - s[1]; return m.d[o:o + n]
    u = lambda a: struct.unpack('<I', rd(a, 4))[0]
    tex = struct.unpack('<175i', rd(u(0xb2b0) + 0xb24a, 700)); frm = struct.unpack('<175i', rd(u(0xb2b4) + 0xb25e, 700))
    T = struct.unpack('<1200i', rd(u(0x89b4 + 0x12c75c), 4800))          # the 6..9 (retina) table
    count = len(json.load(open(os.path.join(ROOT, 'assets', 'ios_v112', 'ccrret', 'index.json')))['records'])
    res = {}
    for i in range(175):
        t, f = T[tex[i]], T[frm[i]]
        res[str(i)] = ['ccrret_en', t - count, f - count] if t >= count else ['ccrret', t, f]
    json.dump(res, open(out, 'w'), indent=0); print(len(res), 'images; language-pack images:', sum(1 for v in res.values() if v[0] != 'ccrret'))
if __name__ == '__main__': main(sys.argv[1])
