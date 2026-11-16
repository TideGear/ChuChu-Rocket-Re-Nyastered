"""Trace model, animation and texture submissions from the Dreamcast executable."""
from pathlib import Path

from sh4 import SH4

BASE = 0x8c010000
ROOT = Path(__file__).resolve().parents[2]
CAT_DRAW = 0x8c0119fe
TEXTURE = 0x8c0df1f8
MORPH_DRAW = 0x8c0e673e
QUAD_DRAW = 0x8c0e4328


def texture_names(sh, binary, table):
    names = sh.rd32(table)
    offsets = (sh.rd32(names + index * 12) - BASE for index in range(sh.rd32(table + 4)))
    return [binary[offset:binary.index(b'\0', offset)].decode('ascii') for offset in offsets]


def verify_cat(binary):
    sh = SH4()
    sh.load(BASE, binary)
    calls = []
    hooks = {
        # Supply the game mode and tutorial predicate used by the costume getter.
        0x8c01907c: lambda m: m.r.__setitem__(0, 12),
        0x8c015506: lambda m: m.r.__setitem__(0, 0),
        TEXTURE: lambda m: calls.append(('textures', m.r[4])),
        MORPH_DRAW: lambda m: calls.append(('morph', *m.r[4:7], float(m.fget(4)))),
        QUAD_DRAW: lambda m: calls.append(('quad', *m.r[4:7])),
        0x8c0e0938: lambda m: None,
        0x8c0e1028: lambda m: None,
        0x8c0e08f8: lambda m: None,
    }
    sh.hooks.update({addr & 0x1fffffff: cb for addr, cb in hooks.items()})
    assert texture_names(sh, binary, 0x8c085c98) == [f'c_cat{i:02}' for i in range(1, 5)]
    assert sh.rd32(0x8c08810c) == sh.rd32(0x8c08cfd8) == 24
    for costume in range(5):
        sh.wr32(0x8c1ae8d0, costume)
        for phase in (0.0, 1.75, 7.0, 15.75, 23.5):
            for angle in (0, 0x7fff, 0x8000, 0xffff):
                sh.fset(4, phase)
                calls.clear()
                sh.call(CAT_DRAW, angle)
                if costume < 3:
                    expected = [('textures', 0x8c085c98),
                                ('morph', 0x8c0878c4, 0x8c088108, 0x8c08cfd4, phase)]
                elif costume == 3:
                    expected = [('textures', 0x8c0b4c24),
                                ('quad', 0x8c0b4ccc, 4 + ((int(phase) >> 1) & 3),
                                 52 if angle & 0x8000 else 48)]
                else:
                    expected = []
                assert calls == expected, (costume, phase, angle, calls)
    print('Dreamcast cat draw matched 100 costume, phase, and heading cases')


def verify_mouse_models(binary):
    sh = SH4()
    sh.load(BASE, binary)
    calls = []
    slots = 0x8c1af10c
    sh.hooks.update({
        0x8c016bd4 & 0x1fffffff: lambda m: m.r.__setitem__(0, costume),
        0x8c018d9c & 0x1fffffff: lambda m: calls.append(('prepare',)),
        TEXTURE & 0x1fffffff: lambda m: calls.append(('textures', m.r[4])),
        0x8c018e20 & 0x1fffffff: lambda m: calls.append(('model', m.r[4], m.r[5])),
    })
    model_sets = (
        (0x8c085d18, (0x8c08efb8, 0x8c08fe38, 0x8c090cb8, 0x8c091b38,
                      0x8c0929b8, 0x8c093838, 0x8c0946b8, 0x8c095538)),
        (0x8c085d8c, (0x8c09c818, 0x8c09d3b0, 0x8c09df48, 0x8c09eae0,
                      0x8c09f678, 0x8c0a0210, 0x8c0a0da8, 0x8c0a1940)),
        (0x8c085e2c, (0x8c0a3230, 0x8c0a3dbc, 0x8c0a4948, 0x8c0a54d4,
                      0x8c0a6060, 0x8c0a6bec, 0x8c0a7778, 0x8c0a8304)),
    )
    assert texture_names(sh, binary, model_sets[0][0]) == [
        f'c_mouse{i:02}' for i in (1, 2, 3, 5, 4, 6, 7, 8, 9, 10)]
    for i in range(8):
        sh.wr32(slots + 4 * i, 0x8cfe0000 + 0x100 * i)
    for costume, (tex, models) in enumerate(model_sets):
        calls.clear()
        sh.call(0x8c01a060)
        assert calls == [('prepare',), ('textures', tex)] + [
            ('model', model, sh.rd32(slots + 4 * i)) for i, model in enumerate(models)]
    costume = 3
    calls.clear()
    sh.call(0x8c01a060)
    assert not calls
    print('Dreamcast mouse preparation matched all 24 model submissions and skips the sprite costume')


if __name__ == '__main__':
    binary = (ROOT / 'local/cache/assets/dreamcast/files/1ST_READ.BIN').read_bytes()
    verify_cat(binary)
    verify_mouse_models(binary)
