"""Ground truth for players-pane case 12 (HD 1.0 0x31d24): team toggle of +0xa40 (0<->1, other values untouched), sfx 2, gated by +0xd20==0 or network flag byte."""
import os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hd_players_input_probe as P
o, scr = P.o, P.scr
for d20 in (0, 1):
    for net in (0, 1):
        for a40 in (0, 1, 2, 0xffffffff):
            o.write(scr + 0xa40, struct.pack('<I', a40)); o.write(scr + 0xd20, bytes([d20]))
            P.run(12, flags=None)  # baseline call resets log
            o.write(scr + 0xa40, struct.pack('<I', a40))
            r = P.run(12)
            print('d20', d20, 'a40', hex(a40), r, hex(struct.unpack('<I', bytes(o.read(scr + 0xa40, 4)))[0]))
# network flag row: DAT_00032170 is a literal-pool pointer to a cell holding the flag address (*DAT is the flag byte's address)
cell = struct.unpack('<I', bytes(o.read(0x32170, 4)))[0]
flag = struct.unpack('<I', bytes(o.read(cell, 4)))[0]
print('flag cell', hex(cell), 'flag addr', hex(flag))
for d20 in (0, 1):
    for a40 in (0, 1):
        o.write(flag, bytes([1])); o.write(scr + 0xd20, bytes([d20])); o.write(scr + 0xa40, struct.pack('<I', a40))
        r = P.run(12); o.write(flag, bytes([0]))
        print('net=1 d20', d20, 'a40', a40, r, struct.unpack('<I', bytes(o.read(scr + 0xa40, 4)))[0])
