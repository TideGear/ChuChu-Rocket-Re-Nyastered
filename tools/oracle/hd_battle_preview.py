"""Capture the original HD 1.0 iPad battle preview before its GL upload."""
import argparse
from pathlib import Path
import struct

from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_SP

import hd_env


class BattlePreviewOracle:
    def __init__(self):
        env = hd_env.make()
        self.oracle = o = env.o
        self.upload = None
        texture = o.u32(env.appdata + 0x3cc + 4 * 148)
        space = o.u32(env.appdata + 0x3a0)
        o.write(texture + 8, struct.pack('<I', 0))
        o.write(space + 0x20, struct.pack('<I', 0x8033))
        o.call(0x15928, 0)  # FI_LoadAllMap
        o.call(0x1ac88)     # Render::initializePlayfields
        address = next(addr for addr, name in o.stubs.items() if name == '_glTexSubImage2D')
        o.uc.hook_add(UC_HOOK_CODE, self.record_upload, begin=address, end=address)

    def record_upload(self, uc, address, size, user):
        stack = uc.reg_read(UC_ARM_REG_SP)
        width, height, color, kind, pixels = struct.unpack('<5I', self.oracle.read(stack, 20))
        assert (width, height, color, kind) == (832, 640, 0x1908, 0x8033)
        self.upload = self.oracle.read(pixels, width * height * 2)

    def capture(self, team, stage):
        self.upload = None
        # The game frees the temporary pixel buffer. The oracle's free stub
        # does not reclaim it, so reuse that heap range between captures.
        heap = self.oracle.heap_ptr
        try:
            self.oracle.call(0x19c94, int(team), stage, 148)
        finally:
            self.oracle.heap_ptr = heap
        assert self.upload is not None
        return self.upload


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('stage', type=int, choices=range(25))
    cli.add_argument('output', type=Path, help='Destination for the 832 by 640 little-endian RGBA4444 buffer')
    cli.add_argument('--team', action='store_true')
    args = cli.parse_args()
    args.output.write_bytes(BattlePreviewOracle().capture(args.team, args.stage))
