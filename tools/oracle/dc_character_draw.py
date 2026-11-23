"""Trace model, animation and texture submissions from the Dreamcast executable."""
from pathlib import Path

from sh4 import SENTINEL, SH4
import export_dc_models as dc_models

BASE = 0x8c010000
ROOT = Path(__file__).resolve().parents[2]
CAT_DRAW = 0x8c0119fe
TEXTURE = 0x8c0df1f8
MORPH_DRAW = 0x8c0e673e
QUAD_DRAW = 0x8c0e4328
MOUSE_DRAW = 0x8c019e26
MOUSE_SLOTS = 0x8c1af10c


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
    slots = MOUSE_SLOTS
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


def verify_mouse_draw(binary):
    sh = SH4()
    sh.load(BASE, binary)
    calls = []
    costume = 0

    def attachment(machine):
        calls.append(('attachment', *machine.r[4:7]))
        machine.r[0] = machine.r[4] + 4

    hooks = {
        0x8c016bd4: lambda m: m.r.__setitem__(0, costume),
        TEXTURE: lambda m: calls.append(('textures', m.r[4])),
        QUAD_DRAW: lambda m: calls.append(('quad', *m.r[4:7])),
        0x8c0e0a1c: lambda m: calls.append(('material', m.r[4])),
        0x8c0e8574: lambda m: calls.append(('prepare',)),
        0x8c0e9056: lambda m: calls.append(('model', m.r[4])),
        0x8c0e6e56: lambda m: calls.append(('motion', *m.r[4:6], float(m.fget(4)))),
        0x8c0e65fe: lambda m: calls.append(('shape', *m.r[4:6], float(m.fget(4)))),
        0x8c018c80: attachment,
        0x8c018d54: lambda m: calls.append(('draw attachment', *m.r[4:7])),
    }
    sh.hooks.update({addr & 0x1fffffff: cb for addr, cb in hooks.items()})
    slots = [0x8cfe0000 + i * 0x100 for i in range(8)]
    for i, address in enumerate(slots):
        sh.wr32(MOUSE_SLOTS + 4 * i, address)

    lists = (0x8c085d18, 0x8c085d8c, 0x8c085e2c, 0x8c0b4c24)
    for costume, textures in enumerate(lists):
        for mouse_type in range(4):
            for frame, model in enumerate(slots):
                for heading in (0x7fff, 0x8000):
                    calls.clear()
                    sh.call(MOUSE_DRAW, mouse_type, frame, heading)
                    expected = [('textures', textures)]
                    if costume in (1, 2):
                        expected.append(('material', 0x8c0b4c18))
                    if costume == 3:
                        expected.append(('quad', 0x8c0b4ccc, frame >> 1,
                                         52 if heading & 0x8000 else 48))
                    elif mouse_type == 0 or (costume == 2 and mouse_type < 3):
                        expected.extend([('prepare',), ('model', model)])
                    elif mouse_type == 1:
                        obj, motion = ((0x8c0960ec, 0x8c09661c) if costume == 0
                                       else (0x8c09962c, 0x8c0a26cc))
                        expected.append(('motion', obj, motion, frame))
                    elif mouse_type == 2 and costume == 0:
                        expected.extend([
                            ('attachment', 0x8c076568, 0x8c076574, textures),
                            ('attachment', 0x8c076580, 0x8c07658c, textures),
                            ('shape', 0x8c08e138, 0x8c0963d0, frame),
                            ('draw attachment', 0x8c076568, 0x8c07656c, textures),
                            ('draw attachment', 0x8c076580, 0x8c076584, textures),
                        ])
                    elif mouse_type == 2:
                        expected.append(('shape', 0x8c09a59c, 0x8c0a20c0, frame))
                    assert calls == expected, (costume, mouse_type, frame, heading, calls)
    print('Dreamcast mouse draw matched 256 costume, type, frame, and heading cases')


def verify_golden_mouse_motion(binary):
    pack = dc_models.Pack.__new__(dc_models.Pack)
    pack.d = binary
    pack.models = {dc_models.BASE + off: (vertices, polygons)
                   for off, vertices, polygons, _, _ in dc_models.M.find_models(binary, dc_models.BASE)}
    order = pack.tree(0x860ec)
    poses = dc_models.golden_mouse_frames(pack, order)
    assert len(poses) == 8 and all(len(pose) == 92 for pose in poses)
    assert all(all(value == value and abs(value) < 1e6
                   for _, tri in pose for vertex in tri for value in vertex)
               for pose in poses)
    assert poses[0] == poses[4] and poses[1] == poses[3]
    assert any(poses[frame] != poses[0] for frame in range(1, 8))
    print('Dreamcast golden-mouse motion exported as eight finite, varying poses from the six source tracks')


def verify_mouse_frame_callers(binary):
    sh = SH4()
    sh.load(BASE, binary)
    calls = []
    task = 0x8cfe0000
    # Capture the transform wrapper boundary. The model dispatcher itself is
    # executed separately by verify_mouse_draw.
    sh.hooks[0x0c0193e0] = lambda m: calls.append(tuple(m.r[4:8]))
    sh.hooks[0x0c060810] = lambda m: m.r.__setitem__(0, 0)

    for frame in range(8):
        sh.wr32(task + 8, 2)
        sh.wr32(task + 32, 0x8000)
        sh.wr32(task + 52, frame)
        sh.call(0x8c01946c, task)
        assert calls.pop() == (task + 20, 0x8000, 2, frame)

    for tick in range(65):
        sh.wr32(task + 4, tick)
        sh.call(0x8c051a76, task)
        assert calls.pop() == (task + 20, 0, 0, (tick // 4) & 7)

    for rate in (0, 1, 4, 8):
        sh.load(task + 45, bytes((rate, 0, 0)))
        for tick in range(65):
            sh.wr32(task + 4, tick)
            sh.call(0x8c05144c, task)
            assert calls.pop() == (task + 20, 0, 0, (tick * rate // 8) & 7)
    print('Dreamcast mouse frame callers matched 333 task snapshots, including wrap')


def verify_gameplay_frame_clock(binary):
    sh = SH4()
    sh.load(BASE, binary)
    tasks = (0x8cfe0000, 0x8cfe0100)

    def stop_at_boundary(machine):
        machine.pr = SENTINEL | 0x80000000

    sh.hooks.update({
        0x0c019b16: stop_at_boundary,
        0x0c019b2e: stop_at_boundary,
        0x0c016512: lambda m: m.r.__setitem__(0, 1),
    })
    for start in (0, 7, 15):
        for tick in range(start):
            sh.call(0x8c016cc8)
        sh.call(0x8c016cc0)
        assert sh.call(0x8c016cd2) == 0
        for tick in range(18):
            assert sh.call(0x8c016cd2) == tick
            for task in tasks:
                sh.r[14] = task
                sh.call(0x8c019b0c)
                assert sh.rd32(task + 0x34) == tick & 7
            # A collision response can turn the mouse and skip the frame write.
            sh.r[14] = tasks[1]
            sh.wr32(tasks[1] + 0x34, (tick + 1) & 7)
            sh.call(0x8c019a00)
            assert sh.rd32(tasks[1] + 0x34) == (tick + 1) & 7
            sh.call(0x8c016cc8)
        sh.call(0x8c016cc0)
    print('Dreamcast gameplay mouse frames matched shared clock, reset, and collision skip')


def verify_clock_scheduler(binary):
    sh = SH4()
    sh.load(BASE, binary)
    ticks = []
    for address in (0x8c018320, 0x8c01f8f4, 0x8c01a174, 0x8c01909c,
                    0x8c01575a, 0x8c020816, 0x8c011e08, 0x8c016e94, 0x8c01a0d2):
        sh.hooks[address & 0x1fffffff] = lambda m: m.r.__setitem__(0, 0)
    status_reads = []

    def read_status(machine):
        status_reads.append(status)
        machine.r[0] = status

    sh.hooks[0x0c0ef8ac] = read_status
    sh.hooks[0x0c0ef8c4] = lambda m: status_reads.append('service')
    sh.hooks[0x0c0190cc] = lambda m: m.r.__setitem__(0, state)
    sh.hooks[0x0c01efd2] = lambda m: ticks.append(m.rd32(0x8c1ae8d8))
    sh.call(0x8c016cc0)
    status = 0
    for blocked, state, running in ((0, 0, 1), (1, 0, 1), (0, 3, 1),
                                     (0, 0, 0), (0, 0, 1)):
        sh.call(0x8c0167e0)
        if blocked:
            sh.call(0x8c0167e8, 0, -23)
        sh.call(0x8c016a42, running)
        status_reads.clear()
        sh.call(0x8c018426)
        assert status_reads == ([] if blocked else [0, 'service'])
    assert ticks == [0, 1]
    assert sh.call(0x8c016cd2) == 2

    sh.hooks[0x0c0ef852] = lambda m: m.r.__setitem__(0, 0)
    sh.hooks[0x0c0ef4c4] = lambda m: m.r.__setitem__(0, device_mode)
    for device_mode in (0, 4):
        for status in (0, 1, 6, 7, 9):
            sh.call(0x8c0167e0)
            status_reads.clear()
            sh.call(0x8c0167fe)
            latched = device_mode != 4 and status in (6, 7, 9)
            assert sh.rd32(0x8c1ae8b0) == latched
            if device_mode == 4:
                assert not status_reads
            else:
                assert status_reads == ([status] if latched else [status, 'service'])
            if latched:
                status_reads.clear()
                assert sh.call(0x8c016848) == 1
                assert not status_reads
    for error in (-34, -33, -23, -22):
        sh.call(0x8c0167e0)
        sh.call(0x8c0167e8, 0, error)
        assert sh.rd32(0x8c1ae8b0) == (error in (-33, -23))
    print('Dreamcast task clock gates matched the run flag, device latch, and controlled transition return')


if __name__ == '__main__':
    binary = (ROOT / 'local/cache/assets/dreamcast/files/1ST_READ.BIN').read_bytes()
    verify_cat(binary)
    verify_mouse_models(binary)
    verify_mouse_draw(binary)
    verify_golden_mouse_motion(binary)
    verify_mouse_frame_callers(binary)
    verify_gameplay_frame_clock(binary)
    verify_clock_scheduler(binary)
