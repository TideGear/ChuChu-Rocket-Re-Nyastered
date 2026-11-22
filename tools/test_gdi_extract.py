"""Focused regression tests for Dreamcast GDI track discovery and ISO extraction."""
import pathlib
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import gdi_extract


def both16(value):
    return struct.pack('<H', value) + struct.pack('>H', value)


def both32(value):
    return struct.pack('<I', value) + struct.pack('>I', value)


def directory_record(lba, size, name, flags=0):
    name = bytes([name]) if isinstance(name, int) else name.encode('ascii')
    length = 33 + len(name) + (1 if len(name) % 2 == 0 else 0)
    return (bytes([length, 0]) + both32(lba) + both32(size) +
            bytes([126, 6, 28, 0, 0, 0, 0, flags, 0, 0]) +
            both16(1) + bytes([len(name)]) + name)


class GdiExtractTest(unittest.TestCase):
    def test_extracts_split_high_density_iso_and_respects_file_offset(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            tracks_dir = root / 'tracks'
            tracks_dir.mkdir()
            output = root / 'out'

            boot = bytearray(17 * 2048)
            pvd = memoryview(boot)[16 * 2048:]
            pvd[0], pvd[1:6], pvd[6] = 1, b'CD001', 1
            pvd[80:88] = both32(45019)
            pvd[128:132] = both16(2048)
            pvd[156:190] = directory_record(45017, 2048, 0, 2)
            (tracks_dir / 'boot data.bin').write_bytes(boot)

            directory = bytearray(2048)
            records = [directory_record(45017, 2048, 0, 2),
                       directory_record(45017, 2048, 1, 2),
                       directory_record(45018, 6, 'HELLO.TXT;1')]
            directory[:sum(map(len, records))] = b''.join(records)
            (tracks_dir / 'directory.bin').write_bytes(directory)
            (tracks_dir / 'file.bin').write_bytes(b'GDI OK' + bytes(2042))

            # GDI offsets are in sectors; skip a raw audio pregap sector.
            (root / 'audio.raw').write_bytes(bytes(2352) + bytes([0x35]) * 2352)
            descriptor = root / 'disc.gdi'
            descriptor.write_text(
                '5\n'
                '1 0 4 2048 "tracks/boot data.bin" 0\n'
                '2 450 0 2352 audio.raw 1\n'
                '3 45000 4 2048 "tracks/boot data.bin" 0\n'
                '4 45017 4 2048 tracks/directory.bin 0\n'
                '5 45018 4 2048 tracks/file.bin 0\n', encoding='utf-8')

            tracks = gdi_extract.extract(descriptor, output)
            self.assertEqual((output / 'HELLO.TXT').read_bytes(), b'GDI OK')
            self.assertEqual(tracks[1].offset, 1)
            self.assertEqual(tracks[1].sectors, 1)
            self.assertEqual([track.lba for track in tracks if track.kind == 4][-2:],
                             [45017, 45018])

    def test_cue_uses_referenced_filenames_modes_and_indexes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            (root / 'track one.bin').write_bytes(bytes(2352))
            (root / 'track two.bin').write_bytes(bytes(2352))
            boot = bytearray(19 * 2048)
            pvd = memoryview(boot)[16 * 2048:17 * 2048]
            pvd[0], pvd[1:6], pvd[6] = 1, b'CD001', 1
            pvd[80:88] = both32(45019)
            pvd[128:132] = both16(2048)
            pvd[156:190] = directory_record(45017, 2048, 0, 2)
            directory = bytearray(2048)
            records = [directory_record(45017, 2048, 0, 2),
                       directory_record(45017, 2048, 1, 2),
                       directory_record(45018, 6, 'CUE OK;1')]
            directory[:sum(map(len, records))] = b''.join(records)
            boot[17 * 2048:18 * 2048] = directory
            boot[18 * 2048:18 * 2048 + 6] = b'CUE OK'
            (root / 'opaque data.bin').write_bytes(boot)
            (root / 'middle audio.bin').write_bytes(bytes(3 * 2352))
            (root / 'last data.bin').write_bytes(bytes(2048))
            cue = root / 'disc.cue'
            cue.write_text(
                'FILE "track one.bin" BINARY\n TRACK 01 MODE1/2352\n INDEX 01 00:00:00\n'
                'FILE "track two.bin" BINARY\n TRACK 02 AUDIO\n INDEX 01 00:00:00\n'
                'FILE "opaque data.bin" BINARY\n TRACK 03 MODE1/2048\n INDEX 01 00:00:00\n'
                'FILE "middle audio.bin" BINARY\n TRACK 04 AUDIO\n INDEX 00 00:00:00\n INDEX 01 00:00:02\n'
                'FILE "last data.bin" BINARY\n TRACK 05 MODE1/2048\n INDEX 01 00:00:00\n',
                encoding='utf-8')
            output = root / 'out'
            tracks = gdi_extract.extract(cue, output)
            self.assertEqual((output / 'CUE OK').read_bytes(), b'CUE OK')
            self.assertEqual([(t.number, t.kind, t.lba) for t in tracks],
                             [(1, 4, 0), (2, 0, 0), (3, 4, 45000),
                              (4, 0, 45019), (5, 4, 45022)])
            self.assertEqual((tracks[3].offset, tracks[3].sectors), (0, 3))

    def test_cue_auto_discovery_finds_nonstandard_referenced_names(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            (root / 'payload.bin').write_bytes(bytes(2048))
            cue = root / 'disc.cue'
            cue.write_text('FILE payload.bin BINARY\n TRACK 01 MODE1/2048\n INDEX 01 00:00:00\n',
                            encoding='utf-8')
            import extract_all
            found = list(extract_all.discover(root, root / 'work'))
            self.assertEqual([(kind, pathlib.Path(path).name) for kind, path, _ in found],
                             [('dreamcast', 'disc.cue')])
            archive_dir = root / 'archive-input'
            archive_dir.mkdir()
            archive = archive_dir / 'disc.zip'
            with __import__('zipfile').ZipFile(archive, 'w') as zipped:
                zipped.write(cue, cue.name)
                zipped.write(root / 'payload.bin', 'payload.bin')
            found = list(extract_all.discover(archive_dir, root / 'work'))
            self.assertEqual([(kind, pathlib.Path(path).suffix.lower()) for kind, path, _ in found],
                             [('dreamcast', '.cue')])
            (root / 'disc.gdi').write_text('0\\n', encoding='utf-8')
            selected = list(extract_all.discover(cue, root / 'work'))
            self.assertEqual([(kind, pathlib.Path(path).name) for kind, path, _ in selected],
                             [('dreamcast', 'disc.cue')])
            ambiguous = list(extract_all.discover(root, root / 'outside-work'))
            self.assertIn(('error', pathlib.Path(root / 'disc.gdi')), [(kind, pathlib.Path(path))
                                                                        for kind, path, _ in ambiguous])

    def test_selected_descriptor_searches_for_optional_bios_beside_it(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            image = root / 'disc'
            image.mkdir()
            cue = image / 'game.cue'
            cue.write_text('FILE track.bin BINARY\n TRACK 01 AUDIO\n INDEX 01 00:00:00\n',
                            encoding='utf-8')
            (image / 'track.bin').write_bytes(bytes(2352))
            (image / 'dc_boot.bin').write_bytes(bytes(2 * 1024 * 1024))
            outside = root / 'unrelated.bin'
            outside.write_bytes(bytes(32))
            import extract_all
            selected_candidates = extract_all.bios_candidates(cue)
            self.assertIn(image / 'dc_boot.bin', selected_candidates)
            self.assertIn(image / 'track.bin', selected_candidates)
            self.assertNotIn(outside, selected_candidates)
            gdi = image / 'game.gdi'
            gdi.write_text('1\n1 0 4 2048 track.bin 0\n', encoding='utf-8')
            self.assertIn(image / 'dc_boot.bin', extract_all.bios_candidates(gdi))
            folder_candidates = extract_all.bios_candidates(image)
            self.assertIn(image / 'dc_boot.bin', folder_candidates)

    def test_cue_supports_several_tracks_in_one_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            (root / 'shared.bin').write_bytes(bytes(4 * 2352))
            cue = root / 'shared.cue'
            cue.write_text(
                'FILE shared.bin BINARY\n TRACK 01 MODE1/2352\n INDEX 01 00:00:00\n'
                ' TRACK 02 MODE1/2352\n INDEX 01 00:00:01\n'
                ' TRACK 03 MODE1/2352\n INDEX 01 00:00:02\n'
                ' TRACK 04 MODE1/2352\n INDEX 01 00:00:03\n', encoding='utf-8')
            tracks = gdi_extract.parse_cue(cue)
            self.assertEqual([(t.number, t.lba, t.offset, t.sectors) for t in tracks],
                             [(1, 0, 0, 1), (2, 0, 1, 1),
                              (3, 45000, 2, 1), (4, 45001, 3, 1)])

    def test_rejects_cue_paths_and_unsupported_layouts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            cue = root / 'disc.cue'
            cue.write_text('FILE ../outside.bin BINARY\n TRACK 01 MODE1/2352\n INDEX 01 00:00:00\n',
                            encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'must stay beside'):
                gdi_extract.parse_cue(cue)
            (root / 'disc.bin').write_bytes(bytes(2352))
            cue.write_text('FILE disc.bin BINARY\n TRACK 01 MODE1/2352\n INDEX 01 00:00:00\n'
                           'PREGAP 00:02:00\n', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'pregap/postgap'):
                gdi_extract.parse_cue(cue)
            cue.write_text('FILE disc.bin BINARY\n TRACK 01 MODE2/2352\n INDEX 01 00:00:00\n',
                           encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'unsupported CUE track mode'):
                gdi_extract.parse_cue(cue)

    def test_rejects_missing_or_malformed_tracks(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            descriptor = root / 'disc.gdi'
            descriptor.write_text('1\n1 0 4 2048 missing.bin 0\n', encoding='utf-8')
            with self.assertRaises(FileNotFoundError):
                gdi_extract.parse_gdi(descriptor)
            descriptor.write_text('1\nnot a GDI row\n', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'invalid GDI track row'):
                gdi_extract.parse_gdi(descriptor)

    def test_rejects_escaping_paths_and_nonconsecutive_numbers(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            outside = root.parent / (root.name + '-outside.bin')
            outside.write_bytes(bytes(2048))
            descriptor = root / 'disc.gdi'
            try:
                descriptor.write_text('1\n1 45000 4 2048 ../' + outside.name + ' 0\n', encoding='utf-8')
                with self.assertRaisesRegex(ValueError, 'must stay beside'):
                    gdi_extract.parse_gdi(descriptor)
            finally:
                outside.unlink(missing_ok=True)

            (root / 'a.bin').write_bytes(bytes(2048))
            (root / 'b.bin').write_bytes(bytes(2048))
            descriptor.write_text('2\n1 45000 4 2048 a.bin 0\n3 45001 4 2048 b.bin 0\n',
                                  encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'numbered consecutively'):
                gdi_extract.parse_gdi(descriptor)

    def test_rejects_overlapping_data_tracks(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            (root / 'a.bin').write_bytes(bytes(2 * 2048))
            (root / 'b.bin').write_bytes(bytes(2048))
            descriptor = root / 'disc.gdi'
            descriptor.write_text('2\n1 45000 4 2048 a.bin 0\n2 45001 4 2048 b.bin 0\n',
                                  encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'overlapping GDI data tracks'):
                gdi_extract.parse_gdi(descriptor)


if __name__ == '__main__':
    unittest.main()
