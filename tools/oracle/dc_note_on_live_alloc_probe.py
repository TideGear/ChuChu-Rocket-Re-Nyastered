"""Run original note-on 0xd68 against captured voice tables, allocation intact.

Usage: dc_note_on_live_alloc_probe.py <MANATEE.DRV> <loaded.MLT> <state>...
For each state, commands use every populated MIDI controller (bank pointer set)
with several keys/velocities/priorities. The captured driver voice table and
voice-count byte stay in place. Reports returns, which voice records changed,
and whether the first changed record equals the Python allocator's first pick.
"""
import argparse, struct, sys
from collections import Counter
from pathlib import Path
from unicorn import UcError, Uc, UC_ARCH_ARM, UC_MODE_ARM
from unicorn.arm_const import UC_ARM_REG_R1, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from arm7_bus import Arm7Bus
from dc_aica_state import inspect
from dc_sound_voices import allocate_voice


def run(driver, mlt, states, saturate=False):
    uc = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    bus = Arm7Bus(uc)
    uc.mem_map(0, 0x200000)
    uc.mem_map(0x210000, 0x1000)
    uc.mem_map(0x800000, 0x10000)
    count_pointer = struct.unpack_from('<I', driver, 32 + 0x1884)[0]
    stats = Counter()
    import random; rng = random.Random()
    for path in states:
        state = path.read_bytes()
        report = inspect(state, mlt)
        base, regs = report['sound_ram_offset'], report['register_offset']
        ram = state[base:base + 0x200000]
        count = ram[count_pointer]
        free = sum(ram[0x10000 + 64 * i:0x10004 + 64 * i] == bytes(4) for i in range(count))
        print(path.name, 'voices', count, 'free', free)
        for group in range(8):
            for chan in range(16):
                ctl = 0xc000 + group * 0x800 + chan * 0x80
                if not struct.unpack_from('<I', ram, ctl + 0x10)[0] or ram[ctl + 0x3f]:
                    continue
                for note in (36, 60, 96):
                    for vel in (1, 100):
                        for prio in (0, 15, 31):
                            uc.mem_write(0, ram)
                            uc.mem_write(0x800000, state[regs:regs + 0x8000])
                            if saturate:
                                rng.seed(hash((group, chan, note, vel, prio)) & 0xffff)
                                live = [bytes(uc.mem_read(0x10000 + 64 * i, 64)) for i in range(count)]
                                donor = next((v for v in live if v[:4] != bytes(4)), None)
                                if donor is None:
                                    continue
                                full = []
                                for _ in range(count):
                                    v = bytearray(donor)
                                    v[0] = rng.choice((0x01, 0x21, 0x80, 0xe1))
                                    v[3] = rng.randrange(0, 4)
                                    v[0x3e] = rng.choice((0, 5, 15, 31, 40))
                                    v[0x3f] = rng.choice((0, 1, 9))
                                    full.append(bytes(v))
                                uc.mem_write(0x10000, b''.join(full))
                            table = bytes(uc.mem_read(0x10000, count * 64))
                            records = [table[i * 64:i * 64 + 64] for i in range(count)]
                            low = bytes(ram[:264])
                            cmd = 0x01000000 | prio << 27 | group << 20 | chan << 16 | note << 8 | vel
                            uc.reg_write(UC_ARM_REG_R1, cmd)
                            uc.reg_write(UC_ARM_REG_SP, 0x210ff0)
                            uc.reg_write(UC_ARM_REG_LR, 0x1ff000)
                            try:
                                uc.emu_start(0xd68, 0x1ff000, count=200000)
                            except UcError:
                                stats['fault_pc_%x' % uc.reg_read(UC_ARM_REG_PC)] += 1
                                stats['faults'] += 1
                                stats['fault_pick_idx_none'] += allocate_voice(records, prio, low).index(count) is None
                                continue
                            bus.flush()
                            if uc.reg_read(UC_ARM_REG_PC) != 0x1ff000:
                                stats['no_return'] += 1
                                continue
                            after = bytes(uc.mem_read(0x10000, count * 64))
                            changed = [i for i in range(count) if after[i*64:i*64+64] != records[i]]
                            first = allocate_voice(records, prio, low)
                            idx = first.index(count)
                            stats['cases'] += 1
                            stats['ret_%s' % ('ok' if uc.reg_read(UC_ARM_REG_R0) == 0 else 'nz')] += 1
                            stats['changed_any'] += bool(changed)
                            stats['no_change'] += not changed
                            if changed:
                                stats['first_pick_nonvoice'] += idx is None
                                if idx is not None and idx in changed:
                                    stats['first_pick_changed'] += 1
                                elif idx is not None:
                                    stats['first_pick_unchanged'] += 1
                            stats['free_%d' % (free > 0)] += 1
    return stats


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('driver', type=Path); p.add_argument('mlt', type=Path)
    p.add_argument('--saturate', action='store_true'); p.add_argument('states', type=Path, nargs='+')
    a = p.parse_args()
    print(dict(run(a.driver.read_bytes(), a.mlt.read_bytes(), a.states, a.saturate)))
