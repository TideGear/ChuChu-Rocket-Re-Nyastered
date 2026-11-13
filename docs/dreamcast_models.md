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
