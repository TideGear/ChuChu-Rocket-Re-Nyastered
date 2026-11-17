"""Checks tools/vms_pack.py against the real DLC packs: re-encoding every decoded slot reproduces lattice, solution and title bytes; the VMI builder reproduces the real DEPuzzle/PuzzleP .VMI exactly."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stage_registry as R, vms_pack as V
bad = 0; n = 0
for name in ('DEPuzzle', 'PuzzleP'):
    for k, s in enumerate(R.dlc_slots(name)):
        if len(s) < 512: continue
        t, w, a, title = V.decode_slot(s); e = V.encode_slot(t, w, a, title)
        n += 1
        nn = min(s[475], 12); mask = (1 << (2 * nn)) - 1   # bytes past the arrow count are unused filler in the real packs (e.g. 0x55 patterns)
        if e[:476] != s[:476] or e[476:476 + nn] != s[476:476 + nn] or (int.from_bytes(e[488:491], 'little') & mask) != (int.from_bytes(s[488:491], 'little') & mask) or e[491:512] != s[491:512].split(b'\0')[0].ljust(21, b'\0'):
            bad += 1; print('slot', name, k, 'differs', [i for i in range(512) if e[i] != s[i]][:6])
print('slots checked', n, 'differing', bad)
for name in ('DEPuzzle', 'PuzzleP'):
    real = open(os.path.join(R.DLC_DIR, name + '.VMI'), 'rb').read(); vms = open(os.path.join(R.DLC_DIR, name + '.VMS'), 'rb').read()
    import struct
    when = struct.unpack_from('<HBBBBBB', real, 0x44)
    class T: pass
    t = T(); t.tm_year, t.tm_mon, t.tm_mday, t.tm_hour, t.tm_min, t.tm_sec, wd = when; t.tm_wday = (wd - 1) % 7
    desc = real[4:36].rstrip(b'\0'); cr = real[36:68].rstrip(b'\0'); res = real[0x50:0x58].rstrip(b'\0'); fn = real[0x58:0x64].rstrip(b'\0')
    built = V.build_vmi(res, fn, struct.unpack_from('<I', real, 0x68)[0], desc, cr, t, struct.unpack_from('<H', real, 0x4e)[0])
    print(name, 'VMI identical' if built == real else 'VMI differs at %s' % [i for i in range(108) if built[i] != real[i]])
# a new pack round trips through our own decoder
b = R.dlc_slots('DEPuzzle')[0]; t, w, a, title = V.decode_slot(b)
vms, vmi = V.pack_puzzles([{'tiles': t, 'walls': w, 'arrows': a, 'title': title}])
print('new pack', len(vms), len(vmi), 'multiple of 512' if len(vms) % 512 == 0 else 'NOT a multiple of 512', 'first slot round trip', V.decode_slot(vms[640:640 + 1536])[:3] == (t, w, a))
sys.exit(1 if bad else 0)
