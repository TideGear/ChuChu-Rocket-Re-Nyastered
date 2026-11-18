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

def export_battle_hud(prs_png, out):
    sources = ['GAMEMENU_' + name for name in
               ('disp01', 'disp02', 'disp03', 'time_num', 'rocket01', 'rocket02')]
    sources += [f'PLAYERCLEAR_winno{i}' for i in range(10)] + ['PLAYERCLEAR_namecpu']
    sources += [f'PLAYERCLEAR_ranking{i:02}' for i in range(1, 5)]
    sources += [f'PLAYERCLEAR_player{i}' for i in range(1, 5)]
    paths = [os.path.join(prs_png, name + '.png') for name in sources]
    if not all(os.path.isfile(path) for path in paths):
        return
    images = [Image.open(path).convert('RGBA') for path in paths]
    scores, timer_panel, column, clock, rocket_on, rocket_off, *digits = [
        image.transpose(Image.Transpose.TRANSPOSE) for image in images[:16]]
    # The Battle NJS_TEXANIM table at 0x8c0b9a80 supplies the UV rectangles.
    tiles = [scores.crop((x, y, x + 128, y + 80))
             for y in (0, 80) for x in (0, 128)]
    tiles += [timer_panel.crop((0, 128, 256, 256)),
              column.crop((0, 0, 128, 256)), column.crop((128, 0, 256, 256)),
              rocket_on, rocket_off]
    tiles += [clock.crop((x, y, x + 16, y + 32))
              for y, count in ((0, 8), (32, 3)) for x in range(0, 16 * count, 16)]
    tiles += digits + [images[16]]
    tiles += [image.transpose(Image.Transpose.TRANSPOSE) for image in images[17:21]]
    tiles += images[21:]
    width = max(tile.width for tile in tiles)
    positions = []
    x = y = row_height = 0
    for tile in tiles:
        if x + tile.width > width:
            x = 0
            y += row_height
            row_height = 0
        positions.append((x, y))
        x += tile.width
        row_height = max(row_height, tile.height)
    height = y + row_height
    atlas = Image.new('RGBA', (width, height))
    with open(os.path.join(out, 'dc_battle_hud.frames.bin'), 'wb') as f:
        f.write(struct.pack('<I', len(tiles)))
        for tile, (x, y) in zip(tiles, positions):
            atlas.paste(tile, (x, y))
            f.write(struct.pack('<9f', x / width, y / height, (x + tile.width) / width,
                                (y + tile.height) / height, 0, 0, 0, 0, 0))
    with open(os.path.join(out, 'dc_battle_hud.tex.bin'), 'wb') as f:
        f.write(struct.pack('<2I', width, height))
        f.write(atlas.tobytes())

def main(prs_png, out, png=None):
    os.makedirs(out, exist_ok=True)
    for src, name, src_dir in (
        ('TITLE_newtitle0.png', 'dlogo', prs_png),
        ('ENGLISH__PRESSSTART.png', 'dpress', png),
        ('PUZZLEMENU_pzleft01.png', 'dc_puzzle_start', prs_png),
        ('PUZZLEMENU_pzleft02.png', 'dc_puzzle_cancel', prs_png),
        ('PUZZLEMENU_pzright.png', 'dc_puzzle_panel', prs_png),
    ):
        if not src_dir: continue
        p = os.path.join(src_dir, src)
        if name == 'dlogo' and not os.path.exists(p):
            p = os.path.join(src_dir, '.__' + src)
        if not os.path.exists(p): continue
        im = Image.open(p).convert('RGBA')
        if name in ('dc_puzzle_start', 'dc_puzzle_cancel', 'dc_puzzle_panel'):
            im = im.transpose(Image.Transpose.ROTATE_270).transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        # The bottom panel is two 256 x 96 quads of one texture (rows 0-95 and 96-191), so it keeps its full size.
        if name != 'dc_puzzle_panel': im = im.crop(im.getbbox())
        w, h = im.size
        with open(os.path.join(out, name + '.tex.bin'), 'wb') as f: f.write(struct.pack('<2I', w, h)); f.write(im.tobytes())
        with open(os.path.join(out, name + '.frames.bin'), 'wb') as f: f.write(struct.pack('<I', 1)); f.write(struct.pack('<9f', 0, 0, 1, 1, 0, 0, 0, 0, 0))
        print(name, src, '%dx%d' % (w, h))
    export_player_sheet(prs_png, out, [f'YAJIRUSI_yp{i:02}.png' for i in range(1, 5)], 'dc_arrows')
    export_player_sheet(prs_png, out, [f'BATTLEMODELS_newk{i}.png' for i in range(1, 5)], 'dc_cursors')
    # The cursor trail quad at 0x8c013f7e maps U down and V across the board.
    export_player_sheet(prs_png, out, [f'BATTLEMODELS_newk{i}s.png' for i in range(1, 5)],
                        'dc_cursor_trail', transpose=True)
    export_battle_hud(prs_png, out)

if __name__ == '__main__': main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
