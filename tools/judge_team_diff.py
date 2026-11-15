"""Diff of the port's team result screen (JudgeWinTeamPriority) against the original under Unicorn for random team scores / ranks / wins."""
import os, random, subprocess, sys
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.insert(0, os.path.join(ROOT, 'tools', 'oracle'))
import hd_judge_probe as P
exe = os.path.join(ROOT, 'build', 'game', 'ccr.exe'); rnd = random.Random(int(sys.argv[2]) if len(sys.argv) > 2 else 5); bad = 0; N = int(sys.argv[1]) if len(sys.argv) > 1 else 20
for i in range(N):
    sc = [rnd.choice([0, 7, 45, 99, 123, 456, 999]) for _ in range(2)]; rk = [0 if sc[0] >= sc[1] else 1, 0 if sc[1] >= sc[0] else 1]
    wp = rnd.randint(0, 4); wins = [rnd.randint(0, wp + 1) for _ in range(2)]; winner = rnd.randrange(2); flag = rnd.choice([0, 1]); reach = rnd.randrange(4)
    ref = P.judge_team(sc, rk, wp, reach, wins, winner, flag)
    exp = ['%d %d %.2f %.2f %d %.3f %d' % (c[1], c[2], c[3], c[4], c[5], c[6], c[7]) for c in ref]
    arg = '%d,%d;%d,%d;%d,%d;%d,%d,%d,%d' % (*sc, *rk, *wins, winner, flag, wp, reach)
    out = subprocess.run([exe, os.path.join(ROOT, 'local', 'cache', 'assets')], env=dict(os.environ, CCR_JUDGET=arg, CCR_HEADLESS='1'), capture_output=True, text=True).stdout.strip().splitlines()
    got = [l.split(' ', 1)[1] for l in out]
    if exp != got:
        bad += 1; print('DIFF', arg)
        for a, b2 in zip(exp, got):
            if a != b2: print('  ref', a, '\n  got', b2); break
        if len(exp) != len(got): print('  count', len(exp), len(got))
print('cases', N, 'mismatches', bad)
