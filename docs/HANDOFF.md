# Handoff — Dreamcast-only fidelity

## Current state

- `main` at `8e78e61` (`Enable PuzzleP DLC stage set`), pushed to `origin/main`.
- Keep user-owned untracked `.vscode/` untouched. Do not stage caches, disc data, captures, or generated files.
- Goal and working rules: `docs/goal.md`. Audit owns coverage (`docs/audit.md`); evidence/log in `docs/roadmap.md`; setup results in `docs/verification.md`.
- Clean image-only setup rechecked 2026-11-27 from a new folder containing only the selected USA Dreamcast ZIP (no BIOS, mobile, DLC, or GBA files). `tools/setup-wizard.ps1` completed extraction and pinned Zig build. Manifest: one error-free ZIP/CUE input, Dreamcast graphics, Puzzle/Battle/Stage Challenge, no DLC stage pack. Direct headless captures for DC_TITLE, MENU, HELP, OPTIONS, STAGES, CHALLENGE_SELECT, PUZZLE, CHALLENGE, BATTLE, TEAM_BATTLE, DC_DEMO were all nonblack (90 ticks; smoke/reachability only). Scratch: `local/fresh-dc-only-20261127/`. Current tests: 30/30 game tests, 14 extractor tests, VMS retail pack check passed. No parity claim.

## Recent code

- PuzzleP DLC (commit `8e78e61`): exports 25 boards using first n directions as stock, with zero placeholder cells and `PuzzleP NN` titles. Separate stage set from DEPuzzle and imported packs. Regressions compare each source slot's count and direction bits. Evidence is slot-format-derived; original live stock/gameplay behavior remains open.
- Puzzle Edit Load includes imported `<data>/imports/*.VMS`; Delete stays local-only. Solution editing, capacity feedback, VMS round-trip and mono SFX mixing have regressions. See `docs/audit.md` / `docs/dlc.md`.
- Build command: `ninja -C build/game-zig ccr input_regression_test vms_test`; full suite: `C:/Windows/py.exe -3 tools/run_tests.py`.

## Next code priorities

1. Continue Puzzle/Challenge/Battle functional gaps from `docs/audit.md`; prefer a small source-backed gameplay fix with a regression over another documentation-only pass.
2. The Basics intro skip: iOS/HD decompile `PuzzleStageControll @ 0x3c108` ends after 120 ticks or `Input::getFlag(4)` once age >4; it consumes flag 4 and sets tutorial tap flag 0x20. HD Puzzle touch handler `0x13050` creates flags from hit rectangles. This is not Dreamcast controller evidence; do not map it to a pad button without original Dreamcast input trace.
3. For PuzzleP, seek original Dreamcast runtime evidence for stock before claiming parity; current regression proves only retail VMS fields map through our format decoder.
4. Battle phrase graphics/selection and Team Battle result scene remain open; use source/runtime evidence before changing behavior. Do not attribute callbacks or texture matches to draw tasks without proof.

## Open evidence / cautions

- Dreamcast Team Battle result: packets absent at tick 1100, present by 1200, remain through 1890 while camera/platform changes. Textures and packet rectangles are mapped, but task creation, scene transition, draw order and timing are not established. Captures/data under `local/battle-result-probe/`; trace from mode transition first.
- Battle phrase task: caller `0x8c027a6c`, predicate `FUN_8c025592`, ctor `FUN_8c056a64`, updater `FUN_8c0565e0`. Held L/R indices change; sampled phrases include “Too easy!”, “Get out of here!”, “Congrats”. This does not establish `GAMEVOICE_vw01..22` mapping, full selection/lifetime, or rendering. Latest captures under `local/phrase-probe/`; Flycast state `local/dc_ref/tb1/t_03600.state`, launch with USA CUE (not ZIP).
- Puzzle Edit Create dialog (2026-11-27, `local/modecap/ed3/m__03250.bmp`): port headless frame vs Flycast full-frame error 5.5; dialog region 10.5. Text glyphs differ in shape (port uses the BIOS ROM atlas at a 12 px advance; the reference looks like a different face), and the gold box is the dc_editor sheet frame 5 (tinted 0.8, 154x84 bilinear). Its interior fits Flycast to mean 2.9-3.4 with no better integer placement, so the residual is not geometry. `ta_dump tex` decodes of the text quads' textures (080ac4f8, 080a83f8) do not show the dialog text, and neither does the dc_editor atlas, so the text source is still unidentified.
- PuzzleP export format, mono SFX behavior, Battle L/R banners, Puzzle Edit VMS acceptance/cap visuals, and tutorial flag 4 all have explicit evidence gaps in `docs/audit.md`.
- Real-USA-CHD extraction/audio parity, staff-roll residual pixels, native `MANATEE.DRV` mono command behavior, BIOS optionality edge cases, other regions and Android runtime remain open. BIOS must remain user-supplied and optional.
- Never infer Dreamcast parity from port-vs-port tests, assets, static packets, or headless harnesses alone. Scope claims to the named evidence.

## Useful paths and commands

- Dreamcast decompile: `analysis/decomp/dc_1st/1ST_READ.BIN.c`; iOS/HD decompile: `analysis/decomp/ios_hd10/CCR_ios_hd10.c`.
- Puzzle/DLC: `game/core/vms.hpp`, `tools/export_dlc_stages.py`, `tools/stage_registry.py`, `tools/vms_pack_check.py`; real packs `Original Game Files/Dreamcast/DLC/`.
- Clean setup: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools/setup-wizard.ps1 -GameFiles <owned image or folder> -Cache <fresh cache>`; this runs the same wizard and build as `setup.cmd` without interactive pause.
- Headless route: `CCR_HEADLESS=1 CCR_TICKS=90 CCR_SHOT=local/<route>.bmp build/game/ccr.exe <cache>/assets <MODE> 0`.
- SH-4 disassembly helper: `C:/Windows/py.exe -3 tools/shdis.py <start> <end>` (Capstone required). Flycast reference: use `local/dc_ref/disc/Chu Chu Rocket! (USA) (En,Ja,Fr,De,Es).cue`, not its ZIP.
- Use `C:/Windows/py.exe -3 tools/run_tests.py`; test executables have cwd/argument requirements handled there. MSVC build tree lacks `stddef.h`; use `build/game-zig`.
