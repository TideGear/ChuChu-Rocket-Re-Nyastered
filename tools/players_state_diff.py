"""Compare HD 1.0 PlayerSelectScreen process states 0x23 through 0x27 against Unicorn."""
import os, subprocess, sys
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.insert(0, os.path.join(ROOT, 'tools', 'oracle'))
import players_state_probe as P
exe = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'build', 'game', 'ccr.exe')
def port(env_name):
    return subprocess.run([exe, os.path.join(ROOT, 'local', 'cache', 'assets')], env=dict(os.environ, CCR_HEADLESS='1', **{env_name: '1'}),
                          capture_output=True, text=True, check=True).stdout.splitlines()


def loading_port(width, dt, clocks, textures):
    args = ' '.join(map(str, (width, len(textures), dt, *clocks, *textures)))
    out = subprocess.run([exe], input=args + '\n', env=dict(os.environ, CCR_PSTEST23='1'),
                         capture_output=True, text=True, check=True).stdout.splitlines()
    trace = []
    for line in out:
        *events, state, count, pulse, rate, preview, preview_frame, character, character_frame = line.split()
        ops = []
        for event in events:
            name, texture, *space = event.split(':')
            ops.append((name, int(texture), int(space[0]) if space else 0))
        bits = lambda x: P.f2u(float.fromhex(x))
        trace.append((tuple(ops), int(state), int(count), bits(pulse), bits(rate), bits(preview),
                      int(preview_frame), bits(character), int(character_frame)))
    return trace


ref = P.grid() + P.grid24()
out = port('CCR_PSTEST') + port('CCR_PSTEST24')
bad = [(r, g) for r, g in zip(ref, out) if r != g]
for r, g in bad[:5]: print('DIFF\n ref', r, '\n got', g)
mismatches = len(bad) + abs(len(ref) - len(out))
print('0x24-0x27 cases', len(ref), 'port lines', len(out), 'mismatches', mismatches)

ticks = loading_mismatches = 0
for costume, width, dt, clocks, empty in (
    (0, 1024, 16667, (0, 0, 0, 0, 0, 0, 0, 0), False),
    (1, 1024, 500, (1122, 7, 500, 2, 3, 495, 3, 4), False),
    (2, 768, 16.25, (765, 0, 999, 2, 4, 991, 3, 5), False),
    (0, 1024, 0, (1018, 7, 999, 1, 3, 994, 1, 3), False),
    (0, 1024, 16667, (1019, 7, 500, 2, 3, 495, 3, 4), True),
):
    textures, ref = P.loading_trace(costume, width, dt, clocks, empty)
    out = loading_port(width, dt, clocks, textures)
    ticks += len(ref)
    differences = [(index, r, g) for index, (r, g) in enumerate(zip(ref, out)) if r != g]
    loading_mismatches += len(differences) + abs(len(ref) - len(out))
    for index, r, g in differences[:3]:
        print('0x23 DIFF costume', costume, 'tick', index, '\n ref', r, '\n got', g)
print('0x23 ticks', ticks, 'mismatches', loading_mismatches)
sys.exit(1 if mismatches or loading_mismatches else 0)
