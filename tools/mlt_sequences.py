"""Inventory SMSB/SMSD events without synthesizing or guessing playback rates.

Format reference: dakrk/manatools docs/msb+msd.hexpat and src/manatools/msd.hpp,
revision d61b1e34182d02dd3dd545ca7db15e6529a666ae (see docs/audio.md).
Offsets in output are relative to each SMSD, time is in raw sequence steps.
Usage: mlt_sequences.py <bank.MLT> <inventory.json>
"""
import argparse
import json
import struct
from pathlib import Path

from mlt_extract import sections


def events(data, limit=100000):
    if len(data) < 12 or data[:4] != b'SMSD':
        raise ValueError('Invalid SMSD header')
    pos, tick, gate_ext, step_ext = 12, 0, 0, 0
    result = []
    remaining = limit

    def read(size):
        nonlocal pos
        if pos + size > len(data):
            raise ValueError('Truncated SMSD event')
        value = int.from_bytes(data[pos:pos + size], 'big')
        pos += size
        return value

    def message(depth=0):
        nonlocal pos, tick, gate_ext, step_ext, remaining
        remaining -= 1
        if remaining < 0 or depth > 32:
            raise ValueError('SMSD event/reference limit exceeded')
        start = pos
        status = read(1)
        if 0x88 <= status <= 0x8f:
            if status < 0x8c:
                gate_ext += (0x200, 0x800, 0x1000, 0x2000)[status & 3]
            else:
                step_ext += (0x100, 0x200, 0x800, 0x1000)[status & 3]
            return message(depth + 1)
        if status == 0x81:
            target, count = read(2), read(1)
            saved = pos
            if target < 12 or target >= len(data):
                raise ValueError('SMSD reference outside event data')
            pos = target
            for _ in range(count):
                if not message(depth + 1):
                    raise ValueError('End of track inside SMSD reference')
            pos = saved
            return True
        row = dict(offset=start, tick=tick, status=status)
        kind = status & 0xf0
        if status < 0x80:
            row.update(type='note', channel=status & 15, note=read(1), velocity=read(1))
            row['gate'] = read((status >> 5) + 1) + gate_ext
            gate_ext = 0
            step = read(2 if status & 0x10 else 1)
        elif kind in (0xb0, 0xc0, 0xd0, 0xe0):
            value = read(1)
            row['channel'] = status & 15
            if kind == 0xb0:
                row.update(type='control', controller=value & 127, value=read(1))
            else:
                row['type'] = {0xc0: 'program', 0xd0: 'pressure', 0xe0: 'pitch'}[kind]
                row['value'] = (value & 127) - (64 if kind == 0xe0 else 0)
            step = read(2 if value & 128 else 1)
        elif status == 0x83:
            row['type'] = 'end'
            result.append(row)
            return False
        elif status == 0x84:
            row.update(type='tempo', value=read(2))
            step = read(1)
        elif status == 0x82:
            value = read(1)
            row.update(type='loop', value=value & 127)
            step = read(2 if value & 128 else 1)
        elif status == 0xf0:
            length_word = read(2)
            length = length_word & 0x7fff
            if not length:
                raise ValueError('Empty SMSD system-exclusive payload')
            row.update(type='sysex', data=[read(1) for _ in range(length)])
            step = read(2 if length_word & 0x8000 else 1)
        else:
            raise ValueError(f'Unsupported SMSD status {status:#x} at {start:#x}')
        if row['type'] == 'loop':
            row['encoded_step'] = step
            row['step_prefix'] = step_ext
        row['step'] = step + step_ext
        step_ext = 0
        tick += row['step']
        result.append(row)
        return True

    while message():
        pass
    return dict(header=list(struct.unpack_from('<2I', data, 4)), events=result)


def inventory(data):
    banks = []
    for section in sections(data):
        if section['tag'] != 'SMSB' or section['offset'] == 0xffffffff:
            continue
        start = section['offset']
        bank = data[start:start + section['size']]
        if len(bank) < 16:
            raise ValueError('Truncated SMSB header')
        version, size, count = struct.unpack_from('<3I', bank, 4)
        table_end = 16 + 4 * count
        if version not in (1, 2) or size > len(bank) or table_end > size:
            raise ValueError('Invalid SMSB header/table bounds')
        pointers = list(struct.unpack_from(f'<{count}I', bank, 16))
        end = size - (8 if version == 2 else 4)
        boundaries = sorted(set(p for p in pointers if p) | {end})
        sequences = []
        for index, offset in enumerate(pointers):
            if not offset:
                sequences.append(dict(index=index, empty=True))
                continue
            if offset < table_end or offset >= end:
                raise ValueError('SMSB sequence pointer outside payload')
            next_offset = next(p for p in boundaries if p > offset)
            sequence = events(bank[offset:next_offset])
            sequence.update(index=index, file_offset=start + offset)
            sequences.append(sequence)
        banks.append(dict(bank=section['bank'], version=version, sequences=sequences))
    return banks


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mlt', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    banks = inventory(args.mlt.read_bytes())
    args.output.write_text(json.dumps(banks, indent=2) + '\n', encoding='utf-8')
    for bank in banks:
        print('bank', bank['bank'], ':', len(bank['sequences']), 'sequences')
