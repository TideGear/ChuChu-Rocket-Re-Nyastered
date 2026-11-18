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
    # Team Battle's two bottom panels (Flycast Team Battle frame): the blue and red one is the lower 96 rows of the score sheet, the orange and green one the upper 97 rows of the timer sheet.
    tiles += [scores.crop((0, 160, 256, 256)), timer_panel.crop((0, 0, 256, 97))]
    export_atlas(out, 'dc_battle_hud', tiles)

def export_atlas(out, name, tiles):
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
    with open(os.path.join(out, name + '.frames.bin'), 'wb') as f:
        f.write(struct.pack('<I', len(tiles)))
        for tile, (x, y) in zip(tiles, positions):
            atlas.paste(tile, (x, y))
            f.write(struct.pack('<9f', x / width, y / height, (x + tile.width) / width,
                                (y + tile.height) / height, 0, 0, 0, 0, 0))
    with open(os.path.join(out, name + '.tex.bin'), 'wb') as f:
        f.write(struct.pack('<2I', width, height))
        f.write(atlas.tobytes())

def export_mode_select(prs_png, png, out):
    if not png:
        return
    back = os.path.join(png, 'ENGLISH__MENU.png')
    parts = [f'MENU_modeback{i}' for i in range(1, 5)]
    parts += ['MENU_bluerocket2', 'MENU_yellowrocket2', 'MENU_modefukidasi', 'MENU_netsousa00',
              'MENU_middleneko0', 'MENU_middleneko1']
    parts += [f'MENU_selectmoji{i}' for i in range(9)]
    parts += [f'MENU_fukidasimoji{i}' for i in range(9)]
    parts += [f'ROCKET_EF_awa{i:02}' for i in range(1, 13)]
    paths = [os.path.join(prs_png, part + '.png') for part in parts]
    if not all(os.path.isfile(path) for path in (back, *paths)):
        return

    tiles = [Image.open(path).convert('RGBA') for path in paths]
    # Compose the five abutting background quads before scaling the menu.
    background = Image.new('RGBA', (640, 512))
    background.paste(Image.open(back).convert('RGBA').transpose(Image.Transpose.TRANSPOSE), (0, 0))
    for i, tile in enumerate(tiles[:4]):
        background.paste(tile.transpose(Image.Transpose.TRANSPOSE), (512, i * 128))
    export_atlas(out, 'dc_mode_select', [background, *tiles[4:]])

def export_challenge_select(prs_png, png, out):
    if not png:
        return
    names = ('stageselecttitle9', 'stargepanel0', 'puzzlefukidasi', 'challengenumber',
             'bluedaen', 'orangedaen', 'check')
    names += tuple(f'challengesetumei{i}' for i in range(6))
    parts = [os.path.join(prs_png, 'CHALLENGE_' + name + '.png') for name in names]
    backs = [os.path.join(prs_png, f'CHALLENGE_selectback{i}.png') for i in range(8)]
    title = os.path.join(png, 'ENGLISH__CHALLENGE.png')
    digits = [os.path.join(prs_png, f'FOURADV_nums{i:02}.png') for i in range(10)]
    if not all(os.path.isfile(path) for path in (title, *parts, *backs, *digits)):
        return

    def read(path):
        return Image.open(path).convert('RGBA')

    background = Image.new('RGBA', (640, 512))
    for part, spot in enumerate(((0, 0), (512, 0), (512, 128), (512, 256), (512, 384),
                                (256, 0), (0, 256), (256, 256))):
        background.paste(read(backs[part]).transpose(Image.Transpose.TRANSPOSE), spot)
    header = Image.new('RGBA', (640, 64))
    tiles = [read(part) for part in parts]
    header.paste(read(title), (0, 0))
    header.paste(tiles[0], (512, 0))
    tiles[3] = tiles[3].transpose(Image.Transpose.TRANSPOSE)
    clock = []
    for digit in digits:
        # White number on an opaque black field. Exclude the black padding.
        ink = read(digit).convert('L').transpose(Image.Transpose.TRANSPOSE)
        clock.append(ink.crop(ink.getbbox()).resize((16, 20), Image.Resampling.BILINEAR).convert('RGBA'))
    export_atlas(out, 'dc_challenge_select', [background, header, *tiles[1:], *clock])

def export_challenge_intro(prs_png, out):
    # CHALLENGEPAUSE contains the localized cards. PUZZLEMENU_A through F
    # contain a separate set, with Japanese text on the USA disc.
    names = [f'c{letter}' for letter in 'abcdef']
    names += [f'odainum{i:02}' for i in range(1, 6)]
    paths = [os.path.join(prs_png, 'CHALLENGEPAUSE_' + name + '.png') for name in names]
    if not all(os.path.isfile(path) for path in paths):
        return
    tiles = [Image.open(path).convert('RGBA') for path in paths]
    export_atlas(out, 'dc_challenge_intro',
                 tiles[:6] + [tile.transpose(Image.Transpose.TRANSPOSE) for tile in tiles[6:]])

def main(prs_png, out, png=None):
    os.makedirs(out, exist_ok=True)
    export_mode_select(prs_png, png, out)
    for src, name, src_dir in (
        ('TITLE_newtitle0.png', 'dlogo', prs_png),
        ('ENGLISH__PRESSSTART.png', 'dpress', png),
        ('PUZZLEMENU_pzleft01.png', 'dc_puzzle_start', prs_png),
        ('PUZZLEMENU_pzleft02.png', 'dc_puzzle_cancel', prs_png),
        ('PUZZLEMENU_pzright.png', 'dc_puzzle_panel', prs_png),
        ('PUZZLEMENU_stage.png', 'dc_puzzle_stage', prs_png),
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
        if name not in ('dc_puzzle_panel', 'dc_puzzle_stage'): im = im.crop(im.getbbox())
        w, h = im.size
        with open(os.path.join(out, name + '.tex.bin'), 'wb') as f: f.write(struct.pack('<2I', w, h)); f.write(im.tobytes())
        with open(os.path.join(out, name + '.frames.bin'), 'wb') as f: f.write(struct.pack('<I', 1)); f.write(struct.pack('<9f', 0, 0, 1, 1, 0, 0, 0, 0, 0))
        print(name, src, '%dx%d' % (w, h))
    # The Puzzle stage number uses the ten 64 x 64 glyph textures PUZZLECLEAR_new0..9 (stored rotated like the other menu sheets), one per digit.
    digits = [os.path.join(prs_png, f'PUZZLECLEAR_new{i}.png') for i in range(10)]
    if all(os.path.exists(d) for d in digits):
        atlas = Image.new('RGBA', (640, 64))
        for i, d in enumerate(digits):
            g = Image.open(d).convert('RGBA').transpose(Image.Transpose.ROTATE_270).transpose(Image.Transpose.FLIP_LEFT_RIGHT)
            atlas.paste(g, (i * 64, 0))
        with open(os.path.join(out, 'dc_puzzle_digits.tex.bin'), 'wb') as f: f.write(struct.pack('<2I', 640, 64)); f.write(atlas.tobytes())
        with open(os.path.join(out, 'dc_puzzle_digits.frames.bin'), 'wb') as f: f.write(struct.pack('<I', 1)); f.write(struct.pack('<9f', 0, 0, 1, 1, 0, 0, 0, 0, 0))
        print('dc_puzzle_digits 640x64')
    # The Puzzle level plate (the bubble sheet without its tail) and the five 256 x 32 difficulty labels (normal, hard, mania, original, special), stacked.
    def sheet(name, im):
        with open(os.path.join(out, name + '.tex.bin'), 'wb') as f: f.write(struct.pack('<2I', im.width, im.height)); f.write(im.tobytes())
        with open(os.path.join(out, name + '.frames.bin'), 'wb') as f: f.write(struct.pack('<I', 1)); f.write(struct.pack('<9f', 0, 0, 1, 1, 0, 0, 0, 0, 0))
        print(name, '%dx%d' % im.size)
    bubble = os.path.join(prs_png, 'PUZZLE_puzzlefukidasi.png')
    if os.path.exists(bubble): sheet('dc_puzzle_plate', Image.open(bubble).convert('RGBA').crop((0, 0, 512, 44)))
    names = [os.path.join(prs_png, f'PUZZLE_{n}.png') for n in ('normal', 'hard', 'mania', 'original', 'special')]
    if all(os.path.exists(n) for n in names):
        labels = Image.new('RGBA', (256, 32 * len(names)))
        for i, n in enumerate(names): labels.paste(Image.open(n).convert('RGBA'), (0, i * 32))
        sheet('dc_puzzle_labels', labels)
    # The Puzzle pause screen (Flycast Puzzle pause frame): the two PAUSED board pieces (the square left one is stored rotated like the other menu sheets), the cat, the two speech bubbles
    # with their tips, and the RESUME and QUIT labels, packed into one 512 x 320 sheet; regions are fixed in main.cpp (dcPauseRegions).
    names = ['pauseboard0', 'pauseboard1', 'yellowneko', 'fukidasi10', 'fukidasi12', 'fukidasi9', 'fukidasi11', 'tudukeru', 'yameru']
    paths = {n: os.path.join(prs_png, f'PUZZLEPAUSE_{n}.png') for n in names}
    if all(os.path.exists(v) for v in paths.values()):
        rot = lambda im: im.transpose(Image.Transpose.ROTATE_270).transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        pl = {n: Image.open(v).convert('RGBA') for n, v in paths.items()}
        atlas = Image.new('RGBA', (512, 512))
        for n, pos in (('pauseboard0', (0, 0)), ('pauseboard1', (256, 0)), ('yellowneko', (384, 0)), ('fukidasi10', (384, 128)), ('fukidasi12', (416, 128)),
                       ('fukidasi9', (0, 256)), ('fukidasi11', (128, 256)), ('tudukeru', (256, 256)), ('yameru', (384, 256))):
            atlas.paste(rot(pl[n]) if n == 'pauseboard0' else pl[n], pos)   # the 128 x 256 right piece is already upright
        # Below the pieces: the "Player 1" plate (PLAYERCLEAR_player1, 256 x 64, drawn when Battle or Challenge is paused) and the six Challenge title lines (256 x 32 each).
        plate = os.path.join(prs_png, 'PLAYERCLEAR_player1.png')
        if os.path.exists(plate): atlas.paste(Image.open(plate).convert('RGBA'), (0, 320))
        for i in range(6):
            t = os.path.join(prs_png, f'PUZZLEPAUSE_challengesetumei{i}.png')
            if os.path.exists(t): atlas.paste(Image.open(t).convert('RGBA'), (256, 320 + 32 * i))
        sheet('dc_pause', atlas)
    # The Battle pause score panels (BATTLEPAUSE_newwinbox1..8): four 128 x 128 panels (stored rotated like the other menu sheets) each followed by a 32 x 128 end piece
    # (upright as exported), in player order blue, orange, red, green, packed in one 640 x 128 sheet (160 px per player).
    boxes = [os.path.join(prs_png, f'BATTLEPAUSE_newwinbox{i}.png') for i in range(1, 9)]
    if all(os.path.exists(b) for b in boxes):
        rot = lambda im: im.transpose(Image.Transpose.ROTATE_270).transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        atlas = Image.new('RGBA', (640, 128))
        for pl in range(4):
            atlas.paste(rot(Image.open(boxes[2 * pl]).convert('RGBA')), (160 * pl, 0))
            atlas.paste(Image.open(boxes[2 * pl + 1]).convert('RGBA'), (160 * pl + 128, 0))
        sheet('dc_pause_boxes', atlas)
    # The Team Battle pause score panels (TEAMPAUSE_teamwinbox1..4, already upright): 256 x 128 and 64 x 128 pieces side by side (blue and red team, then orange and green team).
    tb = [os.path.join(prs_png, f'TEAMPAUSE_teamwinbox{i}.png') for i in range(1, 5)]
    if all(os.path.exists(b) for b in tb):
        atlas = Image.new('RGBA', (640, 128))
        for b, x in zip(tb, (0, 256, 320, 576)): atlas.paste(Image.open(b).convert('RGBA'), (x, 0))
        sheet('dc_pause_team', atlas)
    # The pause win marks (Flycast Battle and Team Battle pause frames): 64 x 64 rockets, white (drawn grey for rounds not yet won) then blue, yellow (the orange player), red, green,
    # blue and red together (team 1) and yellow and green together (team 2), stored rotated like the other menu sheets.
    marks = [os.path.join(prs_png, f'PLAYERCLEAR_s064_lok_{n}.png') for n in ('white', 'blue', 'yellow', 'red', 'green', 'rebl', 'yegr')]
    if all(os.path.exists(m) for m in marks):
        atlas = Image.new('RGBA', (64 * len(marks), 64))
        for i, m in enumerate(marks):
            atlas.paste(Image.open(m).convert('RGBA').transpose(Image.Transpose.ROTATE_270).transpose(Image.Transpose.FLIP_LEFT_RIGHT), (64 * i, 0))
        sheet('dc_pause_marks', atlas)
    export_challenge_select(prs_png, png, out)
    export_challenge_intro(prs_png, out)
    export_player_sheet(prs_png, out, [f'YAJIRUSI_yp{i:02}.png' for i in range(1, 5)], 'dc_arrows')
    export_player_sheet(prs_png, out, [f'BATTLEMODELS_newk{i}.png' for i in range(1, 5)], 'dc_cursors')
    # The cursor trail quad at 0x8c013f7e maps U down and V across the board.
    export_player_sheet(prs_png, out, [f'BATTLEMODELS_newk{i}s.png' for i in range(1, 5)],
                        'dc_cursor_trail', transpose=True)
    export_battle_hud(prs_png, out)

if __name__ == '__main__': main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
