# Handoff — Dreamcast-only fidelity

## Current state

Branch `main`; check `git log` for latest. Untracked `.vscode/` is user-owned; do not commit it. The USA Dreamcast image is in `Original Game Files/Dreamcast/` (zip of the 19-track CUE/BIN set), with the mobile and GBA releases beside it.

Look and sound choice (2026-11-24): settings `presentation` and `sound_source` (`auto`/`dreamcast`/`mobile`) pick the screens/HUDs and the music/effects. `models_3d` now only affects the mobile look. Rows are in mobile Options > Settings (2x5 grid) and Dreamcast Options > Re-Nyastered Settings (a port-only row). RecompLauncher passes `--presentation=`/`--sound=`. Details are in roadmap.md.

End-to-end setup on 2026-11-24 (`tools/setup-wizard.ps1` with throwaway caches under `local/e2e-20261124/cfg-*`): Dreamcast image only, mobile releases only, and all files together. See verification.md.

## Latest gameplay/UI work

- Records controls follow the traced original: L+R+Start deletes (the footer triangle is Start), the delete resets a Chao costume, and A/B/Start leave with cue 3.
- Puzzle pause: global controller and per-mode handler are traced; +5/+3 tap/hold timing remains observation-only. Dreamcast (`0x8c02be0a` → `0x8c01a298`) and mobile (`FUN_0002fb54` → `PA_SetPauseDisable`) disable pause on results; transitions now clear active/pending overlays, covered by a mobile failure regression.
- Monaural: traced to sound-driver command 0x8a. The port's final-mix fold differs for panned voices.
- Character selector, Options pages, Music/SE Test, Battle arrow reset: implemented with regressions; per-element Flycast parity is open.
- Puzzle launch: the full-frame sweep (ages -9..80) passes; only the age -1 dome crops pass per element.
- Dreamcast Stage Select uses localized title records and ANSI/Shift-JIS BIOS glyphs; missing or unmapped Japanese BIOS glyphs fall back to the ASCII stage title. Headless fallback capture checked; Japanese glyph parity remains open.

## Done 2026-11-24

Moved to docs/archive/roadmap_2026-11-12_to_11-25.md ("2026-11-24 session notes").

## Done 2026-11-25

- Puzzle parity fix (2026-11-26): combined assets loaded GBA's alternate Normal 13 before Dreamcast. Main Puzzle now prefers Dreamcast stages, mobile fallback, then GBA; DC/mobile-only renders 1.71 vs GBA variant 3.77. Hard 05 failure cat phase remains fixed (1.064/1.086); 30/30 tests pass.

## Next tasks (milestone: Dreamcast Puzzle end to end; not met, see audit.md for every row's evidence)

State at the end of the 2026-11-25 session (evidence in docs/audit.md; tests 30/30 via `py tools/run_tests.py`):

- **Puzzle Edit (mode 8), ported in `DcEditMode`** (Mode Select row 5): Functions screen, eight tool strips (R / L), grid cursor (d-pad, 42.4 px pitch, no pulse), blinking tool-row box (period ~40 frames, phase not derived), editing for Walls, Mice, Cats, Solution, Rockets, Holes with their sounds (1, 6, 27, 1, 11, 11; tool step 0; Create dialog 4 / 2 / 3), repeat-to-remove, Play + F.F. + launch ending + Save OK badge, Create dialog (white box exact, text placement scanned), pause overlay incl. QUIT frame.
- **Puzzle Edit file flows (functional, parity open):** Load / Delete now list `.VMS` user saves from `<data>/puzzle_edit`; Delete confirms; Load restores tiles, walls and solution arrows. Save runs a 3,600-tick simulation solvability check, then writes a Dreamcast-format 25-slot pack (`.VMS`) plus `.VMI`. Headless `CCR_EDIT_SCRIPT="3,0,0,B;6,1,0,A;0,0,0,Y"` wrote a 39,424-byte VMS and 108-byte VMI in throwaway portable data (one mouse adjacent to a rocket). Original card-slot semantics/title entry and valid-board edge cases remain open; UI is explicitly marked port storage, not a parity claim. Next: trace the disc's VMU slot manager and verify acceptance with Flycast; separately unblock the file screen stream locator (see audit.md), and diff the invalid-save/card screens. Text placement uses per-glyph blits; the original uses a 512 x 256 offscreen buffer (`0x8c022500`).
- **Staff roll (mode 17):** strips, end card, cues, exit and the four unlock texts are verified against Flycast (0.01-0.07 / 0.028). Open: the drifting actors (two scripted 3D tasks `0x8c051200` / `0x8c051580`, row script `0x8c0cde18`, Puzzle camera; start values and actor B unread), the Chao line, and the password lines (pending value 2; the -1 case is closed: it shows no text, see audit.md).
- **Parity (142 cases, rerun 2026-11-26):** 140/142 under full-frame mean 3; only `options_general` 5.04 and `options_4p_battle` 4.25 exceed it (no-BIOS substitute font). Normal 13 now 1.71 (was 3.77 from GBA variant). Failure ring aligns; cat pose and launch shading remain partial; see audit.md.
- **Modes:** 4, 18, 19, 21 are unreachable (unreferenced setters), 16 and 22 online-only, 20 a two-frame transition; 25 functions with sound or task calls remain unattributed (docs/inventory_dc_modes.md, `py tools/oracle/mode_inventory.py --ram [--mode N]`).

Capture recipes (flyhost; libretro `B` = DC A, `A` = DC B, `Y` = DC X, `X` = DC Y): Puzzle Edit = Mode Select DOWN x4 then START (`START@1350-1360;START@1510-1520;DOWN@1800-1804;DOWN@1840-1844;DOWN@1880-1884;DOWN@1920-1924;START@1950-1960`). Editor sound attribution: `FLY_WATCH=1869ec:1024:2250`. The e2e caches have no BIOS (`tools/export_dc_bios_font.py`).

Headless editor hooks (CCR_*): `CCR_EDIT_SCRIPT="tool,x,y,A|B|X|Y;..."`, `CCR_EDIT_CELL=x,y`, `CCR_EDIT_TOOL`, `CCR_EDIT_DIALOG`, `CCR_EDIT_PAUSE=1|2`, `CCR_EDIT_FF=<tick>`, `CCR_EDIT_END`, `CCR_EDIT_CATPHASE`, `CCR_CLEAR_GROUPS=<bitmask>`; launch DC_EDIT directly with `build/game/ccr.exe <assets> DC_EDIT`.

## Blocked (needs an input first)

- **Languages:** French Help plate/footer need a non-USA dump.
- **The Basics:** needs mobile-original frames to diff (port is port-vs-port only).
- **Banner pixel diff (3-2-1, time-left):** needs a clean background; the board moves behind every Flycast banner frame (geometry already fits).
- **Battle captures:** flyhost Battle runs differ between invocations; dump (`FLY_DUMP`) in the same run as the shot you need.

Capture recipes (flyhost): Puzzle `START@1350-1360;START@1510-1520;DOWN@1800-1804;DOWN@1840-1844;DOWN@1880-1884;START@1950-1960;START@2120-2130`; Challenge drops one DOWN and adds `START@2300-2310`; Battle `START@1350/1510/1800/2400/2550`. Mode Select entries (DOWN count from the top, then START): 3 Puzzle (15), 4 Puzzle Edit (8), 5 network (9), 6 network setup (10; the mode read was invalid), 7 Options (11), 8 wraps to Help (6); Mode Select row table `0x8c07f2b4` has a hidden row 9 = mode 16. Keys: X places the north arrow, R2 = R trigger. RAM pokes: style 0x1ae8d0, Puzzle masks 0x22d8a4.., golden 0x1ae8f8. Language: resume `local/star-trace/opt/o03050.state`.

Tests: `py tools/run_tests.py` runs every `build/game/*_test.exe` from game/ with the arguments they need and reports real exit codes (30 of 30 pass on 2026-11-25; `cpu_gba_test` crashed on a missing trailing field in the older `gba_nbr.txt` format, now guarded). Running the exes bare from the repo root fails on paths and usage, which is not a test failure.

Look separation: `py tools/look_leak.py <exe> <one-platform cache> local/e2e-20261124/cfg-both/assets <out> --look dreamcast|mobile` must report 0 differing cases after UI changes.

## Key evidence and paths

- Decompilation: `analysis/decomp/dc_1st/1ST_READ.BIN.c`; SH-4 disassembly with literal pools: `py tools/shdis.py <start> <end>` (needs capstone; the system `py` has it). REA does not support SH-4.
- Pad records are Shinobi `PDS_PERIPHERAL` (52 bytes at `0x8c1aee88`): +8 held, +0x10 pressed; bits C 1, B 2, A 4, Start 8, Up 0x10, Down 0x20, Left 0x40, Right 0x80, Z 0x100, Y 0x200, X 0x400, R 0x10000, L 0x20000.
- Fresh caches: `local/e2e-20261124/cfg-{dc,mobile,both}/assets`; older `local/goal-dc-fresh-setup/assets`; full dev cache `local/cache/assets`.
- Launch saved states: `local/session-resume/puzzle-clear/s00070.state`, `s00085.state`, `s00100.state`. Aligned captures: `local/star-trace/lau`.
- Status docs: `docs/goal.md`, `docs/audit.md` (coverage), `docs/roadmap.md` (current evidence; older log in `docs/archive/`), `docs/verification.md`, `docs/audio.md`. Do not claim parity from harness coverage alone.
- Build: `build.cmd --target <targets>` (pinned Zig/CMake/Ninja into `build/game`). Python with Pillow: `local/tools/windows/python-3.12.10-pillow-12.2.0/python.exe`; tools needing numpy (`pair_assets.py`) run with the system `py`.

## Constraints

Read the decompile before any behavioural change and record addresses; distinguish harness coverage from verification. Do not use the user's screen or audio. Keep caches and disc assets out of commits; build and capture outputs go under `local/` (`build`, `dist`, `analysis` are junctions to D:). Commits use the repo's git identity (TideGear) with no AI attribution, and fixes get a one-line "why" in the message body.
