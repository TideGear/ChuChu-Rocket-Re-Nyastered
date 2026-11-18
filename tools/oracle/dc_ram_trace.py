import sys,struct,collections,json
sys.path.insert(0,'tools/oracle')
from sh4 import SH4
ram0=bytearray(open('local/dc_ref/shots/d3_03100.ram','rb').read())
def run(entry,sets,stubs,args=()):
    stubs=set(stubs)
    for it in range(120):
        ram=bytearray(ram0)
        for a,v in sets: ram[a&0xffffff]=v
        sh=SH4(); sh.ram[:len(ram)]=ram; log=[]; last=[None]
        def mk(addr):
            def h(m): log.append((addr,[m.r[i] for i in (4,5,6,7)],[float(round(float(m.fget(i)),3)) for i in range(4,12)]))
            return h
        sh.hooks={a&0x1fffffff:mk(a) for a in stubs}
        def tr(m,pc,op):
            if (op&0xf0ff)==0x400b: last[0]=m.r[(op>>8)&15]
            elif (op&0xf000)==0xb000:
                d=op&0xfff; d=d-4096 if d&0x800 else d; last[0]=pc+4+2*d
        sh.trace=tr
        try: sh.call(entry,*args,max_insn=20_000_000); return log,stubs,None
        except Exception as e:
            t=last[0]
            if t is None or t in stubs: return log,stubs,str(e)
            stubs.add(t)
    return log,stubs,'many'
if __name__=='__main__':
    stubs=set()
    for st in range(0x80,0x8b):
        log,stubs,err=run(0x8c034c60,[(0x8c2409f1,st)],stubs)
        objs=[(hex(r[0])) for a,r,f in log if a==0x8c0fc308]
        print(hex(st),len(log),'calls',err,'objects',objs[:12])
