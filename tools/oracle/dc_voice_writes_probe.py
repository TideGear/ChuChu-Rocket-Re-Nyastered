"""Compare persistent native voices with synthetic timed Flycast writes.

Uses isolated dc_voice_wave_probe fixtures (channels 8/9). CSV rows have
sample(decimal),channel(decimal),offset(hex),width(decimal),value(hex).
This verifies hardware components, not original-loop whole-cue sound.
"""
import argparse
import struct
import sys
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aica_pcm import SampleStream, SampledVoiceBank, sampled_channel
from dc_aica_state import inspect


def verify(state, mlt, schedule, wav, *, dsp_disabled=False, key_bank=False, fresh_registers=False, monitor_reads=None, monitor_queries=None):
    if (monitor_reads is None) != (monitor_queries is None):
        raise ValueError('Provide both monitor queries and results')
    if fresh_registers and not key_bank:
        raise ValueError('Fresh register setup requires the key bank')
    report = inspect(state, mlt)
    base, regs = report['sound_ram_offset'], report['register_offset']
    if any(state[regs + 0x2000:regs + 0x2048]):
        raise ValueError('DSP/CD returns must be muted')
    if struct.unpack_from('<H', state, regs + 0x2800)[0] & 0x810f != 15:
        raise ValueError('Expected full-volume stereo 16-bit master output')
    ram = state[base:base + 0x200000]
    if any(c['runtime']['enabled'] for c in report['channels'] if c['channel'] not in (8, 9)):
        raise ValueError('Isolated fixture has an enabled unmodeled voice')
    bank_registers = bytearray(state[regs:regs + 0x8000])
    if key_bank:
        # Flycast deserialize calls SetAegState before the synthetic KEY_ON.
        # Release-state channels lose KYONB there; KEY_ON doesn't set it back.
        for channel in report['channels']:
            if channel['runtime']['amplitude_state'] == 3:
                at = channel['channel'] * 128
                control = struct.unpack_from('<I', bank_registers, at)[0] & ~0x4000
                struct.pack_into('<I', bank_registers, at, control)
    models = {}
    for index in (8, 9):
        if fresh_registers and state[report['runtime_offset'] + index * 72 + 71]:
            raise ValueError('Fresh setup requires an initially disabled voice')
        channel = next((c for c in report['channels'] if c['channel'] == index), None)
        if channel is None:
            if not fresh_registers or any(bank_registers[index * 128:(index + 1) * 128]):
                raise ValueError('Expected a configured or explicitly fresh channel')
            channel = sampled_channel([0] * 18)
            at = report['runtime_offset'] + index * 72
            channel['runtime'] = dict(lfo_counter=struct.unpack_from('<I', state, at + 66)[0], lfo_phase=state[at + 70])
        if key_bank:
            channel = dict(channel, register_words=list(struct.unpack_from('<18I', bank_registers, index * 128)))
        models[index] = SampleStream.from_registers(channel, ram,
            lfo_counter=channel['runtime']['lfo_counter'], lfo_phase=channel['runtime']['lfo_phase'], start=not fresh_registers)
    bank = SampledVoiceBank(models, bank_registers) if key_bank else None
    with wave.open(str(wav), 'rb') as stream:
        if (stream.getnchannels(), stream.getsampwidth(), stream.getframerate()) != (2, 2, 44100):
            raise ValueError('Expected stereo PCM16 / 44100 Hz')
        count = stream.getnframes()
        actual = struct.unpack(f'<{count * 2}h', stream.readframes(count))
    events = []
    for row in schedule.read_text().splitlines():
        at, channel, offset, size, value = row.split(',')
        event = (int(at), int(channel), int(offset, 16), int(size), int(value, 16))
        if not 0 <= event[0] < count or not 0 <= event[1] < 64 or (not key_bank and event[1] not in models) or events and event[0] < events[-1][0]:
            raise ValueError('Unordered/out-of-range fixture write')
        events.append(event)
    if not events:
        raise ValueError('A write fixture must exercise register changes')
    timeline = [(at, 0, channel, offset, size, value) for at, channel, offset, size, value in events]
    read_count = loop_reads = 0
    if monitor_reads is not None:
        if bank is None or monitor_queries is None:
            raise ValueError('Monitor comparison requires a voice bank and its query schedule')
        queries = [tuple(int(x, 16 if i in (1, 2) else 10) for i, x in enumerate(row.split(',')))
                   for row in monitor_queries.read_text().splitlines()]
        previous = -1
        for row in monitor_reads.read_text().splitlines():
            at, select, address, size, value = row.split(',')
            at, select, address, size, value = int(at), int(select, 16), int(address, 16), int(size), int(value, 16)
            if not 0 <= at < count or at < previous:
                raise ValueError('Unordered/out-of-range monitor trace')
            if read_count >= len(queries) or queries[read_count] != (at, select, address, size):
                raise AssertionError('Monitor result does not match the requested read schedule')
            previous = at
            timeline.append((at, 1, select, address, size, value))
            read_count += 1
        if not read_count or read_count != len(queries):
            raise ValueError('Monitor trace is empty or incomplete')
    timeline.sort(key=lambda row: (row[0], row[1]))
    expected = []
    position = 0
    for at, kind, channel, offset, size, value in timeline + [(count, 2, None, None, None, None)]:
        if bank is not None:
            expected.extend(sample for pair in bank.render(at - position, dsp_disabled_fallback=dsp_disabled) for sample in pair)
        else:
            blocks = [model.render_stereo(at - position, dsp_disabled_fallback=dsp_disabled) for model in models.values()]
            for pairs in zip(*blocks):
                expected.extend(max(-32768, min(32767, sum(pair[side] for pair in pairs))) for side in (0, 1))
        if kind == 0:
            if bank is not None:
                bank.write_arm(channel * 128 + offset, size, value)
            else:
                models[channel].write_controller(offset, size, value)
        elif kind == 1:
            bank.write_arm(0x280d, 1, channel)
            observed = bank.read_arm(offset, size)
            if observed != value:
                raise AssertionError(('Monitor read', at, hex(channel), hex(offset), size, hex(observed), hex(value)))
            loop_reads += bool((offset == 0x2810 and size != 1 and value & 0x8000) or
                               (offset == 0x2811 and value & 0x80))
        position = at
    if not any(expected):
        raise AssertionError('Silent write fixture')
    different = sum(a != b for a, b in zip(actual, expected))
    if different or len(actual) != len(expected):
        first = [(i // 2, i % 2, a, b) for i, (a, b) in enumerate(zip(actual, expected)) if a != b][:12]
        raise AssertionError((different, 'different samples', 'peak error', max(abs(a - b) for a, b in zip(actual, expected)), first))
    if monitor_reads is not None and not loop_reads:
        raise AssertionError('Monitor trace never exercises a set loop latch')
    print(dict(stereo_pairs=count, timed_writes=len(events), differing_samples=0,
               monitor_reads=read_count, set_loop_reads=loop_reads))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('state', type=Path)
    parser.add_argument('mlt', type=Path)
    parser.add_argument('schedule', type=Path)
    parser.add_argument('wav', type=Path)
    parser.add_argument('--dsp-disabled', action='store_true', help='reference core has DSP disabled: include its zero-direct-output send fallback')
    parser.add_argument('--key-bank', action='store_true', help='consume control writes with the global 64-channel KYONEX scan')
    parser.add_argument('--fresh-registers', action='store_true', help='leave voices disabled until the write schedule starts them; do not force core KEY_ON')
    parser.add_argument('--monitor-reads', type=Path, help='compare original timed monitor results, including repeated latch reads')
    parser.add_argument('--monitor-queries', type=Path, help='the matching complete monitor query schedule')
    args = parser.parse_args()
    verify(args.state.read_bytes(), args.mlt.read_bytes(), args.schedule, args.wav, dsp_disabled=args.dsp_disabled, key_bank=args.key_bank, fresh_registers=args.fresh_registers, monitor_reads=args.monitor_reads, monitor_queries=args.monitor_queries)
