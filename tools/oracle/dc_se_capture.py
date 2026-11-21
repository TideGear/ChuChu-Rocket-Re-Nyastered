"""Record isolated original SFX cues from Flycast (development only; needs the user's disc image and BIOS, never shipped).

usage: dc_se_capture.py <pre-state> <out dir> [--cue N ...] [--workers K]

<pre-state> is a raw Flycast state of Options > General Settings with the "SE test" row selected and the value 0
(see docs/audio.md). For each cue the host resumes that state, steps the value with LEFT/RIGHT (the real screen wraps 0 -> 127),
then runs twice with the same timeline: once pressing START (1ST_READ FUN_8c0535de plays the selected cue) and once not.
Both runs are deterministic, so cue.wav - base.wav is the isolated cue; the ARM bus trace of the START run (channel-register
writes only, compacted) gives the original key-on times and parameters.
Outputs per cue N: cNNN_base.wav, cNNN_cue.wav, cNNN_bus.csv (sample,address,width,value in hex), cNNN_chan.bin (AICA registers and
channel runtime records one frame before START).
"""
import argparse
import csv
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / 'local/handoff-check/flycast-reference/flycast_libretro.dll'
DISC = ROOT / 'local/dc_ref/disc/ChuChu Rocket! (USA) (En,Ja,Fr,De,Es).cue'
HOST = ROOT / 'build/game/flyhost.exe'
SPACING = 6
LEAD = 30
TAIL_FRAMES = 1100
REGISTER_OFFSET = 2098137      # AICA register block in this core's raw state (dc_aica_state.inspect finds it from the bank headers)


def keys(cue, start):
    presses = cue if cue <= 64 else 128 - cue
    button = 'RIGHT' if cue <= 64 else 'LEFT'
    parts = [f'{button}@{LEAD + i * SPACING}-{LEAD + i * SPACING + 3}' for i in range(presses)]
    trigger = LEAD + presses * SPACING + 90
    if start:
        parts.append(f'START@{trigger}-{trigger + 3}')
    return ';'.join(parts) or 'A@1-1', trigger + TAIL_FRAMES


def run(state, out, cue, start, dump=False):
    key_string, frames = keys(cue, start)
    stem = out / f'c{cue:03d}_{"cue" if start else "base"}'
    env = dict(os.environ, FLYHOST_SYNC='1', FLYHOST_STATE=str(state), FLYHOST_WAV=str(stem) + '.wav')
    for name in ('FLY_DUMP', 'FLY_WATCH', 'FLYCAST_AICA_TRACE', 'FLYCAST_AICA_TICKS', 'FLYCAST_AICA_KEY_ON'):
        env.pop(name, None)
    raw = str(stem) + '.bus.raw'
    shots = ''
    if start:
        env['FLYCAST_AICA_BUS_TRACE'] = raw
        if dump:       # the AICA register file one frame before START: voices keep registers the driver does not rewrite (pitch, control bits)
            env['FLY_DUMP'] = '1'
            shots = str(frames - TAIL_FRAMES - 1)
    result = subprocess.run([str(HOST), str(CORE), 'local/dcsys', 'local/rocket-resume/save', str(DISC), str(frames), str(stem), shots, key_string],
                            cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if result.returncode != 0:
        raise RuntimeError(f'flyhost failed for cue {cue} (exit {result.returncode})')
    if start:
        with open(raw, newline='') as source, open(out / f'c{cue:03d}_bus.csv', 'w', newline='') as target:
            reader, writer = csv.reader(source), csv.writer(target)
            next(reader)
            for sample, order, op, address, width, value in reader:
                if op == 'W' and int(address, 16) < 0x2000:
                    writer.writerow((sample, address, width, value))
        os.remove(raw)
    if start and dump:
        state = Path(f'{stem}{frames - TAIL_FRAMES - 1:05d}.state')
        data = state.read_bytes()
        (out / f'c{cue:03d}_chan.bin').write_bytes(data[REGISTER_OFFSET:REGISTER_OFFSET + 0x8000 + 64 * 72])   # registers, then 64 channel runtime records (LFO counter/phase included)
        for extra in (state, state.with_suffix('.ram')):
            if extra.exists():
                extra.unlink()
    for leftover in out.glob(f'{stem.name}_*.bmp'):
        leftover.unlink()
    frames_csv = Path(str(stem) + '.wav.frames.csv')
    if frames_csv.exists():
        frames_csv.unlink()


def capture(state, out, cue):
    if (out / f'c{cue:03d}_bus.csv').exists() and (out / f'c{cue:03d}_base.wav').exists() and (out / f'c{cue:03d}_chan.bin').exists():
        return cue, 'cached'
    if not (out / f'c{cue:03d}_base.wav').exists():
        run(state, out, cue, False)
    run(state, out, cue, True, dump=True)
    return cue, 'ok'


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('state', type=Path)
    parser.add_argument('out', type=Path)
    parser.add_argument('--cue', type=int, nargs='*')
    parser.add_argument('--workers', type=int, default=2)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    cues = args.cue if args.cue else list(range(128))
    with ThreadPoolExecutor(args.workers) as pool:
        for cue, status in pool.map(lambda c: capture(args.state.resolve(), args.out.resolve(), c), cues):
            print(cue, status, flush=True)


if __name__ == '__main__':
    main()
