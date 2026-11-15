"""Diff of the port's result screen (JudgeWinPriority) against the original under Unicorn (tools/oracle/hd_judge_probe.py) for random scores / ranks / win counts."""
import os, random, subprocess, sys
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.insert(0, os.path.join(ROOT, 'tools', 'oracle'))
import hd_judge_probe as P
exe = os.path.join(ROOT, 'build', 'game', 'ccr.exe'); rnd = random.Random(int(sys.argv[2]) if len(sys.argv) > 2 else 7); bad = 0; N = int(sys.argv[1]) if len(sys.argv) > 1 else 40
def dense(sc):
    return [len({x for x in sc if x > s}) for s in sc]
for i in range(N):
    sc = [rnd.choice([0, 3, 12, 45, 99, 100, 123, 250, 999]) for _ in range(4)]; rk = dense(sc); wp = rnd.randint(0, 4); wins = [rnd.randint(0, wp + 1) for _ in range(4)]
    winner = rnd.randrange(4); flag = rnd.choice([0, 1]); reach = rnd.randrange(16)
    ref = P.judge(sc, rk, wp, reach, wins, winner, flag)
    exp = ['%d %d %.2f %.2f %d %.3f %d' % (c[1], c[2], c[3], c[4], c[5], c[6], c[7]) for c in ref]
    arg = '%d,%d,%d,%d;%d,%d,%d,%d;%d,%d,%d,%d;%d,%d,%d,%d' % (*sc, *rk, *wins, winner, flag, wp, reach)
    out = subprocess.run([exe, os.path.join(ROOT, 'local', 'cache', 'assets')], env=dict(os.environ, CCR_JUDGE=arg, CCR_HEADLESS='1'), capture_output=True, text=True).stdout.strip().splitlines()
    got = [l.split(' ', 1)[1] for l in out]
    if exp != got:
        bad += 1; print('DIFF', arg)
        for a, b2 in zip(exp, got):
            if a != b2: print('  ref', a, '\n  got', b2); break
        if len(exp) != len(got): print('  count', len(exp), len(got))
print('cases', N, 'mismatches', bad)
