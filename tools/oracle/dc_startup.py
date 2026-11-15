"""Trace the Dreamcast game startup with graphics and platform calls recorded."""
from pathlib import Path
import struct

from sh4 import SH4, u2f

ROOT = Path(__file__).resolve().parents[2]
BASE = 0x8c010000
TASK = 0x8cfe0000
PADS = 0x8c1aee88
FADE_OUT = 0x8c0157c0
TRACK = 0x8c012560
MODE = 0x8c019088
SONIC_DRAW = 0x8c01fb40
SEGA_DRAW = 0x8c0e4268


def main():
    binary = (ROOT / 'local/cache/assets/dreamcast/files/1ST_READ.BIN').read_bytes()
    sh = SH4()
    sh.load(BASE, binary)
    table = sh.rd32(0x8c0190e8)
    assert [sh.rd32(sh.rd32(table + 4 * i)) for i in range(3)] == [
        0x8c0235ea, 0x8c023776, 0x8c0264d2]
    title = sh.rd32(0x8c07fba4) - BASE
    assert binary[title:title + 6] == b'TITLE\0'
    calls = []
    tick = 0

    def hook(address):
        def record(machine):
            calls.append((tick, address, machine.r[4]))
            machine.r[0] = 0
        sh.hooks[address & 0x1fffffff] = record

    for address in (FADE_OUT, TRACK, MODE, SONIC_DRAW, 0x8c0df1f8):
        hook(address)
    for tick in range(1, 145):
        sh.call(0x8c02356a, TASK)
    assert calls == [(132, FADE_OUT, 11), (144, MODE, 1)], calls

    tiles = []

    def draw(machine):
        p = machine.r[4]
        tiles.append((machine.r[5], machine.r[6], u2f(machine.rd32(p)), u2f(machine.rd32(p + 4)),
                      machine.fget(4).item()))
    sh.hooks[SEGA_DRAW & 0x1fffffff] = draw
    sh.call(0x8c0235e6)
    assert tiles == [(i, 0, 320.0, 0.0, -10.0) for i in range(6)], tiles
    print('SEGA: six ordered texture draws, fade at tick 132, switch to mode 1 at tick 144')

    for player in (None, 0, 1, 2, 3):
        sh.load(TASK, bytes(8))
        sh.load(PADS, bytes(52 * 4))
        calls.clear()
        for tick in range(1, 379):
            if player is not None:
                sh.wr32(PADS + 52 * player + 16, 8 if tick in (10, 40) else 0)
            sh.call(0x8c0236c0, TASK)
            if calls[-1][1] == MODE:
                break
        fade_tick = 365 if player is None else 40
        assert [c for c in calls if c[1] != SONIC_DRAW] == [
            (13, TRACK, 18), (fade_tick, FADE_OUT, 11), (fade_tick + 13, MODE, 2)]
        assert all(address == 0x8c0b6d74 for _, symbol, address in calls if symbol == SONIC_DRAW)

    # Source name for the object submitted by the mode-1 render task.
    texture_list = sh.rd32(0x8c0b6d78)
    name = sh.rd32(sh.rd32(texture_list))
    assert binary[name - BASE:name - BASE + 5] == b'logo\0'
    print('Sonic Team: LOGO, music request 18 at tick 13, fade at 365 or Start, Title after another 13 ticks')


if __name__ == '__main__':
    main()
