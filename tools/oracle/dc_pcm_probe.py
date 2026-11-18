"""Prepare isolated core states and compare exact sampled waveform windows.

prepare <source.state> <loaded.MLT> <isolated.state> --channels 0,2
verify <isolated.state> <loaded.MLT> <core.wav>

The prepare control mutes other channel runtimes and all DSP/CD output returns.
It retains the selected channels' captured source position, filter history and
LFO phase. Resume the isolated state with flyhost/FLYHOST_WAV, then verify its
output. Verified cases include PCM16 amplitude controls and ADPCM decay/release. --keys-csv
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


def prepare_envelope_controls(state, mlt, source_channel=0):
    """Synthetic amplitude cases on channels 8..15; preserve stream/filter phase.

    This tests envelope arithmetic, not original note-on initialization. Each
    tuple is (AR,D1R,D2R,DL,RR,LPSLNK); KRS=15 isolates raw rate selection.
    """
    report = inspect(state, mlt)
    source = next(c for c in report['channels'] if c['channel'] == source_channel)
    if not source['runtime']['enabled']:
        raise ValueError('Envelope controls require an enabled source')
    if source['runtime']['position'] + 128 >= min(source['loop_end'], 65536):
        raise ValueError('Source has insufficient room for the synthetic loop-link point')
    output = prepare(state, mlt, {source_channel}, force_loop=True)
    registers, runtimes = report['register_offset'], report['runtime_offset']
    register_data = bytes(output[registers + 128 * source_channel:registers + 128 * source_channel + 128])
    runtime_data = bytes(output[runtimes + 72 * source_channel:runtimes + 72 * source_channel + 72])
    output[runtimes + 72 * source_channel + 71] = 0
    cases = ((31, 0, 0, 8, 20, False), (18, 18, 22, 8, 20, False),
             (0, 18, 22, 8, 20, False), (31, 31, 31, 0, 31, False),
             (20, 0, 0, 8, 20, False), (18, 18, 0, 0, 20, False),
             (0, 18, 22, 8, 20, True), (31, 18, 22, 8, 20, True))
    for index, (attack, decay1, decay2, level, release, linked) in enumerate(cases, 8):
        reg, runtime = registers + index * 128, runtimes + index * 72
        output[reg:reg + 128] = register_data
        output[runtime:runtime + 72] = runtime_data
        struct.pack_into('<I', output, reg + 16, attack | decay1 << 6 | decay2 << 11)
        struct.pack_into('<I', output, reg + 20, release | level << 5 | 15 << 10 | int(linked) << 14)
        if linked:
            struct.pack_into('<I', output, reg + 8, source['runtime']['position'] + 128)
        struct.pack_into('<iI', output, runtime + 38, 640 << 16, 0)
    return output


def prepare_filter_controls(state, mlt, source_channel=0):
    """Synthetic filter sweeps, boundary/equal targets, frozen rate and release."""
    report = inspect(state, mlt)
    output = prepare_envelope_controls(state, mlt, source_channel)
    registers, runtimes = report['register_offset'], report['runtime_offset']
    cases = (
        ((0x1000, 0x1d00, 0x800, 0x1800, 0x400), 4, 0, 31, 0),
        ((0x1f00, 0x400, 0x1800, 0x200, 0x1d00), 8, 0, 31, 0),
        ((0, 0, 0, 0, 0), 31, 0, 31, 0),
        ((0x1000, 0x1800, 0x800, 0x1c00, 0x400), 4, 3, 31, 0),
        ((0x1000, 0x1800, 0x800, 0x1c00, 0x400), 4, 0, 0, 0),
        ((0x1000, 0x1001, 0x1000, 0x1001, 0), 0, 1, 31, 0x8000),
        ((0x1fff, 0, 0x1fff, 0, 0x1fff), 0, 0, 31, 0),
        ((0x1000, 0x1800, 0x800, 0x1c00, 0x1d00), 16, 3, 31, 0),
    )
    for index, (levels, resonance, phase, attack, fraction) in enumerate(cases, 8):
        reg, runtime = registers + index * 128, runtimes + index * 72
        struct.pack_into('<I', output, reg + 16, 31)
        struct.pack_into('<I', output, reg + 20, 31 | 15 << 10)
        control = struct.unpack_from('<I', output, reg + 40)[0]
        struct.pack_into('<I', output, reg + 40, (control & ~63) | resonance)
        struct.pack_into('<5I', output, reg + 44, *levels)
        struct.pack_into('<2I', output, reg + 64, attack << 8 | 31, 31 << 8 | 31)
        struct.pack_into('<iIII', output, runtime + 38, 0, 2, (levels[0] << 16) | fraction, phase)
        if phase == 0:
            # Flycast SetFegState(Attack), including state restoration, clears history.
            struct.pack_into('<3i', output, runtime + 54, 0, 0, 0)
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
    parser.add_argument('--envelope-controls', action='store_true', help='synthetic amplitude controls from one source channel')
    parser.add_argument('--filter-controls', action='store_true', help='synthetic changing filter controls from one source channel')
    args = parser.parse_args()
    state, mlt = args.state.read_bytes(), args.mlt.read_bytes()
    if args.operation == 'prepare':
        try:
            channels = {int(value) for value in args.channels.split(',')}
        except ValueError:
            parser.error('channels must be comma-separated integers')
        if args.envelope_controls or args.filter_controls:
            if args.envelope_controls and args.filter_controls:
                parser.error('Choose amplitude or filter controls')
            if len(channels) != 1:
                parser.error('--envelope-controls needs exactly one source channel')
            operation = prepare_filter_controls if args.filter_controls else prepare_envelope_controls
            args.output.write_bytes(operation(state, mlt, next(iter(channels))))
        else:
            args.output.write_bytes(prepare(state, mlt, channels, args.force_loop))
    else:
        verify(state, mlt, args.output, args.keys_csv)
