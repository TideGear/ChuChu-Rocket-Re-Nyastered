"""ChuChu Rocket! Re-Nyastered: one-shot asset extraction from the user's own game files.

usage: py -3.12 tools/extract_all.py --game-files "<folder with original files>" --cache "<output folder>"

Everything written to --cache is derived from the user's files and must never be committed or shared.
Writes <cache>/manifest.json: input files with SHA-256, and what was extracted from each.
"""
import argparse, glob, hashlib, json, os, plistlib, re, shutil, struct, subprocess, sys, tempfile, time, wave, zipfile
from pathlib import Path

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
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=dst.parent) as temporary:
        unpacked = Path(temporary, 'input')
        unpacked.mkdir()
        with zipfile.ZipFile(src) as z:
            z.extractall(unpacked)
        unpacked.replace(dst)
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
    root = ipa if os.path.isdir(ipa) else unzip(ipa, os.path.join(work, 'ios', safe + '-' + entry['sha256'][:16]))
    apps = [root] if str(root).lower().endswith('.app') else glob.glob(os.path.join(root, 'Payload', '*.app'))
    if not apps:
        entry['error'] = 'no .app in ipa'; return
    app = apps[0]
    plist = Path(app, 'Info.plist')
    if plist.is_file():
        with plist.open('rb') as stream:
            metadata = plistlib.load(stream)
        entry['version'] = metadata.get('CFBundleShortVersionString') or metadata.get('CFBundleVersion')
    exe = os.path.join(app, 'CCR')
    if not os.path.exists(exe):
        entry['error'] = 'no CCR executable'; return
    os.makedirs(os.path.join(work, 'ios'), exist_ok=True)
    thin = os.path.join(work, 'ios', safe + '.armv7')
    run_tool('thin.py', exe, thin)
    entry['extracted_assets'] = 'ios/' + safe
    entry['packs'] = {}
    for pack in ('ccrphn', 'ccrret', 'ccrpad'):
        if os.path.exists(os.path.join(app, pack)):
            out = os.path.join(assets, 'ios', safe, pack)
            r = extract_packs.extract(thin, app, pack, out)
            if r:
                entry['packs'][pack] = {'records': r[0], 'failed': r[1], 'textures': export_pngs(out, os.path.join(assets, 'ios', safe, pack + '_png'))}
                import extract_ios_locale                  # language packs: the HUD images with text are there (docs/ui_art.md, image id map)
                for lg in ('en', 'fr', 'de', 'es', 'it', 'ja'):
                    if os.path.exists(os.path.join(app, '%s_%s' % (pack, lg))):
                        try: extract_ios_locale.main(thin, app, pack, lg, os.path.join(assets, 'ios', safe, '%s_%s' % (pack, lg)))
                        except KeyError: pass
    for sub in ('song', 'sfx'):
        d = os.path.join(app, sub)
        if os.path.isdir(d):
            dst = os.path.join(assets, 'ios', safe, 'audio_' + sub)
            if not os.path.isdir(dst):
                shutil.copytree(d, dst)
            entry.setdefault('audio', {})[sub] = len(os.listdir(dst))

    if entry.get('version') == '1.0' and 'ccrpad' in entry['packs']:
        export_ipad_presentation(thin, Path(assets) / 'ios' / safe, Path(assets))


def export_ipad_presentation(thin, extracted, assets):
    from macho import Macho
    out = assets / 'ret_all'
    out.mkdir(exist_ok=True)
    pack = extracted / 'ccrpad'
    mach = Macho(thin)
    # CoreSettingsInit selects this 0x700-byte table for the iPad layout.
    address, size = 0xe81f8, 0x700
    for name, vm, _, offset, file_size in mach.segs:
        if name == '__TEXT' and vm <= address and address + size <= vm + file_size:
            start = offset + address - vm
            (assets / 'hd10_layout.bin').write_bytes(mach.d[start:start + size])
            break
    else:
        raise ValueError('iPad layout table is outside the executable text segment')
    run_tool('export_hd_geometry.py', pack, out, thin)
    run_tool('export_hd_images.py', thin, pack, out)
    run_tool('export_hd_locale.py', '', thin, pack, out)
    run_tool('export_tilemaps.py', pack, out)
    run_tool('export_pad_ui.py', extracted, out)


def do_apk(apk, work, assets, entry):
    stem = os.path.splitext(os.path.basename(apk))[0]
    safe = ''.join(c if c.isalnum() else '_' for c in stem)[:48]
    root = apk if os.path.isdir(apk) else unzip(apk, os.path.join(work, 'apk', safe + '-' + entry['sha256'][:16]))
    out = os.path.join(assets, 'android', safe)
    entry['log'] = run_tool('extract_android.py', root, out).strip().splitlines()[-6:]
    entry['textures'] = 0
    main = os.path.join(out, 'libccrjni', 'main')
    if os.path.isdir(main):
        entry['extracted_assets'] = Path(main).relative_to(assets).as_posix()
        entry['textures'] = export_pngs(main, os.path.join(out, 'main_png'))
        entry['phone_art'] = run_tool('export_android_ui.py', out, os.path.join(assets, 'ret_all')).strip().splitlines()
        run_tool('export_strings.py', os.path.dirname(main), os.path.join(out, 'strings.json'),
                 os.path.join(assets, 'strings'))
    for clip in sorted(Path(root, 'res', 'raw').glob('*.ogg')):
        if re.fullmatch(r'm\d{3}', clip.stem):
            name, directory = f'M{int(clip.stem[1:]):02d}.ogg', 'audio_song'
        elif re.fullmatch(r'[sj]\d{3}', clip.stem):
            prefix = 'J' if clip.stem[0] == 'j' else ''
            name, directory = prefix + clip.stem[1:] + '.ogg', 'audio_sfx'
        else:
            continue
        dst = Path(out, directory)
        dst.mkdir(exist_ok=True)
        shutil.copyfile(clip, dst / name)


def do_gba(src, work, assets, entry):
    import gba_stages
    rom_path = src
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
    d = src
    files = os.path.join(assets, 'dreamcast', 'files')
    if not os.path.isdir(files):
        run_tool('gdi_extract.py', d, files, 0)
    entry['files'] = sum(len(f) for _, _, f in os.walk(files))
    png = os.path.join(assets, 'dreamcast', 'png')
    if not os.path.isdir(png):
        run_tool('pvr2png.py', files, png)
    entry['png'] = len(glob.glob(os.path.join(png, '*.png')))
    prs_out = os.path.join(assets, 'dreamcast', 'prs')                  # every ENGLISH/*.PRS = PRS-compressed PVM texture archive (UI screens, model textures)
    if not os.path.isdir(prs_out):
        import prs as _prs
        for f in sorted(glob.glob(os.path.join(files, 'ENGLISH', '*.PRS'))): _prs.main(f, prs_out)
        run_tool('pvr2png.py', prs_out, os.path.join(assets, 'dreamcast', 'prs_png'))
    entry['prs_textures'] = len(glob.glob(os.path.join(prs_out, '*.pvr')))
    run_tool('export_dc_ui.py', os.path.join(assets, 'dreamcast', 'prs_png'),
             os.path.join(assets, 'ret_all'), png)
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
    for p in sorted(Path(d).glob('*')):
        match = re.search(r'track\s*(\d+)\)?\.bin$', p.name, re.I)
        if not match:
            continue
        n = int(match[1])
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


# These are the same two resources in the tested Dreamcast, Android and iOS
# releases. Hashes distinguish Battle from Challenge without record numbers.
BATTLE_MAPS = {
    'BTSTAGE25.DAT': 'b782205539abbe9cb377d3dce230612e9be9bccba289eb1cdd30f9761396bf62',
    'CHSTAGE25.DAT': 'f1736a8afaea5ba51ee425205e944734639115ddc6d8c42044791b28a42c6c5e',
}


def export_playable_stages(assets):
    from export_battle import export_maps
    from export_dc_solutions import main_slots, write_record
    root = Path(assets)
    puzzle_digest = 'e9ce95921a415328c4e2f8b79b38b8bf47a0b95af0526b1b70ad1f89149991df'
    candidates = [root / 'dreamcast' / 'files' / 'ENGLISH' / name for name in BATTLE_MAPS]
    for parent, pattern in (('ios', '*/*/index.json'), ('android', '*/*/main/index.json')):
        for index in sorted((root / parent).glob(pattern)):
            with index.open(encoding='utf-8') as stream:
                records = json.load(stream)['records']
            candidates.extend(index.with_name(f"{record['i']:04d}.bin")
                              for record in records if record['size'] in (11925, 38000))
    by_digest = {}
    for file in candidates:
        if file.is_file() and file.stat().st_size in (11925, 38000):
            by_digest.setdefault(sha256(file), file)
    sources = {}
    dc_puzzles = root / 'dreamcast' / 'files' / 'ENGLISH' / 'PZSTAGE100.DAT'
    if dc_puzzles.is_file() and dc_puzzles.stat().st_size == 153600:
        with (root / 'dreamcast_puzzles.bin').open('wb') as stream:
            stream.write(struct.pack('<I', 100))
            for stage, slot in enumerate(main_slots(dc_puzzles.read_bytes())):
                write_record(stream, 4, stage, slot)
        sources['dreamcast_puzzles'] = dc_puzzles.relative_to(root).as_posix()
    if puzzle_digest in by_digest:
        path = by_digest[puzzle_digest]
        data = path.read_bytes()
        with (root / 'mobile_puzzles.bin').open('wb') as stream:
            stream.write(struct.pack('<I', 100))
            for stage in range(100):
                record = data[stage * 380:(stage + 1) * 380]
                stream.write(struct.pack('<BBH', 5, 0, stage))
                stream.write(record[:108] + record[108:108 + 237])
                stream.write(record[0x15c:0x160])
                stream.write(record[0x160:0x175].ljust(32, b'\0'))
        sources['mobile_puzzles'] = path.relative_to(root).as_posix()
    if all(digest in by_digest for digest in BATTLE_MAPS.values()):
        paths = [by_digest[digest] for digest in BATTLE_MAPS.values()]
    # A Dreamcast release can have different maps. Preserve the original export
    # path for named and well-formed files from that disc.
    elif all(path.is_file() and path.stat().st_size == 11925 for path in candidates[:2]):
        paths = candidates[:2]
    else:
        paths = []
    if paths:
        export_maps(*paths, root / 'battle_stages.bin')
        sources['battle_stages'] = [p.relative_to(root).as_posix() for p in paths]
    return sources


def discover(root, work, prefix='', exclude=None):
    """Yield (kind, local path, original label) for packages and loose input."""
    for base, dirs, files in os.walk(root):
        dirs[:] = sorted(name for name in dirs if (Path(base) / name).resolve() != exclude)
        files.sort()
        folder = Path(base)
        label = prefix + folder.relative_to(root).as_posix()
        if folder.suffix.lower() == '.app' and 'CCR' in files:
            dirs.clear()
            yield 'ios', folder, label
            continue
        if 'AndroidManifest.xml' in files and (folder / 'res' / 'raw' / 'ccr0.png').is_file():
            dirs.clear()
            yield 'android', folder, label
            continue
        if any(re.search(r'track\s*0?3\)?\.bin$', name, re.I) for name in files):
            yield 'dreamcast', folder, label
        for name in files:
            path = folder / name
            suffix = path.suffix.lower()
            label = prefix + path.relative_to(root).as_posix()
            kind = {'.ipa': 'ios', '.apk': 'android', '.gba': 'gba', '.vmi': 'dlc', '.vms': 'dlc'}.get(suffix)
            if kind:
                yield kind, path, label
            elif suffix == '.zip':
                expanded = Path(work, 'zip', sha256(path))
                try:
                    unzip(path, expanded)
                except (OSError, ValueError, zipfile.BadZipFile, RuntimeError) as error:
                    yield 'error', path, (label, str(error))
                    continue
                yield from discover(expanded, work, label + '!')


def input_entry(kind, path, label):
    entry = {'kind': kind, 'file': label}
    if path.is_file():
        entry.update(bytes=path.stat().st_size, sha256=sha256(path))
    else:
        def included(candidate):
            if kind == 'dreamcast':
                return candidate.suffix.lower() in ('.bin', '.cue', '.gdi')
            return True
        entry['files'] = [{'name': p.relative_to(path).as_posix(), 'bytes': p.stat().st_size, 'sha256': sha256(p)}
                          for p in sorted(path.rglob('*')) if p.is_file() and included(p)]
    return entry


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--game-files', required=True)
    ap.add_argument('--cache', required=True)
    a = ap.parse_args()
    gf, cache = a.game_files, a.cache
    work, assets = os.path.join(cache, 'work'), os.path.join(cache, 'assets')
    os.makedirs(work, exist_ok=True); os.makedirs(assets, exist_ok=True)
    manifest = {'created': time.strftime('%Y-%m-%d %H:%M:%S'), 'inputs': []}
    actions = {'ios': do_ios, 'android': do_apk, 'gba': do_gba, 'dreamcast': do_dreamcast}
    for kind, path, label in discover(Path(gf), work, exclude=Path(cache).resolve()):
        if kind == 'error':
            manifest['inputs'].append({'kind': 'zip', 'file': label[0], 'error': label[1]})
            continue
        entry = input_entry(kind, path, label)
        print('[%s] %s' % (kind, entry['file']), flush=True)
        try:
            if kind == 'dlc':
                dst = Path(assets, 'dlc')
                dst.mkdir(exist_ok=True)
                shutil.copy2(path, dst)
            else:
                actions[kind](str(path), work, assets, entry)
        except Exception as e:
            entry['error'] = str(e)
            print('   ERROR:', e, flush=True)
        manifest['inputs'].append(entry)
    from export_sprites import export_base
    for layout, pack, version in (('retina_112', 'ccrret', '1.1.2'),
                                  ('retina_11', 'ccrret', '1.1'),
                                  ('ipad_hd10', 'ccrpad', '1.0'),
                                  ('iphone_102', 'ccrphn', '1.0.2'),
                                  ('iphone_10', 'ccrphn', '1.0'),
                                  ('android_phone', None, None)):
        for entry in manifest['inputs']:
            if pack and (entry.get('version') != version or pack not in entry.get('packs', {})):
                continue
            if not pack and (entry['kind'] != 'android' or 'extracted_assets' not in entry):
                continue
            source = Path(assets, entry['extracted_assets'])
            if pack:
                source /= pack
            try:
                export_base(source, Path(assets, 'ret_all'), layout)
            except (OSError, ValueError, KeyError, struct.error) as error:
                entry['base_graphics_error'] = str(error)
                print('   Base graphics export failed:', error, flush=True)
                continue
            manifest['base_graphics_source'] = source.relative_to(assets).as_posix()
            break
        if 'base_graphics_source' in manifest:
            break
    manifest['stage_sources'] = export_playable_stages(assets)
    dlc = Path(assets, 'dlc')
    if dlc.is_dir() and any(path.name.lower() == 'depuzzle.vms' for path in dlc.iterdir()):
        output = Path(assets, 'gba', 'dlc_stages.bin')
        output.parent.mkdir(exist_ok=True)
        try:
            run_tool('export_dlc_stages.py', output, dlc)
        except RuntimeError as error:
            manifest['dlc_export_error'] = str(error)
    sprites = ('r0930', 'r0447', 'r0503', 'r0484', 'r0729', 'r0726', 'r0749', 'r0023')
    manifest['base_graphics_available'] = all(Path(assets, 'ret_all', sprite + suffix).is_file()
                                              for sprite in sprites for suffix in ('.tex.bin', '.frames.bin'))
    puzzle = any(Path(assets, path).is_file() for path in
                 ('gba/gba_stages.bin', 'mobile_puzzles.bin', 'dreamcast_puzzles.bin'))
    battle = Path(assets, 'battle_stages.bin').is_file()
    manifest['playable_modes'] = [mode for mode, present in (('Puzzle', puzzle), ('Battle', battle))
                                  if present and manifest['base_graphics_available']]
    with open(os.path.join(cache, 'manifest.json'), 'w') as f:
        json.dump(manifest, f, indent=1)
    print('manifest written:', os.path.join(cache, 'manifest.json'))


if __name__ == '__main__':
    main()
