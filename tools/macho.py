"""Minimal thin armv7 Mach-O parser: segments, sections, symbols, indirect symbol table (for import stubs)."""
import struct
class Macho:
    def __init__(self, path):
        d = self.d = open(path, 'rb').read()
        magic, cpu, sub, ft, ncmds, szcmds, flags = struct.unpack('<7I', d[:28]); assert magic == 0xfeedface
        self.flags = flags; self.segs = []; self.sects = []; self.syms = []; self.indirect = []; p = 28
        symtab = dysym = None
        for _ in range(ncmds):
            cmd, sz = struct.unpack('<2I', d[p:p + 8])
            if cmd == 1:
                name = d[p + 8:p + 24].rstrip(b'\0').decode(); vm, vs, fo, fs, mp, ip, ns, fl = struct.unpack('<8I', d[p + 24:p + 56])
                self.segs.append((name, vm, vs, fo, fs))
                q = p + 56
                for _ in range(ns):
                    sn = d[q:q + 16].rstrip(b'\0').decode(); sg = d[q + 16:q + 32].rstrip(b'\0').decode()
                    addr, size, off, al, reloff, nreloc, sflags, r1, r2 = struct.unpack('<9I', d[q + 32:q + 68]) if False else (0,)*9
                    addr, size, off = struct.unpack('<3I', d[q + 32:q + 44]); sflags, r1, r2 = struct.unpack('<3I', d[q + 56:q + 68])
                    self.sects.append(dict(name=sn, seg=sg, addr=addr, size=size, off=off, flags=sflags, r1=r1, r2=r2)); q += 68
            elif cmd == 2: symtab = struct.unpack('<4I', d[p + 8:p + 24])
            elif cmd == 0xb: dysym = struct.unpack('<18I', d[p + 8:p + 80])
            p += sz
        so, ns, sto, ss = symtab
        for i in range(ns):
            strx, typ, sect, desc, value = struct.unpack('<IBBHI', d[so + i * 12:so + i * 12 + 12])
            self.syms.append((d[sto + strx:d.index(b'\0', sto + strx)].decode('latin1'), value, typ, sect))
        if dysym:
            ioff, nind = dysym[12], dysym[13]
            self.indirect = list(struct.unpack('<%dI' % nind, d[ioff:ioff + 4 * nind]))
    def sym_addr(self, name):
        for n, v, t, s in self.syms:
            if n == name: return v
        return None
    def imports(self):
        """{pointer address: imported symbol name} for lazy/non-lazy symbol pointer sections"""
        out = {}
        for s in self.sects:
            t = s['flags'] & 0xff
            if t in (6, 7):          # S_NON_LAZY_SYMBOL_POINTERS, S_LAZY_SYMBOL_POINTERS
                for i in range(s['size'] // 4):
                    idx = self.indirect[s['r1'] + i] if s['r1'] + i < len(self.indirect) else 0
                    if idx < len(self.syms) and idx not in (0x80000000, 0x40000000): out[s['addr'] + 4 * i] = self.syms[idx][0]
        return out
if __name__ == '__main__':
    import sys
    m = Macho(sys.argv[1]); print('segs', [(s[0], hex(s[1]), hex(s[2])) for s in m.segs]); im = m.imports(); print(len(im), 'imports'); print(sorted(set(im.values()))[:80])
