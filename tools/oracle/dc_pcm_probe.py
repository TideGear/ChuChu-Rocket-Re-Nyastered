"""Prepare isolated core states and compare exact sampled waveform windows.

prepare <source.state> <loaded.MLT> <isolated.state> --channels 0,2
verify <isolated.state> <loaded.MLT> <core.wav>

The prepare control mutes other channel runtimes and all DSP/CD output returns.
It retains the selected channels' captured source position, filter history and
LFO phase. Resume the isolated state with flyhost/FLYHOST_WAV, then verify its
output. Verified cases include PCM16 and ADPCM sustain/release. --keys-csv
applies recorded key-off transitions; other sequencer commands remain unsupported.
--force-loop is an explicit synthetic LPCTL control, not original program data.
"""
import argparse
import csv
import struct
import sys
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from aica_pcm import direct_stereo
from dc_aica_state import inspect


def prepare(state, mlt, channels, force_loop=False):
    report = inspect(state, mlt)
    available = {c['channel'] for c in report['channels'] if c['runtime']['enabled']}
    if not channels or not channels <= available:
        raise ValueError('Select enabled captured channels')
    output = bytearray(state)
    for index in range(64):
        if index not in channels:
            output[report['runtime_offset'] + 72 * index + 71] = 0
    returns = report['register_offset'] + 0x2000
    output[returns:returns + 18 * 4] = bytes(18 * 4)
    if force_loop:
        for index in channels:
            at = report['register_offset'] + 128 * index
            control = struct.unpack_from('<H', output, at)[0]
            struct.pack_into('<H', output, at, control | 0x200)
    return output


def verify(state, mlt, wav_path, keys_path=None):
    report = inspect(state, mlt)
    registers = report['register_offset']
    if any(state[registers + 0x2000:registers + 0x2048]):
        raise ValueError('Use an isolated state with DSP/CD returns muted')
    master = struct.unpack_from('<H', state, registers + 0x2800)[0]
    if master & 0x810f != 15:
        raise ValueError('This probe requires full-volume stereo 16-bit output')
    with wave.open(str(wav_path), 'rb') as stream:
        if (stream.getnchannels(), stream.getsampwidth(), stream.getframerate()) != (2, 2, 44100):
            raise ValueError('Expected stereo PCM16 at 44,100 Hz')
        count = stream.getnframes()
        actual = list(struct.unpack(f'<{count * 2}h', stream.readframes(count)))
    ram = state[report['sound_ram_offset']:report['sound_ram_offset'] + 0x200000]
    expected = [0] * (count * 2)
    channels = []
    key_off = {}
    if keys_path is not None:
        previous = {c['channel']: bool(c['register_words'][0] & 0x4000) for c in report['channels']}
        last_sample = -1
        with open(keys_path, newline='', encoding='utf-8') as stream:
            for event in csv.DictReader(stream):
                index, sample = int(event['channel']), int(event['sample'])
                control = int(event['control'], 16)
                if not 0 <= index < 64 or sample < last_sample or sample < 0 or not 0 <= control <= 0xffffffff:
                    raise ValueError('Invalid or unordered core key-state trace')
                last_sample = sample
                on = bool(control & 0x4000)
                if previous.get(index, False) and not on and sample < count:
                    key_off.setdefault(index, []).append(sample)
                previous[index] = on
    for channel in report['channels']:
        if not channel['runtime']['enabled']:
            continue
        events = key_off.get(channel['channel'], ())
        rendered, final = direct_stereo(channel, ram, count, events)
        for index, pair in enumerate(rendered):
            expected[2 * index] += pair[0]
            expected[2 * index + 1] += pair[1]
        channels.append(dict(channel=channel['channel'], final=final, key_off_samples=list(events)))
    if not channels:
        raise ValueError('No enabled channels to compare')
    expected = [max(-32768, min(32767, value)) for value in expected]
    mismatches = sum(a != b for a, b in zip(actual, expected))
    if mismatches:
        maximum = max(abs(a - b) for a, b in zip(actual, expected))
        raise AssertionError(f'{mismatches}/{len(actual)} samples differ; maximum error {maximum}')
    print(f'Exact PCM match: {count} stereo frames, {len(channels)} channel(s), zero sample error')
    return channels


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('prepare', 'verify'))
    parser.add_argument('state', type=Path)
    parser.add_argument('mlt', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--channels', default='0,2')
    parser.add_argument('--force-loop', action='store_true', help='synthetic control: enable the selected sample loops')
    parser.add_argument('--keys-csv', type=Path, help='sample/key transitions from the instrumented core')
    args = parser.parse_args()
    state, mlt = args.state.read_bytes(), args.mlt.read_bytes()
    if args.operation == 'prepare':
        try:
            channels = {int(value) for value in args.channels.split(',')}
        except ValueError:
            parser.error('channels must be comma-separated integers')
        args.output.write_bytes(prepare(state, mlt, channels, args.force_loop))
    else:
        verify(state, mlt, args.output, args.keys_csv)
