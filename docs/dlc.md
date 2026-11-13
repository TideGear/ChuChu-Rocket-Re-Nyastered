# Dreamcast DLC files (notes, 2026-11-13)

Files in the user's `Dreamcast\DLC` folder: `Cartoony`, `UFOCow`, `DEChar` (character packs) and `PuzzleP`, `DEPuzzle` (puzzle packs), each as a `.VMI` (108 bytes, Dreamcast file-info: checksum, description, copyright "Dreamcast..." and file name) plus a `.VMS` (VMU save image).

## .VMS layout (all five)
- 0x00: 16-byte ASCII description `CHU_CHU__C00` (characters) / `CHU_CHU__D01` (puzzles); 0x10: 32-byte Shift-JIS long description (Japanese titles; `UFOCow` has the English `CHUCHU!/CHARA`); 0x30: 16-byte application id; icon frame count / animation speed follow, the 32-byte 16-colour icon palette is at 0x60 and the 32x32 4-bit icon (512 bytes) starts at 0x80.
- Character packs: 17,408 bytes (34 blocks of 512): 0x280 .. end = 16,896 bytes of payload. Not yet decoded: read as plain ARGB4444 at widths 32..128 it does not form an image (it looks tiled/twiddled or a custom sprite table; runs such as `ccfc ccfc ...` and `88f8 88f8 ...` suggest 16-bit pixels). Next step: follow the Dreamcast loader in `1ST_READ.BIN` (VMU file read path) with the SH-4 disassembler to learn the payload layout.
- Puzzle packs: 38,400 bytes = 512-byte header + 25 puzzle slots (24 full 1,536-byte slots plus a shortened 25th) as in [stages.md](stages.md); `DEPuzzle` and `PuzzleP` are readable and their boards are in the stage registry.

## Still to do
VMU loading in the game (read `.VMS` with its `.VMI`), skin payload decoder, the pack found in Oct 2024, English puzzle names.
