#!/usr/bin/env python3
"""Per-mode inventory of the Dreamcast game's tasks, sound effects and music, from the code (goal.md: the audit's lists come from code scans).

usage: mode_inventory.py [--md]
Roots: the 23 modes' phase tables (mode table 0x8c0b373c; each entry points to a list of handler pointers, e.g. Puzzle 15 -> 0x8c0bdaec).
Edges: every code address a function loads from its literal pools or reaches by bsr (calls, task update/draw callbacks, state swaps).
For each mode prints the SE cues (0x8c01203a / 0x8c0120d4 r4), music requests (0x8c012350 r4) and task creations (0x8c01f0a0 / 0x8c01f012
r4/r5, swaps 0x8c01f220 r5) in functions reachable from that mode, split into mode-only and shared (reached by more than one mode).
Limits: indirect calls through RAM tables are not followed unless the table address is a literal pointing into code; r4 values not loaded
by a literal or immediate in the same function print as '-'."""
import os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from task_inventory import load, scan, B

SE = (0x8c01203a, 0x8c0120d4); MUSIC = 0x8c012350; CREATE = (0x8c01f0a0, 0x8c01f012); SWAP = 0x8c01f220
MODES = 0x8c0b373c; NMODES = 23


ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def functions(d, code_end, extra=()):
    """Function starts: Ghidra's list, every `sts.l pr,@-r15` prologue and every code address loaded by a pc-relative mov.l (that catches leaf
    functions entered through jsr, which Ghidra and the prologue scan miss). Each function runs to the next start."""
    u16 = lambda a: struct.unpack_from('<H', d, a - B)[0]; u32 = lambda a: struct.unpack_from('<I', d, a - B)[0]
    st = {int(ln.split('	')[0], 16) for ln in open(os.path.join(ROOT, 'analysis/decomp/dc_1st/1ST_READ.BIN.functions.txt'))}
    for pc in range(B, code_end, 2):
        op = u16(pc)
        if op == 0x4f22: st.add(pc)
        elif (op & 0xf000) == 0xd000:
            t = ((pc + 4) & ~3) + (op & 0xff) * 4
            if t < B + len(d) - 3:
                v = u32(t)
                if B <= v < code_end and v % 2 == 0: st.add(v)
    st |= set(extra)
    st = sorted(a for a in st if B <= a < code_end)
    return [(a, (st[i + 1] if i + 1 < len(st) else code_end) - a) for i, a in enumerate(st)]


def main():
    d = load(); u16 = lambda a: struct.unpack_from('<H', d, a - B)[0]; u32 = lambda a: struct.unpack_from('<I', d, a - B)[0]
    code_end = 0x8c07f6a0
    mode_handlers = [u32(u32(MODES + 4 * m) + 4 * k) for m in range(NMODES) for k in range(64) if all(B <= u32(u32(MODES + 4 * m) + 4 * j) < code_end for j in range(k + 1))]
    fl = functions(d, code_end, mode_handlers); import bisect
    starts = [a for a, n in fl]; size = dict(fl); funcs = starts
    code_end = 0x8c07f6a0                                   # first string data (0x8c07f6a0, see task_inventory sites); code lies below
    def owner(a):
        i = bisect.bisect_right(starts, a) - 1
        return starts[i] if i >= 0 and a < starts[i] + max(size[starts[i]], 2) else None
    incode = lambda v: B <= v < code_end and v % 2 == 0
    edges = {}
    for f in funcs:                                          # literal-pool loads and bsr targets inside the function's body
        out = set()
        for pc in range(f, min(f + size[f], code_end), 2):
            op = u16(pc)
            if (op & 0xf000) == 0xd000:
                t = ((pc + 4) & ~3) + (op & 0xff) * 4
                if t < B + len(d) - 3:
                    v = u32(t)
                    if incode(v): out.add(owner(v))
                    elif code_end <= v < B + len(d) - 4 and v % 4 == 0:   # a data table of handlers (phase tables, state lists): follow its run of code pointers
                        for k in range(256):
                            w = u32(v + 4 * k) if v + 4 * k < B + len(d) - 3 else 0
                            if incode(w): out.add(owner(w))
                            elif k > 0 and w == 0: break
                            elif k > 0 or w != 0: break
            elif (op & 0xf000) == 0xb000:
                disp = op & 0xfff; t = pc + 4 + 2 * (disp - 0x1000 if disp & 0x800 else disp)
                if incode(t): out.add(owner(t))
        end = min(f + size[f], code_end)                     # fall-through: a body with no rts / jmp at all runs into the next start
        term = False
        for pc in range(f, end, 2):                          # any rts / jmp in the body (literal pools follow the last one)
            op = u16(pc)
            if op == 0x000b or (op & 0xf0ff) == 0x402b: term = True
        if not term and end < code_end: out.add(owner(end))
        out.discard(None); out.discard(f); edges[f] = out
    roots = {}
    for m in range(NMODES):
        t = u32(MODES + 4 * m); rs = set()
        for k in range(64):
            v = u32(t + 4 * k)
            if not incode(v): break
            if owner(v) is not None: rs.add(owner(v))
        roots[m] = rs
    if '--ram' in sys.argv:   # run-time roots: the update/draw callbacks live in the task pool (0x8c1d9b30, 88-byte slots, +64/+68) of every
        import glob             # Flycast RAM dump under local/, filed under the mode variable 0x8c1af108 of that dump
        nd = 0
        for fn in glob.glob(os.path.join(ROOT, 'local', '**', '*.ram'), recursive=True):
            r = open(fn, 'rb').read()
            if len(r) < 0x1000000: continue
            ru = lambda a: struct.unpack_from('<I', r, a - 0x8c000000)[0]
            m = ru(0x8c1af108)
            if m >= NMODES: continue
            nd += 1
            for i in range(1024):
                for o in (64, 68):
                    v = ru(0x8c1d9b30 + 88 * i + o)
                    if incode(v) and owner(v) is not None: roots[m].add(owner(v))
        print(f'<!-- run-time roots from {nd} RAM dumps -->')
    reach = {}
    for m, rs in roots.items():
        seen = set(); st = list(rs)
        while st:
            f = st.pop()
            if f in seen or f is None: continue
            seen.add(f); st.extend(edges.get(f, ()))
        reach[m] = seen
    count = {}
    for s in reach.values():
        for f in s: count[f] = count.get(f, 0) + 1
    if '--mode' in sys.argv:   # list the functions only this mode reaches (size, pad-word readers) and stop
        m = int(sys.argv[sys.argv.index('--mode') + 1]); pads = {0x8c1aefd8: 'pressed', 0x8c1aee88: 'pad', 0x8c1aefc8: 'held?', 0x8c1aef98: 'pad+'}
        for f in sorted(g for g in reach[m] if count[g] == 1):
            hit = sorted({pads[u32(((pc + 4) & ~3) + (u16(pc) & 0xff) * 4)] for pc in range(f, f + size[f], 2) if (u16(pc) & 0xf000) == 0xd000 and u32(((pc + 4) & ~3) + (u16(pc) & 0xff) * 4) in pads})
            print(f'{f:#x} {size[f]}', ' '.join(hit))
        return
    sites = [(t, s_, owner(s_), a) for t, s_, f, a in scan(d, set(SE) | {MUSIC} | set(CREATE) | {SWAP})]
    fmt = lambda v: '-' if v is None else hex(v) if isinstance(v, int) and v > 0xffff else str(v)
    def cues(fs, kinds):
        return sorted({fmt(a[0]) for t, s_, f, a in sites if t in kinds and f in fs}, key=lambda x: (not x.lstrip('-').isdigit(), int(x) if x.lstrip('-').isdigit() else 0, x))
    def tasks(fs):
        return sorted({f'{fmt(a[0])}/{fmt(a[1])}' for t, s_, f, a in sites if t in CREATE and f in fs} | {f'swap {fmt(a[1])}' for t, s_, f, a in sites if t == SWAP and f in fs})
    print('# Dreamcast per-mode code inventory (generated)\n')
    print('Generated by `py tools/oracle/mode_inventory.py --ram > docs/inventory_dc_modes.md` from 1ST_READ.BIN. Roots: the phase table of each mode (mode table `0x8c0b373c`). '
          'Edges: code addresses loaded from literal pools, bsr targets, and runs of code pointers in data tables those literals point to. '
          '"All" = every cue reachable from the mode; "only" = reached from no other mode. `-` = argument not a constant in the calling function. '
          'With --ram, the task callbacks live in every Flycast RAM dump under local/ are added as roots of the mode the dump was in; fall-through into the next function counts as an edge. "All" is an upper bound (shared helpers reach cues a mode may never play); a cue is confirmed for a mode only by tracing its trigger. The last section lists call sites no mode reaches yet.\n')
    print('| Mode | Functions (only / all) | SE cues, all | SE only | Music, all | Tasks created / state swaps (all) |\n|---|---|---|---|---|---|')
    for m in range(NMODES):
        own = {f for f in reach[m] if count[f] == 1}
        print(f'| {m} | {len(own)} / {len(reach[m])} | {" ".join(cues(reach[m], SE)) or "none"} | {" ".join(cues(own, SE)) or "none"} | {" ".join(cues(reach[m], (MUSIC,))) or "none"} | {", ".join(tasks(reach[m])) or "none"} |')
    g = set(); st = [owner(0x8c018478)]                     # the main loop (pause controller 0x8c01a174, task server 0x8c01909c): runs in every mode
    while st:
        f = st.pop()
        if f in g or f is None: continue
        g.add(f); st.extend(edges.get(f, ()))
    gn = {f for f in g if f not in count}
    print(f'\n## Every mode: the main loop `0x8c018478` ({len(gn)} functions no mode root reaches)\n\nSE {" ".join(cues(gn, SE)) or "none"}; music {" ".join(cues(gn, (MUSIC,))) or "none"}; tasks {", ".join(tasks(gn)) or "none"}')
    un = sorted({f for t, s_, f, a in sites if f not in count and f not in g and f is not None})
    print(f'\n## Call sites no mode reaches statically ({len(un)} functions)\n\n| Function | SE cues | Music | Tasks / swaps |\n|---|---|---|---|')
    for f in un:
        print(f'| {f:#x} | {" ".join(cues({f}, SE)) or "-"} | {" ".join(cues({f}, (MUSIC,))) or "-"} | {", ".join(tasks({f})) or "-"} |')
    tot = lambda kinds: len([1 for t, s_, f, a in sites if t in kinds])
    print(f'\nTotals: {tot(SE)} SE call sites, {tot((MUSIC,))} music call sites, {tot(CREATE)} task creations, {tot((SWAP,))} state swaps.')


if __name__ == '__main__':
    main()
