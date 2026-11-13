"""Yamaha AICA 4-bit ADPCM decoder (Dreamcast sound RAM samples), as used by the SMPB sample banks of DP2SOUND.MLT / CHU2_SE.MLT.
usage: aica_adpcm.py <bank.bin> <out.wav> [rate=22050] [offset=0] [length=all]   (derived data, never committed)"""
import struct, sys, wave
STEP = [230, 230, 230, 230, 307, 409, 512, 614]
def decode(data, nibble_low_first=True):
    out = []; sig = 0; step = 127
    for b in data:
        for k in ((b & 15, b >> 4) if nibble_low_first else (b >> 4, b & 15)):
            mag = k & 7; sign = -1 if k & 8 else 1
            diff = ((2 * mag + 1) * step) >> 3
            sig = max(-32768, min(32767, sig + sign * diff))
            step = max(127, min(24576, (step * STEP[mag]) >> 8))
            out.append(sig)
    return out
def write_wav(path, samples, rate):
    w = wave.open(path, 'wb'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
    w.writeframes(struct.pack('<%dh' % len(samples), *samples)); w.close()
if __name__ == '__main__':
    d = open(sys.argv[1], 'rb').read(); rate = int(sys.argv[3]) if len(sys.argv) > 3 else 22050
    off = int(sys.argv[4], 0) if len(sys.argv) > 4 else 0; ln = int(sys.argv[5], 0) if len(sys.argv) > 5 else len(d) - off
    write_wav(sys.argv[2], decode(d[off:off + ln]), rate); print('wrote', sys.argv[2])
