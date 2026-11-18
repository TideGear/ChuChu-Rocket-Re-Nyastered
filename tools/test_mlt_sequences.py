"""Bounds and compressed-event regression checks; no copyrighted bank fixtures."""
import struct
import unittest

from mlt_sequences import events, inventory


HEADER = b'SMSD' + struct.pack('<2I', 136, 400)


class SequenceTests(unittest.TestCase):
    def test_note_gate_and_post_event_step(self):
        rows = events(HEADER + bytes.fromhex('c1 1b 01 31 48 5a 08 e8 08 f1 83'))['events']
        self.assertEqual(rows[0]['value'], 27)
        self.assertEqual(rows[1]['tick'], 1)
        self.assertEqual((rows[1]['gate'], rows[1]['step']), (2280, 2289))
        self.assertEqual(rows[-1]['tick'], 2290)

    def test_reference_expansion(self):
        rows = events(HEADER + bytes.fromhex('c1 1b 01 81 00 0c 01 83'))['events']
        self.assertEqual([row['tick'] for row in rows], [0, 1, 2])
        self.assertEqual(rows[0]['offset'], rows[1]['offset'])

    def test_extensions(self):
        row = events(HEADER + bytes.fromhex('88 8c 01 3c 64 02 03 83'))['events'][0]
        self.assertEqual((row['gate'], row['step']), (514, 259))

    def test_bad_events(self):
        for payload in ('81 00 0c 01', '20 40', 'ff', '81 ff ff 01'):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                events(HEADER + bytes.fromhex(payload))

    def test_sysex_length_and_following_step(self):
        for prefix, delay in (('00 04', '09'), ('80 04', '01 23')):
            rows = events(HEADER + bytes.fromhex(f'f0 {prefix} 7e 7f 09 01 {delay} 83'))['events']
            self.assertEqual(rows[0]['data'], [126, 127, 9, 1])
            self.assertEqual(rows[0]['step'], int(delay.replace(' ', ''), 16))
            self.assertEqual(rows[1]['tick'], rows[0]['step'])
        for payload in ('f0 00 00 00 83', 'f0 00 04 7e 7f', 'f0 80 01 7e 01'):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                events(HEADER + bytes.fromhex(payload))

    def test_bad_bank_pointer(self):
        bank = b'SMSB' + struct.pack('<4I', 2, 32, 1, 0xffff) + bytes(12)
        container = b'SMLT' + struct.pack('<2I', 2, 1) + bytes(20)
        container += b'SMSB' + struct.pack('<5I', 0, 0x18000, 32, 64, 32) + bytes(8)
        with self.assertRaisesRegex(ValueError, 'pointer'):
            inventory(container + bank)


if __name__ == '__main__':
    unittest.main()
