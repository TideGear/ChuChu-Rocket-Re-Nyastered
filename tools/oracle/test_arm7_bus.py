"""Golden ARM7 bus cases run through real Unicorn instructions."""
import struct
import unittest

from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_CPSR

from arm7_bus import Arm7Bus


class BusTests(unittest.TestCase):
    def test_load_rotation_and_store_alignment(self):
        for offset, expected in enumerate((0x44332211, 0x11443322, 0x22114433, 0x33221144)):
            with self.subTest(offset=offset):
                uc = Uc(UC_ARCH_ARM, UC_MODE_ARM)
                uc.mem_map(0x1000, 0x3000)
                uc.mem_write(0x1000, struct.pack('<2I', 0xe5901000, 0xe5821000))
                source = bytes.fromhex('11 22 33 44 55 66 77 88')
                target = bytes.fromhex('aa bb cc dd ee ff ab cd')
                uc.mem_write(0x2000, source)
                uc.mem_write(0x3000, target)
                uc.reg_write(UC_ARM_REG_R0, 0x2000 + offset)
                uc.reg_write(UC_ARM_REG_R2, 0x3000 + offset)
                bus = Arm7Bus(uc)
                uc.emu_start(0x1000, 0x1008)
                bus.flush()
                self.assertEqual(uc.reg_read(UC_ARM_REG_R1), expected)
                self.assertEqual(bytes(uc.mem_read(0x2000, 8)), source)
                self.assertEqual(bytes(uc.mem_read(0x3000, 8)), struct.pack('<I', expected) + target[4:])

    def test_failed_condition_has_no_access(self):
        uc = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        uc.mem_map(0x1000, 0x3000)
        uc.mem_write(0x1000, struct.pack('<2I', 0x15901000, 0x15821000))
        uc.reg_write(UC_ARM_REG_R0, 0x2001)
        uc.reg_write(UC_ARM_REG_R2, 0x3001)
        uc.reg_write(UC_ARM_REG_R1, 0x12345678)
        uc.reg_write(UC_ARM_REG_CPSR, uc.reg_read(UC_ARM_REG_CPSR) | (1 << 30))
        bus = Arm7Bus(uc)
        uc.emu_start(0x1000, 0x1008)
        bus.flush()
        self.assertEqual((bus.reads, bus.writes), (0, 0))
        self.assertEqual(uc.reg_read(UC_ARM_REG_R1), 0x12345678)


if __name__ == '__main__':
    unittest.main()
