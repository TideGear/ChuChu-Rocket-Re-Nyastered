"""Original bank/controller fields -> native registers -> fresh-note waveform.

Prepare an isolated core fixture, resume with FLYCAST_AICA_KEY_ON=300 and
FLYHOST_WAV, then verify its direct stereo output. Explicit captured LFO clocks
are retained; driver scheduling and DSP/CD returns are deliberately isolated.
"""
import argparse
import struct
import sys
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dc_sound_controls import VoiceSetup
from aica_pcm import direct_stereo_words
from dc_aica_state import inspect
from dc_pcm_probe import prepare_keyon_controls


def prepare(driver, state, mlt, sources):
    if len(sources) != 2:
        raise ValueError('Select exactly two captured source voices')
    report = inspect(state, mlt)
    base, regs, runtimes = (report[k] for k in ('sound_ram_offset', 'register_offset', 'runtime_offset'))
    ram = state[base:base + 0x200000]
    output = prepare_keyon_controls(state, mlt, sources)
    setup = VoiceSetup(driver)
    for target, source in enumerate(sources, 8):
        voice = ram[0x10000 + 64 * source:0x10040 + 64 * source]
        group, channel, note, velocity = voice[4:8]
        controller = ram[0xc000 + group * 0x800 + channel * 128:0xc080 + group * 0x800 + channel * 128]
        bank, program = struct.unpack_from('<2I', controller, 0x10)
        split_at = struct.unpack_from('<I', voice, 0x10)[0]
        split = ram[split_at:split_at + 48]
        layer = None
        for index in range(4):
            relative = struct.unpack_from('<I', ram, program + index * 4)[0]
            if not relative:
                continue
            header = ram[bank + relative:bank + relative + 16]
            count, first = struct.unpack_from('<2I', header)
            if bank + first <= split_at < bank + first + (count & 127) * 48 and (split_at - bank - first) % 48 == 0:
                layer = header
                break
        if layer is None:
            raise ValueError('Source split has no program layer')
        parameters = struct.unpack_from('<I', voice, 0x18)[0]
        curve = struct.unpack_from('<I', controller, 0x18)[0] + split[0x2a] * 128
        words = setup.words(split, layer, controller, ram[parameters:parameters + 32],
                            ram[curve:curve + 128], bank, note, velocity)
        if not words[0] & 0x4000:
            raise ValueError('Delayed note-on is outside this fresh-trigger fixture')
        struct.pack_into('<18I', output, regs + target * 128, *words)
        print('native voice', target, 'source', source, 'note', note, 'velocity', velocity,
              'sample', hex((words[0] & 127) << 16 | words[1]))
    for target in (10, 11):
        output[runtimes + 72 * target + 71] = 0
    return output


def verify(state, mlt, reference):
    report = inspect(state, mlt)
    registers = report['register_offset']
    if any(state[registers + 0x2000:registers + 0x2048]):
        raise ValueError('DSP/CD returns must be muted')
    if struct.unpack_from('<H', state, registers + 0x2800)[0] & 0x810f != 15:
        raise ValueError('Expected full-volume stereo 16-bit master output')
    ram = state[report['sound_ram_offset']:report['sound_ram_offset'] + 0x200000]
    with wave.open(str(reference), 'rb') as stream:
        if (stream.getnchannels(), stream.getsampwidth(), stream.getframerate()) != (2, 2, 44100):
            raise ValueError('Expected stereo PCM16 / 44100 Hz')
        count = stream.getnframes()
        actual = struct.unpack(f'<{count * 2}h', stream.readframes(count))
    expected = [0] * (count * 2)
    for target in (8, 9):
        channel = next(c for c in report['channels'] if c['channel'] == target)
        runtime = channel['runtime']
        pairs, _ = direct_stereo_words(channel['register_words'], ram, count,
            lfo_counter=runtime['lfo_counter'], lfo_phase=runtime['lfo_phase'])
        for index, (left, right) in enumerate(pairs):
            expected[index * 2] += left
            expected[index * 2 + 1] += right
    expected = [max(-32768, min(32767, sample)) for sample in expected]
    if not any(expected):
        raise AssertionError('A silent fixture cannot verify this note-on path')
    different = sum(a != b for a, b in zip(actual, expected))
    if different:
        raise AssertionError((different, 'different samples; maximum', max(abs(a - b) for a, b in zip(actual, expected))))
    print('Native source-to-wave match:', count, 'stereo pairs, zero sample error')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('prepare', 'verify'))
    parser.add_argument('state', type=Path); parser.add_argument('mlt', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--driver', type=Path)
    parser.add_argument('--channels', default='0,2')
    args = parser.parse_args()
    if args.operation == 'prepare':
        if args.driver is None:
            parser.error('prepare requires --driver')
        args.output.write_bytes(prepare(args.driver.read_bytes(), args.state.read_bytes(), args.mlt.read_bytes(),
                                       [int(v) for v in args.channels.split(',')]))
    else:
        verify(args.state.read_bytes(), args.mlt.read_bytes(), args.output)
