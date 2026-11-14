"""Per-piece resolution comparison of the mobile texture sets (item 4 evidence): every texture of every extracted build, keyed by its record id (`recNNNN`, the position of the texture in the pack, shared between builds that ship the same piece), with its pixel size in each source and the source that has the most pixels.
Reads the PNG names written by the extractors (<index>_rec<id>_<w>x<h>.png) under <cache assets>/android/*/main_png and <cache assets>/ios/*/(ccrpad_png|ccrphn_png|ccrret_png).
usage: measure_assets.py <cache assets dir> <out.md>"""
import collections, glob, os, re, sys
def main(root, out):
    pat = re.compile(r'^\d+_rec(\d+)_(\d+)x(\d+)\.png$'); src = collections.OrderedDict()
    for d in sorted(glob.glob(os.path.join(root, 'android', '*', 'main_png'))):
        src['android:' + os.path.basename(os.path.dirname(d))[:22]] = d
    for d in sorted(glob.glob(os.path.join(root, 'ios', '*', 'cc*_png'))):
        src['ios:%s/%s' % (os.path.basename(os.path.dirname(d))[:24], os.path.basename(d)[:-4])] = d
    fam = lambda n: 'ret' if n.endswith('ccrret') else 'main'   # records are numbered per pack family: the UI/background pack (Android main_png, ccrpad, ccrphn) and the character pack (ccrret)
    table = collections.defaultdict(dict)
    for name, d in src.items():
        for f in os.listdir(d):
            m = pat.match(f)
            if m: table[(fam(name), int(m.group(1)))][name] = (int(m.group(2)), int(m.group(3)))
    best = collections.Counter(); only = collections.Counter(); upscale = 0; rows = []
    for rec in sorted(table):
        e = table[rec]; b = max(e, key=lambda k: e[k][0] * e[k][1]); area = e[b][0] * e[b][1]
        ties = [k for k in e if e[k][0] * e[k][1] == area]; best[b] += 1
        if len(e) == 1: only[b] += 1
        rows.append((rec, len(e), b, e[b], min(e[k][0] * e[k][1] for k in e)))
    with open(out, 'w') as f:
        f.write('# Mobile texture quality, per piece (measured by tools/measure_assets.py)\n\n')
        f.write('%d distinct (family, record) pairs over %d source folders. For each record the source with the most pixels is the "best"; pieces that exist in one source only have no alternative.\n\n' % (len(table), len(src)))
        f.write('| source folder | textures | records where it is the largest | records only it has |\n|---|---|---|---|\n')
        for name, d in src.items(): f.write('| %s | %d | %d | %d |\n' % (name, len([1 for r in table if name in table[r]]), best[name], only[name]))
        f.write('\n## Records where the sources differ in size\n\n| record | sources | best source | best size | smallest pixel count in other sources | gain |\n|---|---|---|---|---|---|\n')
        for rec, n, b, sz, mn in rows:
            if n > 1 and mn != sz[0] * sz[1]: f.write('| %s %d | %d | %s | %dx%d | %d | %.2fx |\n' % (rec[0], rec[1], n, b, sz[0], sz[1], mn, sz[0] * sz[1] / mn))
        f.write('\nRecords identical in size in all sources that have them: %d of %d.\n' % (sum(1 for r in rows if r[1] > 1 and r[4] == r[3][0] * r[3][1]), sum(1 for r in rows if r[1] > 1)))
    print('records', len(table), 'sources', len(src), '->', out)
main(sys.argv[1], sys.argv[2])
