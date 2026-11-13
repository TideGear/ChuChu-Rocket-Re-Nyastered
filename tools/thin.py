import sys, struct
# thin.py <in> <out>: write the highest-subtype ARM slice of a Mach-O (fat or thin) and report encryption.
src, out = sys.argv[1], sys.argv[2]
d = open(src, 'rb').read()
if d[:4] == b'\xca\xfe\xba\xbe':
    n = struct.unpack('>I', d[4:8])[0]
    best = None
    for i in range(n):
        cpu, sub, off, size, align = struct.unpack('>5I', d[8 + i * 20: 28 + i * 20])
        print('slice cpu %d sub %d off %#x size %#x' % (cpu, sub, off, size))
        if cpu == 12 and (best is None or sub > best[0]): best = (sub, off, size)
    d = d[best[1]: best[1] + best[2]]
magic, cpu, sub, ft, ncmds, szcmds, flags = struct.unpack('<7I', d[:28])
p = 28
for i in range(ncmds):
    cmd, sz = struct.unpack('<2I', d[p:p + 8])
    if cmd == 0x21:
        off, size, cid = struct.unpack('<3I', d[p + 8:p + 20])
        print('LC_ENCRYPTION_INFO off %#x size %#x cryptid %d' % (off, size, cid))
    p += sz
print('thin: cpu %d sub %d size %d' % (cpu, sub, len(d)))
open(out, 'wb').write(d)
