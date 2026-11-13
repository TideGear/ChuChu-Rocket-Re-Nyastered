import struct, sys, re
# machosyms.py <thin armv7 macho> <regex>: list matching symbols with vmaddr, file offset, and distance to next symbol.
d = open(sys.argv[1], 'rb').read()
pat = re.compile(sys.argv[2])
magic, cpu, sub, ft, ncmds, szcmds, flags = struct.unpack('<7I', d[:28])
p = 28; segs = []; sym = None
for _ in range(ncmds):
    cmd, sz = struct.unpack('<2I', d[p:p + 8])
    if cmd == 1:  # LC_SEGMENT
        name = d[p + 8:p + 24].rstrip(b'\0').decode()
        vmaddr, vmsize, fileoff, filesize, _, _, nsects, _ = struct.unpack('<8I', d[p + 24:p + 56])
        segs.append((name, vmaddr, vmsize, fileoff, filesize))
    elif cmd == 2:  # LC_SYMTAB
        sym = struct.unpack('<4I', d[p + 8:p + 24])
    p += sz
symoff, nsyms, stroff, strsize = sym
ents = []
for i in range(nsyms):
    strx, typ, sect, desc, value = struct.unpack('<IBBHI', d[symoff + i * 12: symoff + i * 12 + 12])
    nm = d[stroff + strx: d.index(b'\0', stroff + strx)].decode('latin1')
    ents.append((value, nm, typ, sect))
def foff(v):
    for name, vm, vs, fo, fs in segs:
        if vm <= v < vm + vs: return fo + (v - vm)
    return None
ents.sort()
addrs = [e[0] for e in ents if e[0]]
for i, (v, nm, typ, sect) in enumerate(ents):
    if pat.search(nm) and v:
        nxt = next((a for a in addrs if a > v), None)
        print('%-28s vm=%#x fileoff=%s span_to_next=%s' % (nm, v, hex(foff(v)) if foff(v) is not None else None, (nxt - v) if nxt else None))
