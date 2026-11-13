"""Port of BHLib_UnpackData (ChuChu Rocket mobile engine) -- from iOS v1.1.2 decompile @0x87f4.
Stream header: bytes 0..3 (unused/size), 4=escape symbol, 5=literal-prefix bits, 6=max unary len,
7=run threshold, 8=offset extra bits, 9=N aux table bytes (aux[0..N-1] at 10), data at 10+N."""

class _Bits:
    def __init__(self, data, pos):
        self.d = data; self.p = pos; self.left = 0; self.cur = 0
    def nextbyte(self):
        b = self.d[self.p]; self.p += 1; return b
    def bit(self):
        if self.left == 0:
            self.cur = self.nextbyte(); self.left = 8
        self.left -= 1
        return (self.cur >> self.left) & 1
    def bits_add(self, n, add):
        left = self.left
        if left < n:
            old = self.cur
            new = self.nextbyte()
            self.cur = new
            self.left = 8 - (n - left)
            return (((add << left) | (((1 << left) - 1) & old)) << (n - left)) | (new >> self.left)
        self.left = left - n
        return (((1 << n) - 1) & (self.cur >> self.left)) | (add << n)

def unpack(data, expected=None):
    esc, pbits, maxun, thresh, offbits, naux = data[4], data[5], data[6], data[7], data[8], data[9]
    aux = list(data[10:10 + naux])
    br = _Bits(data, 10 + naux)
    out = bytearray()
    def getval():
        i = 1
        while True:
            if br.bit() == 0: v = i; break
            i += 1; v = maxun
            if maxun == i: break
        return br.bits_add(v - 1, 1)
    while True:
        if expected is not None and len(out) > expected + 4096:
            raise ValueError('overrun')
        sym = br.bits_add(pbits, 0)
        if sym != esc:
            out.append(br.bits_add(8 - pbits, sym) & 0xFF)
            continue
        L = getval()
        off_hi = 0
        if L < 2:
            if br.bit():
                if br.bit() == 0:
                    old = esc
                    esc = br.bits_add(pbits, 0)
                    out.append(br.bits_add(8 - pbits, old) & 0xFF)
                    continue
                L = getval()
                if thresh <= L:
                    t = br.bits_add(9 - maxun, L)
                    L = (t & 0xFF) + (getval() - 1) * 256
                k = getval()
                b = aux[k - 1] if k < 0x20 else br.bits_add(3, k) & 0xFF
                out.extend(bytes([b]) * (L + 1))
                continue
            # else fall through to copy with off_hi = 0
        else:
            v = getval()
            if v == thresh * 2 - 1:
                return bytes(out)
            off_hi = br.bits_add(offbits, v - 1)
        low = br.bits_add(8, 0)
        L += 1
        pos = len(out)
        for i in range(L):
            out.append(out[pos + i - off_hi * 256 + low - 256])
