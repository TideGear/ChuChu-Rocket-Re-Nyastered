import sys, os, struct, glob, re
# Extract ISO9660 files from a GD-ROM high-density area spread over tracks 03..N (2352-byte sectors).
# usage: gdi_extract.py <dir with Track NN.bin> <outdir> [gap_between_tracks_sectors]
d, out = sys.argv[1], sys.argv[2]
gap = int(sys.argv[3]) if len(sys.argv) > 3 else 0
tracks = {}
for p in glob.glob(os.path.join(d, '*Track *.bin')):
    n = int(re.search(r'Track (\d+)', p).group(1))
    if n >= 3: tracks[n] = p
order = sorted(tracks)
segs = []  # (start_lba, nsectors, path, is_data)
lba = 45000
for n in order:
    ns = os.path.getsize(tracks[n]) // 2352
    segs.append((lba, ns, tracks[n], n))
    lba += ns + gap
handles = {}
def read_sector(l):
    for st, ns, p, n in segs:
        if st <= l < st + ns:
            h = handles.get(p) or handles.setdefault(p, open(p, 'rb'))
            h.seek((l - st) * 2352 + 16)
            return h.read(2048)
    return b''
def read_range(l, length):
    out_ = bytearray()
    for i in range((length + 2047) // 2048):
        s = read_sector(l + i)
        if not s: raise IOError('LBA %d outside tracks' % (l + i))
        out_ += s
    return bytes(out_[:length])
pvd = read_sector(45016)
assert pvd[1:6] == b'CD001', 'no PVD'
root = pvd[156:190]
rl, rn = struct.unpack('<I', root[2:6])[0], struct.unpack('<I', root[10:14])[0]
def walk(l, n, path):
    data = read_range(l, n); p = 0
    while p < len(data):
        ln = data[p]
        if ln == 0:
            p = (p // 2048 + 1) * 2048; continue
        rec = data[p:p + ln]; p += ln
        el, en = struct.unpack('<I', rec[2:6])[0], struct.unpack('<I', rec[10:14])[0]
        fl, nl = rec[25], rec[32]
        name = rec[33:33 + nl].decode('latin1').split(';')[0]
        if name in ('\x00', '\x01'): continue
        full = os.path.join(path, name)
        if fl & 2:
            os.makedirs(os.path.join(out, full), exist_ok=True); walk(el, en, full)
        else:
            os.makedirs(os.path.join(out, path), exist_ok=True)
            try:
                with open(os.path.join(out, full), 'wb') as o: o.write(read_range(el, en))
                print('%10d %s' % (en, full), flush=True)
            except IOError as e:
                print('FAIL %s: %s' % (full, e), flush=True)
walk(rl // 1, rn, '')
