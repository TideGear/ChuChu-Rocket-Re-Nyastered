"""Find vertex-morph / keyframe tables in the Dreamcast executable: runs of {ptr, index} pairs with constant pointer stride (the cat head table at 0x7ceb8 is the model)."""
import struct, sys, json
d = open(sys.argv[1], 'rb').read(); base = 0x8C010000; n = len(d); out = []
i = 0
while i < n - 16:
    k, p = struct.unpack_from('<II', d, i)
    if base <= p < base + n and k == 0:
        j = i; seq = []
        while j < n - 8:
            k2, p2 = struct.unpack_from('<II', d, j)
            if base <= p2 < base + n and k2 == len(seq): seq.append(p2); j += 8
            else: break
        if len(seq) >= 4:
            st = {seq[x + 1] - seq[x] for x in range(len(seq) - 1)}
            out.append({'offset': i, 'frames': len(seq), 'strides': sorted(st)[:3], 'first': hex(seq[0])})
            i = j; continue
    i += 4
print(len(out), 'tables')
for t in out[:40]: print(hex(t['offset']), t['frames'], [hex(s) for s in t['strides']], t['first'])
json.dump(out, open(sys.argv[2], 'w'), indent=1)
