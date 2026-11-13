"""Compare the mobile music (Ogg, mono) with the Dreamcast CD tracks (WAV, stereo): which track is which, and how they differ.
Uses a coarse energy envelope + spectral-band envelope correlation. Development/analysis tool; reads the extraction cache."""
import glob, os, sys, numpy as np, soundfile as sf
cache = sys.argv[1] if len(sys.argv) > 1 else r'c:\Dev\ChuChu Rocket\local\cache\assets'
ogg = sorted(glob.glob(os.path.join(cache, 'ios', '*v1_1_2*', 'audio_song', '*.ogg')) or glob.glob(os.path.join(cache, 'ios', '*', 'audio_song', '*.ogg'))[:15])
if not ogg: ogg = sorted(glob.glob(os.path.join(cache, 'ios', '*', 'audio_song', '*.ogg')))[:15]
dcs = sorted(glob.glob(os.path.join(cache, 'dreamcast', 'audio', 'track*.wav')))
def feat(x, sr, hop=0.1):
    """mel-ish band energy envelope at 10 Hz (4 bands), z-scored."""
    n = int(sr * hop); frames = len(x) // n
    out = []
    for i in range(frames):
        seg = x[i * n:(i + 1) * n]; spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg))))
        f = np.fft.rfftfreq(len(seg), 1 / sr)
        out.append([np.log1p(spec[(f >= a) & (f < b)].sum()) for a, b in ((50, 250), (250, 1000), (1000, 4000), (4000, 12000))])
    a = np.array(out); return (a - a.mean(0)) / (a.std(0) + 1e-6)
def load_mono(p):
    x, sr = sf.read(p, dtype='float32', always_2d=True); return x.mean(1), sr
ofeat = {}
for p in ogg:
    x, sr = load_mono(p); ofeat[os.path.basename(p)] = (feat(x, sr), len(x) / sr, sr)
dfeat = {}
for p in dcs:
    x, sr = load_mono(p); dfeat[os.path.basename(p)] = (feat(x, sr), len(x) / sr, sr)
def best_offset(a, b):
    """max over lags of mean correlation of a within b (a shorter or equal)."""
    best = (-9, 0)
    if len(a) > len(b): a, b = b, a
    n = len(a)
    for lag in range(0, len(b) - n + 1, 2):
        c = float((a * b[lag:lag + n]).mean())
        if c > best[0]: best = (c, lag)
    return best
print('%-8s %7s | best DC track  corr   offset(s)  dc_len(s)  ratio' % ('mobile', 'len(s)'))
rows = []
for on, (of, olen, osr) in ofeat.items():
    scores = []
    for dn, (df, dlen, dsr) in dfeat.items():
        c, lag = best_offset(of[:300], df) if len(of) > 300 else best_offset(of, df)
        scores.append((c, dn, lag * 0.1 / 1, dlen))
    scores.sort(reverse=True)
    c, dn, lag, dlen = scores[0]
    rows.append((on, olen, dn, c, lag, dlen))
    print('%-8s %7.1f | %-14s %.3f  %8.1f  %9.1f  %.2f   (2nd: %s %.3f)' % (on, olen, dn, c, lag, dlen, dlen / olen, scores[1][1], scores[1][0]))
