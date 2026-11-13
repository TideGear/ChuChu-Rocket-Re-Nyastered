"""Write a Ghidra-style function list (addr, size, name) from the Mach-O symbol table of a thin armv7 binary, for the oracle harnesses when no decompile exists.
usage: macho_funcs.py <thin binary> <out functions.txt>"""
import os, re, sys
sys.path.insert(0, os.path.dirname(__file__))
from macho import Macho
def plain(n):
    m = re.match(r'__Z(\d+)(.*)', n)          # simple Itanium free-function name: __Z<len><name><params>
    if m:
        k = int(m.group(1)); return m.group(2)[:k]
    return n[1:] if n.startswith('_') and not n.startswith('__Z') else n
def main(path, out):
    m = Macho(path); text = [s for s in m.sects if s['name'] == '__text'][0]; lo, hi = text['addr'], text['addr'] + text['size']
    fs = sorted({(v & ~1, n) for n, v, t, s in m.syms if lo <= (v & ~1) < hi and (t & 0xe0) == 0 and (t & 0x0e) == 0x0e and n}, key=lambda x: x[0])
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w') as f:
        for i, (a, n) in enumerate(fs):
            nxt = fs[i + 1][0] if i + 1 < len(fs) else hi
            f.write('%08x\t%d\t%s\n' % (a, nxt - a, plain(n)))
    print(len(fs), 'functions ->', out)
if __name__ == '__main__': main(sys.argv[1], sys.argv[2])
