"""Export the localized UI strings of an extracted Android build (resource .bin files per language folder) to one JSON table {resource id: {lang: text}}.
Text resources are null-terminated UTF-8 (en/fr/de/es/it); the Japanese resources are 16-bit little-endian glyph codes into the Japanese font sheet and are stored as {"glyphs": [codes]}.
usage: export_strings.py <libccrjni dir (contains en/ fr/ de/ es/ it/ ja/)> <out.json>   (derived data, never committed)"""
import glob, json, os, sys

NUL = bytes([0])

def decode(d):
    if not d or len(d) > 4096:
        return None
    body = d[:-1] if d.endswith(NUL) else d
    if NUL in body:                                                    # 16-bit glyph codes
        if len(d) % 2 or not d.endswith(NUL + NUL):
            return None
        return {'glyphs': [int.from_bytes(d[i:i + 2], 'little') for i in range(0, len(d) - 2, 2)]}
    try:
        t = body.decode('utf-8')
    except UnicodeDecodeError:
        try:
            t = body.decode('cp1252')                                  # fr/es/de/it accented text is Latin-1 style single bytes
        except UnicodeDecodeError:
            return None
    if any(ord(c) < 32 and c not in '\n\t' for c in t):
        return None
    return t if any(c.isalpha() for c in t) else None

def main(root, out):
    table = {}
    langs = sorted(l for l in os.listdir(root) if os.path.isdir(os.path.join(root, l)) and l != 'main')
    for lang in langs:
        for f in sorted(glob.glob(os.path.join(root, lang, '*.bin'))):
            rid = os.path.splitext(os.path.basename(f))[0]
            t = decode(open(f, 'rb').read())
            if t:
                table.setdefault(rid, {})[lang] = t
    json.dump(table, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    both = sum(1 for v in table.values() if len(v) == len(langs))
    print('languages', langs, '| text resources', len(table), '| present in all languages', both, '->', out)

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
