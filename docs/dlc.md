# Dreamcast DLC files (notes, 2026-11-13)

Files in the user's `Dreamcast\DLC` folder: `Cartoony`, `UFOCow`, `DEChar` (character packs) and `PuzzleP`, `DEPuzzle` (puzzle packs), each as a `.VMI` (108 bytes, Dreamcast file-info: checksum, description, copyright "Dreamcast..." and file name) plus a `.VMS` (VMU save image).

## .VMS layout (all five)
- 0x00: 16-byte ASCII description `CHU_CHU__C00` (characters) / `CHU_CHU__D01` (puzzles); 0x10: 32-byte Shift-JIS long description (Japanese titles; `UFOCow` has the English `CHUCHU!/CHARA`); 0x30: 16-byte application id; icon frame count / animation speed follow, the 32-byte 16-colour icon palette is at 0x60 and the 32x32 4-bit icon (512 bytes) starts at 0x80.
- Character packs: 17,408 bytes. The icon is 32x32 (0x80..0x27F); from 0x280 the payload is **8 ordinary Dreamcast texture files (GBIX + PVRT, ARGB4444 twiddled, 32x32, 2,080 bytes each = 16,640 bytes)**. They are the four facing directions of the mouse-side character and of the cat-side character: `Cartoony` = cartoon mouse and cat, `UFOCow` = cow (mouse) and UFO (cat), `DEChar` (Dreamcast Express) = the train-style pair. `tools/vms_skin.py <pack.VMS> <out dir>` extracts and decodes them (verified visually on all three packs). The global texture indices (`0x6f22..0x6f68` for Cartoony/DEChar, `0x73d2..0x73d9` for UFOCow) are the ids of the game's own character textures that the pack replaces.
- Puzzle packs: 38,400 bytes = 512-byte header + 25 puzzle slots (24 full 1,536-byte slots plus a shortened 25th) as in [stages.md](stages.md); `DEPuzzle` and `PuzzleP` are readable and their boards are in the stage registry.

## Still to do
VMU loading in the game (read `.VMS` with its `.VMI`), applying a skin in play (map GBIX ids to the game sprites), the pack found in Oct 2024, English puzzle names.

## How the skin format was found
Plain and twiddled interpretations of the whole payload gave noise because the payload is a sequence of texture *files*; the bytes at 0x280 read `GBIX` and 0x290 `PVRT` with header fields pixel format 2 (ARGB4444), data format 1 (twiddled), 32x32. The VMU file code in `1ST_READ.BIN` handles the name prefixes `CHU_CHU__RCT/E/D/C00/D00/NET` (strings at 0x8C0B4CF5..0x8C0B4D31; users: 0x8C020A40..0x8C0219B4) through a generic read helper at 0x8C0F1968.
