"""Write Dreamcast ChuChu Rocket puzzle packs: 25 puzzles as a .VMS (VMU save image) plus its .VMI (file info), the format the game's DLC puzzle packs (PuzzleP, DEPuzzle) use.
Layout (docs/dlc.md, docs/stages.md): the .VMS is 38,400 bytes = 640-byte header (description 'CHU_CHU__D01', Japanese long description, application id, icon) + 24 full 1,536-byte slots + an 896-byte final slot. The final slot's 512-byte board-and-title payload is intact; unused padding is omitted. A slot is: 25x19 lattice (475 bytes: tile
codes at odd/odd positions, wall bytes 0/1 between them, border corner posts 1), then +0 = number n of solution arrows (<= 12), +1..+12 their cells (high nibble x, low nibble y),
+13..+15 a 24-bit little-endian field of 2-bit directions (0 south, 1 west, 2 north, 3 east), +16 the title (21 bytes, ASCII or Shift-JIS, zero padded).
The .VMI is 108 bytes: checksum (first four resource-name characters ANDed with 'SEGA'), description, copyright, timestamp, version, file number, resource name, file name, mode, size.
Verified by tools/vms_pack_check.py: re-encoding the 50 real DLC slots reproduces their lattice, solution and title fields byte for byte.
usage as a module: pack_puzzles(boards, name) -> (vms bytes, vmi bytes)"""
import struct, time

# mobile-layout tile id -> lattice code (inverse of stage_registry.DLC_TILE)
TILE_TO_LATTICE = {0: 0x09, 1: 0x0a, 0x11: 0x07, 9: 0x3d, 10: 0x3e, 11: 0x3f, 12: 0x40, 13: 0x47, 14: 0x48, 15: 0x49, 16: 0x4a}
SLOT = 1536
HEADER = 640

def encode_slot(tiles, walls, arrows, title=b'', filler=0):
    """tiles[108] and walls[237] in the mobile layout (walls: 10 rows of 12 horizontal edges at 25*i + c, 9 rows of 13 vertical edges at 25*i + 12 + c);
    arrows: up to 12 (x, y, dir) solution arrows (also the arrow stock the game offers); returns the 1,536-byte slot."""
    if len(tiles) != 108 or len(walls) != 237: raise ValueError('board size')
    if len(arrows) > 12: raise ValueError('at most 12 solution arrows')
    s = bytearray([filler]) * SLOT
    L = bytearray(475)
    for r in range(9):
        for c in range(12):
            t = tiles[r * 12 + c]
            if t not in TILE_TO_LATTICE: raise ValueError('tile %#x has no Dreamcast code' % t)
            L[(2 * r + 1) * 25 + 2 * c + 1] = TILE_TO_LATTICE[t]
    for i in range(10):
        for c in range(12): L[(2 * i) * 25 + 2 * c + 1] = 1 if walls[25 * i + c] else 0
    for i in range(9):
        for c in range(13): L[(2 * i + 1) * 25 + 2 * c] = 1 if walls[25 * i + 12 + c] else 0
    for i in range(10):
        for c in range(13):
            L[(2 * i) * 25 + 2 * c] = 1 if (i in (0, 9) or c in (0, 12)) else 0   # corner posts: 1 on the border, 0 inside (measured on all 50 real slots)
    s[:475] = L
    s[475] = len(arrows)
    dirs = 0
    for k in range(12):
        s[476 + k] = (arrows[k][0] << 4 | arrows[k][1]) if k < len(arrows) else 0
        if k < len(arrows): dirs |= (arrows[k][2] & 3) << (2 * k)
    s[488:491] = struct.pack('<I', dirs)[:3]
    t = title[:20] if isinstance(title, bytes) else title.encode('ascii', 'replace')[:20]
    s[491:491 + 21] = t.ljust(21, b'\0')
    return bytes(s)

def decode_slot(slot):
    """Inverse of encode_slot for checking: returns (tiles, walls, arrows, title)."""
    lat_to_tile = {v: k for k, v in TILE_TO_LATTICE.items()}
    tiles = bytes(lat_to_tile.get(slot[(2 * r + 1) * 25 + 2 * c + 1], 0xff) for r in range(9) for c in range(12))
    walls = bytearray(237)
    for i in range(10):
        for c in range(12): walls[25 * i + c] = slot[(2 * i) * 25 + 2 * c + 1]
    for i in range(9):
        for c in range(13): walls[25 * i + 12 + c] = slot[(2 * i + 1) * 25 + 2 * c]
    n = slot[475]; dirs = slot[488] | slot[489] << 8 | slot[490] << 16
    arrows = [(slot[476 + k] >> 4, slot[476 + k] & 15, (dirs >> (2 * k)) & 3) for k in range(min(n, 12))]
    return tiles, bytes(walls), arrows, slot[491:512].split(b'\0')[0]

def vmi_checksum(resource):
    return bytes(a & b for a, b in zip(resource.ljust(4, b'\0')[:4], b'SEGA'))

def build_vmi(resource, vms_name, size, description=b'CCR Puzzles', copyright=b'Dreamcast Live', when=None, file_number=1):
    """108-byte VMI. resource: up to 8 ASCII characters (also the .VMI/.VMS base name); vms_name: 12 characters, e.g. b'CHU_CHU__D00'."""
    r = resource.encode('ascii') if isinstance(resource, str) else resource
    if not (1 <= len(r) <= 8): raise ValueError('resource name must be 1-8 characters')
    t = when or time.localtime()
    wd = (t.tm_wday + 1) % 7   # VMI weekday: 0 = Sunday
    out = bytearray()
    out += vmi_checksum(r)
    out += description[:32].ljust(32, b'\0') + copyright[:32].ljust(32, b'\0')
    out += struct.pack('<HBBBBBB', t.tm_year, t.tm_mon, t.tm_mday, t.tm_hour, t.tm_min, t.tm_sec, wd)
    out += struct.pack('<HH', 0x0100, file_number) + r.ljust(8, b'\0') + vms_name[:12].ljust(12, b'\0')
    out += struct.pack('<HHI', 0, 0, size)
    return bytes(out)

def build_header(description=b'CHU_CHU__D01', long_description=b'CCR Re-Nyastered puzzles'):
    h = bytearray(HEADER)
    h[0:16] = description[:16].ljust(16, b' ')
    h[16:48] = long_description[:32].ljust(32, b' ')
    h[48:64] = b'ChuChu Rocket!'.ljust(16, b'\0')
    h[64:66] = struct.pack('<H', 1)      # one icon frame
    # icon palette (0x60) and bitmap (0x80) stay zero: a blank icon
    return bytes(h)

def pack_puzzles(boards, resource='CCRPUZ', title_prefix=b''):
    """boards: list of up to 25 dicts {tiles, walls, arrows, title}; returns (vms, vmi)."""
    if not 1 <= len(boards) <= 25: raise ValueError('a pack holds 1-25 puzzles')
    body = b''.join(encode_slot(b['tiles'], b['walls'], b.get('arrows', []), b.get('title', b'')) for b in boards)
    body += b'\0' * (SLOT * (25 - len(boards)))
    vms = build_header() + body[:24 * SLOT + 896]  # retail packs omit 640 bytes of final-slot padding
    return vms, build_vmi(resource, b'CHU_CHU__D00', len(vms))
