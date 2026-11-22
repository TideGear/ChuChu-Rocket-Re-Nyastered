#!/usr/bin/env python3
"""Windowless asset extraction for launchers (RecompLauncher "prepare" step) on Linux and macOS (tools/prepare.ps1 does the same on Windows).
Extracts assets from YOUR original game files into the data folder; never changes your original files.
usage: prepare.py --game-files <folder with your original files, loose or ZIP (or one file in it)> [--cache <folder>] [--download-python]
--download-python: when Pillow is missing, create a private virtual environment in the data folder and install Pillow into it (needs python3-venv and internet).
Prints "progress <0..1> <text>" lines; exits 0 when the cache holds playable stage data, 1 otherwise.
Needs Python 3.10+ and Pillow (python3 -m pip install pillow, or your distribution's python3-pil / python-pillow package)."""
import argparse, json, os, shutil, subprocess, sys, uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent

def default_cache():
    if sys.platform == 'darwin': return Path.home() / 'Library' / 'Application Support' / 'ChuChuRocketReNyastered'
    base = os.environ.get('XDG_CONFIG_HOME') or str(Path.home() / '.config')   # same folder as the launcher's {config}
    return Path(base) / 'ChuChuRocketReNyastered'

_LOG = None   # set once the data folder is known: every message is also kept in setup.log so a failed run can be reported
def say(text):
    print(text, flush=True)
    if _LOG is not None:
        try:
            with open(_LOG, 'a', encoding='utf8') as f: f.write(str(text) + '\n')
        except OSError: pass

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--game-files', default=os.environ.get('CCR_SETUP_GAME_FILES'))
    ap.add_argument('--cache', default=None)
    ap.add_argument('--download-python', action='store_true')
    a = ap.parse_args()
    gf = Path(a.game_files) if a.game_files else None
    if gf is not None and gf.is_file() and gf.suffix.lower() not in ('.gdi', '.cue', '.chd'):
        gf = gf.parent   # selected packages/ROMs use their containing folder; preserve selected disc descriptors
    if gf is None or not gf.exists() or (not gf.is_dir() and gf.suffix.lower() not in ('.gdi', '.cue', '.chd')):
        say('Your game folder or supported disc descriptor was not found: %s' % a.game_files); return 1
    game = gf.resolve()
    cache = Path(a.cache).resolve() if a.cache else default_cache()
    old = cache.parent / 'ReNyastered'   # the folder name used before the rename: move it once if the new one does not exist
    if not a.cache and not cache.exists() and old.exists(): shutil.move(str(old), str(cache))
    cache.mkdir(parents=True, exist_ok=True)
    global _LOG; _LOG = cache / 'setup.log'
    try: _LOG.write_text('setup started %s (python %s, %s)\ngame files: %s\n' % (__import__('time').strftime('%Y-%m-%d %H:%M:%S'), sys.version.split()[0], sys.platform, game), encoding='utf8')
    except OSError: _LOG = None
    say('progress 0.02 Checking Python')
    if sys.version_info < (3, 10): say('Python 3.10 or later is required (found %s).' % sys.version.split()[0]); return 1
    try: import PIL  # noqa: F401
    except ImportError:
        if a.download_python and not os.environ.get('CCR_PREPARE_VENV'):
            venv = cache / 'venv'; say('progress 0.05 Pillow is missing: creating a private Python environment (needs internet)')
            for cmd in ([sys.executable, '-m', 'venv', str(venv)], [str(venv / 'bin' / 'python'), '-m', 'pip', 'install', '--disable-pip-version-check', 'pillow']):
                res = subprocess.run(cmd, capture_output=True, text=True)
                if res.returncode != 0:
                    say('Could not set up Pillow automatically (%s):' % ' '.join(cmd[:3])); say((res.stdout + res.stderr).strip()[-600:])
                    say('Install Pillow yourself (python3-pil or python-pillow from your package manager; on Debian/Ubuntu also python3-venv), then run setup again.'); return 1
            say('progress 0.1 Pillow installed; continuing')
            return subprocess.call([str(venv / 'bin' / 'python'), str(Path(__file__).resolve()), '--game-files', str(game)] + (['--cache', str(cache)] if a.cache else []), env=dict(os.environ, CCR_PREPARE_VENV='1'))
        say('Pillow is missing. Enable "Download Python and Pillow if needed" (setup then installs Pillow into a private environment; needs python3-venv and internet), or install your distribution package (python3-pil / python-pillow), then run setup again.'); return 1
    lock = open(cache / 'prepare.lock', 'w')
    try:
        import fcntl
        try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError: say('Another setup is already running for this folder.'); return 1
    except ImportError: pass
    staging = cache / ('prepare-' + uuid.uuid4().hex)
    published = False
    try:
        staging.mkdir()
        say('progress 0.15 Extracting from your game files (this can take several minutes)')
        log = cache / 'setup.log'
        with open(log, 'a') as lf:
            code = subprocess.call([sys.executable, str(HERE / 'extract_all.py'), '--game-files', str(game), '--cache', str(staging), '--exclude-cache', str(cache)], stdout=lf, stderr=subprocess.STDOUT)
        if code != 0:
            say('Extraction failed. See %s' % log); say('\n'.join(log.read_text(errors='replace').splitlines()[-10:])); return 1
        say('progress 0.95 Checking what can be played')
        new_manifest = staging / 'manifest.json'
        manifest = json.loads(new_manifest.read_text())
        for entry in manifest.get('inputs', []):
            if entry.get('error'):
                say('Input could not be used: %s — %s' % (entry.get('file', '(unknown)'), entry['error']))
        if not manifest.get('playable_modes'):
            if not manifest.get('base_graphics_available'): say('No playable graphics were found. Check for a supported Dreamcast GDI/numbered BIN-CUE image or add a supported iOS/Android release.')
            else: say('No playable stage data was found. See %s' % log)
            return 1
        assets, new_assets, old_assets = cache / 'assets', staging / 'assets', staging / 'previous-assets'
        had_old = assets.is_dir()
        if had_old:
            for name in ('progress.bin', 'challenge.bin', 'options.bin', 'settings.ini', 'controls.ini'):
                if (assets / name).is_file(): shutil.copy2(assets / name, new_assets / name)
            for d in ('imports', 'logs'):   # player data kept across re-runs
                if (assets / d).is_dir(): shutil.copytree(assets / d, new_assets / d, dirs_exist_ok=True)
            assets.rename(old_assets)
        try:
            new_assets.rename(assets)
            os.replace(new_manifest, cache / 'manifest.json')
            published = True
        except Exception:
            if assets.is_dir(): assets.rename(new_assets)
            if had_old: old_assets.rename(assets)
            raise
        say('Playable modes: %s' % ', '.join(manifest['playable_modes']))
        say('progress 1 Done')
        return 0
    except Exception as e:
        say('Setup failed: %s' % e); return 1
    finally:
        recoverable = (not published) and (staging / 'previous-assets').exists()
        if staging.exists() and not recoverable: shutil.rmtree(staging, ignore_errors=True)
        lock.close()

if __name__ == '__main__':
    code = main()
    if code and _LOG is not None: print('Setup did not finish. Details (please attach this file to a bug report): %s' % _LOG, flush=True)
    sys.exit(code)
