"""Tests for tools/arm7_interp.py and tools/dc_sfx_render.py (run: python tools/test_dc_sfx_render.py).
Disc-dependent checks run only when the extracted English sound files exist under local/ (never committed)."""
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arm7_interp import Arm7, ArmError
import dc_sfx_render as R

ROOT = Path(__file__).resolve().parents[1]
DISC = next(iter(sorted(ROOT.glob('local/*/assets/dreamcast/files/ENGLISH'))), None)


def run(words, **regs):
    ram = bytearray(0x200000)
    struct.pack_into('<%dI' % len(words), ram, 0, *words)
    cpu = Arm7(ram)
    for name, value in regs.items():
        cpu.r[int(name[1:])] = value
    cpu.run(0, len(words) * 4)
    return cpu


class Interpreter(unittest.TestCase):
    def test_arithmetic_flags_and_branch(self):
        # mov r0,#5; subs r0,r0,#5; moveq r1,#7; movne r1,#9; b +0 (to end)
        cpu = run([0xe3a00005, 0xe2500005, 0x03a01007, 0x13a01009])
        self.assertEqual((cpu.r[0], cpu.r[1], cpu.z), (0, 7, 1))

    def test_store_aligns_down_and_load_rotates(self):
        # str r0,[r1,#1]; ldr r2,[r1,#1]
        cpu = run([0xe5810001, 0xe5912001], r0=0x11223344, r1=0x100)
        self.assertEqual(struct.unpack_from('<I', cpu.ram, 0x100)[0], 0x11223344)
        self.assertEqual(cpu.r[2], 0x44112233)

    def test_block_transfer_and_halfword(self):
        # stmia r1!,{r2,r3}; ldrh r4,[r1,#-8]
        cpu = run([0xe8a1000c, 0xe15140b8], r1=0x200, r2=0xdeadbeef, r3=1)
        self.assertEqual((cpu.r[1], cpu.r[4]), (0x208, 0xbeef))

    def test_unmapped_access_raises(self):
        with self.assertRaises(ArmError):
            run([0xe5910000], r1=0x400000)


class Cues(unittest.TestCase):
    def test_cue_location(self):
        self.assertEqual([R.cue_location(c) for c in (0, 28, 29, 127)], [(0, 0), (0, 28), (1, 0), (1, 98)])

    @unittest.skipUnless(DISC, 'extracted Dreamcast files not present')
    def test_cold_state_and_install_tables(self):
        driver, mlt = (DISC / 'MANATEE.DRV').read_bytes(), (DISC / 'CHU2_SE.MLT').read_bytes()
        ram, registers = R.cold_state(driver, mlt)
        self.assertEqual(len(registers), 0x8000)
        R.install_banks(ram, mlt)
        self.assertEqual(struct.unpack_from('<2I', ram, 0x14080), (0x28ce0, 0x5f320))     # SMPB bank 0, as in a live Flycast state
        self.assertEqual(struct.unpack_from('<2I', ram, 0x14088), (0x8a000, 0x16bfc0))    # SMPB bank 1

    @unittest.skipUnless(DISC, 'extracted Dreamcast files not present')
    def test_cue_27_voices_and_length(self):
        driver, mlt = (DISC / 'MANATEE.DRV').read_bytes(), (DISC / 'CHU2_SE.MLT').read_bytes()
        frames, info = R.render_cue(driver, mlt, 27)
        self.assertEqual(info['writes'], 43)
        self.assertTrue(60000 < sum(1 for f in frames if f[0] or f[1]) + 180 < 66000)   # sample 0x66f6a plays out in ~63,300 frames


if __name__ == '__main__':
    unittest.main()
