"""Regression tests for rebuilding cached Dreamcast-derived assets."""
import pathlib
import sys
import tempfile
import types
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import extract_all


class DreamcastCacheTest(unittest.TestCase):
    def test_failed_disc_extract_preserves_existing_cache(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            assets, work = root / 'assets', root / 'work'
            files = assets / 'dreamcast' / 'files'
            files.mkdir(parents=True)
            work.mkdir()
            (files / 'old.bin').write_bytes(b'working cache')
            (assets / 'ret_all' / 'r0930.tex.bin').parent.mkdir(parents=True)
            (assets / 'ret_all' / 'r0930.tex.bin').write_bytes(b'mobile')
            def fail(*args):
                raise ValueError('bad ISO')
            with mock.patch.dict(sys.modules, {'gdi_extract': types.SimpleNamespace(extract=fail)}):
                with self.assertRaisesRegex(ValueError, 'bad ISO'):
                    extract_all.refresh_dreamcast_files(root / 'bad.gdi', str(work), str(assets))
            self.assertEqual((files / 'old.bin').read_bytes(), b'working cache')
            self.assertEqual((assets / 'ret_all' / 'r0930.tex.bin').read_bytes(), b'mobile')

    def test_successful_extract_replaces_only_dreamcast_cache(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            assets, work = root / 'assets', root / 'work'
            files = assets / 'dreamcast' / 'files'
            files.mkdir(parents=True)
            work.mkdir()
            (files / 'old.bin').write_bytes(b'stale')
            (assets / 'dreamcast' / 'models.bin').write_bytes(b'stale model')
            (assets / 'ret_all' / 'dc_options.tex.bin').parent.mkdir(parents=True)
            (assets / 'ret_all' / 'dc_options.tex.bin').write_bytes(b'stale DC')
            (assets / 'ret_all' / 'r0930.tex.bin').write_bytes(b'mobile')
            def extract(src, output, gap):
                pathlib.Path(output, 'NEW.BIN').write_bytes(b'fresh disc')
                return ['track']
            with mock.patch.dict(sys.modules, {'gdi_extract': types.SimpleNamespace(extract=extract)}):
                tracks, refreshed = extract_all.refresh_dreamcast_files(root / 'disc.gdi', str(work), str(assets))
            self.assertEqual(tracks, ['track'])
            self.assertEqual(pathlib.Path(refreshed, 'NEW.BIN').read_bytes(), b'fresh disc')
            self.assertFalse((pathlib.Path(refreshed) / 'old.bin').exists())
            self.assertFalse((assets / 'dreamcast' / 'models.bin').exists())
            self.assertFalse((assets / 'ret_all' / 'dc_options.tex.bin').exists())
            self.assertEqual((assets / 'ret_all' / 'r0930.tex.bin').read_bytes(), b'mobile')

    def test_clears_generated_stage_packs_before_current_sources_are_exported(self):
        with tempfile.TemporaryDirectory() as temporary:
            assets = pathlib.Path(temporary) / 'assets'
            assets.mkdir()
            for name in ('battle_stages.bin', 'dreamcast_puzzles.bin', 'mobile_puzzles.bin'):
                (assets / name).write_bytes(b'stale pack')
            (assets / 'challenge.bin').write_bytes(b'user save')
            extract_all.clear_derived_stage_packs(str(assets))
            self.assertFalse((assets / 'battle_stages.bin').exists())
            self.assertFalse((assets / 'dreamcast_puzzles.bin').exists())
            self.assertFalse((assets / 'mobile_puzzles.bin').exists())
            self.assertEqual((assets / 'challenge.bin').read_bytes(), b'user save')

    def test_clears_stale_dreamcast_outputs_and_preserves_other_assets(self):
        with tempfile.TemporaryDirectory() as temporary:
            assets = pathlib.Path(temporary) / 'assets'
            dreamcast = assets / 'dreamcast'
            ret = assets / 'ret_all'
            for name in ('files/ENGLISH', 'png', 'prs', 'prs_png', 'models', 'objects', 'audio', 'sfx'):
                (dreamcast / name).mkdir(parents=True, exist_ok=True)
                (dreamcast / name / 'stale.bin').write_bytes(b'stale')
            (dreamcast / 'models.bin').write_bytes(b'stale model pack')
            (ret / 'dc_options.tex.bin').parent.mkdir(parents=True, exist_ok=True)
            (ret / 'dc_options.tex.bin').write_bytes(b'stale Dreamcast atlas')
            (ret / 'dc_assets_version.txt').write_text('5', encoding='ascii')
            (ret / 'r0930.tex.bin').write_bytes(b'mobile atlas')
            (assets / 'challenge.bin').write_bytes(b'user save')

            extract_all.clear_dreamcast_cache(str(assets))

            self.assertFalse(dreamcast.exists() and any(dreamcast.iterdir()))
            self.assertFalse((ret / 'dc_options.tex.bin').exists())
            self.assertFalse((ret / 'dc_assets_version.txt').exists())
            self.assertEqual((ret / 'r0930.tex.bin').read_bytes(), b'mobile atlas')
            self.assertEqual((assets / 'challenge.bin').read_bytes(), b'user save')

    def test_version_marker_is_published_only_after_successful_complete_export(self):
        with tempfile.TemporaryDirectory() as temporary:
            assets = pathlib.Path(temporary) / 'assets'
            ret = assets / 'ret_all'
            ret.mkdir(parents=True)
            marker = ret / 'dc_assets_version.txt'
            marker.write_text('stale', encoding='ascii')
            extract_all.clear_dreamcast_cache(str(assets))
            entry = {'model_pack': True, 'sfx_error': 'render failed'}
            self.assertFalse(extract_all.publish_dc_asset_version(str(assets), entry))
            self.assertFalse(marker.exists())
            entry.pop('sfx_error')
            sfx = assets / 'dreamcast' / 'sfx'
            sfx.mkdir(parents=True)
            (sfx / 'cues.json').write_text('{}', encoding='ascii')
            self.assertTrue(extract_all.publish_dc_asset_version(str(assets), entry))
            self.assertEqual(marker.read_text(encoding='ascii'), '7')


if __name__ == '__main__':
    unittest.main()
