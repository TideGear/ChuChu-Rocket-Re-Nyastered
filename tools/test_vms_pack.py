import unittest

import vms_pack


class VmsPackValidationTest(unittest.TestCase):
    def board(self, arrows=((0, 0, 0),), title=b'ok'):
        return [0] * 108, [0] * 237, list(arrows), title

    def test_rejects_arrow_outside_board(self):
        with self.assertRaises(ValueError):
            vms_pack.encode_slot(*self.board(((12, 0, 0),)))
        with self.assertRaises(ValueError):
            vms_pack.encode_slot(*self.board(((0, 9, 0),)))

    def test_rejects_invalid_direction(self):
        with self.assertRaises(ValueError):
            vms_pack.encode_slot(*self.board(((0, 0, 4),)))

    def test_rejects_overlong_title_instead_of_truncating(self):
        with self.assertRaises(ValueError):
            vms_pack.encode_slot(*self.board(title=b'x' * 21))

    def test_accepts_maximum_title_and_edge_arrow(self):
        slot = vms_pack.encode_slot(*self.board(((11, 8, 3),), b'x' * 20))
        self.assertEqual(vms_pack.decode_slot(slot)[2], [(11, 8, 3)])
        self.assertEqual(vms_pack.decode_slot(slot)[3], b'x' * 20)


if __name__ == '__main__':
    unittest.main()
