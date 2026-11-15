"""Differential test: PlayerSelectScreen process states 0x26 / 0x27 (playersFlowStep in game/app/main.cpp) against the original
under Unicorn (tools/oracle/players_state_probe.py). 192 cases: state, timer gate, a3c, a40, network flag, split flag, dt, fade."""
import os, subprocess, sys
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.insert(0, os.path.join(ROOT, 'tools', 'oracle'))
import players_state_probe as P
ref = P.grid()
exe = os.path.join(ROOT, 'build', 'game', 'ccr.exe')
out = subprocess.run([exe, os.path.join(ROOT, 'local', 'cache', 'assets')], env=dict(os.environ, CCR_PSTEST='1', CCR_HEADLESS='1'),
                     capture_output=True, text=True).stdout.splitlines()
bad = [(r, g) for r, g in zip(ref, out) if r != g]
for r, g in bad[:5]: print('DIFF\n ref', r, '\n got', g)
print('cases', len(ref), 'port lines', len(out), 'mismatches', len(bad) + abs(len(ref) - len(out)))
sys.exit(1 if bad or len(ref) != len(out) else 0)
