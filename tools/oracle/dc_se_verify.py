"""Compare rendered SFX cues with the isolated Flycast captures made by dc_se_capture.py (development only; needs numpy).

usage: dc_se_verify.py <capture dir> <MANATEE.DRV> <CHU2_SE.MLT> [--cue N ...] [--json out.json]

Per cue, two independent checks against the original:
  dispatch  my native sequence/channel dispatch vs the ARM's AICA channel-register writes in the bus trace: every (register,
            width,value) in order; the first control word of a voice is compared only in KYONEX/KYONB, because its other bits keep what
            the voice held before.
  waveform  the voice renderer driven by the trace's own writes and times (so ARM latency is not part of this check) against
            cue.wav - base.wav. Pitch/amplitude-LFO phase is history dependent in the original (Flycast steps a channel's LFO only
            while it is enabled), so each LFO voice's phase is searched (0..255) over the first samples after its key-on.
Reports correlation, mean absolute error per channel (levels of 16-bit PCM) and the maximum error.
"""
import argparse
import collections
import csv
import json
import struct
import sys
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import dc_sfx_render as R

SEARCH_WINDOW = 3000


def read_wav(path):
    with wave.open(str(path)) as w:
        return np.frombuffer(w.readframes(w.getnframes()), '<i2').reshape(-1, 2).astype(np.int32)


def read_trace(path):
    with open(path, newline='') as f:
        return [(int(s), int(a, 16), int(w), int(v, 16)) for s, a, w, v in csv.reader(f)]


class Phases:
    """Per voice and key-on count LFO phase (default 0)."""
    def __init__(self):
        self.table = {}
        self.counts = {}

    def next(self, index):
        n = self.counts.get(index, 0)
        self.counts[index] = n + 1
        return self.table.get((index, n), 0)


class PhasedEngine(R.VoiceEngine):
    def __init__(self, ram, registers, phases):
        super().__init__(ram, registers, 0)
        self.phases = phases
        self.created = []                   # (voice, key-on count, sample position)
        self.position = 0

    def initial_phase(self, index):
        count = self.phases.counts.get(index, 0)
        self.created.append((index, count, self.position))
        self.phases.counts[index] = count + 1
        return self.phases.table.get((index, count), 0)

    def start_voice(self, index, previous):
        if previous is not None:
            self.created.append((index, self.phases.counts.get(index, 0), self.position))
        super().start_voice(index, previous)


def drive(ram, registers, writes, phases, start, end, stop_after=None):
    """Feed trace writes at their sample times; returns the mix over [start, end) and the engine."""
    engine = PhasedEngine(bytearray(ram), registers, phases)
    mix = np.zeros((end - start, 2), np.int64)
    cursor = start
    for sample, at, size, value in writes:
        if sample >= end:
            break
        if sample > cursor:
            block = np.array(engine.render(sample - cursor), np.int64).reshape(-1, 2) if engine.audible() else None
            if block is not None:
                mix[cursor - start:sample - start] = block
            cursor = sample
        engine.position = sample
        engine.write(at, size, value)
    if cursor < end:
        block = np.array(engine.render(end - cursor), np.int64).reshape(-1, 2) if engine.audible() else None
        if block is not None:
            mix[cursor - start:end - start] = block
    return np.clip(mix, -32768, 32767), engine


def lfo_voice(words):
    lfo = words[7]
    return bool(lfo & 7 or lfo >> 5 & 7)


def verify_cue(capture, cue, driver, mlt, cold):
    base, played = read_wav(capture / f'c{cue:03d}_base.wav'), read_wav(capture / f'c{cue:03d}_cue.wav')
    n = min(len(base), len(played))
    ref = played[:n] - base[:n]
    active = np.nonzero(np.abs(ref).max(axis=1))[0]
    result = dict(cue=cue)
    if not len(active):
        result['error'] = 'isolated capture is silent'
        return result
    first, last = int(active[0]), int(active[-1])
    trace = read_trace(capture / f'c{cue:03d}_bus.csv')
    window = [w for w in trace if first - 600 <= w[0] <= last + 400000]      # key-offs follow the audible end; the START run records nothing else
    channels_used = sorted({w[1] // 128 for w in window})
    result.update(original_samples=last - first + 1, original_peak=int(np.abs(ref).max()), voices=channels_used)
    # ---- dispatch: native writes vs the trace
    keyed = {at // 128 for _, at, size, value in window if at % 128 == 0 and value & 0x4000}   # only voices that key on in the window
    result['voices_keyed'] = sorted(keyed)
    record = []
    saved_regs = capture / f'c{cue:03d}_chan.bin'
    native_cold = (cold[0], saved_regs.read_bytes()[:0x8000]) if saved_regs.exists() else cold
    frames, info = R.render_cue(driver, mlt, cue, native_cold, record=record)
    native = [(at, size, value) for _, at, size, value in record]
    seen, expected = set(), []
    native_keyed = {at // 128 for at, size, value in native if at % 128 == 0 and value & 0x4000}
    for at, size, value in native:
        if at // 128 in native_keyed:    # the driver may pick other voice numbers than the original did (allocation depends on earlier sounds)
            expected.append((at, size, value))
    actual = [(at, size, value) for _, at, size, value in window if at // 128 in keyed]
    def mask(item, first_control):
        at, size, value = item
        if at % 128 == 0 and first_control:
            return at, size, value & 0xc000
        return at, size, value
    def normalize(rows):
        seen, out = set(), []
        for item in rows:
            voice = item[0] // 128
            first_control = item[0] % 128 == 0 and voice not in seen
            out.append(mask(item, first_control))
            if item[0] % 128 == 0:
                seen.add(voice)
        return out
    def key_events(rows, wanted, mask_on):
        return [(sample, at // 128) for sample, at, size, value in rows
                if at % 128 == 0 and value & 0xc000 == mask_on and at // 128 in wanted]
    for label, mask_on in (('key_on', 0xc000), ('key_off', 0x8000)):
        original = key_events(window, keyed, mask_on)
        native_events = key_events(record, keyed, mask_on)
        entry = dict(original=len(original), native=len(native_events))
        if len(original) == len(native_events) and original:
            offsets_o = [t - original[0][0] for t, _ in original]
            offsets_n = [t - native_events[0][0] for t, _ in native_events]
            diffs = [n - o for n, o in zip(offsets_n, offsets_o)]
            entry.update(max_abs_relative_error=max(abs(d) for d in diffs), mean_relative_error=sum(diffs) / len(diffs))
        result.setdefault('timing', {})[label] = entry
    def per_voice(rows):
        voices = {}
        for item in rows:
            voice = item[0] // 128
            if voice not in voices and item[0] % 128 != 0:
                continue                       # writes before the voice's first control write are history, not the cue
            voices.setdefault(voice, []).append(item)
        return {v: normalize(items) for v, items in voices.items()}
    def notes(voices):
        """Split each voice's writes into per-note segments (a pre-stop control write followed by the sample-address write starts one;
        the later key-off write ends it) so the comparison does not depend on which voice index the driver picked."""
        out = []
        for items in voices.values():
            segment = []
            for i, item in enumerate(items):
                starts = item[0] % 128 == 0 and not item[2] & 0x4000 and i + 1 < len(items) and items[i + 1][0] % 128 == 4
                if starts and segment:
                    out.append(tuple((at % 128, size, value) for at, size, value in segment))
                    segment = []
                if starts:       # the pre-stop write keeps whatever the voice held before (format, loop, address bits): only KYONEX/KYONB are the driver's
                    item = (item[0], item[1], item[2] & 0xc000)
                segment.append(item)
            if segment:
                out.append(tuple((at % 128, size, value) for at, size, value in segment))
        return sorted(out)
    a_voices, e_voices = per_voice(actual), per_voice(expected)
    a_notes, e_notes = notes(a_voices), notes(e_voices)
    original_notes, native_notes = collections.Counter(a_notes), collections.Counter(e_notes)
    result['dispatch_writes'] = dict(original_notes=len(a_notes), native_notes=len(e_notes),
                                     original=sum(len(n) for n in a_notes), native=sum(len(n) for n in e_notes),
                                     equal=original_notes == native_notes)
    if original_notes != native_notes:
        only_a = list((original_notes - native_notes).elements())
        only_e = list((native_notes - original_notes).elements())
        result['dispatch_writes']['unmatched'] = dict(original=len(only_a), native=len(only_e))
        if only_a and only_e:
            index = next((i for i, (p, q) in enumerate(zip(only_a[0], only_e[0])) if p != q), 0)
            result['dispatch_writes']['first_difference'] = dict(original=[hex(t) for t in only_a[0][index]], native=[hex(t) for t in only_e[0][index]])
    # ---- waveform
    ram, registers = cold
    saved = capture / f'c{cue:03d}_chan.bin'
    lfo_state = {}
    if saved.exists():
        data = saved.read_bytes()
        registers = data[:0x8000]            # the real AICA register file just before START (voices keep what the driver does not rewrite)
        for voice in range(64):              # sgc_if.cpp serialize(): LFO counter at +66, phase at +70 of each 72-byte channel record
            lfo_state[voice] = data[0x8000 + 72 * voice + 70]
        result['registers'] = 'captured'
    else:
        result['registers'] = 'cold (voices keep stale registers in the original: pitch may be missing)'
    ram = bytearray(ram)
    R.install_banks(ram, mlt)
    start, end = first - 700, last + 400
    window_audio = [w for w in window if w[0] < end]
    phases = Phases()
    for voice, phase in lfo_state.items():
        phases.table[(voice, 0)] = phase          # a channel's LFO only advances while it plays, so its phase at key-on is the saved one
    search = []
    mix, engine = drive(ram, registers, window_audio, phases, start, end)
    for voice, count, position in engine.created:
        if lfo_voice(engine.words[voice]) or True:
            search.append((voice, count, position))
    if not lfo_state:                                   # no saved state: search each voice's phase
        for voice, count, position in search:
            best = None
            lo, hi = max(start, position - 4), min(end, position + SEARCH_WINDOW)
            for phase in range(256):
                phases.table[(voice, count)] = phase
                phases.counts.clear()
                trial, _ = drive(ram, registers, window_audio, phases, start, hi)
                error = np.abs(trial[lo - start:hi - start] - ref[lo:hi]).sum()
                if best is None or error < best[0]:
                    best = (error, phase)
                if not lfo_voice(engine.words[voice]) and phase == 0:
                    break
            phases.table[(voice, count)] = best[1]
    phases.counts.clear()
    mix, engine = drive(ram, registers, window_audio, phases, start, end)
    compare = slice(0, end - start)
    x, y = mix.astype(float), ref[start:end].astype(float)
    result['waveform'] = dict(
        lfo_phases={f'{v}.{c}': phases.table.get((v, c), 0) for v, c, _ in search},
        corr=float(np.corrcoef(x[:, 0], y[:, 0])[0, 1]) if x[:, 0].std() and y[:, 0].std() else None,
        mean_abs_error=[float(np.abs(x[:, k] - y[:, k]).mean()) for k in (0, 1)],
        max_abs_error=int(np.abs(x - y).max()), rendered_active_samples=int(np.count_nonzero(np.abs(mix).max(axis=1))),
        original_active_samples=int(np.count_nonzero(np.abs(ref[start:end]).max(axis=1))))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('capture', type=Path)
    parser.add_argument('driver', type=Path)
    parser.add_argument('mlt', type=Path)
    parser.add_argument('--cue', type=int, nargs='*')
    parser.add_argument('--json', type=Path)
    args = parser.parse_args()
    driver, mlt = args.driver.read_bytes(), args.mlt.read_bytes()
    cold = R.cold_state(driver, mlt)
    cues = args.cue if args.cue else [int(p.name[1:4]) for p in sorted(args.capture.glob('c???_bus.csv'))]
    results = []
    for cue in cues:
        result = verify_cue(args.capture, cue, driver, mlt, cold)
        results.append(result)
        print(json.dumps(result), flush=True)
    if args.json:
        args.json.write_text(json.dumps(results, indent=1))


if __name__ == '__main__':
    main()
