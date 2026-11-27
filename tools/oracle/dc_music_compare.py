"""Align a headless recording to a decoded Dreamcast CD track and compare PCM.

Usage: dc_music_compare.py <recording.wav|stereo-s16.raw> <track.wav>
       [--skip seconds] [--seconds 4] [--gain 1] [--swap-reference]
Both files must be 44.1 kHz stereo signed 16-bit PCM. A .raw recording is
the port's CCR_AUDIO_CAPTURE output. FFT correlation finds the content;
full-rate refinement selects the sample offset. Strict parity uses only
the explicitly supplied gain, never a fitted gain. Fitted gains/residuals
are diagnostics. This verifies the selected window, not start/loop/fade
timing (repeated passages can have several equivalent offsets).
"""
import argparse
import json
from pathlib import Path
import wave
import numpy as np


def read(path):
    if Path(path).suffix.lower() == '.raw':
        raw = Path(path).read_bytes()
    else:
        with wave.open(str(path), 'rb') as w:
            if (w.getframerate(), w.getnchannels(), w.getsampwidth()) != (44100, 2, 2):
                raise ValueError('requires 44100 Hz stereo 16-bit PCM: ' + str(path))
            raw = w.readframes(w.getnframes())
    if len(raw) % 4: raise ValueError('incomplete stereo PCM frame')
    return np.frombuffer(raw, '<i2').reshape(-1, 2)


def window_energy(samples, count):
    sums = np.r_[0, np.cumsum(samples)]
    squares = np.r_[0, np.cumsum(samples * samples)]
    return squares[count:] - squares[:-count] - (sums[count:] - sums[:-count]) ** 2 / count


def compare(recording, track, skip=0, seconds=4, gain=1, swap_reference=False):
    record, source = read(recording), read(track)
    if swap_reference: source = source[:, ::-1]
    first, count = round(skip * 44100), round(seconds * 44100)
    if first < 0 or count < 1024 or first + count > len(record) or len(source) < count + 192:
        raise ValueError('comparison window outside recording/reference')
    query = record[first:first + count, 0].astype(float)
    step = 32
    coarse_source = source[:len(source) // step * step, 0].reshape(-1, step).mean(1)
    coarse_query = query[:len(query) // step * step].reshape(-1, step).mean(1)
    coarse_query -= coarse_query.mean()
    qenergy = np.sum(coarse_query ** 2)
    if qenergy < 1: raise ValueError('recording window is silent')
    size = 1 << (len(coarse_source) + len(coarse_query) - 2).bit_length()
    conv = np.fft.irfft(np.fft.rfft(coarse_source, size) * np.fft.rfft(coarse_query[::-1], size), size)
    dots = conv[len(coarse_query) - 1:len(coarse_source)]
    scores = dots / np.sqrt(np.maximum(window_energy(coarse_source, len(coarse_query)), 1) * qenergy)
    candidate = int(np.argmax(scores)) * step
    start = max(0, candidate - 96)
    patch = source[start:min(len(source), candidate + count + 96), 0].astype(float)
    centered = query - query.mean()
    scores = np.correlate(patch, centered, 'valid') / np.sqrt(np.maximum(window_energy(patch, count), 1) * np.sum(centered ** 2))
    offset = start + int(np.argmax(scores))
    reference = source[offset:offset + count].astype(float)
    actual = record[first:first + count].astype(float)
    errors = actual - reference * gain
    energy = np.sum(reference * reference, axis=0)
    if np.min(energy) < 1: raise ValueError('matched reference channel is silent')
    fitted = np.sum(reference * actual, axis=0) / energy
    residual = actual - reference * fitted
    result = dict(recording=str(recording), track=str(track), rate=44100,
                  recording_offset_frames=first, track_offset_frames=offset, frames=count,
                  correlation=[float(np.corrcoef(reference[:, ch], actual[:, ch])[0, 1]) for ch in range(2)],
                  expected_gain=gain, reference_swapped=swap_reference, mean_abs_error=np.abs(errors).mean(0).tolist(),
                  max_abs_error=np.abs(errors).max(0).tolist(),
                  samples_over_2=(np.abs(errors) > 2).sum(0).tolist(),
                  fitted_gain=fitted.tolist(), fitted_mean_abs_error=np.abs(residual).mean(0).tolist(),
                  fitted_max_abs_error=np.abs(residual).max(0).tolist())
    result['pass'] = bool(np.max(np.abs(errors)) <= 2)
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('recording'); p.add_argument('track')
    p.add_argument('--skip', type=float, default=0); p.add_argument('--seconds', type=float, default=4)
    p.add_argument('--gain', type=float, default=1)
    p.add_argument('--swap-reference', action='store_true', help='apply the original game CDDA routing (disc L->right, R->left)')
    args = p.parse_args()
    result = compare(**vars(args))
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['pass'] else 1)
