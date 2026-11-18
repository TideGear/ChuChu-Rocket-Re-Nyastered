import struct,bisect,sys
d=open('local/cache/assets/dreamcast/files/1ST_READ.BIN','rb').read(); B=0x8c010000
funcs=sorted((int(l.split()[0],16)) for l in open('analysis/decomp/dc_1st/1ST_READ.BIN.functions.txt'))
def fn(a): return funcs[bisect.bisect_right(funcs,a)-1]
bsr={}
for i in range(0,len(d)-1,2):
    op=struct.unpack_from('<H',d,i)[0]
    if op&0xf000==0xb000:
        disp=op&0xfff; disp=disp-4096 if disp&0x800 else disp
        bsr.setdefault(B+i+4+2*disp,[]).append(B+i)
ptr={}
for i in range(0,len(d)-3,4):
    v=struct.unpack_from('<I',d,i)[0]
    if B<=v<B+len(d): ptr.setdefault(v,[]).append(B+i)
def callers(f):
    r=set()
    for a in bsr.get(f,[]): r.add(('bsr',hex(fn(a))))
    for a in ptr.get(f,[]): r.add(('ptr',hex(a),hex(fn(a))))
    return sorted(r)
f=int(sys.argv[1],16)
for depth in range(int(sys.argv[2]) if len(sys.argv)>2 else 3):
    c=callers(f); print(hex(f),'<-',c)
    nxt=[int(x[-1],16) for x in c if x[0]=='bsr'] or [int(x[-1],16) for x in c]
    if not nxt: break
    f=nxt[0]
