"""Ground truth for HelpScreen (How to Play, HD 1.0): init 0x26218, render 0x25314. usage: hd_help_probe.py [topic page]"""
import os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hd_env
env = hd_env.make(); o = env.o; scr = env.alloc(0xd00); o.write(scr + 0xa14, bytes([1]))
o.call(0x26218, scr)
def state(topic=-1, page=0, st=-1, fade=0.0, mascot=0, a31=0, a32=0, count=None):
    o.write(scr + 0xa24, struct.pack('<i', topic)); o.write(scr + 0xa38, struct.pack('<i', page)); o.write(scr + 0xa34, struct.pack('<i', st)); o.write(scr + 0xa20, struct.pack('<f', fade))
    o.write(scr + 0xa2c, struct.pack('<i', mascot)); o.write(scr + 0xa31, bytes([a31])); o.write(scr + 0xa32, bytes([a32]))
    if count is not None: o.write(scr + 0xa3c, struct.pack('<i', count))
def render():
    del env.log[:]; o.call(0x25314, scr); return list(env.log)
if __name__ == '__main__':
    if len(sys.argv) > 2: state(int(sys.argv[1]), int(sys.argv[2]), 1, 0.0, 0, 1, 0, 6)
    for l in render(): print(l)
