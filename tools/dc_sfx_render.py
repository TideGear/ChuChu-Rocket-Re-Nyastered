"""Render Dreamcast sound-effect cues from the disc's own sound driver and sound bank (no BIOS, no emulator).

usage: dc_sfx_render.py <MANATEE.DRV> <CHU2_SE.MLT> <out dir> [--cue N ...]

Pipeline, each stage derived from the original driver (see docs/audio.md):
  1. cold state: the driver's own startup (FUN_00000100 .. 0x194) runs in tools/arm7_interp.py on the loaded image;
  2. bank install: every SMLT section's (address, allocated size) goes into the driver's bank tables by tag and bank
     (SMSB 0x14000, SMPB 0x14080, SPSR 0x14180, SFPB 0x14200, SFOB 0x14280, SFPW 0x14288), the layout seen in a live Flycast run;
  3. cue id N -> bank 0 sequence N for N < 0x1d, bank 1 sequence N - 0x1d (1ST_READ FUN_8c012024 @ 8c012024);
  4. each driver tick (Timer A divider, tools/dc_sound_clock.py) runs the sequence scheduler and the native channel dispatch;
  5. the resulting AICA channel-register writes drive tools/aica_pcm.py voices, mixed at 44.1 kHz.
Open items (docs/audit.md): the ARM main-loop latency between a tick and its register writes (observed 34-113 samples) is not
modeled; the pitch-LFO phase of a channel depends on that channel's earlier use, so cues start from the power-on phase.
"""
import argparse
import os
import struct
import sys
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arm7_interp import Arm7
from aica_pcm import SampleStream, sampled_channel
from dc_sound_channels import ChannelCommands
from dc_sound_clock import DriverSampleClock
from dc_sound_sequence import SequenceCommands
from mlt_extract import sections
from mlt_sequences import inventory

TABLES = {'SMSB': 0x14000, 'SMPB': 0x14080, 'SPSR': 0x14180}      # indexed by bank, 8 bytes each
SINGLE_TABLES = {'SFPB': 0x14200, 'SFOB': 0x14280, 'SFPW': 0x14288}
LOOP_CAP_SECONDS = 20
SILENT_ATTENUATION = 0x3bf


def cue_location(cue):
    """FUN_8c012024: ids below 0x1d are bank 0; the rest are bank 1 with the id offset by 0x1d."""
    return (0, cue) if cue < 0x1d else (1, cue - 0x1d)


def cold_state(driver, mlt):
    """Run the original startup on the loaded driver image; returns (sound RAM, AICA registers)."""
    ram = bytearray(0x200000)
    image = driver[32:]
    ram[:len(image)] = image
    for row in sections(mlt):
        if row['offset'] != 0xffffffff:
            ram[row['address']:row['address'] + row['size']] = mlt[row['offset']:row['offset'] + row['size']]
    cpu = Arm7(ram)
    cpu.run(0x100, 0x194)
    return cpu.ram, cpu.regs_mem


def install_banks(ram, mlt):
    for row in sections(mlt):
        if row['tag'] in TABLES:
            at = TABLES[row['tag']] + row['bank'] * 8
        elif row['tag'] in SINGLE_TABLES:
            at = SINGLE_TABLES[row['tag']]
        else:
            continue
        struct.pack_into('<2I', ram, at, row['address'], row['allocated'])


class VoiceEngine:
    """AICA sampled voices fed with the driver's ordered channel-register writes."""
    def __init__(self, sound_ram, registers, lfo_phase=0):
        self.ram = sound_ram
        self.words = [list(struct.unpack_from('<18I', registers, i * 128)) for i in range(64)]
        self.streams = {}
        self.lfo_phase = lfo_phase

    def write(self, at, size, value):
        if at >= 0x2000:
            return                              # common/monitor registers: no effect on sampled output
        index, offset = at // 128, at % 128
        if offset >= 0x48:
            return
        if size == 4:                           # arm_mem.cpp writeReg<u32> stores only the low halfword
            size, value = 2, value & 0xffff
        words = self.words[index]
        packed = bytearray(struct.pack('<18I', *words))
        packed[offset:offset + size] = value.to_bytes(size, 'little')
        words[:] = struct.unpack('<18I', packed)
        execute = offset in (0, 1) and (size == 2 or offset == 1) and words[0] & 0x8000
        if execute:
            words[0] &= ~0x8000
            self.key_scan()
            return
        stream = self.streams.get(index)
        if stream is not None and offset not in (0, 1):
            stream.write_register(offset, size, value)
        elif stream is not None:
            stream.channel['register_words'][0] = words[0]

    def key_scan(self):
        for index, words in enumerate(self.words):
            stream = self.streams.get(index)
            if words[0] & 0x4000:
                if stream is None or stream.state['amplitude_state'] == 3:
                    if (words[0] >> 7 & 3) == 3 or words[0] & 0x400:
                        raise NotImplementedError('Unsupported voice format at key-on')
                    channel = sampled_channel(list(words))
                    self.streams[index] = SampleStream.from_registers(
                        channel, self.ram, lfo_counter=1, lfo_phase=self.lfo_phase)
                    self.streams[index].state['lfo_counter'] = self.streams[index].period
            elif stream is not None and stream.state['amplitude_state'] != 3:
                stream.key_off()

    def audible(self):
        for stream in self.streams.values():
            state = stream.state
            if state['enabled'] and not (state['amplitude_state'] == 3 and state['amplitude_value'] >> 16 > SILENT_ATTENUATION):
                return True
        return False

    def render(self, count):
        mix = [[0, 0] for _ in range(count)]
        for stream in self.streams.values():
            state = stream.state
            if not state['enabled'] or (state['amplitude_state'] == 3 and state['amplitude_value'] >> 16 > SILENT_ATTENUATION):
                continue
            for i, pair in enumerate(stream.render_stereo(count)):
                mix[i][0] += pair[0]
                mix[i][1] += pair[1]
        for index, stream in self.streams.items():     # sgc_if.cpp SetAegState: entering release clears KYONB
            if stream.state['amplitude_state'] == 3:
                self.words[index][0] &= ~0x4000
                stream.channel['register_words'][0] &= ~0x4000
        return mix


def render_cue(driver, mlt, cue, cold=None, max_seconds=LOOP_CAP_SECONDS, lfo_phase=0, record=None):
    """Return (stereo frames as [L, R] pairs, info dict) for one cue id. record, if a list, receives (sample, register offset, width, value) per write."""
    ram, registers = cold if cold is not None else cold_state(driver, mlt)
    ram, registers = bytearray(ram), bytearray(registers)
    install_banks(ram, mlt)
    bank, index = cue_location(cue)
    banks = {b['bank']: b for b in inventory(mlt)}
    sequence = banks[bank]['sequences'][index]
    if sequence.get('empty'):
        return None, dict(cue=cue, empty=True)
    timer = struct.unpack_from('<I', registers, 0x2890)[0]
    clock = DriverSampleClock(driver, ram, timer)
    commands = SequenceCommands(sequence)
    channels = ChannelCommands(driver, ram, registers)
    engine = VoiceEngine(channels.ram, channels.registers, lfo_phase)
    limit = max_seconds * 44100
    tick_times = [sample for sample, _ in clock.advance(limit)][1:]    # first observation is the sample-zero baseline
    frames, position, ticks, ended_at, writes = [], 0, 0, None, 0
    for sample in tick_times:
        if sample > position:
            frames.extend(engine.render(sample - position)); position = sample
        ticks += 1
        batch = []
        for command in commands.update():
            channels.apply(command)
            batch.extend(channels.writes)
        channels.update_voices()
        batch.extend(channels.writes)
        for at, size, value in batch:
            if record is not None:
                record.append((position, at, size, value))
            engine.write(at, size, value); writes += 1
        if commands.clock.ended and ended_at is None:
            ended_at = ticks
        if commands.clock.ended and not any(g.command for g in commands.gates) and not engine.audible():
            break
    info = dict(cue=cue, bank=bank, sequence=index, ticks=ticks, writes=writes, sequence_end_tick=ended_at,
                frames=len(frames),
                capped=ticks == len(tick_times))
    return frames, info


def save_wav(path, frames):
    with wave.open(str(path), 'wb') as out:
        out.setnchannels(2); out.setsampwidth(2); out.setframerate(44100)
        out.writeframes(b''.join(struct.pack('<hh', max(-32768, min(32767, l)), max(-32768, min(32767, r))) for l, r in frames))


def all_cues(mlt):
    return range(0x1d + len(next(b for b in inventory(mlt) if b['bank'] == 1)['sequences']))


def export_all(driver, mlt, out, cues=None, log=print):
    """Render cues to out/cueNNN.wav plus out/cues.json (per-cue info or the reason a cue is unsupported)."""
    import json
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    cold = cold_state(driver, mlt)
    manifest = {}
    for cue in (cues if cues is not None else all_cues(mlt)):
        try:
            frames, info = render_cue(driver, mlt, cue, cold)
        except (NotImplementedError, ValueError) as error:
            info, frames = dict(cue=cue, unsupported=str(error)), None
        if frames:
            save_wav(out / ('cue%03d.wav' % cue), frames)
        manifest[str(cue)] = info
        log(info)
    (out / 'cues.json').write_text(json.dumps(manifest, indent=1), encoding='utf-8')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('driver', type=Path)
    parser.add_argument('mlt', type=Path)
    parser.add_argument('out', type=Path)
    parser.add_argument('--cue', type=int, nargs='*')
    args = parser.parse_args()
    export_all(args.driver.read_bytes(), args.mlt.read_bytes(), args.out, args.cue or None)


if __name__ == '__main__':
    main()
