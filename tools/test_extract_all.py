"""Regression tests for rebuilding cached Dreamcast-derived assets."""
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import extract_all


class DreamcastCacheTest(unittest.TestCase):
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
            (ret / 'dc_assets_version.txt').write_text('4', encoding='ascii')
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
            self.assertEqual(marker.read_text(encoding='ascii'), '4')


if __name__ == '__main__':
    unittest.main()
