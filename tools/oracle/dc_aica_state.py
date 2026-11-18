"""Inspect AICA registers in the locally tested Flycast raw state layout.

Supports only header word 0x356. Locate sound RAM using at least two MLT bank
headers, not an unchecked fixed state offset. Flycast aica_if.cpp serializes
four RTC/reset words then 0x8000 register bytes after its 2 MiB sound RAM.
Channel register bit layout: Flycast sgc_if.cpp, ChannelCommonData.
Key-on is a register flag, not proof that a channel is still audible.
Usage: dc_aica_state.py <snapshot.state> <loaded.MLT> <report.json>
"""
import argparse
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mlt_extract import sections
from mlt_programs import inventory


def inspect(state, mlt):
    if len(state) < 4 or struct.unpack_from('<I', state)[0] != 0x356:
        raise ValueError('Unsupported Flycast state header/layout')
    banks = [r for r in sections(mlt) if r['tag'] in ('SMPB', 'SMDB', 'SMSB')
             and r['offset'] != 0xffffffff]
    if len(banks) < 2:
        raise ValueError('At least two loaded bank headers are required')
    candidates = None
    for row in banks:
        header = mlt[row['offset']:row['offset'] + 16]
        found, pos = set(), 0
        while True:
            pos = state.find(header, pos)
            if pos < 0:
                break
            base = pos - row['address']
            if 0 <= base < 0x10000 and base + 0x208010 <= len(state):
                found.add(base)
            pos += 1
        candidates = found if candidates is None else candidates & found
    if len(candidates) != 1:
        raise ValueError('No unique loaded AICA RAM image matched all bank headers')
    base = candidates.pop()
    registers = base + 0x200000 + 16
    samples = {}
    for bank in inventory(mlt):
        for program in bank['programs']:
            for layer in program['layers']:
                for split in layer['splits']:
                    address = split['sample_ram_address']
                    if address is None:
                        continue
                    off, length = split['sample_file_offset'], split['sample_bytes']
                    if state[base + address:base + address + length] != mlt[off:off + length]:
                        raise ValueError('Loaded sample differs from disc payload')
                    samples.setdefault(address, []).append(dict(bank=bank['bank'], tag=bank['tag'],
                        program=program['index'], layer=layer['index'], split=split['index'],
                        format=split['format'], loop_start=split['loop_start'], loop_end=split['loop_end']))
    channels = []
    for index in range(64):
        at = registers + 128 * index
        words = [struct.unpack_from('<H', state, at + offset)[0] for offset in range(0, 0x48, 4)]
        control = words[0]
        address = ((control & 127) << 16) | words[1]
        if not any(words):
            continue
        channels.append(dict(channel=index, key_on=bool(control & 0x4000),
            sample_address=address, pcm_mode=(control >> 7) & 3,
            loop=bool(control & 0x200), loop_start=words[2], loop_end=words[3],
            pitch_raw=words[6], fns=words[6] & 1023, octave_raw=(words[6] >> 11) & 15,
            lfo_raw=words[7], pan_raw=words[9] & 31, direct_level=(words[9] >> 8) & 15,
            total_level=words[10] >> 8, register_words=words,
            sample_references=samples.get(address, [])))
    return dict(state_header=0x356, sound_ram_offset=base, register_offset=registers,
                verified_sample_addresses=len(samples), channels=channels)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('state', type=Path)
    parser.add_argument('mlt', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    report = inspect(args.state.read_bytes(), args.mlt.read_bytes())
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print('sample addresses checked:', report['verified_sample_addresses'])
    for channel in report['channels']:
        if channel['key_on']:
            print('key-on channel', channel['channel'], 'sample', hex(channel['sample_address']),
                  'mode', channel['pcm_mode'], 'pitch', hex(channel['pitch_raw']))
