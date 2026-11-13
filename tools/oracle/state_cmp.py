import sys
def load(p):
    d = {}
    for l in open(p):
        k = l.split(); key = (int(k[1]), k[0], int(k[2]) if k[0] == 'C' else 0)
        d[key] = k[2:] if k[0] == 'H' else k[3:]
    return d
a, b = load(sys.argv[1]), load(sys.argv[2])
for key in sorted(a):
    if a[key] != b.get(key):
        print('first difference at frame %d %s %s' % (key[0], key[1], ('player %d' % key[2]) if key[1] == 'C' else ''))
        if key[1] == 'H':
            A = list(map(int, a[key])); Bv = list(map(int, b.get(key, ['0'] * 108)))
            print(' cells differing:', [(i % 12, i // 12, A[i], Bv[i]) for i in range(108) if A[i] != Bv[i]][:12])
        else: print(' original:', a[key], '\n ours    :', b.get(key))
        break
else: print('identical')
