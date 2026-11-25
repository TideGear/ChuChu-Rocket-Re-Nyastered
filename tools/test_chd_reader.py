"""Tests for the CHD v5 GD-ROM reader (tools/chd_reader.py).

FLAC frames come from ffmpeg's independent encoder when it is installed; ECC is
checked against the ECMA-130 parity equations evaluated separately here. The
synthetic CHD writer below follows the v5 layout read by the reader; real-file
correctness is additionally enforced at setup time by the CHD's own SHA-1.
"""
import binascii
import hashlib
import heapq
import lzma
import math
import pathlib
import random
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from array import array

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import chd_reader
import extract_all
import gdi_extract

FFMPEG = shutil.which('ffmpeg')


# --------------------------------------------------------------------------- helpers

def gf_tables():
    exp, log = [0] * 512, [0] * 256
    value = 1
    for power in range(255):
        exp[power] = value
        log[value] = power
        value <<= 1
        if value & 0x100:
            value ^= 0x11d
    for power in range(255, 512):
        exp[power] = exp[power - 255]
    return exp, log


EXP, LOG = gf_tables()


def gf_mul(a, b):
    return 0 if a == 0 or b == 0 else EXP[LOG[a] + LOG[b]]


def syndromes(codeword):
    """S0 = sum v_i, S1 = sum v_i * alpha^(n-1-i) for an ECMA-130 P or Q codeword."""
    s0 = s1 = 0
    n = len(codeword)
    for index, value in enumerate(codeword):
        s0 ^= value
        s1 ^= gf_mul(value, EXP[n - 1 - index])
    return s0, s1


def mode1_sector(lba, payload):
    lba += 150
    msf = bytes(int('%02d' % part, 16) for part in (lba // 4500, lba // 75 % 60, lba % 75))
    sector = chd_reader.SYNC + msf + b'\x01' + payload.ljust(2048, b'\0') + b'\0' * 288
    return chd_reader.ecc_generate(sector)


def flac_frames(samples_le, options=()):
    """Bare FLAC frames for 16-bit stereo PCM, from ffmpeg's encoder."""
    with tempfile.TemporaryDirectory() as temporary:
        source, target = pathlib.Path(temporary, 'in.raw'), pathlib.Path(temporary, 'out.flac')
        source.write_bytes(samples_le)
        subprocess.run([FFMPEG, '-v', 'error', '-f', 's16le', '-ar', '44100', '-ac', '2', '-i', str(source),
                        '-c:a', 'flac', '-frame_size', '2352', *options, '-f', 'flac', str(target)], check=True)
        data = target.read_bytes()
    assert data[:4] == b'fLaC'
    pos = 4
    while True:
        last, length = data[pos] & 0x80, int.from_bytes(data[pos + 1:pos + 4], 'big')
        pos += 4 + length
        if last:
            return data[pos:]


def test_audio(samples, seed):
    rng = random.Random(seed)
    left, right = [], []
    for index in range(samples):
        t = index / 44100.0
        a = int(9000 * math.sin(2 * math.pi * 440 * t) + rng.randint(-300, 300))
        b = int(12000 * math.sin(2 * math.pi * 97 * t + 1) + 4000 * math.sin(2 * math.pi * 3000 * t))
        if index % 5000 < 300:
            a, b = 32767 if index & 1 else -32768, 0
        left.append(max(-32768, min(32767, a)))
        right.append(max(-32768, min(32767, b)))
    pcm = array('h', [0] * (2 * samples))
    pcm[0::2], pcm[1::2] = array('h', left), array('h', right)
    if sys.byteorder == 'big':
        pcm.byteswap()
    return pcm.tobytes()


class BitWriter:
    def __init__(self):
        self.bits = []

    def write(self, value, count):
        self.bits.extend((value >> (count - 1 - index)) & 1 for index in range(count))

    def bytes(self):
        padded = self.bits + [0] * (-len(self.bits) % 8)
        return bytes(int(''.join(map(str, padded[index:index + 8])), 2) for index in range(0, len(padded), 8))


def huffman_lengths(counts, maxbits=8):
    used = [symbol for symbol, count in enumerate(counts) if count]
    lengths = [0] * len(counts)
    if len(used) == 1:
        lengths[used[0]] = 1
        return lengths
    heap = [(counts[symbol], index, [symbol]) for index, symbol in enumerate(used)]
    heapq.heapify(heap)
    tie = len(heap)
    while len(heap) > 1:
        a, _, sa = heapq.heappop(heap)
        b, _, sb = heapq.heappop(heap)
        for symbol in sa + sb:
            lengths[symbol] += 1
        heapq.heappush(heap, (a + b, tie, sa + sb))
        tie += 1
    if max(lengths) > maxbits:
        raise AssertionError('test histogram too skewed')
    return lengths


def write_tree(bits, lengths):
    index = 0
    while index < len(lengths):
        value = lengths[index]
        run = 1
        while index + run < len(lengths) and lengths[index + run] == value and run < 18:
            run += 1
        if value != 1 and run >= 3:
            bits.write(1, 4); bits.write(value, 4); bits.write(run - 3, 4)
            index += run
        elif value == 1:
            bits.write(1, 4); bits.write(1, 4)
            index += 1
        else:
            bits.write(value, 4)
            index += 1


def make_chd(path, tracks, codec_for, compressors=(b'cdlz', b'cdzl', b'cdfl', b'\0\0\0\0'),
             frames_per_hunk=8, version=5, parent=False, tag=b'CHGD', mangle=None):
    """Write a CHD v5 GD-ROM. tracks: list of dicts(number, type, frames=[2352-byte sectors], pregap, pgtype, postgap)."""
    hunkbytes = frames_per_hunk * chd_reader.CD_FRAME
    raw = bytearray()
    for track in tracks:
        for sector in track['frames']:
            if track['type'] == 'AUDIO':
                swapped = array('h', sector)
                swapped.byteswap()
                sector = swapped.tobytes()
            raw += sector + bytes(chd_reader.CD_SUBCODE)
        raw += bytes(chd_reader.CD_FRAME * (-len(track['frames']) % 4))
    logical = len(raw)
    raw += bytes(-len(raw) % hunkbytes)
    hunks = [bytes(raw[i:i + hunkbytes]) for i in range(0, len(raw), hunkbytes)]
    meta = b''
    entries_meta = []
    for track in tracks:
        text = ('TRACK:%d TYPE:%s SUBTYPE:NONE FRAMES:%d PAD:%d PREGAP:%d PGTYPE:%s PGSUB:RW POSTGAP:%d'
                % (track['number'], track['type'], len(track['frames']), -len(track['frames']) % 4,
                   track.get('pregap', 0), track.get('pgtype', 'MODE1'), track.get('postgap', 0))).encode() + b'\0'
        entries_meta.append(text)
    meta_offset = 124
    blob = bytearray()
    for index, text in enumerate(entries_meta):
        following = meta_offset + len(blob) + 16 + len(text) if index + 1 < len(entries_meta) else 0
        blob += struct.pack('>4sIQ', tag, (1 << 24) | len(text), following) + text
    data_start = meta_offset + len(blob)
    data = bytearray()
    kinds, records, seen = [], [], {}
    for number, hunk in enumerate(hunks):
        choice = codec_for(number, hunk)
        if choice == 'self' and hunk in seen:
            kinds.append(chd_reader.COMPRESSION_SELF)
            records.append(('self', seen[hunk]))
            continue
        seen.setdefault(hunk, number)
        if choice in ('none', 'self'):
            kinds.append(chd_reader.COMPRESSION_NONE)
            records.append(('none', len(data), hunkbytes, binascii.crc_hqx(hunk, 0xffff)))
            data += hunk
            continue
        compressed = encode_hunk(choice, hunk, frames_per_hunk)
        kinds.append(compressors.index(choice))
        records.append(('comp', len(data), len(compressed), binascii.crc_hqx(hunk, 0xffff)))
        data += compressed
    # pass 1: types with SELF_0/SELF_1 and RLE
    symbols, last_self, coded = [], 0, []
    for kind, record in zip(kinds, records):
        if kind == chd_reader.COMPRESSION_SELF:
            if record[1] == last_self:
                kind = chd_reader.SELF_0
            elif record[1] == last_self + 1:
                kind = chd_reader.SELF_1
            last_self = record[1]
        coded.append(kind)
    index = 0
    while index < len(coded):
        run = 1
        while index + run < len(coded) and coded[index + run] == coded[index]:
            run += 1
        symbols.append((coded[index],))
        rest = run - 1
        while rest >= 2:
            if rest >= 18:
                take = min(rest, 18 + 255)
                symbols.append((chd_reader.RLE_LARGE, (take - 18) >> 4, (take - 18) & 15))
            else:
                take = rest
                symbols.append((chd_reader.RLE_SMALL, take - 2))
            rest -= take
        symbols.extend([(coded[index],)] * rest)
        index += run
    counts = [0] * 16
    for symbol in symbols:
        for part in symbol:
            counts[part] += 1
    lengths = huffman_lengths(counts)
    tree = chd_reader.Huffman(16, 8)
    tree.lengths = lengths
    tree._assign()
    codes = {symbol: (length, code) for (length, code), symbol in tree.table.items()}
    lengthbits = max(1, max((record[2] for record in records if record[0] == 'comp'), default=1).bit_length())
    selfbits = max(1, len(hunks).bit_length())
    rawmap = bytearray()
    for kind, record in zip(kinds, records):
        if record[0] == 'self':
            rawmap += bytes([kind]) + bytes(3) + record[1].to_bytes(6, 'big') + bytes(2)
        else:
            rawmap += bytes([kind]) + (record[2] if record[0] == 'comp' else hunkbytes).to_bytes(3, 'big') + \
                (data_start + record[1]).to_bytes(6, 'big') + record[3].to_bytes(2, 'big')
    bits2 = BitWriter()
    write_tree(bits2, lengths)
    for symbol in symbols:
        for part in symbol:
            bits2.write(codes[part][1], codes[part][0])
    for code, record in zip(coded, records):
        if record[0] == 'comp':
            bits2.write(record[2], lengthbits); bits2.write(record[3], 16)
        elif record[0] == 'none':
            bits2.write(record[3], 16)
        elif code == chd_reader.COMPRESSION_SELF:
            bits2.write(record[1], selfbits)
    mapbits = bits2.bytes()
    map_offset = data_start + len(data)
    map_header = struct.pack('>I', len(mapbits)) + data_start.to_bytes(6, 'big') + \
        struct.pack('>H', binascii.crc_hqx(bytes(rawmap), 0xffff)) + bytes([lengthbits, selfbits, 0, 0])
    header = bytearray(124)
    header[0:8] = b'MComprHD'
    struct.pack_into('>II', header, 8, 124, version)
    for index, codec in enumerate(compressors):
        header[16 + 4 * index:20 + 4 * index] = codec
    struct.pack_into('>QQQII', header, 32, logical, map_offset, meta_offset, hunkbytes, chd_reader.CD_FRAME)
    header[64:84] = hashlib.sha1(bytes(raw[:logical])).digest()
    header[84:104] = hashlib.sha1(b'overall').digest()
    if parent:
        header[104:124] = b'\x11' * 20
    image = bytes(header) + bytes(blob) + bytes(data) + map_header + mapbits
    if mangle:
        image = mangle(bytearray(image), data_start)
    pathlib.Path(path).write_bytes(image)
    return bytes(raw[:logical])


def encode_hunk(codec, hunk, frames):
    sectors = bytearray()
    subcode = bytearray()
    ecc = bytearray((frames + 7) // 8)
    for index in range(frames):
        frame = hunk[index * chd_reader.CD_FRAME:(index + 1) * chd_reader.CD_FRAME]
        sector, sub = bytearray(frame[:2352]), frame[2352:]
        if codec != b'cdfl' and sector[:12] == chd_reader.SYNC and chd_reader.ecc_generate(bytes(sector)) == bytes(sector):
            ecc[index // 8] |= 1 << (index % 8)
            sector[:12] = bytes(12)
            sector[0x81c:0x81c + 276] = bytes(276)
        sectors += sector
        subcode += sub
    deflate = zlib.compressobj(9, zlib.DEFLATED, -15)
    sub = deflate.compress(bytes(subcode)) + deflate.flush()
    if codec == b'cdfl':
        pcm = array('h', bytes(sectors))
        if sys.byteorder == 'little':
            pcm.byteswap()
        return flac_frames(pcm.tobytes()) + sub
    if codec == b'cdlz':
        base = lzma.compress(bytes(sectors), format=lzma.FORMAT_ALONE,
                             filters=[{'id': lzma.FILTER_LZMA1, 'dict_size': 1 << 16, 'lc': 3, 'lp': 0, 'pb': 2}])[13:]
    else:
        deflate = zlib.compressobj(9, zlib.DEFLATED, -15)
        base = deflate.compress(bytes(sectors)) + deflate.flush()
    length_bytes = 2 if len(hunk) < 65536 else 3
    return bytes(ecc) + len(base).to_bytes(length_bytes, 'big') + base + sub


def directory_record(name, lba, size, directory=False):
    name = name.encode()
    length = 33 + len(name) + (1 - len(name) % 2)
    record = bytearray(length)
    record[0] = length
    struct.pack_into('<I', record, 2, lba)
    struct.pack_into('>I', record, 6, lba)
    struct.pack_into('<I', record, 10, size)
    struct.pack_into('>I', record, 14, size)
    record[25] = 2 if directory else 0
    record[32] = len(name)
    record[33:33 + len(name)] = name
    return bytes(record)


def gd_layout():
    """A small GD-ROM: low-density data/audio, track 03 ISO, two audio tracks, last data track."""
    rng = random.Random(7)
    audio2 = test_audio(588 * 20, 1)
    audio4 = test_audio(588 * 37, 2)
    audio5 = bytes(2352 * 24)  # a silent track: self-referencing hunks
    files = {'A.BIN': bytes(rng.randrange(256) for _ in range(5000)),
             'SUB/B.TXT': b'hello from the high-density area\n' * 80,
             'LATE.BIN': bytes(rng.randrange(256) for _ in range(9000))}
    track3_frames = 40
    pregap5, last_lba = 150, None
    track4_lba = 45000 + track3_frames
    track5_lba = track4_lba + len(audio4) // 2352
    track6_lba = track5_lba + len(audio5) // 2352 + pregap5
    sectors3 = [bytes(2048) for _ in range(track3_frames)]
    root, sub = 45000 + 20, 45000 + 21
    a_lba, b_lba = 45000 + 22, 45000 + 26
    late_lba = track6_lba
    pvd = bytearray(2048)
    pvd[0], pvd[1:6], pvd[6] = 1, b'CD001', 1
    root_dir = (directory_record('\x00', root, 2048, True) + directory_record('\x01', root, 2048, True) +
                directory_record('A.BIN;1', a_lba, len(files['A.BIN'])) +
                directory_record('LATE.BIN;1', late_lba, len(files['LATE.BIN'])) +
                directory_record('SUB', sub, 2048, True))
    pvd[156:190] = directory_record('\x00', root, 2048, True)
    sub_dir = (directory_record('\x00', sub, 2048, True) + directory_record('\x01', root, 2048, True) +
               directory_record('B.TXT;1', b_lba, len(files['SUB/B.TXT'])))
    sectors3[16], sectors3[20], sectors3[21] = bytes(pvd), root_dir.ljust(2048, b'\0'), sub_dir.ljust(2048, b'\0')
    for name, lba in (('A.BIN', a_lba), ('SUB/B.TXT', b_lba)):
        data = files[name]
        for index in range(0, len(data), 2048):
            sectors3[lba - 45000 + index // 2048] = data[index:index + 2048]
    late = [files['LATE.BIN'][index:index + 2048] for index in range(0, len(files['LATE.BIN']), 2048)]
    late += [bytes(2048)] * (10 - len(late))
    tracks = [
        {'number': 1, 'type': 'MODE1_RAW', 'frames': [mode1_sector(i, b'low %d' % i) for i in range(300)]},
        {'number': 2, 'type': 'AUDIO', 'frames': [audio2[i:i + 2352] for i in range(0, len(audio2), 2352)],
         'pregap': 150, 'pgtype': 'AUDIO'},
        {'number': 3, 'type': 'MODE1_RAW', 'frames': [mode1_sector(45000 + i, s) for i, s in enumerate(sectors3)]},
        {'number': 4, 'type': 'AUDIO', 'frames': [audio4[i:i + 2352] for i in range(0, len(audio4), 2352)]},
        {'number': 5, 'type': 'AUDIO', 'frames': [audio5[i:i + 2352] for i in range(0, len(audio5), 2352)]},
        {'number': 6, 'type': 'MODE1_RAW', 'frames': [mode1_sector(track6_lba + i, s) for i, s in enumerate(late)],
         'pregap': pregap5, 'pgtype': 'MODE1'},
    ]
    return tracks, files, {'audio2': audio2, 'audio4': audio4, 'audio5': audio5, 'track6_lba': track6_lba}


def mixed_codecs(number, hunk):
    if not any(hunk):
        return 'self'
    if FFMPEG and number % 3 == 0:
        return b'cdfl'
    return (b'cdlz', b'cdzl', 'none')[number % 3]


# --------------------------------------------------------------------------- tests

class EccTest(unittest.TestCase):
    def test_generated_parity_satisfies_ecma130_equations(self):
        rng = random.Random(3)
        for trial in range(6):
            sector = mode1_sector(rng.randrange(400000), bytes(rng.randrange(256) for _ in range(2048)))
            body = sector[12:12 + 2064]
            for major in range(86):
                word = [body[major + 86 * minor] for minor in range(24)] + [sector[0x81c + major], sector[0x81c + 86 + major]]
                self.assertEqual(syndromes(word), (0, 0))
            body = sector[12:12 + 2236]
            for major in range(52):
                word = [body[((major >> 1) * 86 + (major & 1) + 88 * minor) % 2236] for minor in range(43)]
                word += [sector[0x8c8 + major], sector[0x8c8 + 52 + major]]
                self.assertEqual(syndromes(word), (0, 0))


@unittest.skipUnless(FFMPEG, 'ffmpeg is needed to produce independent FLAC frames')
class FlacTest(unittest.TestCase):
    def check(self, options, samples=2352 * 6, seed=11):
        pcm = test_audio(samples, seed)
        frames = flac_frames(pcm, options)
        (left, right), used = chd_reader.flac_decode(frames + b'tail', samples)
        self.assertEqual(used, len(frames))
        decoded = array('h', [0] * (2 * samples))
        decoded[0::2], decoded[1::2] = array('h', left), array('h', right)
        if sys.byteorder == 'big':
            decoded.byteswap()
        self.assertEqual(decoded.tobytes(), pcm)

    def test_stereo_modes(self):
        for mode in ('indep', 'left_side', 'right_side', 'mid_side'):
            with self.subTest(mode=mode):
                self.check(['-ch_mode', mode])

    def test_predictors_and_partitions(self):
        for options in (['-compression_level', '0'], ['-compression_level', '12'],
                        ['-lpc_type', 'fixed'], ['-lpc_type', 'none'],
                        ['-lpc_type', 'cholesky', '-min_prediction_order', '32', '-max_prediction_order', '32'],
                        ['-min_partition_order', '0', '-max_partition_order', '0'],
                        ['-exact_rice_parameters', '1', '-max_partition_order', '8']):
            with self.subTest(options=options):
                self.check(options)

    def test_silence_and_constant_frames(self):
        pcm = bytes(2352 * 4 * 4)
        frames = flac_frames(pcm)
        (left, right), _ = chd_reader.flac_decode(frames, 2352 * 4)
        self.assertEqual(left, [0] * (2352 * 4))
        self.assertEqual(right, [0] * (2352 * 4))


class ChdTest(unittest.TestCase):
    def build(self, root, **options):
        tracks, files, extra = gd_layout()
        path = pathlib.Path(root, 'disc.chd')
        raw = make_chd(path, tracks, options.pop('codec_for', mixed_codecs), **options)
        return path, tracks, files, extra, raw

    def test_converts_and_extracts_gdrom_chd(self):
        with tempfile.TemporaryDirectory() as temporary:
            path, tracks, files, extra, _ = self.build(temporary)
            out = pathlib.Path(temporary, 'files')
            rows = gdi_extract.extract(path, out, 0, pathlib.Path(temporary, 'scratch'))
            for name, data in files.items():
                self.assertEqual(pathlib.Path(out, name).read_bytes(), data)
            by_number = {row.number: row for row in rows}
            self.assertEqual(by_number[3].lba, 45000)
            self.assertEqual(by_number[6].lba, extra['track6_lba'])
            self.assertEqual(by_number[6].sector_size, 2048)
            for number, key in ((2, 'audio2'), (4, 'audio4'), (5, 'audio5')):
                self.assertEqual(by_number[number].kind, 0)
                self.assertEqual(by_number[number].path.read_bytes(), extra[key])
            self.assertEqual(by_number[1].path.read_bytes()[:5], b'low 0')

    def test_describe_reports_track_table(self):
        with tempfile.TemporaryDirectory() as temporary:
            path, *_ = self.build(temporary)
            info = chd_reader.describe(path)
            self.assertEqual([track['number'] for track in info['tracks']], [1, 2, 3, 4, 5, 6])
            self.assertEqual(info['tracks'][2]['lba'], 45000)
            self.assertEqual(info['codecs'], ['cdlz', 'cdzl', 'cdfl'])

    def test_uncompressed_and_all_lzma_variants(self):
        for codec in (b'cdlz', b'cdzl', 'none'):
            with self.subTest(codec=codec), tempfile.TemporaryDirectory() as temporary:
                path, _, files, _, _ = self.build(temporary, codec_for=lambda number, hunk, c=codec: c)
                out = pathlib.Path(temporary, 'files')
                gdi_extract.extract(path, out, 0, pathlib.Path(temporary, 'scratch'))
                self.assertEqual(pathlib.Path(out, 'LATE.BIN').read_bytes(), files['LATE.BIN'])

    def test_damaged_hunk_is_rejected(self):
        def mangle(image, data_start):
            image[data_start + 40] ^= 0x55
            return bytes(image)
        with tempfile.TemporaryDirectory() as temporary:
            path, *_ = self.build(temporary, codec_for=lambda n, h: 'none', mangle=mangle)
            with self.assertRaisesRegex(chd_reader.ChdError, 'CRC mismatch'):
                chd_reader.convert(path, pathlib.Path(temporary, 'scratch'))

    def test_unsupported_variants_are_reported(self):
        cases = ((dict(compressors=(b'cdzs', b'cdzl', b'cdlz', b'\0\0\0\0'), codec_for=lambda n, h: b'cdzl'), 'cdzs'),
                 (dict(parent=True), 'parent'),
                 (dict(version=4), 'version 4'),
                 (dict(tag=b'CHT2'), 'CD-ROM'),
                 (dict(tag=b'CHGT'), 'pre-2013'))
        for options, message in cases:
            with self.subTest(message=message), tempfile.TemporaryDirectory() as temporary:
                path, *_ = self.build(temporary, **options)
                with self.assertRaisesRegex(chd_reader.ChdError, message):
                    chd_reader.convert(path, pathlib.Path(temporary, 'scratch'))

    def test_setup_discovers_chd_and_rejects_mixed_folders(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            path, *_ = self.build(temporary)
            found = list(extract_all.discover(path, root / 'work'))
            self.assertEqual(found[0][0], 'dreamcast')
            entry = extract_all.input_entry('dreamcast', path, 'disc.chd')
            self.assertEqual(entry['chd']['tracks'][2]['lba'], 45000)
            folder = list(extract_all.discover(root, root / 'work'))
            self.assertEqual([kind for kind, *_ in folder], ['dreamcast'])
            (root / 'other.gdi').write_text('0\n')
            folder = list(extract_all.discover(root, root / 'work'))
            self.assertEqual([kind for kind, *_ in folder], ['error'])

    def test_do_dreamcast_removes_decoded_tracks(self):
        with tempfile.TemporaryDirectory() as temporary:
            path, *_ = self.build(temporary)
            work = pathlib.Path(temporary, 'work')
            tracks, files = extract_all.refresh_dreamcast_files(path, str(work), str(pathlib.Path(temporary, 'assets')))
            self.assertTrue(extract_all.chd_scratch(work).is_dir())
            self.assertTrue(pathlib.Path(files, 'SUB', 'B.TXT').is_file())


if __name__ == '__main__':
    unittest.main()
