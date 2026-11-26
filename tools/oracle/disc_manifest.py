#!/usr/bin/env python3
"""Disc file manifest: every file of the extracted Dreamcast disc, marked by whether its name (or stem) appears anywhere in tools/ or game/.
usage: disc_manifest.py   (writes local/disc_manifest.tsv: folder, path, referenced 0/1, bytes; prints per-folder counts and the unreferenced names)
A name match is a first pass only: files loaded by a pattern (e.g. "WINNO%d") or by table index count as unreferenced, and extraction converts every
PRS archive and PVR wholesale, so "unreferenced" means "probably not drawn by the port yet", to be checked against the code that loads it."""
import os,glob,collections
root='local/cache/assets/dreamcast/files'
src=''
for f in glob.glob('tools/**/*.py',recursive=True)+glob.glob('game/**/*.[ch]pp',recursive=True)+glob.glob('game/**/*.h',recursive=True):
    src+=open(f,encoding='utf-8',errors='ignore').read().upper()+'\n'
rows=[]
for dp,dn,fn in os.walk(root):
    for f in fn:
        rel=os.path.relpath(os.path.join(dp,f),root).replace(os.sep,'/')
        top=rel.split('/')[0] if '/' in rel else '(root)'
        stem=os.path.splitext(f)[0].upper()
        used = f.upper() in src or (len(stem)>=4 and stem in src)
        rows.append((top,rel,used,os.path.getsize(os.path.join(dp,f))))
by=collections.defaultdict(lambda:[0,0])
for top,rel,used,sz in rows: by[top][0]+=1; by[top][1]+=used
for t,(n,u) in sorted(by.items()): print(f'{t:12} {u:4}/{n:4} referenced')
open('local/disc_manifest.tsv','w').write('\n'.join(f'{t}\t{r}\t{int(u)}\t{s}' for t,r,u,s in rows))
print('unreferenced ENGLISH:',sorted(r.split('/')[-1] for t,r,u,s in rows if t=='ENGLISH' and not u))
print('unreferenced other:',sorted(r for t,r,u,s in rows if t not in ('ENGLISH','FRENCH','GERMAN','SPANISH','JAPANIESE') and not u))
