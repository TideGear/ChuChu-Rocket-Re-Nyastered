# Dreamcast polygonal models (FOUND, 2026-11-12)

The retail disc's `DPMODEL/` folder is empty. The game models are Ninja *chunk* models compiled into `1ST_READ.BIN` (load base 0x8C010000, no NJCM headers).
`tools/dc_models.py` finds them by scanning for `NJS_CNK_MODEL` structs (vlist ptr, plist ptr, centre xyz, radius), validates the vertex chunks (types 32-50) and polygon chunks (materials 16-23, tiny textures 8/9, strips 64-75), and writes one OBJ per model plus `index.json`.

Result: 128 models in `1ST_READ.BIN` (`2_DP.BIN` contains none; its `/dptutor/model/*.nj` are loaded from other media). Contact sheet checked visually (`local/models_sheet.png`):
- #4 (0x778ac): 69-vertex character head, with the 24-frame vertex-morph table at 0x7ceb8 (frames = {ptr,index} pairs, stride 828 bytes);
- #12-20: big-eared mouse body, 96 vertices, 8 animation variants;
- #26, #33, #44, #57...: small gems/spheres/pickups; #63-78: round-bodied "chao"-style special characters (2 sets, with and without wings);
- #84-89: rockets with exhaust fins; #80-83: quarter-sphere/tile pieces; #97: sphere; #90-96, #98+: flat quads (planes, shadows, UI polys).

Still to do: the object hierarchy (NJS_CNK_OBJECT: eval flags, pos/ang/scale, child/sibling) to assemble multi-part characters, texture-id to PVR mapping (texids 16384.. = 0x4000 | index, per-model texture lists), morph animation playback, and model-to-gameplay-role labels (cat vs mouse vs rocket).

## Object hierarchies (done, tools/dc_objects.py)
`NJS_CNK_OBJECT` (52 bytes: evalflags, model*, pos, ang (BAMS), scl, child*, sibling*) trees are located by linking to the known models; 4,595 candidate nodes, 80 roots, 60 assembled multi-part objects exported to `assets/dreamcast/objects/obj_<offset>.obj` (contact sheet `local/objects_sheet.png`). Identified: cat (157 vertices, root 0x778c4), big-eared mouse in 8 variants (96 vertices), a second mouse-like body (0x7e138, 0x860ec), two round characters with 74/77 vertices (second set with wings/halo), six rockets (113 vertices), board pieces. Remaining: texture-id to PVR mapping, morph animation playback, exact role labels.

## Textures and rendering (2026-11-12, verified visually)
- Every `ENGLISH/*.PRS` is a PRS-compressed PVM texture archive (`tools/prs.py`; 54 archives, 978 named PVRs): one per UI screen (TITLE, MENU, PUZZLE, BATTLE...), plus CAT (4), MOUSE (10), CHAO (9), BIGCHAO (4), BATTLEMODELS (38), EFFECT (56), ROCKET_EF (12). They decode with `tools/pvr2png.py` (954 of 978; 24 use a format not yet handled). Output file names are `<archive>_<texname>.png`.
- Texture-name lists (`NJS_TEXNAME` arrays: name pointer, attr, 0) are baked into `1ST_READ.BIN` for every screen and model (55 found; cat: c_cat01-04 at 0x75c68, mice: c_mouse01-10, chao, chu_p, vw...). Strip chunks carry the index in the texture id (`id & 0x1fff`).
- `tools/dc_objects.py` now exports UVs and per-triangle materials (`obj_<off>.obj/.mtl`, `texN.png` = index N of the model's list). `tools/dc_render.py` is a small software renderer: the assembled cat (root 0x778c4) with c_cat01-04 renders correctly (orange body, spiral eyes, zigzag teeth).
- Animation: the 8 near-identical mouse/chao objects (96/74/77 vertices) are consecutive keyframe meshes, and the cat head has a 24-frame vertex-morph table (frame pointers at 0x7ceb8). Timing and the state-to-animation mapping still need to be read from the code (SH-4 disassembly); not done.

## Animation data (2026-11-13)
- Frame lists are arrays of object pointers: at file offset 0xa37b0 a 24-entry array (8 mouse walk keyframe objects 0x7efb8..0x85538, then 16 chao/other keyframes 0x8c818..0x98304); other short arrays at 0x75994 (4-frame groups: 0x987b8.., 0xa2640 x4, 0x7e138 x4, 0x778c4 x4) and 0xa3798. The cat head is a vertex-morph table of 24 frames (`tools/dc_anim_scan.py`, table at 0x7ceb4, stride 0x33c).
- Phase driver (Android `FUN_00028ffc`, same code base): the cat's walk phase advances 0.45 per tick and wraps at 20.0; the turn angle uses 16-bit angles with `diffAngle`/`adjustAngle` smoothing. Mapping of the phase to the Dreamcast keyframe index (and per-state animations: rocket-in, hole fall, eaten) still has to be read from the SH-4 code.

## Dreamcast character model selection

- The cat draw dispatcher at `0x8c0119fe` selects texture list `0x8c085c98` and submits model root `0x8c0878c4` for costume modes 0–2. Texture indices 0–3 resolve to `c_cat01` through `c_cat04`. The call to `0x8c0e673e` receives both 24-frame motion descriptors, `0x8c088108` and `0x8c08cfd4`, with the caller's floating-point phase intact. A live renderer needs both tracks.
- Costume mode 3 binds the loaded sprite texture list at `0x8c0b4c24` and submits a quad. Frame `4 + ((int(phase) >> 1) & 3)` uses one of the four cat images. Heading bit 15 selects draw parameter 48 or 52. Tested mode 4 issues no texture or draw command.
- Mouse model preparation at `0x8c01a060` selects one of three eight-object sets for costume modes 0–2 and skips mesh preparation for mode 3. The first set uses `MOUSE` textures in the executable's slot order: 01, 02, 03, **05, 04**, 06, 07, 08, 09, 10. Alphabetical sorting swaps two materials.
- `tools/oracle/dc_character_draw.py` executes the original SH-4 dispatchers, recording texture, morph and quad submissions for 100 cat fixtures and all 24 mouse model preparations. The cat probe supplies the game mode and tutorial predicate. The mouse probe supplies the costume selection. GPU rasterization, animation timing for live callbacks and field occlusion remain open. Next, trace the mouse frame selection and the cat's motion sampling before integrating the models.
