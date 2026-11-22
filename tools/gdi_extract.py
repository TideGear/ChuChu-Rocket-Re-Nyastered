"""Extract the ISO9660 high-density area from a Dreamcast GDI or numbered BIN set.

A GDI track row is: number, start LBA, type, sector size, filename, file offset.
Usage: gdi_extract.py <disc.gdi | directory with Track NN.bin> <outdir> [legacy gap sectors]
"""
import os
import re
import struct
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Track:
    number: int
    lba: int
    kind: int
    sector_size: int
    path: Path
    offset: int

    @property
    def sectors(self):
        size = self.path.stat().st_size - self.offset * self.sector_size
        if size < 0 or size % self.sector_size:
            raise ValueError('invalid GDI track size or offset: %s' % self.path)
        return size // self.sector_size


def parse_gdi(path):
    """Parse a GDI and resolve track paths relative to its descriptor."""
    path = Path(path)
    lines = path.read_text(encoding='utf-8-sig').splitlines()
    rows = [line.strip() for line in lines if line.strip() and not line.lstrip().startswith('#')]
    if not rows:
        raise ValueError('empty GDI descriptor: %s' % path)
    try:
        expected = int(rows[0])
    except ValueError as error:
        raise ValueError('invalid GDI track count: %s' % path) from error
    tracks = []
    for row in rows[1:]:
        match = re.fullmatch(r'\s*(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(?:"([^"]+)"|(\S+))\s+(\d+)\s*', row)
        if not match:
            raise ValueError('invalid GDI track row: %s' % row)
        number, lba, kind, sector_size, quoted_name, bare_name, offset = match.groups()
        filename = quoted_name or bare_name
        filename = filename.replace('\\', os.sep).replace('/', os.sep)
        relative_path = Path(filename)
        if relative_path.is_absolute() or '..' in relative_path.parts:
            raise ValueError('GDI track path must stay beside the descriptor: %s' % filename)
        track_path = (path.parent.resolve() / relative_path).resolve()
        if not track_path.is_relative_to(path.parent.resolve()):
            raise ValueError('GDI track path escapes its descriptor folder: %s' % filename)
        if not track_path.is_file():
            raise FileNotFoundError('GDI track %s is missing: %s' % (number, track_path))
        track = Track(int(number), int(lba), int(kind), int(sector_size), track_path, int(offset))
        valid_sector_size = (track.sector_size in (2048, 2336, 2352, 2448) if track.kind == 4
                             else track.sector_size in (2352, 2448))
        if (track.number <= 0 or track.lba < 0 or track.kind not in (0, 4) or
                not valid_sector_size or track.offset < 0):
            raise ValueError('unsupported GDI track parameters: %s' % row)
        if track.sectors <= 0:
            raise ValueError('empty GDI track: %s' % track_path)
        tracks.append(track)
    tracks.sort(key=lambda track: (track.lba, track.number))
    if len(tracks) != expected:
        raise ValueError('GDI declares %d tracks but contains %d rows: %s' % (expected, len(tracks), path))
    if [track.number for track in tracks] != list(range(1, expected + 1)):
        raise ValueError('GDI tracks must be numbered consecutively from 1: %s' % path)
    if len({track.lba for track in tracks}) != len(tracks):
        raise ValueError('duplicate GDI track LBA: %s' % path)
    data_tracks = [track for track in tracks if track.kind == 4]
    for previous, current in zip(data_tracks, data_tracks[1:]):
        if previous.lba + previous.sectors > current.lba:
            raise ValueError('overlapping GDI data tracks %d and %d: %s' % (previous.number, current.number, path))
    return tracks


class DiscReader:
    def __init__(self, tracks):
        self.tracks = [(track.lba, track.lba + track.sectors, track) for track in tracks if track.kind == 4]
        self.handles = {}

    def close(self):
        for handle in self.handles.values():
            handle.close()
        self.handles.clear()

    def sector(self, lba):
        for start, end, track in self.tracks:
            if start <= lba < end:
                relative = lba - start
                handle = self.handles.get(track.path)
                if handle is None:
                    handle = self.handles[track.path] = track.path.open('rb')
                handle.seek((track.offset + relative) * track.sector_size)
                raw = handle.read(track.sector_size)
                if track.sector_size == 2048:
                    data = raw
                elif track.sector_size == 2336:
                    data = raw[8:2056]
                else:
                    data = raw[16:2064]
                if len(data) != 2048:
                    raise IOError('short read at LBA %d (%s)' % (lba, track.path))
                return data
        raise IOError('LBA %d is outside all data tracks' % lba)

    def read_range(self, lba, size):
        return b''.join(self.sector(lba + i) for i in range((size + 2047) // 2048))[:size]


def extract_records(tracks, outdir):
    reader = DiscReader(tracks)
    try:
        pvd = reader.sector(45016)  # Dreamcast high-density ISO starts at LBA 45000.
        if pvd[1:6] != b'CD001' or pvd[0] != 1:
            raise ValueError('no ISO9660 primary volume descriptor at high-density LBA 45016')
        root = pvd[156:190]
        root_lba = struct.unpack_from('<I', root, 2)[0]
        root_size = struct.unpack_from('<I', root, 10)[0]
        os.makedirs(outdir, exist_ok=True)

        def walk(lba, size, relative):
            data = reader.read_range(lba, size)
            pos = 0
            while pos < len(data):
                length = data[pos]
                if length == 0:
                    pos = (pos // 2048 + 1) * 2048
                    continue
                if length < 34 or pos + length > len(data):
                    raise ValueError('malformed ISO9660 directory record at LBA %d' % lba)
                record = data[pos:pos + length]
                pos += length
                extent = struct.unpack_from('<I', record, 2)[0]
                file_size = struct.unpack_from('<I', record, 10)[0]
                flags, name_len = record[25], record[32]
                name = record[33:33 + name_len].decode('latin1').split(';', 1)[0]
                if name in ('\x00', '\x01'):
                    continue
                if name in ('', '.', '..') or '/' in name or '\\' in name:
                    raise ValueError('unsafe ISO9660 path component %r' % name)
                child = os.path.join(relative, name) if relative else name
                destination = Path(outdir, child)
                if flags & 2:
                    destination.mkdir(parents=True, exist_ok=True)
                    walk(extent, file_size, child)
                else:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    with destination.open('wb') as output:
                        remaining, sector = file_size, extent
                        while remaining:
                            chunk = reader.sector(sector)
                            take = min(2048, remaining)
                            output.write(chunk[:take])
                            remaining -= take
                            sector += 1
                    print('%10d %s' % (file_size, child), flush=True)

        walk(root_lba, root_size, '')
    finally:
        reader.close()


def extract(source, outdir, gap=0):
    source = Path(source)
    if source.is_file() and source.suffix.lower() == '.gdi':
        tracks = parse_gdi(source)
        extract_records(tracks, outdir)
        return tracks
    descriptors = sorted(source.glob('*.gdi'))
    if descriptors:
        if len(descriptors) != 1:
            raise ValueError('put each Dreamcast GDI in its own folder')
        tracks = parse_gdi(descriptors[0])
        extract_records(tracks, outdir)
        return tracks

    tracks = {}
    for name in sorted(os.listdir(source)):
        match = re.search(r'track\s*(\d+)\)?\.bin$', name, re.I)
        if match and int(match[1]) >= 3:
            number = int(match[1])
            if number in tracks:
                raise ValueError('more than one file for track %d; put each dump in its own folder' % number)
            tracks[number] = source / name
    lba, legacy = 45000, []
    for number, path in sorted(tracks.items()):
        if path.stat().st_size % 2352:
            raise ValueError('track size is not a multiple of 2352 bytes: %s' % path)
        # The old numbered-BIN convention reserves tracks 03 and 19 for data;
        # intervening files are raw CD-DA tracks used for Dreamcast music.
        track = Track(number, lba, 4 if number in (3, 19) else 0, 2352, path.resolve(), 0)
        legacy.append(track)
        lba += track.sectors + gap
    extract_records(legacy, outdir)
    return legacy


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) not in (2, 3):
        raise SystemExit(__doc__)
    extract(argv[0], argv[1], int(argv[2]) if len(argv) == 3 else 0)


if __name__ == '__main__':
    main()
