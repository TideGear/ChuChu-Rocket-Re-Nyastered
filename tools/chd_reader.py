"""Read Dreamcast GD-ROM images stored as MAME CHD v5 files.

The reader decodes the file itself instead of relying on `chdman extractcd`, whose
cue output does not describe the GD-ROM high-density area. Decoding is checked
three ways before any track is used:

* every hunk's CRC-16 recorded in the CHD map;
* the SHA-1 of all raw data recorded in the CHD header (`rawsha1`);
* the BCD address in each raw data sector header, which fixes each data track's
  LBA (the high-density area must start at LBA 45000).

Supported: uncompressed and compressed v5 files with the CD codecs chdman uses by
default (cdlz = LZMA, cdzl = deflate, cdfl = FLAC) plus self-referencing hunks.
cdzs (zstd) needs a zstd module that the pinned Python does not ship, and parent
(delta) CHDs need their parent; both are reported, not guessed.

Usage: chd_reader.py <disc.chd> [outdir]   (prints the track table; converts with outdir)
"""
import binascii
import hashlib
import lzma
import operator
import os
import re
import struct
import sys
import zlib
from array import array
from dataclasses import dataclass
from pathlib import Path

CD_SECTOR = 2352
CD_SUBCODE = 96
CD_FRAME = CD_SECTOR + CD_SUBCODE
SYNC = b'\x00' + b'\xff' * 10 + b'\x00'
GD_HIGH_DENSITY_LBA = 45000

COMPRESSION_NONE, COMPRESSION_SELF, COMPRESSION_PARENT = 4, 5, 6
RLE_SMALL, RLE_LARGE = 7, 8
SELF_0, SELF_1, PARENT_SELF, PARENT_0, PARENT_1 = 9, 10, 11, 12, 13

GDROM_TAG = b'CHGD'
GDROM_OLD_TAG = b'CHGT'
CD_TAGS = (b'CHT2', b'CHTR', b'CHCD')


class ChdError(ValueError):
    pass


# --------------------------------------------------------------------------- bits / Huffman

class BitReader:
    """MSB-first bit reader; reads past the end return zero bits and set `overflow`."""

    def __init__(self, data):
        self.data = data
        self.pos = 0
        self.total = len(data) * 8

    @property
    def overflow(self):
        return self.pos > self.total

    def read(self, count):
        if count == 0:
            return 0
        value = 0
        pos = self.pos
        end = pos + count
        while pos < end:
            byte_index = pos >> 3
            byte = self.data[byte_index] if byte_index < len(self.data) else 0
            offset = pos & 7
            take = min(8 - offset, end - pos)
            bits = (byte >> (8 - offset - take)) & ((1 << take) - 1)
            value = (value << take) | bits
            pos += take
        self.pos = end
        return value


class Huffman:
    """MAME canonical Huffman decoder (longest codes take the lowest values)."""

    def __init__(self, numcodes, maxbits):
        self.numcodes, self.maxbits = numcodes, maxbits
        self.lengths = [0] * numcodes
        self.table = {}

    def import_tree_rle(self, bits):
        width = 5 if self.maxbits >= 16 else (4 if self.maxbits >= 8 else 3)
        node = 0
        while node < self.numcodes:
            value = bits.read(width)
            if value != 1:
                self.lengths[node] = value
                node += 1
                continue
            value = bits.read(width)
            if value == 1:
                self.lengths[node] = 1
                node += 1
                continue
            repeat = bits.read(width) + 3
            if node + repeat > self.numcodes:
                raise ChdError('invalid CHD Huffman tree')
            for _ in range(repeat):
                self.lengths[node] = value
                node += 1
        self._assign()

    def _assign(self):
        histogram = [0] * 33
        for length in self.lengths:
            if length > self.maxbits:
                raise ChdError('invalid CHD Huffman code length')
            histogram[length] += 1
        start = 0
        for length in range(32, 0, -1):
            following = (start + histogram[length]) >> 1
            if length != 1 and following * 2 != start + histogram[length]:
                raise ChdError('inconsistent CHD Huffman tree')
            histogram[length], start = start, following
        self.table = {}
        for symbol, length in enumerate(self.lengths):
            if length:
                self.table[(length, histogram[length])] = symbol
                histogram[length] += 1

    def decode(self, bits):
        code = 0
        for length in range(1, self.maxbits + 1):
            code = (code << 1) | bits.read(1)
            symbol = self.table.get((length, code))
            if symbol is not None:
                return symbol
        raise ChdError('invalid CHD Huffman code')


# --------------------------------------------------------------------------- codecs

def inflate(data, size):
    decoder = zlib.decompressobj(-15)
    out = decoder.decompress(data, size)
    if len(out) != size:
        raise ChdError('deflate stream decoded %d of %d bytes' % (len(out), size))
    return out


def lzma_decode(data, size):
    # CHD stores a bare LZMA1 stream (lc=3, lp=0, pb=2) with no end marker; the
    # .lzma container with a known size decodes exactly that. A dictionary at least
    # as large as the encoder's is always valid; hunks are far below 16 MiB.
    header = bytes([93]) + struct.pack('<I', 1 << 24) + struct.pack('<Q', size)
    try:
        out = lzma.LZMADecompressor(format=lzma.FORMAT_ALONE).decompress(header + data, size)
    except lzma.LZMAError as error:
        raise ChdError('LZMA hunk is damaged: %s' % error) from error
    if len(out) != size:
        raise ChdError('LZMA stream decoded %d of %d bytes' % (len(out), size))
    return out


# CD-ROM ECC (ECMA-130 P and Q Reed-Solomon parity over GF(2^8), x^8+x^4+x^3+x^2+1).
_MUL2 = bytes(((value << 1) ^ (0x11d if value & 0x80 else 0)) & 0xff for value in range(256))
_DIV3 = bytearray(256)
for _value in range(256):
    _DIV3[_value ^ _MUL2[_value]] = _value
_DIV3 = bytes(_DIV3)
_Q_ROWS = [operator.itemgetter(*[((major >> 1) * 86 + (major & 1) + 88 * minor) % 2236 for major in range(52)])
           for minor in range(43)]


def _parity(rows, width):
    a = b = 0
    for row in rows:
        value = int.from_bytes(row, 'big')
        b ^= value
        a = int.from_bytes((a ^ value).to_bytes(width, 'big').translate(_MUL2), 'big')
    first = (int.from_bytes(a.to_bytes(width, 'big').translate(_MUL2), 'big') ^ b).to_bytes(width, 'big').translate(_DIV3)
    return first + (int.from_bytes(first, 'big') ^ b).to_bytes(width, 'big')


def ecc_generate(sector):
    """Return a 2352-byte Mode 1 sector with its P and Q parity regenerated."""
    sector = bytearray(sector)
    region = bytes(sector[12:12 + 2064])
    sector[0x81c:0x81c + 172] = _parity([region[86 * minor:86 * minor + 86] for minor in range(24)], 86)
    region = bytes(sector[12:12 + 2236])
    sector[0x8c8:0x8c8 + 104] = _parity([bytes(row(region)) for row in _Q_ROWS], 52)
    return bytes(sector)


# FLAC frames (cdfl hunks carry bare frames; CHD supplies 44.1 kHz, 2 ch, 16 bit).
_FIXED = ([], [1], [2, -1], [3, -3, 1], [4, -6, 4, -1])


class FlacError(ChdError):
    pass


class _FlacBits:
    def __init__(self, data):
        self.bits = bin(int.from_bytes(b'\x01' + data, 'big'))[3:]
        self.pos = 0

    def read(self, count):
        if count == 0:
            return 0
        end = self.pos + count
        if end > len(self.bits):
            raise FlacError('FLAC frame runs past the hunk')
        value = int(self.bits[self.pos:end], 2)
        self.pos = end
        return value

    def signed(self, count):
        value = self.read(count)
        return value - (1 << count) if count and value >> (count - 1) else value

    def unary(self):
        one = self.bits.find('1', self.pos)
        if one < 0:
            raise FlacError('FLAC unary code runs past the hunk')
        count = one - self.pos
        self.pos = one + 1
        return count

    def align(self):
        self.pos = (self.pos + 7) & ~7


def _flac_residual(bits, blocksize, order):
    method = bits.read(2)
    if method > 1:
        raise FlacError('reserved FLAC residual coding method')
    param_bits, escape = (4, 15) if method == 0 else (5, 31)
    partition_order = bits.read(4)
    count = blocksize >> partition_order
    if count << partition_order != blocksize or count < order:
        raise FlacError('invalid FLAC partition order')
    residual = []
    append = residual.append
    text, find = bits.bits, bits.bits.find
    for partition in range(1 << partition_order):
        samples = count - order if partition == 0 else count
        parameter = bits.read(param_bits)
        if parameter == escape:
            width = bits.read(5)
            if width == 0:
                residual.extend([0] * samples)
            else:
                for _ in range(samples):
                    append(bits.signed(width))
            continue
        pos = bits.pos
        for _ in range(samples):
            one = find('1', pos)
            if one < 0:
                raise FlacError('FLAC residual runs past the hunk')
            if parameter:
                end = one + 1 + parameter
                value = ((one - pos) << parameter) | int(text[one + 1:end], 2)
                pos = end
            else:
                value = one - pos
                pos = one + 1
            append((value >> 1) ^ -(value & 1))
        if pos > len(text):
            raise FlacError('FLAC residual runs past the hunk')
        bits.pos = pos
    return residual


def _predict(warmup, coefficients, shift, residual):
    out = warmup
    order = len(coefficients)
    reverse = coefficients[::-1]
    mul = operator.mul
    append = out.append
    if order == 0:
        out.extend(residual)
        return out
    for index, value in enumerate(residual):
        append((sum(map(mul, reverse, out[index:index + order])) >> shift) + value)
    return out


def _flac_subframe(bits, blocksize, bps):
    if bits.read(1):
        raise FlacError('FLAC subframe padding bit set')
    kind = bits.read(6)
    wasted = bits.unary() + 1 if bits.read(1) else 0
    bps -= wasted
    if bps <= 0:
        raise FlacError('invalid FLAC wasted bits')
    if kind == 0:
        samples = [bits.signed(bps)] * blocksize
    elif kind == 1:
        samples = [bits.signed(bps) for _ in range(blocksize)]
    elif 8 <= kind <= 12:
        order = kind - 8
        warmup = [bits.signed(bps) for _ in range(order)]
        samples = _predict(warmup, _FIXED[order], 0, _flac_residual(bits, blocksize, order))
    elif kind >= 32:
        order = kind - 31
        warmup = [bits.signed(bps) for _ in range(order)]
        precision = bits.read(4) + 1
        if precision == 16:
            raise FlacError('invalid FLAC coefficient precision')
        shift = bits.signed(5)
        if shift < 0:
            raise FlacError('negative FLAC LPC shift')
        coefficients = [bits.signed(precision) for _ in range(order)]
        samples = _predict(warmup, coefficients, shift, _flac_residual(bits, blocksize, order))
    else:
        raise FlacError('reserved FLAC subframe type %d' % kind)
    if wasted:
        samples = [sample << wasted for sample in samples]
    return samples


_BLOCK_SIZES = {1: 192, 2: 576, 3: 1152, 4: 2304, 5: 4608}
_SAMPLE_BITS = {0: 16, 1: 8, 2: 12, 4: 16, 5: 20, 6: 24, 7: 32}


def flac_decode(data, total_samples, channels=2):
    """Decode bare FLAC frames to `total_samples` per channel; return (channel lists, bytes used)."""
    bits = _FlacBits(data)
    output = [[] for _ in range(channels)]
    decoded = 0
    while decoded < total_samples:
        if bits.read(15) != 0x7ffc:
            raise FlacError('missing FLAC frame sync')
        bits.read(1)
        size_code, rate_code = bits.read(4), bits.read(4)
        assignment, size_bits = bits.read(4), bits.read(3)
        if bits.read(1):
            raise FlacError('reserved FLAC header bit set')
        first = bits.read(8)
        extra = 0
        while first & (0x80 >> extra) and extra < 7:
            extra += 1
        if extra == 1 or extra == 7:
            raise FlacError('invalid FLAC frame number')
        for _ in range(max(0, extra - 1)):
            if bits.read(8) >> 6 != 2:
                raise FlacError('invalid FLAC frame number')
        if size_code == 6:
            blocksize = bits.read(8) + 1
        elif size_code == 7:
            blocksize = bits.read(16) + 1
        elif size_code >= 8:
            blocksize = 256 << (size_code - 8)
        elif size_code in _BLOCK_SIZES:
            blocksize = _BLOCK_SIZES[size_code]
        else:
            raise FlacError('reserved FLAC block size')
        if rate_code == 12:
            bits.read(8)
        elif rate_code in (13, 14):
            bits.read(16)
        elif rate_code == 15:
            raise FlacError('invalid FLAC sample rate')
        bits.read(8)  # header CRC-8; the hunk CRC-16 and file SHA-1 cover the data
        if size_bits not in _SAMPLE_BITS:
            raise FlacError('reserved FLAC sample size')
        bps = _SAMPLE_BITS[size_bits]
        if assignment < 8:
            if assignment + 1 != channels:
                raise FlacError('FLAC frame has %d channels, expected %d' % (assignment + 1, channels))
            frame = [_flac_subframe(bits, blocksize, bps) for _ in range(channels)]
        elif assignment <= 10 and channels == 2:
            first_bps = bps + (1 if assignment == 9 else 0)
            second_bps = bps + (1 if assignment in (8, 10) else 0)
            a = _flac_subframe(bits, blocksize, first_bps)
            b = _flac_subframe(bits, blocksize, second_bps)
            if assignment == 8:
                frame = [a, [left - side for left, side in zip(a, b)]]
            elif assignment == 9:
                frame = [[side + right for side, right in zip(a, b)], b]
            else:
                left, right = [], []
                for mid, side in zip(a, b):
                    mid = (mid << 1) | (side & 1)
                    left.append((mid + side) >> 1)
                    right.append((mid - side) >> 1)
                frame = [left, right]
        else:
            raise FlacError('reserved FLAC channel assignment')
        bits.align()
        bits.read(16)  # frame CRC-16
        for channel, samples in zip(output, frame):
            channel.extend(samples)
        decoded += blocksize
    if decoded != total_samples:
        raise FlacError('FLAC frames hold %d samples, expected %d' % (decoded, total_samples))
    return output, bits.pos // 8


def _samples_be(left, right):
    interleaved = array('h', bytes(4 * len(left)))
    try:
        interleaved[0::2] = array('h', left)
        interleaved[1::2] = array('h', right)
    except OverflowError as error:
        raise FlacError('FLAC sample outside 16-bit range') from error
    if sys.byteorder == 'little':
        interleaved.byteswap()
    return interleaved.tobytes()


def _cd_frames(sectors, subcode, frames):
    return b''.join(sectors[CD_SECTOR * index:CD_SECTOR * (index + 1)] +
                    subcode[CD_SUBCODE * index:CD_SUBCODE * (index + 1)] for index in range(frames))


def cd_decompress(codec, data, hunkbytes):
    frames = hunkbytes // CD_FRAME
    if codec == b'cdfl':
        (left, right), used = flac_decode(data, frames * CD_SECTOR // 4)
        sectors = _samples_be(left, right)
        subcode = inflate(data[used:], frames * CD_SUBCODE)
        return _cd_frames(sectors, subcode, frames)
    length_bytes = 2 if hunkbytes < 65536 else 3
    ecc_bytes = (frames + 7) // 8
    header = ecc_bytes + length_bytes
    if len(data) < header:
        raise ChdError('CD hunk is truncated')
    base_length = int.from_bytes(data[ecc_bytes:header], 'big')
    if header + base_length > len(data):
        raise ChdError('CD hunk is truncated')
    base = data[header:header + base_length]
    rest = data[header + base_length:]
    if codec == b'cdlz':
        sectors = lzma_decode(base, frames * CD_SECTOR)
    elif codec == b'cdzl':
        sectors = inflate(base, frames * CD_SECTOR)
    else:
        raise ChdError('unsupported CHD codec %s' % codec.decode('latin1'))
    subcode = inflate(rest, frames * CD_SUBCODE)
    out = bytearray(_cd_frames(sectors, subcode, frames))
    for index in range(frames):
        if data[index // 8] & (1 << (index % 8)):
            start = index * CD_FRAME
            out[start:start + CD_SECTOR] = ecc_generate(SYNC + bytes(out[start + 12:start + CD_SECTOR]))
    return bytes(out)


SUPPORTED_CODECS = {b'cdlz', b'cdzl', b'cdfl'}


# --------------------------------------------------------------------------- container

@dataclass
class ChdTrack:
    number: int
    type: str
    subtype: str
    frames: int
    pad: int
    pregap: int
    pregap_type: str
    pregap_subtype: str
    postgap: int
    chd_frame: int = 0

    @property
    def audio(self):
        return self.type == 'AUDIO'

    @property
    def stored_pregap(self):
        return self.pregap if self.pregap_type.startswith('V') else 0


class ChdFile:
    def __init__(self, path):
        self.path = Path(path)
        self.handle = self.path.open('rb')
        try:
            self._read_header()
            self.metadata = self._read_metadata()
            self.map = self._read_map()
        except Exception:
            self.handle.close()
            raise
        self._last = (None, None)
        # Hunks that later hunks copy (COMPRESSION_SELF), kept decoded once.
        self._targets = {entry[1] for entry in self.map if entry[0] == COMPRESSION_SELF}
        self._kept = {}

    def close(self):
        self.handle.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def _read(self, offset, size):
        self.handle.seek(offset)
        data = self.handle.read(size)
        if len(data) != size:
            raise ChdError('CHD file is truncated at offset %d' % offset)
        return data

    def _read_header(self):
        head = self._read(0, 16)
        if head[:8] != b'MComprHD':
            raise ChdError('not a CHD file: %s' % self.path)
        length, version = struct.unpack('>II', head[8:16])
        if version != 5:
            raise ChdError('CHD version %d is not supported; recompress with a current chdman (v5)' % version)
        if length < 124:
            raise ChdError('invalid CHD v5 header length')
        raw = self._read(0, 124)
        self.compressors = [raw[16 + 4 * i:20 + 4 * i] for i in range(4)]
        self.logicalbytes, self.mapoffset, self.metaoffset = struct.unpack('>QQQ', raw[32:56])
        self.hunkbytes, self.unitbytes = struct.unpack('>II', raw[56:64])
        self.rawsha1, self.sha1, self.parentsha1 = raw[64:84], raw[84:104], raw[104:124]
        if self.hunkbytes == 0 or self.hunkbytes % CD_FRAME or self.unitbytes != CD_FRAME:
            raise ChdError('CHD is not a CD/GD-ROM image (hunk %d, unit %d bytes)' % (self.hunkbytes, self.unitbytes))
        if any(self.parentsha1):
            raise ChdError('CHD needs a parent CHD; recompress it as a standalone image with chdman')
        self.hunkcount = (self.logicalbytes + self.hunkbytes - 1) // self.hunkbytes
        self.compressed = self.compressors[0] != b'\0\0\0\0'

    def unsupported_codecs(self):
        return sorted({codec.decode('latin1') for codec in self.compressors
                       if codec != b'\0\0\0\0' and codec not in SUPPORTED_CODECS})

    def _read_metadata(self):
        entries, offset, seen = [], self.metaoffset, set()
        while offset:
            if offset in seen:
                raise ChdError('CHD metadata chain loops')
            seen.add(offset)
            head = self._read(offset, 16)
            tag, flags_length, following = struct.unpack('>4sIQ', head)
            data = self._read(offset + 16, flags_length & 0xffffff)
            entries.append((tag, data))
            offset = following
        return entries

    def _read_map(self):
        if not self.compressed:
            raw = self._read(self.mapoffset, 4 * self.hunkcount)
            return [('raw', struct.unpack_from('>I', raw, 4 * i)[0] * self.hunkbytes, self.hunkbytes, None)
                    for i in range(self.hunkcount)]
        head = self._read(self.mapoffset, 16)
        mapbytes = struct.unpack('>I', head[0:4])[0]
        offset = int.from_bytes(head[4:10], 'big')
        mapcrc = struct.unpack('>H', head[10:12])[0]
        lengthbits, selfbits, parentbits = head[12], head[13], head[14]
        if max(lengthbits, selfbits, parentbits) > 32:
            raise ChdError('invalid CHD map header')
        bits = BitReader(self._read(self.mapoffset + 16, mapbytes))
        huffman = Huffman(16, 8)
        huffman.import_tree_rle(bits)
        kinds, last, repeat = [], 0, 0
        for _ in range(self.hunkcount):
            if repeat:
                kinds.append(last)
                repeat -= 1
                continue
            value = huffman.decode(bits)
            if value == RLE_SMALL:
                kinds.append(last)
                repeat = 2 + huffman.decode(bits)
            elif value == RLE_LARGE:
                kinds.append(last)
                repeat = 2 + 16 + (huffman.decode(bits) << 4)
                repeat += huffman.decode(bits)
            else:
                kinds.append(value)
                last = value
        entries, raw = [], bytearray()
        last_self = last_parent = 0
        for number, kind in enumerate(kinds):
            location, length, crc = offset, 0, 0
            if kind <= 3:
                length = bits.read(lengthbits)
                crc = bits.read(16)
                offset += length
            elif kind == COMPRESSION_NONE:
                length = self.hunkbytes
                crc = bits.read(16)
                offset += length
            elif kind == COMPRESSION_SELF:
                location = last_self = bits.read(selfbits)
            elif kind == COMPRESSION_PARENT:
                location = last_parent = bits.read(parentbits)
            elif kind in (SELF_0, SELF_1):
                if kind == SELF_1:
                    last_self += 1
                kind, location = COMPRESSION_SELF, last_self
            elif kind == PARENT_SELF:
                kind = COMPRESSION_PARENT
                location = last_parent = number * self.hunkbytes // self.unitbytes
            elif kind in (PARENT_0, PARENT_1):
                if kind == PARENT_1:
                    last_parent += self.hunkbytes // self.unitbytes
                kind, location = COMPRESSION_PARENT, last_parent
            else:
                raise ChdError('invalid CHD map entry type %d' % kind)
            raw += bytes([kind]) + length.to_bytes(3, 'big') + location.to_bytes(6, 'big') + crc.to_bytes(2, 'big')
            entries.append((kind, location, length, crc))
        if bits.overflow:
            raise ChdError('CHD map is truncated')
        if binascii.crc_hqx(bytes(raw), 0xffff) != mapcrc:
            raise ChdError('CHD map CRC mismatch')
        return entries

    def hunk(self, number):
        if self._last[0] == number:
            return self._last[1]
        if number in self._kept:
            return self._kept[number]
        kind, location, length, crc = self.map[number]
        if kind == 'raw':
            data = self._read(location, self.hunkbytes) if location else bytes(self.hunkbytes)
            crc = None
        elif kind <= 3:
            codec = self.compressors[kind]
            if codec not in SUPPORTED_CODECS:
                raise ChdError('CHD hunk uses unsupported codec %s' % codec.decode('latin1'))
            data = cd_decompress(codec, self._read(location, length), self.hunkbytes)
        elif kind == COMPRESSION_NONE:
            data = self._read(location, self.hunkbytes)
        elif kind == COMPRESSION_SELF:
            if location >= number:
                raise ChdError('CHD hunk %d refers forward to hunk %d' % (number, location))
            data = self.hunk(location)
            crc = None
        else:
            raise ChdError('CHD hunk %d needs a parent CHD' % number)
        if crc is not None and binascii.crc_hqx(data, 0xffff) != crc:
            raise ChdError('CHD hunk %d CRC mismatch (damaged file or decoder error)' % number)
        self._last = (number, data)
        if number in self._targets and len(self._kept) < 512:
            self._kept[number] = data
        return data

    def gdrom_tracks(self):
        tags = {tag for tag, _ in self.metadata}
        if GDROM_TAG not in tags:
            if GDROM_OLD_TAG in tags:
                raise ChdError('CHD uses the pre-2013 GD-ROM layout; recompress it from GDI with a current chdman')
            if tags & set(CD_TAGS):
                raise ChdError('CHD holds a CD-ROM, not a Dreamcast GD-ROM')
            raise ChdError('CHD has no GD-ROM track metadata')
        pattern = re.compile(r'TRACK:(\d+) TYPE:(\S+) SUBTYPE:(\S+) FRAMES:(\d+) PAD:(\d+) PREGAP:(\d+) '
                             r'PGTYPE:(\S+) PGSUB:(\S+) POSTGAP:(\d+)')
        tracks = []
        for tag, data in self.metadata:
            if tag != GDROM_TAG:
                continue
            match = pattern.fullmatch(data.rstrip(b'\0').decode('ascii', 'replace').strip())
            if not match:
                raise ChdError('invalid GD-ROM track metadata: %r' % data[:80])
            number, kind, subtype, frames, pad, pregap, pgtype, pgsub, postgap = match.groups()
            tracks.append(ChdTrack(int(number), kind, subtype, int(frames), int(pad), int(pregap),
                                   pgtype, pgsub, int(postgap)))
        tracks.sort(key=lambda track: track.number)
        if [track.number for track in tracks] != list(range(1, len(tracks) + 1)):
            raise ChdError('GD-ROM tracks in the CHD are not numbered 1..%d' % len(tracks))
        frame = 0
        for track in tracks:
            if track.type not in ('AUDIO', 'MODE1_RAW', 'MODE1'):
                raise ChdError('unsupported GD-ROM track %d type %s' % (track.number, track.type))
            if track.stored_pregap > track.frames:
                raise ChdError('GD-ROM track %d pregap exceeds its frames' % track.number)
            track.chd_frame = frame
            frame += track.frames + track.pad
        if frame * CD_FRAME != self.logicalbytes:
            raise ChdError('GD-ROM track table covers %d frames but the CHD holds %d'
                           % (frame, self.logicalbytes // CD_FRAME))
        if len(tracks) < 3 or tracks[2].audio:
            raise ChdError('CHD has no Dreamcast high-density data track 03')
        return tracks


def _bcd(value):
    return (value >> 4) * 10 + (value & 15) if (value >> 4) < 10 and (value & 15) < 10 else -1


def sector_lba(sector):
    minute, second, frame = (_bcd(value) for value in sector[12:15])
    if minute < 0 or second < 0 or frame < 0 or second >= 60 or frame >= 75:
        return None
    return (minute * 60 + second) * 75 + frame - 150


def planned_lbas(tracks):
    """LBA of each track's first stored frame from the GD-ROM table (checked against sector headers later)."""
    lbas, cursor = {}, 0
    for track in tracks:
        if track.number == 3:
            cursor = GD_HIGH_DENSITY_LBA - track.stored_pregap
        else:
            cursor += track.pregap - track.stored_pregap
        lbas[track.number] = cursor
        cursor += track.frames + track.postgap
    return lbas


def convert(path, outdir, progress=None):
    """Decode a GD-ROM CHD into per-track files; return gdi_extract.Track rows for them.

    Data tracks become cooked 2048-byte sectors from INDEX 01; audio tracks become
    little-endian 2352-byte CD-DA sectors including any stored pregap, as in a raw GDI.
    """
    import gdi_extract
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    with ChdFile(path) as chd:
        unsupported = chd.unsupported_codecs()
        if unsupported:
            raise ChdError('CHD uses codec %s, which setup cannot decode; recompress with '
                           '`chdman createcd` default codecs (cdlz,cdzl,cdfl)' % ', '.join(unsupported))
        tracks = chd.gdrom_tracks()
        planned = planned_lbas(tracks)
        frames_per_hunk = chd.hunkbytes // CD_FRAME
        sha1 = hashlib.sha1()
        outputs, derived, warnings = {}, {}, []
        spans = []
        for track in tracks:
            name = outdir / ('track%02d.%s' % (track.number, 'raw' if track.audio else 'iso'))
            outputs[track.number] = name.open('wb')
            spans.append((track.chd_frame, track.chd_frame + track.frames, track))
        try:
            span_index = 0
            remaining = chd.logicalbytes
            for number in range(chd.hunkcount):
                data = chd.hunk(number)
                used = min(remaining, chd.hunkbytes)
                sha1.update(data[:used])
                remaining -= used
                for local in range(frames_per_hunk):
                    frame = number * frames_per_hunk + local
                    while span_index < len(spans) and frame >= spans[span_index][1] + spans[span_index][2].pad:
                        span_index += 1
                    if span_index >= len(spans):
                        break
                    start, end, track = spans[span_index]
                    if not start <= frame < end:
                        continue  # chdman padding frames between tracks
                    sector = data[local * CD_FRAME:local * CD_FRAME + CD_SECTOR]
                    relative = frame - start
                    if track.audio:
                        swapped = array('h', sector)
                        swapped.byteswap()
                        outputs[track.number].write(swapped.tobytes())
                        continue
                    if relative < track.stored_pregap:
                        continue
                    if track.type == 'MODE1':
                        outputs[track.number].write(sector[:2048])
                        continue
                    address = sector_lba(sector)
                    if track.number not in derived:
                        if sector[:12] != SYNC or sector[15] != 1 or address is None:
                            raise ChdError('GD-ROM track %d does not start with a Mode 1 sector' % track.number)
                        derived[track.number] = address - relative
                        if derived[track.number] != planned[track.number]:
                            warnings.append('track %d sector headers place it at LBA %d; the track table implies %d'
                                            % (track.number, derived[track.number], planned[track.number]))
                    elif address != derived[track.number] + relative:
                        raise ChdError('GD-ROM track %d sector %d has address %s, expected %d'
                                       % (track.number, relative, address, derived[track.number] + relative))
                    outputs[track.number].write(sector[16:2064])
                if progress and number % 4096 == 0:
                    progress('   CHD %d%%' % (100 * number // max(1, chd.hunkcount)))
        finally:
            for handle in outputs.values():
                handle.close()
        if sha1.digest() != chd.rawsha1:
            raise ChdError('CHD raw data SHA-1 mismatch: the file is damaged or uses an unsupported layout')
        if derived.get(3, GD_HIGH_DENSITY_LBA) != GD_HIGH_DENSITY_LBA:
            raise ChdError('GD-ROM track 03 starts at LBA %d, not 45000' % derived[3])
        rows = []
        for track in tracks:
            if track.audio:
                lba, sectors, size = planned[track.number], track.frames, 2352
            else:
                lba = derived.get(track.number, planned[track.number] + track.stored_pregap)
                sectors, size = track.frames - track.stored_pregap, 2048
            rows.append(gdi_extract.Track(track.number, lba, 0 if track.audio else 4, size,
                                          (outdir / ('track%02d.%s' % (track.number, 'raw' if track.audio else 'iso'))).resolve(),
                                          0, sectors, 0 if not track.audio else None))
        for message in warnings:
            if progress:
                progress('   CHD note: ' + message)
        return rows


def describe(path):
    """Header and GD-ROM track table without decoding hunks (for the setup manifest)."""
    with ChdFile(path) as chd:
        info = {'version': 5, 'hunk_bytes': chd.hunkbytes, 'logical_bytes': chd.logicalbytes,
                'codecs': [codec.decode('latin1') for codec in chd.compressors if codec != b'\0\0\0\0'],
                'raw_sha1': chd.rawsha1.hex(), 'sha1': chd.sha1.hex()}
        unsupported = chd.unsupported_codecs()
        if unsupported:
            info['unsupported_codecs'] = unsupported
        tracks = chd.gdrom_tracks()
        lbas = planned_lbas(tracks)
        info['tracks'] = [{'number': track.number, 'type': track.type, 'frames': track.frames,
                           'pad': track.pad, 'pregap': track.pregap, 'pregap_type': track.pregap_type,
                           'postgap': track.postgap, 'lba': lbas[track.number]} for track in tracks]
        return info


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) not in (1, 2):
        raise SystemExit(__doc__)
    if len(argv) == 1:
        import json
        print(json.dumps(describe(argv[0]), indent=1))
        return
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    for row in convert(argv[0], argv[1], print):
        print('%2d %6d %d %4d %s' % (row.number, row.lba, row.kind, row.sector_size, row.path.name))


if __name__ == '__main__':
    main()
