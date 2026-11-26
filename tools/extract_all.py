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


def bios_candidates(game_files):
    """Find optional BIOS files beside a selected descriptor or in a game-files folder."""
    source = Path(game_files)
    roots = [source.parent] if source.is_file() else [source]
    candidates = set()
    for root in roots:
        candidates.update(root.glob('*.bin'))
        candidates.update(root.glob('*/*.bin'))
    return sorted(candidates)


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


def clear_dreamcast_cache(assets):
    """Remove generated Dreamcast outputs before rebuilding, without touching saves or mobile exports."""
    root = Path(assets)
    dreamcast = root / 'dreamcast'
    for name in ('files', 'png', 'prs', 'prs_png', 'models', 'objects', 'audio', 'sfx', 'models.bin'):
        path = dreamcast / name
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()
    ret = root / 'ret_all'
    if ret.is_dir():
        for path in ret.glob('dc_*'):
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
        for name in ('dlogo.tex.bin', 'dlogo.frames.bin', 'dpress.tex.bin', 'dpress.frames.bin',
                     'dc_assets_version.txt'):
            path = ret / name
            if path.exists():
                path.unlink()


def clear_derived_stage_packs(assets):
    """Discard generated stage packs so the final export reflects the current extracted sources."""
    for name in ('battle_stages.bin', 'dreamcast_puzzles.bin', 'mobile_puzzles.bin'):
        path = Path(assets, name)
        if path.exists():
            path.unlink()


def chd_scratch(work):
    """Folder for the decoded tracks of a CHD; removed once its CD audio is exported."""
    return Path(work, 'chd-tracks')


def refresh_dreamcast_files(src, work, assets):
    """Extract first, then replace the cached Dreamcast tree only after disc parsing succeeds."""
    import gdi_extract
    Path(work).mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='dc-extract-', dir=work) as staged:
        if Path(src).suffix.lower() == '.chd':
            scratch = chd_scratch(work)
            if scratch.exists():
                shutil.rmtree(scratch)
            tracks = gdi_extract.extract(src, staged, 0, scratch)
        else:
            tracks = gdi_extract.extract(src, staged, 0)
        clear_dreamcast_cache(assets)
        files = Path(assets, 'dreamcast', 'files')
        files.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(staged, files)
    return tracks, str(files)


def publish_dc_asset_version(assets, entry):
    sfx_manifest = Path(assets, 'dreamcast', 'sfx', 'cues.json')
    if (not entry.get('model_pack') or entry.get('model_pack_error') or entry.get('sfx_error') or
            not sfx_manifest.is_file()):
        return False
    version = Path(assets, 'ret_all', 'dc_assets_version.txt')
    version.parent.mkdir(parents=True, exist_ok=True)
    temporary = version.with_suffix('.tmp')
    temporary.write_text('8', encoding='ascii')   # 8: the staff roll sheet (dc_staffroll); 7: sky model; 6: the Puzzle focus ring model (focus_ring) in models.bin
    os.replace(temporary, version)
    return True


def do_dreamcast(src, work, assets, entry):
    try:
        _do_dreamcast(src, work, assets, entry)
    finally:
        if Path(src).suffix.lower() == '.chd' and chd_scratch(work).exists():
            shutil.rmtree(chd_scratch(work), ignore_errors=True)


def _do_dreamcast(src, work, assets, entry):
    d = Path(src)
    tracks, files = refresh_dreamcast_files(d, work, assets)
    entry['extracted_file_count'] = sum(len(f) for _, _, f in os.walk(files))
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
    # The other disc languages: each folder holds the same 54 PRS archives and loose PVRs with that language's text; the app loads ret_all/dc_loc_<xx> for its language
    # (Italian has no folder and keeps English).
    for folder, code in (('FRENCH', 'fr'), ('GERMAN', 'de'), ('SPANISH', 'es'), ('JAPANIESE', 'ja')):
        if not os.path.isdir(os.path.join(files, folder)): continue
        lang_prs = os.path.join(assets, 'dreamcast', 'prs_' + code)
        if not os.path.isdir(lang_prs):
            import prs as _prs
            for f in sorted(glob.glob(os.path.join(files, folder, '*.PRS'))): _prs.main(f, lang_prs)
            run_tool('pvr2png.py', lang_prs, os.path.join(assets, 'dreamcast', 'prs_png_' + code))
        run_tool('export_dc_ui.py', os.path.join(assets, 'dreamcast', 'prs_png_' + code),
                 os.path.join(assets, 'ret_all', 'dc_loc_' + code), png, folder)
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
    try:   # the 3D character models and their textures in one file the app loads (dreamcast/models.bin)
        import export_dc_models
        export_dc_models.main(os.path.join(assets, 'dreamcast'), os.path.join(files, '1ST_READ.BIN'))
        entry['model_pack'] = True
    except Exception as error:
        entry['model_pack_error'] = str(error)
    # CD audio tracks 04..18 (raw 16-bit stereo 44.1 kHz) -> WAV
    audio = os.path.join(assets, 'dreamcast', 'audio'); os.makedirs(audio, exist_ok=True)
    wavs = []
    if tracks:
        for track in tracks:
            n = track.number
            if track.kind != 0 or n in (1, 2, 3, 19):
                continue
            if track.sector_size not in (2352, 2448):
                entry.setdefault('warnings', []).append('audio track %d has unsupported %d-byte sectors' % (n, track.sector_size))
                continue
            out = os.path.join(audio, 'track%02d.wav' % n)
            if not os.path.exists(out):
                with track.path.open('rb') as f, wave.open(out, 'wb') as w:
                    w.setnchannels(2); w.setsampwidth(2); w.setframerate(44100)
                    f.seek(track.offset * track.sector_size)
                    for _ in range(track.sectors):
                        sector = f.read(track.sector_size)
                        if len(sector) != track.sector_size:
                            raise IOError('short read in GDI audio track %d' % n)
                        w.writeframesraw(sector[:2352])
            wavs.append(os.path.basename(out))
    else:
        for p in sorted(d.glob('*')) if d.is_dir() else []:
            match = re.search(r'track\s*(\d+)\)?\.bin$', p.name, re.I)
            if not match:
                continue
            n = int(match[1])
            if n == 1 or n == 3 or n == 19:
                continue                                              # data tracks
            out = os.path.join(audio, 'track%02d.wav' % n)
            if not os.path.exists(out):
                with p.open('rb') as f, wave.open(out, 'wb') as w:
                    w.setnchannels(2); w.setsampwidth(2); w.setframerate(44100)
                    while True:
                        b = f.read(1 << 20)
                        if not b: break
                        w.writeframes(b)
            wavs.append(os.path.basename(out))
    entry['audio_tracks'] = wavs
    # sound effects: the disc's own driver and sound bank rendered to one WAV per cue (tools/dc_sfx_render.py, docs/audio.md)
    sfx = os.path.join(assets, 'dreamcast', 'sfx')
    drv, mlt = os.path.join(files, 'ENGLISH', 'MANATEE.DRV'), os.path.join(files, 'ENGLISH', 'CHU2_SE.MLT')
    if os.path.exists(drv) and os.path.exists(mlt):
        try:
            import dc_sfx_render
            if not os.path.exists(os.path.join(sfx, 'cues.json')):
                manifest = dc_sfx_render.export_all(open(drv, 'rb').read(), open(mlt, 'rb').read(), sfx, log=lambda info: None)
                entry['sfx_cues'] = sum(1 for m in manifest.values() if 'frames' in m)
                entry['sfx_unsupported'] = [int(k) for k, m in manifest.items() if 'unsupported' in m]
            # The Japanese Dreamcast bank keeps the same sequence events but uses different bank-1 instruments/samples.
            # Bank 0 differs only for cue 24; render only those known language-specific cues to avoid duplicate assets.
            ja_mlt = os.path.join(files, 'JAPANIESE', 'CHU2_SE.MLT')
            ja_drv = os.path.join(files, 'JAPANIESE', 'MANATEE.DRV')
            ja_manifest = os.path.join(sfx, 'ja', 'cues.json')
            if os.path.exists(ja_drv) and os.path.exists(ja_mlt) and not os.path.exists(ja_manifest):
                cues = [24, *range(29, 128)]
                manifest = dc_sfx_render.export_all(open(ja_drv, 'rb').read(), open(ja_mlt, 'rb').read(),
                                                    os.path.join(sfx, 'ja'), cues=cues, log=lambda info: None)
                entry['sfx_ja_cues'] = sum(1 for m in manifest.values() if 'frames' in m)
        except Exception as error:
            entry['sfx_error'] = str(error)
    # Publish only after all Dreamcast-derived assets, including the model and SFX packs, completed.
    publish_dc_asset_version(assets, entry)


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
    # Per-language stage titles (the Puzzle hint text, slot bytes 0x1eb..0x200, Shift-JIS on the Japanese disc folder): 100 x 32 bytes each.
    for folder, code in (('ENGLISH', 'en'), ('FRENCH', 'fr'), ('GERMAN', 'de'), ('SPANISH', 'es'), ('JAPANIESE', 'ja')):
        lang_puzzles = root / 'dreamcast' / 'files' / folder / 'PZSTAGE100.DAT'
        if lang_puzzles.is_file() and lang_puzzles.stat().st_size == 153600:
            data = lang_puzzles.read_bytes()
            with (root / f'dreamcast_titles_{code}.bin').open('wb') as stream:
                for k in range(100):
                    stream.write(data[k * 1536 + 640 + 0x1eb:k * 1536 + 640 + 0x200].split(b'\0')[0].ljust(32, b'\0'))
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
    root = Path(root)
    if root.resolve() == exclude:
        return
    if root.is_file():
        suffix = root.suffix.lower()
        if suffix in ('.gdi', '.cue', '.chd'):
            yield 'dreamcast', root, prefix + root.name
        elif suffix == '.zip':
            expanded = Path(work, 'zip', sha256(root))
            try:
                unzip(root, expanded)
            except (OSError, ValueError, zipfile.BadZipFile, RuntimeError) as error:
                yield 'error', root, (prefix + root.name, str(error))
                return
            yield from discover(expanded, work, prefix + root.name + '!', exclude)
        elif suffix in ('.ipa', '.apk', '.gba', '.vmi', '.vms'):
            kind = {'.ipa': 'ios', '.apk': 'android', '.gba': 'gba',
                    '.vmi': 'dlc', '.vms': 'dlc'}[suffix]
            yield kind, root, prefix + root.name
        return
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
        gdis = [name for name in files if Path(name).suffix.lower() == '.gdi']
        cues = [name for name in files if Path(name).suffix.lower() == '.cue']
        chds = [name for name in files if Path(name).suffix.lower() == '.chd']
        numbered = any(re.search(r'track\s*0?3\)?\.bin$', name, re.I) for name in files)
        descriptors = gdis + cues + chds
        if len(descriptors) > 1 or (chds and numbered):
            path = folder / descriptors[0]
            message = 'multiple Dreamcast images in one folder; select one .gdi/.cue/.chd file or separate the dumps'
            yield 'error', path, (prefix + path.relative_to(root).as_posix(), message)
        elif descriptors:
            path = folder / descriptors[0]
            yield 'dreamcast', path, prefix + path.relative_to(root).as_posix()
        elif numbered:
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
        if kind == 'dreamcast' and path.suffix.lower() in ('.gdi', '.cue'):
            import gdi_extract
            tracks = gdi_extract.parse_gdi(path) if path.suffix.lower() == '.gdi' else gdi_extract.parse_cue(path)
            entry['tracks'] = [{'number': track.number, 'lba': track.lba, 'type': track.kind,
                                'sector_size': track.sector_size, 'offset': track.offset,
                                'file': track.path.name, 'bytes': track.path.stat().st_size,
                                'sha256': sha256(track.path)} for track in tracks]
            if any(track.path.suffix.lower() == '.chd' for track in tracks):
                raise ValueError('CHD-compressed GDI tracks are not supported; select the .chd image itself or raw GDI tracks.')
        elif kind == 'dreamcast' and path.suffix.lower() == '.chd':
            import chd_reader
            entry['chd'] = chd_reader.describe(path)
            if entry['chd'].get('unsupported_codecs'):
                raise ValueError('CHD uses codec %s, which setup cannot decode; recompress with chdman createcd '
                                 'default codecs (cdlz,cdzl,cdfl)' % ', '.join(entry['chd']['unsupported_codecs']))
    else:
        def included(candidate):
            if kind == 'dreamcast':
                return candidate.suffix.lower() in ('.bin', '.cue', '.gdi', '.raw')
            return True
        entry['files'] = [{'name': p.relative_to(path).as_posix(), 'bytes': p.stat().st_size, 'sha256': sha256(p)}
                          for p in sorted(path.rglob('*')) if p.is_file() and included(p)]
    return entry


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--game-files', required=True)
    ap.add_argument('--cache', required=True)
    ap.add_argument('--exclude-cache', type=Path, help='existing cache to skip when extracting into staging')
    a = ap.parse_args()
    gf, cache = a.game_files, a.cache
    work, assets = os.path.join(cache, 'work'), os.path.join(cache, 'assets')
    os.makedirs(work, exist_ok=True); os.makedirs(assets, exist_ok=True)
    clear_derived_stage_packs(assets)
    manifest = {'created': time.strftime('%Y-%m-%d %H:%M:%S'), 'game_files': os.path.abspath(gf), 'inputs': []}   # game_files: lets the game offer to refresh an out-of-date cache from the same originals
    actions = {'ios': do_ios, 'android': do_apk, 'gba': do_gba, 'dreamcast': do_dreamcast}
    for kind, path, label in discover(Path(gf), work, exclude=(a.exclude_cache or Path(cache)).resolve()):
        if kind == 'error':
            manifest['inputs'].append({'kind': 'zip', 'file': label[0], 'error': label[1]})
            continue
        try:
            entry = input_entry(kind, path, label)
        except Exception as error:
            entry = {'kind': kind, 'file': label, 'error': str(error)}
            manifest['inputs'].append(entry)
            print('   ERROR:', error, flush=True)
            continue
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
    # Optional: a Dreamcast BIOS image the user placed with the game files supplies the ROM font the original draws its clocks and hints with (never shipped).
    import export_dc_bios_font
    for candidate in bios_candidates(gf):
        try:
            if candidate.stat().st_size == 2097152 and export_dc_bios_font.is_bios(candidate.read_bytes()):
                export_dc_bios_font.main(str(candidate), str(Path(assets, 'ret_all')), str(assets))
                manifest['dreamcast_bios_font'] = candidate.name
                print('[bios] ROM font exported from', candidate.name, flush=True)
                break
        except OSError:
            continue
    dlc = Path(assets, 'dlc')
    if dlc.is_dir() and any(path.name.lower() == 'depuzzle.vms' for path in dlc.iterdir()):
        output = Path(assets, 'gba', 'dlc_stages.bin')
        output.parent.mkdir(exist_ok=True)
        try:
            run_tool('export_dlc_stages.py', output, dlc)
        except RuntimeError as error:
            manifest['dlc_export_error'] = str(error)
    sprites = ('r0930', 'r0447', 'r0503', 'r0484', 'r0729', 'r0726', 'r0749', 'r0023')
    mobile_graphics = all(Path(assets, 'ret_all', sprite + suffix).is_file()
                          for sprite in sprites for suffix in ('.tex.bin', '.frames.bin'))
    dreamcast_graphics = Path(assets, 'dreamcast', 'models.bin').is_file()   # the disc's 3D model pack (cats, mice, rockets, floor, walls) lets the app run from a Dreamcast image alone
    manifest['base_graphics_available'] = mobile_graphics or dreamcast_graphics
    manifest['graphics_source'] = 'mobile' if mobile_graphics else ('dreamcast' if dreamcast_graphics else 'none')
    puzzle = any(Path(assets, path).is_file() for path in
                 ('gba/gba_stages.bin', 'mobile_puzzles.bin', 'dreamcast_puzzles.bin'))
    battle = Path(assets, 'battle_stages.bin').is_file()
    challenge = False
    if battle:
        stage_data = Path(assets, 'battle_stages.bin').read_bytes()
        if len(stage_data) >= 4:
            count = struct.unpack_from('<I', stage_data)[0]
            if len(stage_data) == 4 + count * 381:
                challenge_stages = {struct.unpack_from('<H', stage_data, 6 + i * 381)[0]
                                    for i in range(count) if stage_data[4 + i * 381] == 3}
                challenge = set(range(25)).issubset(challenge_stages)
    manifest['playable_modes'] = [mode for mode, present in
                                  (('Puzzle', puzzle), ('Battle', battle), ('Stage Challenge', challenge))
                                  if present and manifest['base_graphics_available']]
    with open(os.path.join(cache, 'manifest.json'), 'w') as f:
        json.dump(manifest, f, indent=1)
    print('manifest written:', os.path.join(cache, 'manifest.json'))


if __name__ == '__main__':
    main()
