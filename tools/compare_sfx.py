"""Compare the sound-effect (and song) Ogg files of every extracted iOS build: hash identity and Vorbis stream properties (channels, sample rate, nominal bitrate, size).
usage: compare_sfx.py <cache assets dir> [audio_sfx|audio_song]"""
import collections, glob, hashlib, os, struct, sys

def vorbis_info(b):
    i = b.find(b'\x01vorbis')
    if i < 0:
        return None
    ver, ch, rate, bmax, bnom, bmin = struct.unpack_from('<IBIiii', b, i + 7)
    return ch, rate, bnom

def main(root, kind='audio_sfx'):
    sets = {}
    for d in sorted(glob.glob(os.path.join(root, 'ios', '*', kind))):
        files = sorted(glob.glob(os.path.join(d, '*.ogg')))
        if files:
            sets[os.path.basename(os.path.dirname(d))] = files
    table = collections.defaultdict(dict)
    for build, files in sets.items():
        for f in files:
            b = open(f, 'rb').read()
            table[os.path.basename(f)][build] = (hashlib.sha1(b).hexdigest()[:10], vorbis_info(b), len(b))
    names = sorted(table)
    print({k[:30]: len(v) for k, v in sets.items()})
    same = sum(1 for n in names if len({v[0] for v in table[n].values()}) == 1)
    print('files', len(names), '| identical in every build that has them:', same)
    print('stream properties (channels, rate, nominal bitrate):', collections.Counter(v[1] for n in names for v in table[n].values()).most_common(5))
    for n in names:
        hs = {v[0] for v in table[n].values()}
        if len(hs) > 1:
            print('DIFFERS', n, {k[:20]: v[0] for k, v in table[n].items()})
    sizes = [list(table[n].values())[0][2] for n in names]
    print('total bytes (one copy of each):', sum(sizes))

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else 'audio_sfx')
