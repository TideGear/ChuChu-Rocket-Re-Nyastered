"""Read SMPB/SMDB program, layer and sample references; never guess sample rates.

Format facts: dakrk/manatools docs/mpb.hexpat, revision
d61b1e34182d02dd3dd545ca7db15e6529a666ae. Raw pitch/envelope fields are retained
for comparison with the original AICA driver, rather than interpreted as Hz.
Usage: mlt_programs.py <bank.MLT> <inventory.json>
"""
import argparse
import json
import struct
from pathlib import Path

from mlt_extract import sections


def programs(data, file_offset=0, ram_address=0):
    if len(data) < 48 or data[:4] not in (b'SMPB', b'SMDB'):
        raise ValueError('Invalid program-bank header')
    version, size = struct.unpack_from('<2I', data, 4)
    if version not in (1, 0x5001, 2) or size > len(data) or size < 48:
        raise ValueError('Invalid program-bank version/size')

    def block(offset, length):
        if offset < 48 or length > size - offset:
            raise ValueError('Program-bank reference outside payload')
        return data[offset:offset + length]

    table, count, velocities, velocity_count = struct.unpack_from('<4I', data, 16)
    if count > 128 or velocity_count > 128:
        raise ValueError('Program-bank count exceeds format limit')
    pointers = struct.unpack(f'<{count}I', block(table, count * 4))
    block(velocities, velocity_count * 128)
    result = []
    for program, pointer in enumerate(pointers):
        layers = []
        if pointer:
            for layer, address in enumerate(struct.unpack('<4I', block(pointer, 16))):
                if not address:
                    continue
                header = block(address, 16)
                count_word, splits_at = struct.unpack_from('<2I', header)
                if count_word > 255:
                    raise ValueError('Unsupported program-layer count flags')
                split_count = count_word & 127
                splits = []
                for index in range(split_count):
                    at = splits_at + 48 * index
                    raw = block(at, 48)
                    jump, flags, low, loop_start, loop_end = struct.unpack_from('<2B3H', raw)
                    sample = ((jump & 127) << 16) | low
                    kind = 'adpcm' if flags & 1 else 'pcm8' if jump & 128 else 'pcm16'
                    length = (loop_end + 1) // 2 if kind == 'adpcm' else loop_end * (1 if kind == 'pcm8' else 2)
                    if sample:
                        block(sample, length)
                    splits.append(dict(index=index, offset=at, sample_offset=sample,
                        sample_file_offset=file_offset + sample if sample else None,
                        sample_ram_address=ram_address + sample if sample else None,
                        sample_bytes=length, format=kind, flags=flags,
                        loop=bool(flags & 2), loop_start=loop_start, loop_end=loop_end,
                        amp_raw=int.from_bytes(raw[8:12], 'little'),
                        pitch_raw=int.from_bytes(raw[12:14], 'little'),
                        lfo_raw=int.from_bytes(raw[14:16], 'little'),
                        pan_raw=raw[18], direct_level=raw[19],
                        note_low=raw[36], note_high=raw[37], base_note=raw[38],
                        fine_tune=struct.unpack_from('<b', raw, 39)[0],
                        velocity_curve=raw[42], velocity_low=raw[43], velocity_high=raw[44],
                        drum_mode=bool(raw[45]), raw=raw.hex()))
                layers.append(dict(index=layer, offset=address, delay=int.from_bytes(header[8:10], 'little'),
                    disabled=bool(count_word & 128),
                    bend_high=header[12], bend_low=header[13], splits=splits))
        result.append(dict(index=program, offset=pointer, layers=layers))
    return dict(tag=data[:4].decode('ascii'), version=version, programs=result)


def split_matches(raw, note, velocity):
    """Original ARM 0xf3c..0xf70 inclusive bounds, before drum/allocation work."""
    if len(raw) < 48 or not 0 <= note <= 127 or not 0 <= velocity <= 127:
        raise ValueError('Expected a split and seven-bit note/velocity')
    return raw[36] <= note <= raw[37] and raw[43] <= velocity <= raw[44]


def matching_splits(program, note, velocity):
    """Ordered candidates per enabled layer; allocation may reject a candidate.

    A zero-velocity command is note-off and has no note-on candidates.
    """
    if not 0 <= note <= 127 or not 0 <= velocity <= 127:
        raise ValueError('Expected seven-bit note/velocity')
    if not velocity:
        return []
    return [(layer['index'], [split for split in layer['splits']
                             if split_matches(bytes.fromhex(split['raw']), note, velocity)])
            for layer in program['layers'] if not layer.get('disabled', False)]


def inventory(data):
    result = []
    for section in sections(data):
        if section['tag'] not in ('SMPB', 'SMDB') or section['offset'] == 0xffffffff:
            continue
        start = section['offset']
        bank = programs(data[start:start + section['size']], start, section['address'])
        bank['bank'] = section['bank']
        result.append(bank)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mlt', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    banks = inventory(args.mlt.read_bytes())
    args.output.write_text(json.dumps(banks, indent=2) + '\n', encoding='utf-8')
    for bank in banks:
        print(bank['tag'], bank['bank'], ':', len(bank['programs']), 'programs')
