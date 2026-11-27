# Handoff — Dreamcast-only fidelity

## Current state

Branch `main`; check `git log` for latest. Untracked `.vscode/` is user-owned; do not commit it. The USA Dreamcast image is in `Original Game Files/Dreamcast/` (zip of the 19-track CUE/BIN set), with the mobile and GBA releases beside it.

CHD setup: corrected bare LZMA1 decoding in `tools/chd_reader.py` (raw stream, `lc=3,lp=0,pb=2`); the previous `.lzma` wrapper failed on the synthetic cdlz regression under Windows Python. Updated the asset-marker regression for current version 11. Extraction suite 25/25 and game suite 30/30 pass. Real-USA-CHD file/audio parity remains unverified. Fix pushed in `7fe8a40`.

Look and sound choice (2026-11-24): settings `presentation` and `sound_source` (`auto`/`dreamcast`/`mobile`) pick the screens/HUDs and the music/effects. `models_3d` now only affects the mobile look. Rows are in mobile Options > Settings (2x5 grid) and Dreamcast Options > Re-Nyastered Settings (a port-only row). RecompLauncher passes `--presentation=`/`--sound=`. Details are in roadmap.md.

End-to-end setup on 2026-11-24 (`tools/setup-wizard.ps1` with throwaway caches under `local/e2e-20261124/cfg-*`): Dreamcast image only, mobile releases only, and all files together. See verification.md.

## Latest gameplay/UI work (2026-11-27)

- Team Battle round winners now launch the team-colored result rocket using HD 1.0 `ResultRocketCons` layout offsets (`0x3e4`, `0x3e8`, `0x30c` icon table); regression checks team-1 lane/frame and the shared rise/pulse/settle sequence. Windows build and full game suite pass (30/30). This is source-derived/harness-tested; Dreamcast Flycast result capture and pixel/timing parity remain open. Details in `docs/ui_art.md` and `docs/roadmap.md`.
- Records controls follow the traced original: L+R+Start deletes (the footer triangle is Start), the delete resets a Chao costume, and A/B/Start leave with cue 3.
- Results: Puzzle DC navigation is A/Start next, B back, Y ignored; mobile Y retained. Challenge clear sets pending 1 at all-25, else -1 (`0x8c02aa7a–0x8c02aa8a`); final A/B/Start enters Chao roll (`0x8c02ad02–0x8c02ad22`). Regression covers route/text. Puzzle/Challenge Flycast inputs remain unverified.
- Monaural: traced to sound-driver command 0x8a. The port's final-mix fold differs for panned voices.
- Character selector, Options pages, Music/SE Test, Battle arrow reset: implemented with regressions; per-element Flycast parity is open.
- Puzzle launch: ages -9..80 full-frame sweep passes; only age -1 dome crops pass per element.
- Stage Select: Japanese glyph parity remains open.
- Taunts: `0x8c027d68` routes L/R press codes `0x20000`/`0x10000` to IDs 125/126 via `FUN_8c01203a`. L/R timed captures show “You’re weak!”/“I’m sorry!”, pairing them with 125/126. Held-trigger cycling remains unverified; pad records are neutral.
- Challenge 24: seed 1000 failure and 132 seed-3000 arrows match; other seeds remain unresolved.

## Done 2026-11-24

Moved to docs/archive/roadmap_2026-11-12_to_11-25.md ("2026-11-24 session notes").

## Done 2026-11-25

- Puzzle parity fix (2026-11-26): combined assets loaded GBA's alternate Normal 13 before Dreamcast. Main Puzzle now prefers Dreamcast stages, mobile fallback, then GBA; DC/mobile-only renders 1.71 vs GBA variant 3.77. Hard 05 failure cat phase remains fixed (1.064/1.086); 30/30 tests pass.

## Next tasks (milestone: Dreamcast Puzzle end to end; not met, see audit.md for every row's evidence)

State (tests 30/30; evidence in docs/audit.md):

- **Puzzle Edit (mode 8), ported in `DcEditMode`** (Mode Select row 5): Functions screen, eight tool strips (R / L), grid cursor (d-pad, 42.4 px pitch, no pulse), blinking tool-row box (period ~40 frames, phase not derived), editing for Walls, Mice, Cats, Solution, Rockets, Holes with their sounds (1, 6, 27, 1, 11, 11; tool step 0; Create dialog 4 / 2 / 3), repeat-to-remove, Play + F.F. + launch ending + Save OK badge, Create dialog (white box exact, text placement scanned), pause overlay incl. QUIT frame.
- **Puzzle Edit (partial):** Local Load/Delete/Save uses `.VMS`/`.VMI`; Save appends solvable puzzles to one 25-slot, 38,400-byte pack. Rewrites preserve the header; VMS/VMI replacement failure is tested. New-pack header is unverified. Damaged packs, multi-pack deletion, object caps and no-mouse Play gate are regression-tested. Empty Load/Delete uses original background, Enter badge and distinct prompts (frame 2390 compared). Without BIOS, fallback text differs. Empty/non-ASCII titles show `PUZZLE n`. Port title UI: SDL text/pad grid (20 ASCII chars, Y toggles case, Start saves); row navigation and named-slot regressions pass. Original keyboard/card semantics and game acceptance remain open; local storage is not VMU parity. See audit.md.
- **Staff roll (mode 17):** strips, end card, cues, exit and the four unlock texts are verified against Flycast (0.01-0.07 / 0.028). Start was missing from the port's exit buttons despite the original `0x60e` mask; now fixed and regression-tested. Unlock text now falls back to the built-in bitmap font when the optional BIOS font is absent (Dreamcast-only/no-BIOS setup); regression checks framebuffer output. BIOS rendering remains preferred. Mouse A (`0x8c051200`) now runs its full original script: all 4037 update ages match Flycast RAM, four standard-mouse crops pass (0.199–0.455). Cat B and all 84 flock mice are now ported: all 3168 cat ages and 42084 flock observations match original RAM. Six cat crops and the flock crop pass. Open: one off-edge pixel in cat age 2715, two individual flock crop means >1, costume/unsampled rendered poses, Chao line, and password lines (pending value 2; -1 shows no text; see audit.md).
- **Parity (142 cases, rerun 2026-11-26):** 140/142 under full-frame mean 3; only `options_general` 5.04 and `options_4p_battle` 4.25 exceed it (no-BIOS substitute font). Normal 13 now 1.71 (was 3.77 from GBA variant). Failure ring aligns. Traced the Puzzle cat light; Hard 05 failure crop mean is 0.509, board off-edge residue remains; cat pose/normal comparison and launch shading remain partial; see audit.md.
- **Modes:** 4, 18, 19, 21 are unreachable (unreferenced setters), 16 and 22 online-only, 20 a two-frame transition; 25 functions with sound or task calls remain unattributed (docs/inventory_dc_modes.md, `py tools/oracle/mode_inventory.py --ram [--mode N]`).

Capture recipes (flyhost; libretro `B` = DC A, `A` = DC B, `Y` = DC X, `X` = DC Y): Puzzle Edit = Mode Select DOWN x4 then START (`START@1350-1360;START@1510-1520;DOWN@1800-1804;DOWN@1840-1844;DOWN@1880-1884;DOWN@1920-1924;START@1950-1960`). Editor sound attribution: `FLY_WATCH=1869ec:1024:2250`. The e2e caches have no BIOS (`tools/export_dc_bios_font.py`).

Headless editor hooks (CCR_*): `CCR_EDIT_SCRIPT="tool,x,y,A|B|X|Y;..."`, `CCR_EDIT_CELL=x,y`, `CCR_EDIT_TOOL`, `CCR_EDIT_DIALOG`, `CCR_EDIT_PAUSE=1|2`, `CCR_EDIT_FF=<tick>`, `CCR_EDIT_END`, `CCR_EDIT_CATPHASE`, `CCR_CLEAR_GROUPS=<bitmask>`; launch DC_EDIT directly with `build/game/ccr.exe <assets> DC_EDIT`.

## Blocked (needs an input first)

- **Languages:** French Help plate/footer need a non-USA dump.
- **The Basics:** needs mobile-original frames to diff (port is port-vs-port only).
- **Banner pixel diff (3-2-1, time-left):** needs a clean background; the board moves behind every Flycast banner frame (geometry already fits).
- **Battle captures:** runs vary; dump (`FLY_DUMP`) with the shot. Taunt RAM pad records are neutral.

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

## Current staff-roll continuation (2026-11-26)

Mouse A, cat B and all 84 flock mice are ported in `game/core/dc_staffroll.hpp`, reading scripts from the extracted original executable. All 4037 A updates, 3168 B updates and 42084 live flock observations match original-loop RAM. Tools: `staff_mouse_compare.py` (local/staff-mouse-20261126/i_watch.bin vs port.txt), `staff_cat_compare.py` (local/staff-cat-20261126/r_watch.bin vs port.txt); `CCR_STAFF_TRACE=1` prints state. Cat uses Ninja screen distance 500 from RAM 0x8c2c8294, native XYZ camera (112,218,85.5), signed Y/Z rotations quantized by 182.04444885, transposed texture UV and second-list depth writes (ISP 0xc8800000). `staff_cat_projection.py` verifies head vertices to <=0.00001242 world units at seven frames.

Six of seven cat crops pass (0.0716–0.3743); age 2715 still has one >8 off-edge pixel (mean 0.2154). Combined flock crop passes (0.6078); 82/84 individual mouse crops pass. Two born-at-1992 mice (slots 0/2) remain partial (1.0351/1.0512, no off-edge >8 pixels, residual above rounding allowance). Four earlier A crops pass. Unsampled/costume poses remain open. New parity refs: local/staff-cat-20261126/r__*.bmp; recipes/results in roadmap.md. Cat/flock sound functions have no additional cue requests in the traced paths; CD track 16/song 12 remains ported, Flycast WAV/loop/fade parity open. Password/Chao lines remain open. Rocket creator 0x8c051060 has no direct references in the tested code scan; reachability unproven.

Fresh Dreamcast-only cache: `local/staff-mouse-20261126/dc-config/assets` (USA CUE, no mobile/BIOS input, asset version 11, 15 CD WAVs, 128 SFX WAVs). No new extraction format for cat/flock. Build and 30/30 tests pass; input regression passes on that and the mobile-only cache. Dreamcast look comparison versus local/cache/assets is 0/23 differing cases; `look_leak.py` now isolates save data using `CCR_TEST_SAVE_DIR`, avoiding false differences from clear marks/records. Quiet-guarded 120 Hz attempts were excluded for background GPU activity; a clean higher-rate check remains open. Next: age-2715 pixel, two flock crop means, costume/unsampled poses and remaining end-text branches; compare the shared gameplay cat UV/depth-write path with original field packets before applying staff-only findings there.

## Current audio continuation (2026-11-26)

Restored Puzzle Edit BGM (init 0x8c02dcc6 -> CD 15/song 11). Also fixed shared native CD stereo: original CDDA return 16/17 controls are 0x0f0f/0x0f1f at AICA 0x2040/0x2044, routing raw disc L to right and R to left. App::loadSong exchanges actual Dreamcast WAV channels only; mobile and SFX paths are unchanged.

Evidence: local/editor-music-20261126/boot.wav from a fresh boot (standard editor entry recipe). Seconds 45..49 are host frames 2090..2284 and equal swapped track 15 at sample frame 329280 exactly. Saved-state original.wav continued title track 4, so it is not editor evidence. Port-song11-swapped.raw vs boot.wav: 4 seconds at explicit port gain 75/255, max error 0.9412. Tool: tools/oracle/dc_music_compare.py; full commands/controls in audio.md. All 30 tests pass; DC-only/mobile-only input regression passes; Functions/Play/Load keep song 11. Native default volume calibration (original capture is unity), fades/loops and original audio across all Play/file transitions remain open. Capture from fresh boot when checking CD selection; use WAV frames.csv for time alignment.

flyhost now suppresses debug-level core logs by default (FLYHOST_DEBUG=1 opts in), preventing huge polling logs. This does not change sound/frame capture. No new extraction format or asset version.
