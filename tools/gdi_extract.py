"""Extract the ISO9660 high-density area from Dreamcast GDI or separate-file BIN/CUE.

A GDI track row is: number, start LBA, type, sector size, filename, file offset.
Usage: gdi_extract.py <disc.gdi | disc.cue | directory with Track NN.bin> <outdir> [legacy gap sectors]
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
    sector_count: int = None
    data_offset: int = None

    @property
    def sectors(self):
        if self.sector_count is not None:
            return self.sector_count
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
                elif track.data_offset is not None:
                    data = raw[track.data_offset:track.data_offset + 2048]
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


def _cue_time(value):
    match = re.fullmatch(r'(\d+):(\d{2}):(\d{2})', value)
    if not match:
        raise ValueError('invalid CUE index time: %s' % value)
    minutes, seconds, frames = map(int, match.groups())
    if seconds >= 60 or frames >= 75:
        raise ValueError('invalid CUE index time: %s' % value)
    return (minutes * 60 + seconds) * 75 + frames


def parse_cue(path):
    """Parse a separate-file raw BIN/CUE set using its declared track modes."""
    path = Path(path)
    lines = path.read_text(encoding='utf-8-sig').splitlines()
    file_re = re.compile(r'FILE\s+(?:"([^"]+)"|(\S+))\s+(BINARY|MOTOROLA)\s*$', re.I)
    track_re = re.compile(r'TRACK\s+(\d+)\s+([A-Z0-9/]+)\s*$', re.I)
    index_re = re.compile(r'INDEX\s+(\d+)\s+(\d+:\d{2}:\d{2})\s*$', re.I)
    modes = {'AUDIO': (0, 2352, None), 'MODE1/2048': (4, 2048, 0),
             'MODE1/2352': (4, 2352, 16)}
    entries = []
    current_file = None
    current_track = None
    ignored = ('REM ', 'TITLE ', 'PERFORMER ', 'SONGWRITER ', 'FLAGS ', 'ISRC ',
               'CATALOG ', 'CDTEXTFILE ')
    for raw in lines:
        line = raw.strip()
        if not line or line.upper().startswith(ignored):
            continue
        match = file_re.fullmatch(line)
        if match:
            name = match.group(1) or match.group(2)
            name = name.replace('\\', os.sep).replace('/', os.sep)
            relative_path = Path(name)
            if relative_path.is_absolute() or '..' in relative_path.parts:
                raise ValueError('CUE track path must stay beside the descriptor: %s' % name)
            track_path = (path.parent.resolve() / relative_path).resolve()
            if not track_path.is_relative_to(path.parent.resolve()):
                raise ValueError('CUE track path escapes its descriptor folder: %s' % name)
            if not track_path.is_file():
                raise FileNotFoundError('CUE track file is missing: %s' % track_path)
            current_file = (track_path, match.group(3).upper())
            current_track = None
            continue
        match = track_re.fullmatch(line)
        if match:
            if current_file is None:
                raise ValueError('CUE TRACK appears before FILE')
            number, mode = int(match.group(1)), match.group(2).upper()
            if mode not in modes:
                raise ValueError('unsupported CUE track mode: %s' % mode)
            current_track = {'number': number, 'mode': mode, 'file': current_file[0],
                             'file_type': current_file[1], 'indexes': {}}
            entries.append(current_track)
            continue
        match = index_re.fullmatch(line)
        if match:
            if current_track is None:
                raise ValueError('CUE INDEX appears before TRACK')
            index = int(match.group(1))
            if index in current_track['indexes']:
                raise ValueError('duplicate CUE INDEX %02d on track %02d' % (index, current_track['number']))
            if index == 0 and 1 in current_track['indexes']:
                raise ValueError('CUE INDEX 00 must precede INDEX 01 on track %02d' % current_track['number'])
            current_track['indexes'][index] = _cue_time(match.group(2))
            continue
        if re.match(r'(?:PREGAP|POSTGAP)\b', line, re.I):
            raise ValueError('external CUE pregap/postgap directives are unsupported; use a raw GDI or separate-file CUE with indexed pregaps')
        if re.match(r'^(?:FILE|TRACK|INDEX)\b', line, re.I):
            raise ValueError('invalid CUE directive: %s' % line)
        raise ValueError('unsupported CUE directive: %s' % line)

    if not entries:
        raise ValueError('CUE descriptor contains no tracks: %s' % path)
    numbers = [entry['number'] for entry in entries]
    if numbers != list(range(1, len(numbers) + 1)):
        raise ValueError('CUE tracks must be numbered consecutively from 1: %s' % path)
    if any(entry['file_type'] != 'BINARY' for entry in entries):
        raise ValueError('CUE tracks must use raw BINARY files: %s' % path)

    tracks = []
    for index, entry in enumerate(entries):
        indexes = entry['indexes']
        if 1 not in indexes or set(indexes) - {0, 1}:
            raise ValueError('CUE track %02d needs INDEX 01 and optional INDEX 00' % entry['number'])
        if 0 in indexes and indexes[0] > indexes[1]:
            raise ValueError('CUE INDEX 00 must precede INDEX 01 on track %02d' % entry['number'])
        kind, sector_size, data_offset = modes[entry['mode']]
        entry['sector_size'] = sector_size
        entry['data_offset'] = data_offset
        entry['start'] = indexes.get(0, indexes[1])
        entry['program_start'] = indexes[1]
        previous = next((prior for prior in reversed(entries[:index])
                         if prior['file'] == entry['file']), None)
        if previous:
            if sector_size != previous['sector_size']:
                raise ValueError('CUE tracks sharing a raw file must use the same sector size')
            if entry['start'] < previous['start']:
                raise ValueError('CUE indexes must advance within a shared track file')
        file_sectors = entry['file'].stat().st_size // sector_size
        if entry['file'].stat().st_size % sector_size:
            raise ValueError('CUE file size is not a whole number of sectors: %s' % entry['file'])
        if entry['start'] >= file_sectors or any(position >= file_sectors for position in indexes.values()):
            raise ValueError('CUE index lies outside track %02d file: %s' % (entry['number'], entry['file']))

    tracks = []
    for index, entry in enumerate(entries):
        file_sectors = entry['file'].stat().st_size // entry['sector_size']
        end = file_sectors
        next_track = next((later for later in entries[index + 1:]
                           if later['file'] == entry['file']), None)
        if next_track:
            end = next_track['start']
        if end <= entry['start']:
            raise ValueError('CUE track %02d has no sectors before the next track' % entry['number'])
        if any(position >= end for position in entry['indexes'].values()):
            raise ValueError('CUE index lies outside track %02d boundary' % entry['number'])
        if entry['program_start'] >= end:
            raise ValueError('CUE INDEX 01 lies outside track %02d boundary' % entry['number'])
        kind, sector_size, data_offset = modes[entry['mode']]
        tracks.append(Track(entry['number'], 0, kind, sector_size, entry['file'], entry['start'],
                            end - entry['start'], data_offset))
    if not any(track.number == 3 and track.kind == 4 for track in tracks):
        raise ValueError('CUE has no Dreamcast high-density data track 03')
    lba = 45000
    if tracks[2].number != 3 or tracks[2].kind != 4 or tracks[2].sector_size not in (2048, 2336, 2352):
        raise ValueError('CUE track 03 must be the Dreamcast high-density data track: %s' % path)
    for index, track in enumerate(tracks):
        if track.number < 3:
            continue
        if track.number != index + 1:
            raise ValueError('CUE high-density tracks must be consecutive from track 03')
        tracks[index] = Track(track.number, lba, track.kind, track.sector_size, track.path,
                              track.offset, track.sectors, track.data_offset)
        lba += track.sectors
    return tracks


def extract(source, outdir, gap=0):
    source = Path(source)
    if source.is_file() and source.suffix.lower() in ('.gdi', '.cue'):
        tracks = parse_gdi(source) if source.suffix.lower() == '.gdi' else parse_cue(source)
        extract_records(tracks, outdir)
        return tracks
    descriptors = sorted(source.glob('*.gdi'))
    if descriptors:
        if len(descriptors) != 1:
            raise ValueError('put each Dreamcast GDI in its own folder')
        tracks = parse_gdi(descriptors[0])
        extract_records(tracks, outdir)
        return tracks
    cues = sorted(source.glob('*.cue'))
    if cues:
        if len(cues) != 1:
            raise ValueError('put each Dreamcast CUE in its own folder')
        tracks = parse_cue(cues[0])
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
