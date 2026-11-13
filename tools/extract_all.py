"""ChuChu Rocket! Re-Nyastered: one-shot asset extraction from the user's own game files.

usage: py -3.12 tools/extract_all.py --game-files "<folder with iOS/Android/GBA/Dreamcast subfolders>" --cache "<output folder>"

Everything written to --cache is derived from the user's files and must never be committed or shared.
Writes <cache>/manifest.json: input files with SHA-256, and what was extracted from each.
"""
import argparse, glob, hashlib, json, os, re, shutil, struct, subprocess, sys, time, wave, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
PY = [sys.executable]


def sha256(path, chunk=1 << 22):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(chunk), b''):
            h.update(b)
    return h.hexdigest()


def unzip(src, dst):
    if os.path.isdir(dst) and os.listdir(dst):
        return dst
    os.makedirs(dst, exist_ok=True)
    with zipfile.ZipFile(src) as z:
        z.extractall(dst)
    return dst


def run_tool(script, *args):
    r = subprocess.run(PY + [os.path.join(HERE, script)] + [str(a) for a in args], capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError('%s failed: %s' % (script, (r.stderr or r.stdout)[-400:]))
    return r.stdout


def export_pngs(pack_dir, png_dir):
    import textures as T
    os.makedirs(png_dir, exist_ok=True)
    ts = T.textures(pack_dir)
    for k, t in enumerate(ts):
        T.to_image(t).save(os.path.join(png_dir, '%03d_rec%04d_%dx%d.png' % (k, t['rec'], t['w'], t['h'])))
    return len(ts)


def do_ios(ipa, work, assets, entry):
    import extract_packs
    stem = os.path.splitext(os.path.basename(ipa))[0]
    safe = ''.join(c if c.isalnum() else '_' for c in stem)[:48]
    root = unzip(ipa, os.path.join(work, 'ios', safe))
    apps = glob.glob(os.path.join(root, 'Payload', '*.app'))
    if not apps:
        entry['error'] = 'no .app in ipa'; return
    app = apps[0]
    exe = os.path.join(app, 'CCR')
    if not os.path.exists(exe):
        entry['error'] = 'no CCR executable'; return
    thin = os.path.join(work, 'ios', safe + '.armv7')
    run_tool('thin.py', exe, thin)
    entry['packs'] = {}
    for pack in ('ccrphn', 'ccrret', 'ccrpad'):
        if os.path.exists(os.path.join(app, pack)):
            out = os.path.join(assets, 'ios', safe, pack)
            r = extract_packs.extract(thin, app, pack, out)
            if r:
                entry['packs'][pack] = {'records': r[0], 'failed': r[1], 'textures': export_pngs(out, os.path.join(assets, 'ios', safe, pack + '_png'))}
    for sub in ('song', 'sfx'):
        d = os.path.join(app, sub)
        if os.path.isdir(d):
            dst = os.path.join(assets, 'ios', safe, 'audio_' + sub)
            if not os.path.isdir(dst):
                shutil.copytree(d, dst)
            entry.setdefault('audio', {})[sub] = len(os.listdir(dst))


def do_apk(apk, work, assets, entry):
    stem = os.path.splitext(os.path.basename(apk))[0]
    safe = ''.join(c if c.isalnum() else '_' for c in stem)[:48]
    root = unzip(apk, os.path.join(work, 'apk', safe))
    out = os.path.join(assets, 'android', safe)
    entry['log'] = run_tool('extract_android.py', root, out).strip().splitlines()[-6:]
    entry['textures'] = 0
    main = os.path.join(out, 'libccrjni', 'main')
    if os.path.isdir(main):
        entry['textures'] = export_pngs(main, os.path.join(out, 'main_png'))


def do_gba(src, work, assets, entry):
    import gba_stages
    rom_path = src
    if src.lower().endswith('.zip'):
        d = unzip(src, os.path.join(work, 'gba'))
        roms = glob.glob(os.path.join(d, '*.gba'))
        if not roms:
            entry['error'] = 'no .gba in zip'; return
        rom_path = roms[0]
    gba_stages.ROM = rom_path
    rom = open(rom_path, 'rb').read()
    entry['rom_sha256'] = sha256(rom_path)
    entry['main_stages'] = len(gba_stages.main_records(rom))
    entry['user_stages'] = len(gba_stages.user_records(rom))
    out = os.path.join(assets, 'gba'); os.makedirs(out, exist_ok=True)
    import export_testdata
    export_testdata.G.ROM = rom_path
    export_testdata.main(os.path.join(out, 'gba_stages.bin'))


def do_dreamcast(src, work, assets, entry):
    d = unzip(src, os.path.join(work, 'dc'))
    files = os.path.join(assets, 'dreamcast', 'files')
    if not os.path.isdir(files):
        run_tool('gdi_extract.py', d, files, 0)
    entry['files'] = sum(len(f) for _, _, f in os.walk(files))
    png = os.path.join(assets, 'dreamcast', 'png')
    if not os.path.isdir(png):
        run_tool('pvr2png.py', files, png)
    entry['png'] = len(glob.glob(os.path.join(png, '*.png')))
    models = os.path.join(assets, 'dreamcast', 'models')
    if not os.path.isdir(models):
        import dc_models
        dc_models.main(os.path.join(files, '1ST_READ.BIN'), models)
    entry['models'] = len(glob.glob(os.path.join(models, '*.obj')))
    objects = os.path.join(assets, 'dreamcast', 'objects')
    if not os.path.isdir(objects):
        import dc_objects
        dc_objects.main(os.path.join(files, '1ST_READ.BIN'), objects)
    entry['objects'] = len(glob.glob(os.path.join(objects, 'obj_*.obj')))
    # CD audio tracks 04..18 (raw 16-bit stereo 44.1 kHz) -> WAV
    audio = os.path.join(assets, 'dreamcast', 'audio'); os.makedirs(audio, exist_ok=True)
    wavs = []
    for p in sorted(glob.glob(os.path.join(d, '*Track *.bin'))):
        n = int(re.search(r'Track (\d+)', p).group(1))
        if n == 1 or n == 3 or n == 19:
            continue                                              # data tracks
        out = os.path.join(audio, 'track%02d.wav' % n)
        if not os.path.exists(out):
            with open(p, 'rb') as f, wave.open(out, 'wb') as w:
                w.setnchannels(2); w.setsampwidth(2); w.setframerate(44100)
                while True:
                    b = f.read(1 << 20)
                    if not b: break
                    w.writeframes(b)
        wavs.append(os.path.basename(out))
    entry['audio_tracks'] = wavs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--game-files', required=True)
    ap.add_argument('--cache', required=True)
    a = ap.parse_args()
    gf, cache = a.game_files, a.cache
    work, assets = os.path.join(cache, 'work'), os.path.join(cache, 'assets')
    os.makedirs(work, exist_ok=True); os.makedirs(assets, exist_ok=True)
    manifest = {'created': time.strftime('%Y-%m-%d %H:%M:%S'), 'inputs': []}
    jobs = []
    for p in sorted(glob.glob(os.path.join(gf, '**', '*'), recursive=True)):
        if not os.path.isfile(p): continue
        low = p.lower()
        if low.endswith('.ipa'): jobs.append(('ios', p, do_ios))
        elif low.endswith('.apk'): jobs.append(('android', p, do_apk))
        elif low.endswith('.gba') or ('game boy advance' in low and low.endswith('.zip')): jobs.append(('gba', p, do_gba))
        elif 'dreamcast' in low and low.endswith('.zip'): jobs.append(('dreamcast', p, do_dreamcast))
    dlc_dir = os.path.join(gf, 'Dreamcast', 'DLC')
    for kind, p, fn in jobs:
        entry = {'kind': kind, 'file': os.path.relpath(p, gf), 'bytes': os.path.getsize(p)}
        print('[%s] %s' % (kind, entry['file']), flush=True)
        entry['sha256'] = sha256(p)
        try:
            fn(p, work, assets, entry)
        except Exception as e:
            entry['error'] = str(e)
            print('   ERROR:', e, flush=True)
        manifest['inputs'].append(entry)
    if os.path.isdir(dlc_dir):
        dst = os.path.join(assets, 'dlc'); os.makedirs(dst, exist_ok=True)
        e = {'kind': 'dlc', 'file': os.path.relpath(dlc_dir, gf), 'files': []}
        for p in sorted(glob.glob(os.path.join(dlc_dir, '*'))):
            shutil.copy2(p, dst); e['files'].append({'name': os.path.basename(p), 'sha256': sha256(p)})
        manifest['inputs'].append(e)
    with open(os.path.join(cache, 'manifest.json'), 'w') as f:
        json.dump(manifest, f, indent=1)
    print('manifest written:', os.path.join(cache, 'manifest.json'))


if __name__ == '__main__':
    main()
