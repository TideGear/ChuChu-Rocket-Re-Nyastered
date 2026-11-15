"""Ground truth for the battle banner tasks (HD 1.0): BattleCountDrawPriority (0x1f580, modes 0..6, lifetime 120 / 60 / 45 ticks) and RoundCountDrawPriority (0x205fc);
logs the Render::drawImage calls per tick. usage: hd_task_probe.py count <mode> | round <round number>"""
import os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hd_bubble_probe as P
o, log, appdata = P.make()
def task(counter_byte, tick=0):
    t = o.alloc(0x80); o.write(t + 4, struct.pack('<I', tick)); o.write(t + 0x2c, bytes([counter_byte])); return t
def life(m): return 45 if m > 5 else (60 if m <= 2 else 120)
def count_calls(m, tick):
    t = task(m, tick); del log[:]; o.call(0x1f580, t); return list(log)
def round_calls(n, tick=0):
    t = task(n, tick); del log[:]; o.call(0x205fc, t); return list(log)
if __name__ == '__main__':
    if sys.argv[1] == 'count':
        m = int(sys.argv[2])
        for tick in (0, life(m) // 2, life(m) - 1): print(tick, count_calls(m, tick))
    else:
        for tick in (0, 1, 10, 37, 74): print(tick, round_calls(int(sys.argv[2]), tick))
