"""Parse the sample directory of a Dreamcast sound bank (DP2SOUND.MLT / CHU2_SE.MLT) and decode the samples that live in the banks stored in the file.
Directory format (found 2026-11-13): after the section table (32-byte entries: tag, flags, file offset, padded size, ...), an 'SOSB' entry lists N descriptors of 0x40 bytes; each descriptor is
'SOSP' u8 bank u8 flag u32 start u16 length ... 'ENDP' (start = byte offset inside the bank, length = number of samples, 4-bit AICA ADPCM = length/2 bytes, high nibble first).
Banks 0, 1, 2 = the SOSB, SMPB, SMDB sections of the file; banks 3+ are not in the file (they live in sound RAM images loaded elsewhere) and are listed but not decoded.
usage: mlt_samples.py <bank.MLT> <out dir> [rate=22050]   (derived data, never committed)"""
import os, struct, sys, wave
sys.path.insert(0, os.path.dirname(__file__))
from aica_adpcm import decode, write_wav
from mlt_extract import sections as container_sections

def sections(m):
    out = {}
    for row in container_sections(m):
        if row['offset'] != 0xffffffff:
            out.setdefault(row['tag'].encode('ascii'), []).append((row['offset'], row['size']))
    return out

def directory(m):
    recs = []; i = m.find(b'SOSP')
    while i >= 0 and i < 0x8000:
        j = m.find(b'ENDP', i)
        rec = m[i:j + 4]; recs.append(dict(bank=rec[4], flag=rec[5], start=struct.unpack_from('<I', rec, 6)[0], length=struct.unpack_from('<H', rec, 10)[0]))
        i = m.find(b'SOSP', j)
    return recs

def main(path, out, rate=22050):
    m = open(path, 'rb').read(); sec = sections(m); os.makedirs(out, exist_ok=True)
    if not all(tag in sec for tag in (b'SOSB', b'SMPB', b'SMDB')):
        raise ValueError('This exploratory decoder requires SOSB, SMPB and SMDB payloads')
    print('EXPERIMENTAL: sample references, format and playback rate remain unverified; do not use these WAVs in the game')
    banks = {0: sec[b'SOSB'][0], 1: sec[b'SMPB'][0], 2: sec[b'SMDB'][0]}
    recs = directory(m); done = 0
    for k, r in enumerate(recs):
        if r['bank'] not in banks:
            print('sample %2d bank %d (not in the file), start %#x, %d samples' % (k, r['bank'], r['start'], r['length'])); continue
        off, size = banks[r['bank']]
        if r['start'] + r['length'] // 2 > size:
            print('sample %2d outside its bank' % k); continue
        data = m[off + r['start']: off + r['start'] + r['length'] // 2 + 1]
        write_wav(os.path.join(out, 'dc_%02d.wav' % k), decode(data, False)[:r['length']], rate); done += 1
        print('sample %2d bank %d start %#x %d samples = %.3f s at %d Hz -> dc_%02d.wav' % (k, r['bank'], r['start'], r['length'], r['length'] / rate, rate, k))
    print(len(recs), 'descriptors,', done, 'decoded')

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 22050)
