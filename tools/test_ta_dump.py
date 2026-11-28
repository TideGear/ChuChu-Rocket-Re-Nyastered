"""Regression checks for conservative TA crop selection."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent / 'oracle'))
from ta_dump import select


def polygon(points, tex=1):
    return {'tex': tex, 'strips': [[(0xe0000000, x, y, z) for x, y, z in points]]}


class CropSelectionTests(unittest.TestCase):
    def test_full_canvas_encloses_dialog(self):
        canvas = polygon([(0, 0, 1), (0, 512, 1), (512, 0, 1), (512, 512, 1)])
        self.assertEqual(select([canvas], [154, 160, 498, 256], None), [canvas])

    def test_crossing_strip_without_vertex_in_crop(self):
        strip = polygon([(0, 190, 1), (640, 190, 1), (640, 210, 1)])
        self.assertEqual(select([strip], [300, 180, 340, 220], None), [strip])

    def test_unrelated_or_invalid_depth_is_excluded(self):
        outside = polygon([(0, 0, 1), (10, 0, 1), (0, 10, 1)])
        invalid = polygon([(200, 200, 0), (210, 200, -1), (200, 210, 101)])
        self.assertEqual(select([outside, invalid], [154, 160, 498, 256], None), [])

    def test_texture_filter_still_applies(self):
        canvas = polygon([(0, 0, 1), (0, 512, 1), (512, 512, 1)])
        self.assertEqual(select([canvas], [154, 160, 498, 256], 2), [])


if __name__ == '__main__':
    unittest.main()
