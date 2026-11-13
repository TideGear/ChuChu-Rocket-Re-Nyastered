"""Extract the textures of a Dreamcast ChuChu character-pack .VMS (Cartoony, UFOCow, DEChar): after the 0x280-byte VMS header (description, icon, palette)
the payload is a sequence of GBIX+PVRT texture files. usage: vms_skin.py <pack.VMS> <out dir>   (derived data; never committed)"""
import os, struct, sys
sys.path.insert(0, os.path.dirname(__file__))
from pvr2png import decode

def textures(vms):
    """yield (offset, global index, pixel fmt, data fmt, w, h, bytes of the whole GBIX+PVRT blob)"""
    i = 0x200
    while True:
        i = vms.find(b'GBIX', i)
        if i < 0 or vms[i + 16:i + 20] != b'PVRT': return
        gidx = struct.unpack_from('<I', vms, i + 8)[0]; size = struct.unpack_from('<I', vms, i + 20)[0]
        pf, dt, _, w, h = struct.unpack_from('<BBHHH', vms, i + 24)
        end = i + 24 + size
        yield i, gidx, pf, dt, w, h, vms[i:end]
        i = end

def main(path, out):
    vms = open(path, 'rb').read(); os.makedirs(out, exist_ok=True); n = 0
    print(path, 'description', vms[:16].decode('ascii', 'replace').strip())
    for off, g, pf, dt, w, h, blob in textures(vms):
        img = decode(blob)
        name = '%s_%02d_g%04x_%dx%d' % (os.path.splitext(os.path.basename(path))[0], n, g, w, h)
        open(os.path.join(out, name + '.pvr'), 'wb').write(blob)
        if img is not None: img.save(os.path.join(out, name + '.png'))
        print('  texture %d @%#x gbix %#x fmt %d/%d %dx%d %d bytes%s' % (n, off, g, pf, dt, w, h, len(blob), '' if img is not None else ' (not decoded)')); n += 1
    print('  %d textures' % n); return n

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
