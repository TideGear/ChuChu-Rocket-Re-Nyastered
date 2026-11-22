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
