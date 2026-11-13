import json, os, struct, sys
from PIL import Image

def textures(base):
    idx = json.load(open(os.path.join(base, 'index.json')))['records']
    out = []; i = 0
    while i < len(idx):
        r = idx[i]
        if r['size'] == 8 and not r['compressed']:
            w, h = struct.unpack('<2I', open(os.path.join(base, '%04d.bin' % i), 'rb').read())
            need = w * h * 2
            if 0 < w <= 4096 and 0 < h <= 4096 and i + 1 < len(idx):
                data = b''; j = i + 1
                while j < len(idx) and len(data) < need and idx[j]['size'] > 8:
                    data += open(os.path.join(base, '%04d.bin' % j), 'rb').read(); j += 1
                if len(data) == need:
                    out.append({'rec': i, 'w': w, 'h': h, 'data': data, 'next': j}); i = j; continue
        i += 1
    return out

def to_image(t, fmt='rgba4444'):
    w, h = t['w'], t['h']
    px = struct.unpack('<%dH' % (w * h), t['data']); out = bytearray()
    if fmt == 'rgba4444':
        for v in px: out += bytes((((v >> 12) & 15) * 17, ((v >> 8) & 15) * 17, ((v >> 4) & 15) * 17, (v & 15) * 17))
    elif fmt == 'argb4444':
        for v in px: out += bytes((((v >> 8) & 15) * 17, ((v >> 4) & 15) * 17, (v & 15) * 17, ((v >> 12) & 15) * 17))
    elif fmt == 'rgb565':
        for v in px: out += bytes((((v >> 11) & 31) * 255 // 31, ((v >> 5) & 63) * 255 // 63, (v & 31) * 255 // 31, 255))
    elif fmt == 'rgba5551':
        for v in px: out += bytes((((v >> 11) & 31) * 255 // 31, ((v >> 6) & 31) * 255 // 31, ((v >> 1) & 31) * 255 // 31, (v & 1) * 255))
    return Image.frombytes('RGBA', (w, h), bytes(out))

if __name__ == '__main__':
    base = sys.argv[1]
    ts = textures(base)
    print(len(ts), 'textures')
    for t in ts: print(' rec %4d  %4dx%-4d' % (t['rec'], t['w'], t['h']))
