"""Call tree of a function in a Ghidra C export (analysis/decomp/<build>/<lib>.c): callee names to a given depth, for the 'every function the per-frame loop calls' audit.
usage: callgraph.py <file.c> <function name> [depth=2]"""
import re, sys
src = open(sys.argv[1], encoding='utf-8', errors='replace').read(); depth = int(sys.argv[3]) if len(sys.argv) > 3 else 2
bodies = {}
for m in re.finditer(r'^// ==== (\S+) @ [0-9a-f]+\n(.*?)(?=^// ==== )', src, re.S | re.M): bodies.setdefault(m.group(1), m.group(2))
call = re.compile(r'\b([A-Za-z_][A-Za-z0-9_:]*)\s*\(')
SKIP = {'if', 'while', 'for', 'switch', 'return', 'sizeof'}
seen = set()
def walk(n, d, ind):
    b = bodies.get(n)
    if b is None: print(' ' * ind + n + ' (no body)'); return
    print(' ' * ind + n + ' [%d lines]' % b.count('\n'))
    if d == 0 or n in seen: return
    seen.add(n)
    names = []
    for c in call.findall(b):
        if c in SKIP or c.startswith(('__aeabi', '__', 'Ghidra')) or c == n or c in names: continue
        names.append(c)
    for c in names: walk(c, d - 1, ind + 2)
walk(sys.argv[2], depth, 0)
