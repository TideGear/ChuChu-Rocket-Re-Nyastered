"""GBA ChuChu Rocket stage extraction.
Record layout found by matching mobile boards: 9 rows x 12 cells, each cell a little-endian halfword;
high nibble = walls (bit12 right, bit13 bottom, bit14 left, bit15 top), low 12 bits = cell content.
Record stride 296 bytes (216 bytes of cells + 80 bytes of other data)."""
import glob, struct, sys

ROM = (glob.glob(r'c:\Dev\ChuChu Rocket\analysis\extracted\gba\*.gba') or [None])[0]   # overridden by extract_all.py and other callers
STRIDE = 296

def cells(rom, o):
    return struct.unpack_from('<108H', rom, o)

def consistent(c):
    """Shared edges must agree and the outer border must be (almost) all walls."""
    bad = 0
    for r in range(9):
        for k in range(12):
            v = c[r * 12 + k]; right, bottom, left, top = (v >> 12) & 1, (v >> 13) & 1, (v >> 14) & 1, (v >> 15) & 1
            if k < 11 and right != ((c[r * 12 + k + 1] >> 14) & 1): bad += 1
            if r < 8 and bottom != ((c[(r + 1) * 12 + k] >> 15) & 1): bad += 1
    border = sum(((c[k] >> 15) & 1) + ((c[96 + k] >> 13) & 1) for k in range(12)) + sum(((c[r * 12] >> 14) & 1) + ((c[r * 12 + 11] >> 12) & 1) for r in range(9))
    return bad, border

def scan(rom):
    found = []
    for o in range(0, len(rom) - 216, 2):
        # cheap prefilter: first row shared edges
        c = cells(rom, o)
        bad, border = consistent(c)
        if bad == 0 and border >= 30: found.append(o)
    return found

if __name__ == '__main__':
    rom = open(ROM, 'rb').read()
    f = scan(rom)
    print(len(f), 'consistent 108-cell blocks')
    # group into arrays by stride
    arrays = []; cur = []
    for o in f:
        if cur and o - cur[-1] == STRIDE: cur.append(o)
        else:
            if len(cur) >= 3: arrays.append(cur)
            cur = [o]
    if len(cur) >= 3: arrays.append(cur)
    for a in arrays: print('array @%#x x%d (ends %#x)' % (a[0], len(a), a[-1] + STRIDE))
    print('isolated:', len(f) - sum(len(a) for a in arrays))


# Cell content (low 12 bits) -> mobile tile code. Learned from 99 title-matched main puzzles.
# 0x100..0x103 mice, 0x200..0x203 cats, 0x020 rocket, 0x080 hole; overlay bits 0x4c = reference-solution arrows.
GBA_TILE = {0x000: 0, 0x020: 1, 0x080: 0x11, 0x101: 9, 0x102: 0xa, 0x103: 0xb, 0x100: 0xc,
            0x201: 0xd, 0x202: 0xe, 0x203: 0xf, 0x200: 0x10}
MAIN_START, MAIN_COUNT = 0xaf3e8, 100          # 296-byte records: 216 cells + 80 extras (title at +256, UTF-16LE, char-0x20)
USER_START, USER_END, USER_STRIDE = 0xb6c90, 0x152090, 256   # 216 cells + 40 extras, no title

def to_board(c):
    """108 cell halfwords -> (tiles[108], walls[237]) in the mobile layout. Unknown contents keep 0xf0|raw marker bits."""
    tiles = bytes(GBA_TILE.get((v & 0xfff) & ~0x4c, 0xf0 | ((v & 0xfff) >> 2 & 0xf)) for v in c)   # 0x40/0x44/0x48/0x4c = overlay flag bits, ignored in the board key
    walls = bytearray(237)
    for r in range(9):
        for k in range(12):
            v = c[r * 12 + k]
            if v >> 15 & 1: walls[25 * r + k] = 1               # top edge of this cell
            if v >> 13 & 1: walls[25 * (r + 1) + k] = 1         # bottom edge
            if v >> 14 & 1: walls[25 * r + 12 + k] = 1          # left edge
            if v >> 12 & 1: walls[25 * r + 12 + k + 1] = 1      # right edge
    return tiles, bytes(walls)

def title(rom, o):
    t = rom[o + 256:o + 296]
    return ''.join(chr(((t[i] | t[i + 1] << 8) + 0x20) & 0xff) if (t[i] | t[i + 1] << 8) else ' ' for i in range(0, 40, 2)).strip()

def main_records(rom):
    return [MAIN_START + MAIN_STRIDE * k for k in range(MAIN_COUNT)] if False else [MAIN_START + STRIDE * k for k in range(MAIN_COUNT)]

def user_records(rom):
    out = []
    for o in range(USER_START, USER_END, USER_STRIDE):
        c = cells(rom, o); bad, _ = consistent(c)
        if bad == 0 and sum(1 for v in c if v >> 12) >= 12: out.append(o)
    return out
