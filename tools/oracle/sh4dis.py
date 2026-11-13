"""Compact SH-4 disassembler for the user's own 1ST_READ.BIN (base 0x8C010000). usage: sh4dis.py <file> <start hex> <count> [base hex]"""
import struct, sys
def s8(v): return v - 256 if v & 128 else v
def dis(d, base, a):
    op = struct.unpack_from('<H', d, a - base)[0]; n = (op >> 8) & 15; m = (op >> 4) & 15; hi = op >> 12; lo = op & 15; k = op & 255
    R = lambda x: 'r%d' % x; F = lambda x: 'fr%d' % x
    def lit(sz, mul):
        t = (((a + 4) & ~3) if sz == 4 else a + 4) + k * mul; v = struct.unpack_from('<I' if sz == 4 else '<h', d, t - base)[0] if 0 <= t - base < len(d) - 3 else 0
        return t, v
    if hi == 0xE: return 'mov #%d,%s' % (s8(k), R(n))
    if hi == 0x7: return 'add #%d,%s' % (s8(k), R(n))
    if hi == 0xD: t, v = lit(4, 4); return 'mov.l @(%#x),%s   ; %#x' % (t, R(n), v)
    if hi == 0x9: t, v = lit(2, 2); return 'mov.w @(%#x),%s   ; %d' % (t, R(n), v)
    if hi == 0x1: return 'mov.l %s,@(%d,%s)' % (R(m), lo * 4, R(n))
    if hi == 0x5: return 'mov.l @(%d,%s),%s' % (lo * 4, R(m), R(n))
    if hi == 0x6:
        t = ['mov %s,%s', 'mov.b @%s,%s', 'mov.w @%s,%s', 'mov.l @%s,%s', 'mov.b @%s,%s', 'mov.w @%s,%s']
        names = {3: 'mov %s,%s', 0: 'mov.b @%s,%s', 1: 'mov.w @%s,%s', 2: 'mov.l @%s,%s', 4: 'mov.b @%s+,%s', 5: 'mov.w @%s+,%s', 6: 'mov.l @%s+,%s', 7: 'not %s,%s', 8: 'swap.b %s,%s', 9: 'swap.w %s,%s', 0xA: 'negc %s,%s', 0xB: 'neg %s,%s', 0xC: 'extu.b %s,%s', 0xD: 'extu.w %s,%s', 0xE: 'exts.b %s,%s', 0xF: 'exts.w %s,%s'}
        return names[lo] % (R(m), R(n))
    if hi == 0x2:
        names = {0: 'mov.b %s,@%s', 1: 'mov.w %s,@%s', 2: 'mov.l %s,@%s', 4: 'mov.b %s,@-%s', 5: 'mov.w %s,@-%s', 6: 'mov.l %s,@-%s', 7: 'div0s %s,%s', 8: 'tst %s,%s', 9: 'and %s,%s', 0xA: 'xor %s,%s', 0xB: 'or %s,%s', 0xC: 'cmp/str %s,%s', 0xD: 'xtrct %s,%s', 0xE: 'mulu.w %s,%s', 0xF: 'muls.w %s,%s'}
        return (names[lo] % (R(m), R(n))) if lo in names else '.word %04x' % op
    if hi == 0x3:
        names = {0: 'cmp/eq', 2: 'cmp/hs', 3: 'cmp/ge', 4: 'div1', 5: 'dmulu.l', 6: 'cmp/hi', 7: 'cmp/gt', 8: 'sub', 0xA: 'subc', 0xB: 'subv', 0xC: 'add', 0xD: 'dmuls.l', 0xE: 'addc', 0xF: 'addv'}
        return '%s %s,%s' % (names.get(lo, '?'), R(m), R(n))
    if hi == 0x4:
        sp = {0x00: 'shll', 0x01: 'shlr', 0x04: 'rotl', 0x05: 'rotr', 0x08: 'shll2', 0x09: 'shlr2', 0x18: 'shll8', 0x19: 'shlr8', 0x28: 'shll16', 0x29: 'shlr16', 0x20: 'shal', 0x21: 'shar', 0x24: 'rotcl', 0x25: 'rotcr', 0x10: 'dt', 0x11: 'cmp/pz', 0x15: 'cmp/pl', 0x0B: 'jsr @', 0x2B: 'jmp @', 0x0E: 'ldc sr,', 0x1E: 'ldc gbr,', 0x0A: 'lds mach,', 0x1A: 'lds macl,', 0x2A: 'lds pr,', 0x5A: 'lds fpul,', 0x6A: 'lds fpscr,', 0x22: 'sts.l pr,@-', 0x52: 'sts.l fpul,@-', 0x62: 'sts.l fpscr,@-', 0x26: 'lds.l @%s+,pr', 0x56: 'lds.l @%s+,fpul', 0x66: 'lds.l @%s+,fpscr'}
        if k in sp:
            t = sp[k]
            if '%s' in t: return t % R(n)
            if t.endswith(',') or t.endswith('@') or t.endswith('@-'): return t.replace('@-', '@-' + R(n)) if t.endswith('@-') else (t + R(n) if t.endswith('@') else t + R(n))
            return t + ' ' + R(n)
        if lo == 0xC: return 'shad %s,%s' % (R(m), R(n))
        if lo == 0xD: return 'shld %s,%s' % (R(m), R(n))
        return '.word %04x' % op
    if hi == 0x0:
        if lo == 4: return 'mov.b %s,@(r0,%s)' % (R(m), R(n))
        if lo == 5: return 'mov.w %s,@(r0,%s)' % (R(m), R(n))
        if lo == 6: return 'mov.l %s,@(r0,%s)' % (R(m), R(n))
        if lo == 7: return 'mul.l %s,%s' % (R(m), R(n))
        if lo == 0xC: return 'mov.b @(r0,%s),%s' % (R(m), R(n))
        if lo == 0xD: return 'mov.w @(r0,%s),%s' % (R(m), R(n))
        if lo == 0xE: return 'mov.l @(r0,%s),%s' % (R(m), R(n))
        sp = {0x09: 'nop', 0x0B: 'rts', 0x08: 'clrt', 0x18: 'sett', 0x28: 'clrmac', 0x19: 'div0u', 0x29: 'movt %s', 0x12: 'stc gbr,%s', 0x0A: 'sts mach,%s', 0x1A: 'sts macl,%s', 0x2A: 'sts pr,%s', 0x5A: 'sts fpul,%s', 0x6A: 'sts fpscr,%s', 0x02: 'stc sr,%s', 0x03: 'bsrf %s', 0x23: 'braf %s', 0x93: 'ocbi @%s', 0xA3: 'ocbp @%s', 0xB3: 'ocbwb @%s', 0x83: 'pref @%s', 0xC3: 'movca.l r0,@%s'}
        t = sp.get(k, '.word %04x' % op); return t % R(n) if '%s' in t else t
    if hi == 0x8:
        sub = n; t = a + 4 + s8(k) * 2
        d_ = {0: 'mov.b r0,@(%d,%s)' % (lo, R(m)), 1: 'mov.w r0,@(%d,%s)' % (lo * 2, R(m)), 4: 'mov.b @(%d,%s),r0' % (lo, R(m)), 5: 'mov.w @(%d,%s),r0' % (lo * 2, R(m)), 8: 'cmp/eq #%d,r0' % s8(k), 9: 'bt %#x' % t, 0xB: 'bf %#x' % t, 0xD: 'bt/s %#x' % t, 0xF: 'bf/s %#x' % t}
        return d_.get(sub, '.word %04x' % op)
    if hi in (0xA, 0xB):
        x = op & 0xfff; x = x - 4096 if x & 0x800 else x; return ('bra %#x' if hi == 0xA else 'bsr %#x') % (a + 4 + x * 2)
    if hi == 0xC:
        sub = n; return {0: 'mov.b r0,@(%d,gbr)' % k, 1: 'mov.w r0,@(%d,gbr)' % (k * 2), 2: 'mov.l r0,@(%d,gbr)' % (k * 4), 3: 'trapa #%d' % k, 4: 'mov.b @(%d,gbr),r0' % k, 5: 'mov.w @(%d,gbr),r0' % (k * 2), 6: 'mov.l @(%d,gbr),r0' % (k * 4), 7: 'mova @(%#x),r0' % (((a + 4) & ~3) + k * 4), 8: 'tst #%d,r0' % k, 9: 'and #%d,r0' % k, 0xA: 'xor #%d,r0' % k, 0xB: 'or #%d,r0' % k}.get(sub, '.word %04x' % op)
    if hi == 0xF:
        if lo < 6 or lo == 0xE: return {0: 'fadd', 1: 'fsub', 2: 'fmul', 3: 'fdiv', 4: 'fcmp/eq', 5: 'fcmp/gt', 0xE: 'fmac fr0,'}[lo] + ' %s,%s' % (F(m), F(n)) if lo != 0xE else 'fmac fr0,%s,%s' % (F(m), F(n))
        names = {6: 'fmov.s @(r0,%s),%s', 7: 'fmov.s %s,@(r0,%s)', 8: 'fmov.s @%s,%s', 9: 'fmov.s @%s+,%s', 0xA: 'fmov.s %s,@%s', 0xB: 'fmov.s %s,@-%s', 0xC: 'fmov %s,%s'}
        if lo in names:
            if lo in (6, 8, 9): return names[lo] % (R(m), F(n))
            if lo in (7, 0xA, 0xB): return names[lo] % (F(m), R(n))
            return names[lo] % (F(m), F(n))
        if lo == 0xD:
            return {0: 'flds %s,fpul', 1: 'fsts fpul,%s', 2: 'float fpul,%s', 3: 'ftrc %s,fpul', 4: 'fneg %s', 5: 'fabs %s', 6: 'fsqrt %s', 7: 'fsrra %s', 8: 'fldi0 %s', 9: 'fldi1 %s'}.get(m, '.word %04x' % op).replace('%s', F(n))
    return '.word %04x' % op
if __name__ == '__main__':
    f = sys.argv[1]; start = int(sys.argv[2], 16); cnt = int(sys.argv[3]); base = int(sys.argv[4], 16) if len(sys.argv) > 4 else 0x8C010000
    d = open(f, 'rb').read()
    for i in range(cnt):
        a = start + 2 * i; print('%08x  %04x  %s' % (a, struct.unpack_from('<H', d, a - base)[0], dis(d, base, a)))
