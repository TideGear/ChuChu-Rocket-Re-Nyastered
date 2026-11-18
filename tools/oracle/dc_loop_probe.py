"""Generated finite/infinite loop cases against the original scheduler.

Distinct opening/closing delays exercise which marker's delay is used on a
repeat versus exit. No copyrighted bank data is embedded.
"""
import argparse
import struct
from pathlib import Path
from dc_sequence_clock_probe import verify
from dc_sysex_probe import bank_fixture


def run(driver):
    count = 0
    for repeats in (0, 1, 2, 3, 127):
        for wide in (False, True):
            opening_step = 291 if wide and repeats < 4 else 1
            for opening_prefix, closing_prefix in ((b'', b''), (b'\x8c', b''),
                                                    (b'', b'\x8c'), (b'\x8c', b'\x8c')):
                sequence = (b'SMSD' + struct.pack('<2I', 136, 400) + opening_prefix +
                            bytes([0x82, repeats | (0x80 if wide else 0)]) +
                            opening_step.to_bytes(2 if wide else 1, 'big') +
                            bytes.fromhex('c0 16 01') + closing_prefix + bytes.fromhex('82 00 03 83'))
                result = verify(driver, bank_fixture(sequence), 0, 0)
                if repeats == 0 and result.get('loop_repeats') != 2:
                    raise AssertionError('Infinite loop did not repeat twice')
                if repeats and result['sequence_end'] is None:
                    raise AssertionError('Finite loop did not end')
                count += 1
    return count


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('driver', type=Path)
    args = parser.parse_args()
    print(f'{run(args.driver.read_bytes())} finite/infinite loop cases match original scheduler')
