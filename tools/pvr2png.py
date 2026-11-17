import os, struct, sys
from PIL import Image

def prs_decompress(src):
    # Sega PRS (LZ77 variant)
    out = bytearray(); p = 0
    ctrl = 0; bits = 0
    def getbit():
        nonlocal ctrl, bits, p
        if bits == 0:
            ctrl = src[p]; p += 1; bits = 8
        b = ctrl & 1; ctrl >>= 1; bits -= 1
        return b
    while p < len(src):
        if getbit():
            out.append(src[p]); p += 1; continue
        if getbit():
            if p + 1 >= len(src): break
            a = src[p]; b = src[p + 1]; p += 2
            off = (b << 5) | (a >> 3)
            off -= 0x2000
            n = a & 7
            if n == 0:
                if p >= len(src): break
                n = src[p] + 1; p += 1
                if n == 1: break
            else:
                n += 2
            if off == -0x2000: break
        else:
            n = (getbit() << 1) | getbit()
            n += 2
            off = src[p] - 0x100; p += 1
        for _ in range(n):
            out.append(out[len(out) + off])
    return bytes(out)

def untwiddle_index(x, y):
    r = 0
    for i in range(10):
        r |= ((x >> i) & 1) << (2 * i) | ((y >> i) & 1) << (2 * i + 1)
    return r

def px(v, fmt):
    if fmt == 0:  # ARGB1555
        a = 255 if v & 0x8000 else 0
        return (((v >> 10) & 31) * 255 // 31, ((v >> 5) & 31) * 255 // 31, (v & 31) * 255 // 31, a)
    if fmt == 1:  # RGB565
        return (((v >> 11) & 31) * 255 // 31, ((v >> 5) & 63) * 255 // 63, (v & 31) * 255 // 31, 255)
    if fmt == 2:  # ARGB4444
        return (((v >> 8) & 15) * 17, ((v >> 4) & 15) * 17, (v & 15) * 17, ((v >> 12) & 15) * 17)
    raise ValueError(fmt)

def decode(data):
    i = data.find(b'PVRT')
    if i < 0: return None
    pf, dt, _, w, h = struct.unpack('<BBHHH', data[i + 8:i + 16])
    body = data[i + 16:]
    img = Image.new('RGBA', (w, h))
    pix = img.load()
    u16 = lambda o: struct.unpack_from('<H', body, o)[0]
    if dt in (1, 2):    # twiddled (2 = with mips; mips stored smallest first)
        off = 0
        if dt == 2:
            # skip mip chain: sizes 1x1 .. w/2; plus 1x1 pad 2 bytes
            s = w >> 1; skip = 2
            while s >= 1: skip += s * s * 2; s >>= 1
            off = skip
        for y in range(h):
            for x in range(w):
                pix[x, y] = px(u16(off + untwiddle_index(x, y) * 2), pf)
    elif dt in (7, 9, 0x0D):  # linear/rectangle
        for y in range(h):
            for x in range(w):
                pix[x, y] = px(u16((y * w + x) * 2), pf)
    elif dt in (3, 4, 0x10, 0x11):  # VQ
        ncode = 256
        if dt >= 0x10:
            ncode = {8: 16, 16: 32, 32: 128}.get(w, 256) if w <= 32 else (256 if w < 128 else 256)
            ncode = 16 if w <= 8 else 32 if w <= 16 else 64 if w <= 32 else 256
            if w <= 8: ncode = 16
        book = [struct.unpack_from('<4H', body, k * 8) for k in range(ncode)]
        idx_off = ncode * 8
        if dt in (4, 0x11):
            s = w >> 1; skip = 1
            while s >= 1: skip += max(1, (s // 2) * (s // 2)); s >>= 1
            idx_off += skip
        for y in range(h // 2):
            for x in range(w // 2):
                code = body[idx_off + untwiddle_index(x, y)]
                q = book[code]  # order: (0,0),(0,1),(1,0),(1,1) in column-major twiddled
                pix[x * 2, y * 2] = px(q[0], pf)
                pix[x * 2, y * 2 + 1] = px(q[1], pf)
                pix[x * 2 + 1, y * 2] = px(q[2], pf)
                pix[x * 2 + 1, y * 2 + 1] = px(q[3], pf)
    else:
        return None
    return img

if __name__ == '__main__':
    src, dst = sys.argv[1], sys.argv[2]
    n = bad = 0
    for root, _, fs in os.walk(src):
        for f in fs:
            up = f.upper()
            if not up.endswith(('.PVR', '.PRS')): continue
            data = open(os.path.join(root, f), 'rb').read()
            try:
                if up.endswith('.PRS'): data = prs_decompress(data)
                img = decode(data)
            except Exception as e:
                img = None
            rel = os.path.relpath(root, src).replace('\\', '_')
            if img is None:
                bad += 1; continue
            os.makedirs(dst, exist_ok=True)
            base = os.path.splitext(f)[0]
            img.save(os.path.join(dst, base + '.png' if rel == '.' else '%s__%s.png' % (rel, base)))   # files directly in the source folder keep their plain name (a '.__' prefix made hidden files)
            n += 1
    print('decoded', n, 'failed', bad)
