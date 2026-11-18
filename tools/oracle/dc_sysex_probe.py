"""Synthetic SMSD system-exclusive cases through original scheduler calls.

Exercises lengths 1..5, chunk/padding boundaries and both step widths.
These generated banks contain no game assets; this does not test voice dispatch.
"""
import argparse
import struct
from pathlib import Path
from dc_sequence_clock_probe import verify


def fixture(length, step, wide):
    payload = bytes((index * 37 + 126) & 255 for index in range(length))
    length_word = length | (0x8000 if wide else 0)
    sequence = (b'SMSD' + struct.pack('<2I', 136, 400) + b'\xf0' +
                length_word.to_bytes(2, 'big') + payload + step.to_bytes(2 if wide else 1, 'big') + b'\x83')
    return bank_fixture(sequence)


def bank_fixture(sequence):
    bank = b'SMSB' + struct.pack('<4I', 1, 24 + len(sequence), 1, 20) + sequence + b'END!'
    header = b'SMLT' + struct.pack('<2I', 2, 1) + bytes(20)
    entry = b'SMSB' + struct.pack('<5I', 0, 0x88000, len(bank), 64, len(bank)) + bytes(8)
    return header + entry + bank


def run(driver):
    count = 0
    for length in (1, 2, 3, 4, 5):
        for wide, step in ((False, 0), (False, 1), (False, 255), (True, 291)):
            verify(driver, fixture(length, step, wide), 0, 0)
            count += 1
    return count


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('driver', type=Path)
    args = parser.parse_args()
    print(f'{run(args.driver.read_bytes())} synthetic sysex sequences match original scheduler')
