"""Export Dreamcast UI textures (the highest-resolution title logo) into the app's sheet format. usage: export_dc_ui.py <dreamcast prs_png dir> <ret_all output dir> [<dreamcast png dir>]   (the optional third directory supplies the English 'PRESS START BUTTON!' prompt, ENGLISH/PRESSSTART)   (derived data, never committed)"""
import os, struct, sys
from PIL import Image

def export_player_sheet(prs_png, out, sources, name, transpose=False):
    paths = [os.path.join(prs_png, source) for source in sources]
    if not all(os.path.isfile(path) for path in paths):
        return
    tiles = [Image.open(path).convert('RGBA') for path in paths]
    if transpose:
        tiles = [tile.transpose(Image.Transpose.TRANSPOSE) for tile in tiles]
    width, height = tiles[0].size
    if not all(tile.size == (width, height) for tile in tiles):
        return
    atlas = Image.new('RGBA', (4 * width, height))
    for i, tile in enumerate(tiles):
        atlas.paste(tile, (i * width, 0))
    with open(os.path.join(out, name + '.tex.bin'), 'wb') as f:
        f.write(struct.pack('<2I', *atlas.size))
        f.write(atlas.tobytes())
    with open(os.path.join(out, name + '.frames.bin'), 'wb') as f:
        f.write(struct.pack('<I', 4))
        for i in range(4):
            f.write(struct.pack('<9f', i / 4, 0, (i + 1) / 4, 1, 0, 0, 0, 0, 0))

def main(prs_png, out, png=None):
    os.makedirs(out, exist_ok=True)
    for src, name, src_dir in (
        ('TITLE_newtitle0.png', 'dlogo', prs_png),
        ('ENGLISH__PRESSSTART.png', 'dpress', png),
        ('PUZZLEMENU_pzleft01.png', 'dc_puzzle_start', prs_png),
        ('PUZZLEMENU_pzleft02.png', 'dc_puzzle_cancel', prs_png),
    ):
        if not src_dir: continue
        p = os.path.join(src_dir, src)
        if name == 'dlogo' and not os.path.exists(p):
            p = os.path.join(src_dir, '.__' + src)
        if not os.path.exists(p): continue
        im = Image.open(p).convert('RGBA')
        if name in ('dc_puzzle_start', 'dc_puzzle_cancel'):
            im = im.transpose(Image.Transpose.ROTATE_270).transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        im = im.crop(im.getbbox()); w, h = im.size
        with open(os.path.join(out, name + '.tex.bin'), 'wb') as f: f.write(struct.pack('<2I', w, h)); f.write(im.tobytes())
        with open(os.path.join(out, name + '.frames.bin'), 'wb') as f: f.write(struct.pack('<I', 1)); f.write(struct.pack('<9f', 0, 0, 1, 1, 0, 0, 0, 0, 0))
        print(name, src, '%dx%d' % (w, h))
    export_player_sheet(prs_png, out, [f'YAJIRUSI_yp{i:02}.png' for i in range(1, 5)], 'dc_arrows')
    export_player_sheet(prs_png, out, [f'BATTLEMODELS_newk{i}.png' for i in range(1, 5)], 'dc_cursors')
    # The cursor trail quad at 0x8c013f7e maps U down and V across the board.
    export_player_sheet(prs_png, out, [f'BATTLEMODELS_newk{i}s.png' for i in range(1, 5)],
                        'dc_cursor_trail', transpose=True)

if __name__ == '__main__': main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
