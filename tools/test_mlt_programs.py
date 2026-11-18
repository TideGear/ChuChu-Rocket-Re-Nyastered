"""Program-bank pointer and split layout checks using synthetic data."""
import struct
import unittest

from mlt_programs import programs, matching_splits


def fixture():
    data = bytearray(384)
    data[:4] = b'SMPB'
    struct.pack_into('<2I', data, 4, 2, len(data))
    struct.pack_into('<4I', data, 16, 48, 1, 160, 1)
    struct.pack_into('<I', data, 48, 52)
    struct.pack_into('<4I', data, 52, 68, 0, 0, 0)
    struct.pack_into('<2I', data, 68, 1, 84)
    struct.pack_into('<2B3H', data, 84, 0, 0, 300, 0, 20)
    data[84 + 36:84 + 40] = bytes((0, 127, 84, 255))
    data[84 + 42:84 + 45] = bytes((0, 1, 127))
    return data


class ProgramTests(unittest.TestCase):
    def test_split_and_addresses(self):
        split = programs(fixture(), 0x1000, 0x20000)['programs'][0]['layers'][0]['splits'][0]
        self.assertEqual(split['sample_file_offset'], 0x112c)
        self.assertEqual(split['sample_ram_address'], 0x2012c)
        self.assertEqual((split['format'], split['sample_bytes']), ('pcm16', 40))
        self.assertEqual((split['base_note'], split['fine_tune']), (84, -1))

    def test_adpcm_odd_length(self):
        data = fixture()
        data[85] = 3
        struct.pack_into('<H', data, 90, 21)
        split = programs(data)['programs'][0]['layers'][0]['splits'][0]
        self.assertEqual((split['format'], split['sample_bytes'], split['loop']), ('adpcm', 11, True))

    def test_outside_references(self):
        for offset in (48, 52, 72):
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                data = fixture()
                struct.pack_into('<I', data, offset, 0xffff)
                programs(data)

    def test_outside_sample(self):
        data = fixture()
        struct.pack_into('<H', data, 86, 380)
        with self.assertRaises(ValueError):
            programs(data)

    def test_candidates_disabled_layer_and_note_off(self):
        data = fixture()
        program = programs(data)['programs'][0]
        self.assertEqual(len(matching_splits(program, 84, 64)[0][1]), 1)
        self.assertEqual(matching_splits(program, 84, 0), [])
        struct.pack_into('<I', data, 68, 129)
        program = programs(data)['programs'][0]
        self.assertTrue(program['layers'][0]['disabled'])
        self.assertEqual(matching_splits(program, 84, 64), [])


if __name__ == '__main__':
    unittest.main()
