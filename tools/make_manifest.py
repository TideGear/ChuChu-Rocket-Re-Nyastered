"""Asset manifest: every file in the local asset cache with size and SHA-256, grouped by source folder, plus the input files' hashes (from extract_all's manifest.json).
usage: make_manifest.py <cache dir> [out.json]. The manifest describes the user's derived data and is never committed."""
import hashlib, json, os, sys, time

def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 22), b''):
            h.update(b)
    return h.hexdigest()

def main(cache, out):
    assets = os.path.join(cache, 'assets'); groups = {}; total = 0
    for root, _, fs in os.walk(assets):
        for f in fs:
            p = os.path.join(root, f); rel = os.path.relpath(p, assets).replace(os.sep, '/')
            top = '/'.join(rel.split('/')[:2]) if '/' in rel else rel
            groups.setdefault(top, []).append({'path': rel, 'bytes': os.path.getsize(p), 'sha256': sha(p)}); total += 1
    mp = os.path.join(cache, 'manifest.json')
    inputs = json.load(open(mp))['inputs'] if os.path.exists(mp) else []
    m = {'created': time.strftime('%Y-%m-%d %H:%M:%S'), 'files': total, 'inputs': inputs,
         'groups': {k: {'count': len(v), 'bytes': sum(x['bytes'] for x in v), 'files': v} for k, v in sorted(groups.items())}}
    json.dump(m, open(out, 'w'), indent=1)
    print(total, 'files in', len(groups), 'groups ->', out)

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else os.path.join(sys.argv[1], 'asset_manifest.json'))
