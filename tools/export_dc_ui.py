"""Export Dreamcast UI textures (the highest-resolution title logo) into the app's sheet format. usage: export_dc_ui.py <dreamcast prs_png dir> <ret_all output dir> [<dreamcast png dir>]   (the optional third directory supplies the English 'PRESS START BUTTON!' prompt, ENGLISH/PRESSSTART)   (derived data, never committed)"""
import os, struct, sys
from PIL import Image

def export_player_sheet(prs_png, out, sources, name, transpose=False, gutter=0):
    paths = [os.path.join(prs_png, source) for source in sources]
    if not all(os.path.isfile(path) for path in paths):
        return
    tiles = [Image.open(path).convert('RGBA') for path in paths]
    if transpose:
        tiles = [tile.transpose(Image.Transpose.TRANSPOSE) for tile in tiles]
    width, height = tiles[0].size
    if not all(tile.size == (width, height) for tile in tiles):
        return
    # Power-of-two dimensions also keep frame UVs exactly representable,
    # matching the original separate 32x32 textures at fractional pulse sizes.
    pitch = (1 << (width + 2 * gutter - 1).bit_length()) if gutter else width
    atlas_height = (1 << (height + 2 * gutter - 1).bit_length()) if gutter else height
    atlas = Image.new('RGBA', (4 * pitch, atlas_height))
    for i, tile in enumerate(tiles):
        x = i * pitch + gutter
        atlas.paste(tile, (x, gutter))
        if gutter:
            # Separate textures in the original; emulate their clamped edges.
            # Linear filtering a fractional-size cursor must never read the
            # first column of the next player's cursor from our shared atlas.
            for dx in range(-gutter, width + gutter):
                for dy in range(-gutter, height + gutter):
                    if 0 <= dx < width and 0 <= dy < height: continue
                    atlas.putpixel((x + dx, gutter + dy), tile.getpixel((max(0, min(width - 1, dx)), max(0, min(height - 1, dy)))))
    with open(os.path.join(out, name + '.tex.bin'), 'wb') as f:
        f.write(struct.pack('<2I', *atlas.size))
        f.write(atlas.tobytes())
    with open(os.path.join(out, name + '.frames.bin'), 'wb') as f:
        f.write(struct.pack('<I', 4))
        for i in range(4):
            f.write(struct.pack('<9f', (i * pitch + gutter) / atlas.width, gutter / atlas.height,
                                (i * pitch + gutter + width) / atlas.width, (gutter + height) / atlas.height, 0, 0, 0, 0, 0))

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
    tiles[6] = tiles[6].transpose(Image.Transpose.TRANSPOSE)   # the cleared-stage mark (Flycast quad 151..183 x 112..144 for C1)
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

def export_challenge_failure(prs_png, out):
    names = ['yellowrocket', 'bluerocket', 'challengemiss', 'rocketmoji24',
             'rocketmoji26', 'netsousa00', 'titleline0', 'titleline1']
    names += ['new' + letter for letter in 'abcde'] + ['new' + str(i) for i in range(1, 6)]
    names += ['newfin']
    paths = [os.path.join(prs_png, 'CHALLENGECLEAR_' + name + '.png') for name in names]
    if not all(os.path.isfile(path) for path in paths):
        return
    tiles = [Image.open(path).convert('RGBA') for path in paths]
    for i in (7, *range(8, len(tiles))):
        tiles[i] = tiles[i].transpose(Image.Transpose.TRANSPOSE)
    # These screen quads use packed UV endpoints 255/256 (frame 4250).
    # Bake their bilinear sampling into each tile before packing the atlas.
    tiles = [tile.transform(tile.size, Image.Transform.AFFINE,
                            (255 / 256, 0, 0, 0, 255 / 256, 0),
                            Image.Resampling.BILINEAR) for tile in tiles]
    export_atlas(out, 'dc_challenge_failure', tiles)

def export_challenge_result(prs_png, out):
    names = ['challengeclear', 'fukidasi7', 'challengepanel0', 'challengepanel1',
             'challengepanel2', 'puzzlesetumei0']
    paths = [os.path.join(prs_png, 'CHALLENGECLEAR_' + name + '.png') for name in names]
    if not all(os.path.isfile(path) for path in paths):
        return
    tiles = [Image.open(path).convert('RGBA') for path in paths]
    tiles = [tile.transform(tile.size, Image.Transform.AFFINE,
                            (255 / 256, 0, 0, 0, 255 / 256, 0),
                            Image.Resampling.BILINEAR) for tile in tiles]
    export_atlas(out, 'dc_challenge_result', tiles)

def export_puzzle_result(prs_png, out):
    # Live Normal 01 clear: s00320.state, packets 0x19bd53b..0x19bd99b.
    names = ['puzzleclear', 'titleline0', 'titleline1', 'puzzlesetumei0']
    names += ['new' + str(i) for i in range(10)]
    names += ['normal', 'hard', 'special', 'mania', 'original', 'challengeboard']
    paths = [os.path.join(prs_png, 'PUZZLECLEAR_' + n + '.png') for n in names]
    if not all(os.path.isfile(p) for p in paths): return
    tiles = [Image.open(p).convert('RGBA') for p in paths]
    for i in (2, *range(4, 14)):
        tiles[i] = tiles[i].transpose(Image.Transpose.TRANSPOSE)
    for i in (0, 1, 2, *range(4, 14)):
        tile = tiles[i]
        tiles[i] = tile.transform(tile.size, Image.Transform.AFFINE,
                                 (255 / 256, 0, 0, 0, 255 / 256, 0), Image.Resampling.BILINEAR)
    export_atlas(out, 'dc_puzzle_result', tiles)
    # s00320.state packet 0x19be17b uses full 0..1 UVs, unlike the
    # banner's 0..255/256 range. Preserve the full texture coordinate range.
    saved = Image.open(os.path.join(prs_png, 'PUZZLECLEAR_saving.png')).convert('RGBA')
    # Flycast ta_vtx.cpp: intensity 1 * face white -> 255*255/256 =
    # 254 in the vertex RGB, then fragment texture modulation rounds.
    r, g, b, alpha = saved.split()
    saved = Image.merge('RGBA', tuple(c.point(lambda v: round(v * 254 / 255)) for c in (r, g, b)) + (alpha,))
    export_atlas(out, 'dc_puzzle_saved', [saved])

def export_puzzle_select(prs_png, out):
    # Normal 01, real result -> selector route, a00249.state packets
    # 0x19bd59b..0x19bee9b. Same tiled backing arrangement as Challenge.
    read = lambda name: Image.open(os.path.join(prs_png, 'PUZZLE_' + name + '.png')).convert('RGBA')
    names = ['stageselecttitle6', 'stageselecttitle7', 'selectsetumei2', 'puzzleselect',
             'puzzlefukidasi', 'puzzlenumber', 'bluedaen', 'orangedaen', 'check',
             'normal', 'hard', 'special', 'mania']
    if not all(os.path.isfile(os.path.join(prs_png, 'PUZZLE_' + n + '.png')) for n in names + [f'selectback{i}' for i in range(8)]): return
    background = Image.new('RGBA', (640, 512))
    for i, at in enumerate(((0, 0), (512, 0), (512, 128), (512, 256), (512, 384), (256, 0), (0, 256), (256, 256))):
        background.paste(read(f'selectback{i}').transpose(Image.Transpose.TRANSPOSE), at)
    tiles = [read(n) for n in names]
    for i in (5, 8): tiles[i] = tiles[i].transpose(Image.Transpose.TRANSPOSE)
    for i in (6, 7, 8):
        tile = tiles[i]
        tiles[i] = tile.transform(tile.size, Image.Transform.AFFINE,
                                 (255 / 256, 0, 0, 0, 255 / 256, 0), Image.Resampling.BILINEAR)
    export_atlas(out, 'dc_puzzle_select', [background, *tiles])

def export_dc_startup(prs_png, png, out):
    """Dreamcast SEGA logo, Sonic Team bubble and Title screen art, laid out from Flycast frames 600/800/1200 (docs/HANDOFF.md).
    Frames: 0 SEGA canvas 768 x 512 (SEGALOGO tiles, stored transposed, 3 x 2 grid, drawn at (-64, 0)); 1 Sonic Team bubble 256 x 256 (LOGO, transposed, at (193, 160));
    2 Title background 640 x 480 (TITLE_titlegamen0..7 at (0,0) (512,0) (0,256) (512,256) (0,384) (512,384) (0,448) (512,448); tile 3 is transposed);
    3 Title logo 512 x 256 (at (16, 64)); 4 Title PRESS START (176,360);
    5 flying rocket; 6 logo edge shadow; 7 disc PRESSSTART for the demo (176,220)."""
    seg = [os.path.join(prs_png, f'SEGALOGO_segalogo{i}.png') for i in range(6)]
    logo = os.path.join(png, 'ENGLISH__LOGO.png') if png else ''
    title = [os.path.join(prs_png, f'TITLE_titlegamen{i}.png') for i in range(8)]
    extra = [os.path.join(prs_png, 'TITLE_newtitle0.png'), os.path.join(prs_png, 'TITLE_pressstart.png'), os.path.join(prs_png, 'TITLE_titlerocket.png')]
    if not (png and all(os.path.isfile(f) for f in seg + title + extra + [logo])):
        return
    def read(path): return Image.open(path).convert('RGBA')
    sega = Image.new('RGBA', (768, 512), (255, 255, 255, 255))
    for i, f in enumerate(seg):
        sega.alpha_composite(read(f).transpose(Image.Transpose.TRANSPOSE), ((i % 3) * 256, (i // 3) * 256))
    bg = Image.new('RGBA', (640, 480))
    for i, (f, at) in enumerate(zip(title, ((0, 0), (512, 0), (0, 256), (512, 256), (0, 384), (512, 384), (0, 448), (512, 448)))):
        tile = read(f)
        bg.alpha_composite(tile.transpose(Image.Transpose.TRANSPOSE) if i == 3 else tile, at)
    rocket = os.path.join(prs_png, 'TITLE_titlerocket.png')
    export_atlas(out, 'dc_startup', [sega, read(logo).transpose(Image.Transpose.TRANSPOSE), bg, read(extra[0]), read(extra[1]), read(rocket), read(os.path.join(prs_png, 'TITLE_newtitle1.png')), read(os.path.join(png, 'ENGLISH__PRESSSTART.png'))])   # frame 5: the flying rocket, 128 x 256 upright; frame 6: the logo's 8 x 32 right-edge shadow strip at (528,152)

def export_dc_battle_setup(prs_png, out):
    """Dreamcast 4P Battle 'Select Players' and 'Stage Select' art (Flycast frames 1900/2300, packets matched to disc textures with 0 differing values).
    Frames: 0 players background 640 x 512 (BATTLE_playerselect0..7, stored transposed); 1 stage background 640 x 480 (BATTLE_stargeselect0..7, tile 3 transposed);
    2-3 header 4P Battle (stageselecttitle2/3), 4-5 header Team Battle (stageselecttitle4/5), 6 'Select Players' strip, 7 Human, 8 Computer, 9 plate, 10 white button, 11 orange button,
    12-17 Weak, Hates cats, Loves mice, Tough, Random, None, 18 orange capsule, 19 blue capsule, 20 stage numbers 256 x 256 (transposed), 21 point-match panel, 22 info strip, 23-27 point digits 1-5 (transposed), 28 type list, 29 list frame."""
    def path(n): return os.path.join(prs_png, n + '.png')
    names = [f'BATTLE_playerselect{i}' for i in range(8)] + [f'BATTLE_stargeselect{i}' for i in range(8)] + [
        'BATTLE_stageselecttitle2', 'BATTLE_stageselecttitle3', 'BATTLE_stageselecttitle4', 'BATTLE_stageselecttitle5', 'BATTLE_titletuketasi',
        'BATTLE_ningen', 'BATTLE_cpu', 'BATTLE_panel1', 'BATTLE_panel2', 'BATTLE_panel3', 'BATTLE_yowai', 'BATTLE_kirai', 'BATTLE_suki', 'BATTLE_tuyoi',
        'BATTLE_randamu', 'BATTLE_nasi', 'BATTLE_orangedaen', 'BATTLE_bluedaen', 'BATTLE_playernumber', 'BATTLEPOINT_battleselect', 'BATTLEPOINT_selectsetumei3'] + [
        f'BATTLEPOINT_battle{i}' for i in range(1, 6)] + ['BATTLE_panel0', 'BATTLE_waku']
    if not all(os.path.isfile(path(n)) for n in names): return
    def read(n): return Image.open(path(n)).convert('RGBA')
    T = Image.Transpose.TRANSPOSE
    players = Image.new('RGBA', (640, 512))
    for i, at in enumerate(((0, 0), (256, 0), (0, 256), (256, 256), (512, 0), (512, 128), (512, 256), (512, 384))):
        players.alpha_composite(read(f'BATTLE_playerselect{i}').transpose(T), at)
    stage = Image.new('RGBA', (640, 480))
    for i, at in enumerate(((0, 0), (512, 0), (0, 256), (512, 256), (0, 384), (512, 384), (0, 448), (512, 448))):
        t = read(f'BATTLE_stargeselect{i}')
        stage.alpha_composite(t.transpose(T) if i == 3 else t, at)
    tiles = [players, stage] + [read(n) for n in names[16:]]
    tiles[20] = tiles[20].transpose(T)
    for k in range(23, 28): tiles[k] = tiles[k].transpose(T)
    export_atlas(out, 'dc_battle_setup', tiles)

def export_dc_fallback_fonts(out):
    """No-BIOS look-alikes for the text the Dreamcast draws with its BIOS ROM font (tools/export_dc_bios_font.py overwrites these files when the user supplies a BIOS):
    dc_bios_ansi (95 glyphs, characters 0x20..0x7e, 24 x 48 cells = the BIOS 12 x 24 cell at twice the size) and dc_select_clock (digits 0-9 and the colon in 48 x 48 cells = 24 x 24 at 2x).
    Text: Roboto Mono (SIL OFL); clock digits: M PLUS Rounded 1c Regular (OFL); both bundled unmodified in tools/fonts/. Chosen by scoring 20 free fonts against the BIOS glyph bitmaps and by eye;
    Roboto Mono has the single-storey g and open t of the BIOS font, and M PLUS Rounded's digits are the closest in curve and weight to its plain oval zero and base-less 1. Glyphs are anti-aliased at 2x so the port's 1.6x layout is a smooth down-scale."""
    from PIL import ImageDraw, ImageFont
    here = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts')
    def load(name, size, weight):
        path = os.path.join(here, name)
        if not os.path.isfile(path): return None
        font = ImageFont.truetype(path, size)
        try: font.set_variation_by_axes([weight if a['name'] in (b'Weight', 'Weight') else a['default'] for a in font.get_variation_axes()])
        except (OSError, AttributeError, KeyError): pass
        return font
    text_font, digit_font = load('RobotoMono.ttf', 47, 400), load('MPLUSRounded1c-Regular.ttf', 200, 400)
    if not text_font or not digit_font: return
    def sheet_files(name, cells, w, h):
        atlas = Image.new('RGBA', (w * len(cells), h))
        for k, cell in enumerate(cells): atlas.paste(cell, (w * k, 0))
        with open(os.path.join(out, name + '.tex.bin'), 'wb') as f:
            f.write(struct.pack('<2I', atlas.width, atlas.height)); f.write(atlas.tobytes())
        with open(os.path.join(out, name + '.frames.bin'), 'wb') as f:
            f.write(struct.pack('<I', len(cells)))
            for k in range(len(cells)): f.write(struct.pack('<9f', w * k / atlas.width, 0, w * (k + 1) / atlas.width, 1, 0, 0, 0, 0, 0))
        print(name, '%dx%d' % atlas.size, '(fallback)')
    def white(mask):
        cell = Image.new('RGBA', mask.size, (255, 255, 255, 0)); cell.putalpha(mask); return cell
    glyphs = []
    for c in range(0x20, 0x7f):
        wide = Image.new('L', (40, 48), 0)
        ImageDraw.Draw(wide).text((0, 40), chr(c), font=text_font, fill=255, anchor='ls')   # baseline at row 40 of 48 (20 of 24, like the BIOS cell: descenders are cut at the cell bottom, as in the original)
        mask = wide.crop((0, 0, 28, 48)).resize((24, 48), Image.Resampling.BOX)            # squeeze the 0.6 em mono advance to the BIOS cell's narrow, tall proportions
        glyphs.append(white(mask.point(lambda v: min(255, int(v * 1.3)))))
    sheet_files('dc_bios_ansi', glyphs, 24, 48)
    cells = []
    for d in '0123456789':
        mask = Image.new('L', (300, 340), 0)
        ImageDraw.Draw(mask).text((20, 260), d, font=digit_font, fill=255, anchor='ls'); box = mask.getbbox()
        width = 32 if d != '1' else round((box[2] - box[0]) * 40 / (box[3] - box[1]))   # 16 x 20 digits at 1x like the BIOS ovals (the 1 keeps its natural width)
        ink = mask.crop(box).resize((width, 40), Image.Resampling.BOX).point(lambda v: min(255, int(v * 1.5)))   # a little bolder, like the BIOS strokes
        cell = Image.new('L', (48, 48), 0); cell.paste(ink, ((48 - width) // 2, 2)); cells.append(white(cell))   # rows 1-20 at 1x, like the BIOS digits
    colon = Image.new('L', (48, 48), 0); dr = ImageDraw.Draw(colon)
    for top in (10, 30): dr.rectangle((22, top, 25, top + 7), fill=255)
    cells.append(white(colon))
    sheet_files('dc_select_clock', cells, 48, 48)

def export_dc_help(prs_png, out):
    """Dreamcast Help Menu art (Flycast frame 2000): 0 title bar 512 x 32 at (16,48), 1 'Select a mode.' 512 x 64 at (104,88), 2 entry list 256 x 256 (stored transposed) at (280,160),
    3 controls strip 128 x 128 (transposed) at (16,320). Frame word z order: all .333; the red arrow cursor is drawn by the game (a 30 x 22 triangle), not a texture."""
    names = ['HELP1_helptop01', 'HELP1_helptop02', 'HELP1_helptop03', 'HELP1_helptop04']
    paths = [os.path.join(prs_png, n + '.png') for n in names]
    if not all(os.path.isfile(x) for x in paths): return
    T = Image.Transpose.TRANSPOSE
    tiles = [Image.open(x).convert('RGBA') for x in paths]
    tiles[2] = tiles[2].transpose(T); tiles[3] = tiles[3].transpose(T)
    export_atlas(out, 'dc_help', tiles)

def export_dc_options(prs_png, out):
    """Dreamcast Options menu art (Flycast mode 11): 0 background 640 x 512 (OPTION_optionback0 at (0,0) and optionback1..4 at (512, 128k), all stored transposed),
    1 Menu button 256 x 64 at (16,88), 2 controls strip OPTION_newsousa2 512 x 64 at (16,407) (pixel-identical to the Flycast crop)."""
    names = ['OPTION_optionback%d' % i for i in range(5)] + ['OPTION_menu', 'OPTION_newsousa2']
    paths = [os.path.join(prs_png, n + '.png') for n in names]
    if not all(os.path.isfile(x) for x in paths): return
    T = Image.Transpose.TRANSPOSE
    bg = Image.new('RGBA', (640, 512))
    bg.alpha_composite(Image.open(paths[0]).convert('RGBA').transpose(T), (0, 0))
    for k in range(4): bg.alpha_composite(Image.open(paths[k + 1]).convert('RGBA').transpose(T), (512, 128 * k))
    export_atlas(out, 'dc_options', [bg, Image.open(paths[5]).convert('RGBA'), Image.open(paths[6]).convert('RGBA')])

def export_dc_help_pages(prs_png, out):
    """Dreamcast Help pages from tools/data/dc_help_layout.json (made by tools/oracle/dc_export_layout.py from Flycast frames): every distinct disc piece goes in one atlas
    (dc_help_pages, stored upright) and dc_help_pages.bin lists, per page, quads (frame, x, y, w, h) in draw order: u32 pages, then per page u32 entry (Help Menu entry 0-8, the digit before '_' in the page key), u32 quads and 5 x f32 per quad."""
    import json
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'dc_help_layout.json')
    if not os.path.isfile(path): return
    pages = json.load(open(path, encoding='utf-8'))
    pieces = {}
    for quads in pages.values():
        for q in quads: pieces.setdefault((q['png'], q['transposed']), len(pieces))
    tiles = []
    for (name, tr), _ in sorted(pieces.items(), key=lambda kv: kv[1]):
        f = os.path.join(prs_png, name + '.png') if os.path.isfile(os.path.join(prs_png, name + '.png')) else os.path.join(os.path.dirname(prs_png), 'png', name + '.png')
        if not os.path.isfile(f): return
        im = Image.open(f).convert('RGBA')
        tiles.append(im.transpose(Image.Transpose.TRANSPOSE) if tr else im)
    export_atlas(out, 'dc_help_pages', tiles)
    with open(os.path.join(out, 'dc_help_pages.bin'), 'wb') as f:
        f.write(struct.pack('<I', len(pages)))
        for name in sorted(pages, key=lambda k: (int(k.split('_')[0]), int(k.split('_')[1]))):
            f.write(struct.pack('<2I', int(name.split('_')[0]), len(pages[name])))
            for q in pages[name]: f.write(struct.pack('<5f', pieces[(q['png'], q['transposed'])], q['x'], q['y'], q['w'], q['h']))

def main(prs_png, out, png=None):
    os.makedirs(out, exist_ok=True)
    export_puzzle_result(prs_png, out)
    export_puzzle_select(prs_png, out)
    export_mode_select(prs_png, png, out)
    for src, name, src_dir in (
        ('TITLE_newtitle0.png', 'dlogo', prs_png),
        ('ENGLISH__PRESSSTART.png', 'dpress', png),
        ('PUZZLEMENU_pzleft01.png', 'dc_puzzle_start', prs_png),
        ('PUZZLEMENU_pzleft02.png', 'dc_puzzle_cancel', prs_png),
        ('PUZZLEMENU_pzright.png', 'dc_puzzle_panel', prs_png),
        ('PUZZLEMENU_stage.png', 'dc_puzzle_stage', prs_png),
        ('BATTLEMODELS_s01.png', 'dc_cursor_bracket', prs_png),
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
        # The R/L Trigger panels are full 128 x 128 quads at (5, 32) and (5, 160) of 640 x 480 (Flycast frame 2390), so they keep their whole texture too.
        if name not in ('dc_puzzle_panel', 'dc_puzzle_stage', 'dc_puzzle_start', 'dc_puzzle_cancel'): im = im.crop(im.getbbox())
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
    board = os.path.join(prs_png, 'PUZZLECLEAR_challengeboard.png')
    if os.path.exists(board):
        # The Puzzle plate/bubble texture (word 04046c00 in Flycast frame 2390) is this 278 x 42 bar with no tail. It starts at row 0 of the 512 x 64 texture: the Normal plate and the bubble, two quads of this texture, both start 2 rows too low with the bar at row 2 and align with it at row 0 (frame error 3.97 -> 3.04).
        plate = Image.new('RGBA', (512, 44))
        plate.paste(Image.open(board).convert('RGBA').crop((0, 0, 512, 42)), (0, 0))
        sheet('dc_puzzle_plate', plate)
    elif os.path.exists(bubble): sheet('dc_puzzle_plate', Image.open(bubble).convert('RGBA').crop((0, 0, 512, 44)))
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
    export_dc_startup(prs_png, png, out)
    export_dc_battle_setup(prs_png, out)
    export_dc_help(prs_png, out)
    export_dc_options(prs_png, out)
    export_dc_help_pages(prs_png, out)
    export_dc_fallback_fonts(out)
    export_challenge_intro(prs_png, out)
    export_challenge_failure(prs_png, out)
    export_challenge_result(prs_png, out)
    export_player_sheet(prs_png, out, [f'YAJIRUSI_yp{i:02}.png' for i in range(1, 5)], 'dc_arrows')
    export_player_sheet(prs_png, out, [f'BATTLEMODELS_newk{i}.png' for i in range(1, 5)], 'dc_cursors', gutter=1)
    # The cursor trail quad at 0x8c013f7e maps U down and V across the board.
    export_player_sheet(prs_png, out, [f'BATTLEMODELS_newk{i}s.png' for i in range(1, 5)],
                        'dc_cursor_trail', transpose=True, gutter=1)
    export_battle_hud(prs_png, out)

if __name__ == '__main__': main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
