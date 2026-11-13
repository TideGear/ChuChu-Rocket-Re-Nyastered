"""Compare per-frame multisets of entity positions (task pointers are recycled, so identities are unreliable)."""
import sys
def load(p):
    d = {}
    for l in open(p):
        f, k, x, z = l.split(); d.setdefault(int(f), set()).add((round(float(x), 2), round(float(z), 2), int(k)))
    return {f: sorted((x, z) for x, z, k in v) for f, v in d.items()}
a, b = load(sys.argv[1]), load(sys.argv[2]); lim = int(sys.argv[3]) if len(sys.argv) > 3 else 10**9
for f in sorted(a):
    if f > lim: break
    A = a[f]; B = b.get(f, [])
    if A != B:
        sa, sb = set(A), set(B)
        print('first divergence at frame', f); print('  only original:', sorted(sa - sb)[:6]); print('  only ours    :', sorted(sb - sa)[:6]); break
else: print('identical through', lim)
