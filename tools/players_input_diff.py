"""Diff of the players-pane input cases 0..13 (sound-free state flags, cumulative in one sequence) between the port and the original under Unicorn (tools/oracle/hd_players_input_probe.py)."""
import os, subprocess, sys
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.insert(0, os.path.join(ROOT, 'tools', 'oracle'))
import hd_players_input_probe as I
from unicorn import UC_HOOK_CODE
from ios_oracle import s32
o = I.o; scr = I.scr
o.uc.hook_add(UC_HOOK_CODE, lambda uc, a, s, u: I.item_stub(uc, a, s, u), begin=0xf2b0, end=0xf2b2)
offs = {'d3c': 0xd3c, 'd40': 0xd40, 'd44': 0xd44, 'd58': 0xd58, 'a40': 0xa40, 'a3c': 0xa3c, 'a38': 0xa38, 'd20': 0xd20}
ref = []
for item in range(14):
    I.run(item, 0)
    ref.append('%d ' % item + ' '.join('%s=%d' % (k, s32(o.u32(scr + v))) for k, v in offs.items()))
exe = os.path.join(ROOT, 'build', 'game', 'ccr.exe')
out = subprocess.run([exe, os.path.join(ROOT, 'local', 'cache', 'assets')], env=dict(os.environ, CCR_PLAYIN='1', CCR_HEADLESS='1'), capture_output=True, text=True).stdout.strip().splitlines()
bad = 0
for r, g in zip(ref, out):
    ok = r == g.replace(' ', ' ').strip(); bad += 0 if ok else 1
    if not ok: print('DIFF\n ref', r, '\n got', g)
print('cases', len(ref), 'mismatches', bad)
