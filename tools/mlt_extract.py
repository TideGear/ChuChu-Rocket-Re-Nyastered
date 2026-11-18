"""Extract file-backed sections from Dreamcast SMLT containers.

Each 32-byte entry holds tag, bank, sound-RAM address, allocation size,
file offset and file size. Offset 0xffffffff reserves RAM without file data.
Usage: mlt_extract.py <bank.MLT> <output directory>
"""
import os
import struct
import sys


def sections(data):
    if len(data) < 32 or data[:4] != b'SMLT':
        raise ValueError('Not an SMLT container')
    count = struct.unpack_from('<I', data, 8)[0]
    if count > (len(data) - 32) // 32:
        raise ValueError('Truncated SMLT section table')
    rows = []
    table_end = 32 + count * 32
    for index in range(count):
        entry = 32 + index * 32
        tag = data[entry:entry + 4].decode('ascii')
        bank, address, allocated, offset, size = struct.unpack_from('<5I', data, entry + 4)
        if offset != 0xffffffff:
            if offset < table_end or size > len(data) - offset:
                raise ValueError(f'Section {index} {tag} extends outside the file')
            if size < 4 or data[offset:offset + 4] != data[entry:entry + 4]:
                raise ValueError(f'Section {index} {tag} payload signature mismatch')
        rows.append(dict(index=index, tag=tag, bank=bank, address=address,
                         allocated=allocated, offset=offset, size=size))
    return rows


def main(path, out):
    data = open(path, 'rb').read()
    rows = sections(data)
    os.makedirs(out, exist_ok=True)
    for row in rows:
        print(row)
        if row['offset'] == 0xffffffff:
            continue
        name = f"{row['index']:02d}_{row['tag']}.bin"
        with open(os.path.join(out, name), 'wb') as stream:
            start = row['offset']
            stream.write(data[start:start + row['size']])
    return rows, data


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
