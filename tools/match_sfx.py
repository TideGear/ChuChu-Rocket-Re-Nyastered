"""Match decoded Dreamcast samples (tools/mlt_samples.py output) to the mobile effects by amplitude-envelope correlation, trying several playback rates for each Dreamcast sample.
No listening: both signals are reduced to a 100 Hz RMS envelope, time-aligned by cross-correlation (lags within +-0.15 s), and compared with Pearson correlation.
usage: match_sfx.py <dc wav dir> <mobile audio_sfx dir>"""
import glob, os, struct, sys, wave
import numpy as np

def read_wav(p):
    w = wave.open(p, 'rb'); n = w.getnframes(); d = np.frombuffer(w.readframes(n), dtype='<i2').astype(np.float64); return d, w.getframerate()

def read_ogg(p):
    from stb_vorbis_py import decode   # optional; fall back to ffmpeg-less decode below
    return decode(p)

def decode_ogg(p):
    try:
        import soundfile as sf
        d, r = sf.read(p, dtype='int16'); return d.astype(np.float64), r
    except Exception:
        pass
    import subprocess, tempfile
    out = os.path.join(tempfile.gettempdir(), 'ccr_tmp.wav')
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', p, out], check=True)
    return read_wav(out)

def env(x, rate, hz=100):
    step = max(1, int(rate / hz)); n = len(x) // step
    return np.sqrt((x[:n * step].reshape(n, step) ** 2).mean(axis=1)) if n else np.zeros(1)

def corr(a, b):
    best = -1
    for lag in range(-15, 16):
        x = a[max(0, lag):]; y = b[max(0, -lag):]; m = min(len(x), len(y))
        if m < 20: continue
        x = x[:m]; y = y[:m]
        if x.std() < 1e-9 or y.std() < 1e-9: continue
        c = float(np.corrcoef(x, y)[0, 1]); best = max(best, c)
    return best

def main(dcdir, mobdir):
    mob = {}
    for f in sorted(glob.glob(os.path.join(mobdir, '*.ogg'))):
        try: d, r = decode_ogg(f); mob[os.path.basename(f)[:-4]] = env(d, r)
        except Exception as e: print('cannot decode', f, e); return
    for f in sorted(glob.glob(os.path.join(dcdir, 'dc_*.wav'))):
        d, r = read_wav(f); res = []
        for rate in (8000, 11025, 16000, 22050, 32000, 44100):
            e = env(d, rate)
            for k, m in mob.items():
                if abs(len(e) - len(m)) > 0.06 * max(len(e), len(m)): continue
                c = corr(e, m); res.append((c, rate, k))
        res.sort(reverse=True)
        print(os.path.basename(f), [('%.3f' % c, r, k) for c, r, k in res[:2]])

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
