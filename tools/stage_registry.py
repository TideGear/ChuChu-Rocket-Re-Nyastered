"""Build the master stage registry from every extracted source.
Mobile stage struct (380 bytes): 0x00..0x6b tile grid 12x9, 0x6c..0x15b wall layers, 0x15c..0x15f arrow counts,
0x160..0x174 title (21 bytes), 0x178 checksum. Board fingerprint = bytes[0:0x160] (title excluded)."""
import hashlib, json, os, sys

ROOT = r'c:\Dev\ChuChu Rocket\analysis'

def looks_like_stage(s):
    z = s[0x160:0x175].split(b'\0')[0]
    return len(z) >= 2 and all(32 <= c < 127 for c in z) and all(c in (0, 1) for c in s[0x6c:0x6c + 12])

def title(s):
    return s[0x160:0x175].split(b'\0')[0].decode('latin1').strip()

def groups_in(base):
    idx = json.load(open(os.path.join(base, 'index.json')))['records']
    for r in idx:
        if r['size'] % 380 or r['size'] < 380: continue
        d = open(os.path.join(base, '%04d.bin' % r['i']), 'rb').read()
        st = [d[i * 380:(i + 1) * 380] for i in range(len(d) // 380)]
        if sum(1 for s in st if looks_like_stage(s)) >= len(st) * 0.8:
            yield r['i'], st

SOURCES = {
    'ios_1.0.2': 'assets/ios_102/ccrphn', 'ios_hd1.0': 'assets/ios_hd10/ccrphn', 'ios_1.1': 'assets/ios_v11os30/ccrphn',
    'ios_1.1.2': 'assets/ios_v112/ccrphn', 'android_1.14': 'assets/android_apk114/libccrjni/main',
    'android_1.15': 'assets/android_apk115/libccrjni/main',
}

def mobile_key(s):
    return board_key(bytes(s[:108]), bytes(s[0x6c:0x6c + 237]))

def build():
    reg = {}      # board key -> {titles, where[], arrows set}
    per_source = {}
    for name, rel in SOURCES.items():
        base = os.path.join(ROOT, rel); per_source[name] = []
        for rec, st in groups_in(base):
            for k, s in enumerate(st):
                h = mobile_key(s)
                e = reg.setdefault(h, {'titles': set(), 'where': [], 'arrows': set()})
                e['titles'].add(title(s)); e['where'].append('%s#rec%d[%d]' % (name, rec, k)); e['arrows'].add(bytes(s[0x15c:0x160]).hex())
                per_source[name].append(h)
    DCDIR = os.path.join(ROOT, 'extracted', 'dc_files', 'ENGLISH')
    def add(name, h, where, titles=()):
        e = reg.setdefault(h, {'titles': set(), 'where': [], 'arrows': set()})
        e['where'].append(where); e['titles'].update(titles); per_source.setdefault(name, []).append(h)
    d = open(os.path.join(DCDIR, 'PZSTAGE100.DAT'), 'rb').read()
    for k in range(100):
        sl = d[k * 1536 + 640:(k + 1) * 1536]; t, w = dlc_to_board(sl)
        add('dc_puzzle100', board_key(t, w), 'dc_puzzle100[%d]' % k, [sl[0x1eb:0x1eb + 21].split(bytes([0]))[0].decode('latin1').strip()])
    for fn, tag in (('BTSTAGE25.DAT', 'battle25'), ('CHSTAGE25.DAT', 'challenge25')):
        d = open(os.path.join(DCDIR, fn), 'rb').read()
        for k in range(25):
            t, w = ascii_to_board(d[k * 477:k * 477 + 475]); add('dc_' + tag, board_key(t, w), 'dc_%s[%d]' % (tag, k))
    for bname, base in (('ios_1.1.2', 'ios_v112/ccrphn'), ('android_1.15', 'android_apk115/libccrjni/main')):
        idx = json.load(open(os.path.join(ROOT, 'assets', base, 'index.json')))['records']
        for r in idx:
            if r['size'] == 11925:
                d = open(os.path.join(ROOT, 'assets', base, '%04d.bin' % r['i']), 'rb').read()
                tag = 'challenge25' if d == open(os.path.join(DCDIR, 'CHSTAGE25.DAT'), 'rb').read() else 'battle25'
                for k in range(25):
                    t, w = ascii_to_board(d[k * 477:k * 477 + 475]); add('%s_%s' % (bname, tag), board_key(t, w), '%s_%s[%d]' % (bname, tag, k))
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import gba_stages as G
    grom = open(G.ROM, 'rb').read()
    for k, o in enumerate(G.main_records(grom)):
        t, w = G.to_board(G.cells(grom, o)); add('gba_main100', board_key(t, w), 'gba_main100[%d]@%#x' % (k, o), [G.title(grom, o)])
    for k, o in enumerate(G.user_records(grom)):
        t, w = G.to_board(G.cells(grom, o)); add('gba_user', board_key(t, w), 'gba_user[%d]@%#x' % (k, o))
    for pack in ('PuzzleP', 'DEPuzzle'):
        name = 'dlc_' + pack; per_source[name] = []
        for k, sl in enumerate(dlc_slots(pack)):
            t, w = dlc_to_board(sl); h = board_key(t, w)
            e = reg.setdefault(h, {'titles': set(), 'where': [], 'arrows': set()})
            e['where'].append('%s[%d]' % (name, k)); per_source[name].append(h)
    return reg, per_source

DLC_DIR = r'c:\Dev\ChuChu Rocket\Original Game Files\Dreamcast\DLC'
# Dreamcast/DLC cell byte -> mobile tile code (learned from 9 wall-identical pairs; see docs/stages.md)
DLC_TILE = {0x09: 0, 0x0a: 1, 0x07: 0x11, 0x3d: 9, 0x3e: 0xa, 0x3f: 0xb, 0x40: 0xc, 0x47: 0xd, 0x48: 0xe, 0x49: 0xf, 0x4a: 0x10}

def dlc_to_board(slot):
    """25x19 lattice -> (tiles[108], walls[237]) in the mobile layout; returns 0x160-byte board key (arrow counts not yet decoded)."""
    L = [slot[r * 25:(r + 1) * 25] for r in range(19)]
    tiles = bytes(DLC_TILE.get(L[2 * r + 1][2 * c + 1], 0xff) for r in range(9) for c in range(12))
    walls = bytearray(237)
    for i in range(10):
        for c in range(12): walls[25 * i + c] = L[2 * i][2 * c + 1]
    for i in range(9):
        for c in range(13): walls[25 * i + 12 + c] = L[2 * i + 1][2 * c]
    return tiles, bytes(walls)

def dlc_slots(name):
    p = open(os.path.join(DLC_DIR, name + '.VMS'), 'rb').read()[640:]
    return [p[k * 1536:(k + 1) * 1536] for k in range((len(p) + 1535) // 1536) if len(p[k * 1536:(k + 1) * 1536]) >= 475]

def board_key(tiles, walls):
    return hashlib.sha1(tiles + walls).hexdigest()[:16]

def ascii_to_board(rec):
    """Dreamcast ASCII text map (25x19 chars, CRLF-terminated) -> (tiles, walls) in the mobile layout.
    Rule taken from Android FUN_0002e6cc: '7'->0x11, '9'->0, else ord(c)-0x40; wall where char == '1'."""
    L = [rec[r * 25:(r + 1) * 25] for r in range(19)]
    def tile(ch): return 0x11 if ch == 0x37 else 0 if ch == 0x39 else (ch - 0x40) & 0xff
    tiles = bytes(tile(L[2 * r + 1][2 * c + 1]) for r in range(9) for c in range(12))
    walls = bytearray(237)
    for i in range(10):
        for c in range(12): walls[25 * i + c] = 1 if L[2 * i][2 * c + 1] == 0x31 else 0
    for i in range(9):
        for c in range(13): walls[25 * i + 12 + c] = 1 if L[2 * i + 1][2 * c] == 0x31 else 0
    return tiles, bytes(walls)

if __name__ == '__main__':
    reg, per = build()
    print('unique boards across all sources:', len(reg))
    base = set(per['ios_1.1.2'])
    for name, hs in per.items():
        st = set(hs)
        print('%-14s stages %4d unique %4d | not in ios_1.1.2: %3d | ios_1.1.2 boards missing here: %3d' % (name, len(hs), len(st), len(st - base), len(base - st)))
    dlc_only = {h for n in ('dlc_PuzzleP', 'dlc_DEPuzzle') for h in per[n]} - base
    print('DLC boards not in any mobile build:', len(dlc_only), 'of', len({h for n in ('dlc_PuzzleP', 'dlc_DEPuzzle') for h in per[n]}))
    json.dump({h: {'titles': sorted(e['titles']), 'where': e['where'], 'arrow_counts': sorted(e['arrows'])} for h, e in reg.items()},
              open(r'c:\Dev\ChuChu Rocket\docs\stage_registry.json', 'w'), indent=1)
