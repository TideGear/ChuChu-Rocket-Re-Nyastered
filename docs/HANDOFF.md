# Handoff — Dreamcast-only fidelity

## Current state

Branch `main`; check `git log` for latest. Untracked `.vscode/` is user-owned; do not commit it. The USA Dreamcast image is in `Original Game Files/Dreamcast/` (zip of the 19-track CUE/BIN set), with the mobile and GBA releases beside it.

Look and sound choice (2026-11-24): settings `presentation` and `sound_source` (`auto`/`dreamcast`/`mobile`) pick the screens/HUDs and the music/effects. `models_3d` now only affects the mobile look. Rows are in mobile Options > Settings (2x5 grid) and Dreamcast Options > Re-Nyastered Settings (a port-only row). RecompLauncher passes `--presentation=`/`--sound=`. Details are in roadmap.md.

End-to-end setup on 2026-11-24 (`tools/setup-wizard.ps1` with throwaway caches under `local/e2e-20261124/cfg-*`): Dreamcast image only, mobile releases only, and all files together. See verification.md.

## Latest gameplay/UI work

- Records controls follow the traced original: L+R+Start deletes (the footer triangle is Start), the delete resets a Chao costume, and A/B/Start leave with cue 3.
- Puzzle pause: the global controller and per-mode handler are traced. The +5/+3 tap/hold timing is still observation-only.
- Monaural: traced to sound-driver command 0x8a. The port's final-mix fold differs for panned voices.
- Character selector, Options pages, Music/SE Test, Battle arrow reset: implemented with regressions; per-element Flycast parity is open.
- Puzzle launch: the full-frame sweep (ages -9..80) passes; only the age -1 dome crops pass per element.

## Done this session (2026-11-24; evidence in roadmap.md "2026-11-24 session notes")

- Mouse pose follows the global clock ((clock - 1) & 7 on unpaused passes; Flycast RAM shows no reset at stage start).
- Puzzle pause overlay: every element passes (exact float placement). Japanese pause case passes too.
- Cursor bracket dims and pulses on cells with 0xF00 set in Battle, Puzzle and Challenge (`0x8c0146e6`); Puzzle phase measured (cticks - 53), Challenge phase not measured. Pointers hold their pulse through the intro.
- Dreamcast Battle START/countdown banners (`0x8c028d90`) and Round panel (`0x8c028fd8`, PLAYERCLEAR winno digits).
- Options text drawn from the original Shift-JIS lines with BIOS full-width glyphs (`dc_bios_wide`); per-language Dreamcast art (`ret_all/dc_loc_<xx>`), per-language Puzzle hint titles (`dreamcast_titles_<xx>.bin`, `dc_bios_sjis`).
- Costumes: njScale 1.3 on the model only, scaled diffuse, per-strip alpha / untextured / environment flags and material diffuse as face colour (models.bin CCM4). Chao passes per element in both mice crops; Pian left passes.
- Hard/Special/Mania: floor stays tan/pink, arrow stock in direction-code order S, W, N, E. Puzzle clear masks RAM 0x8c22d8a4 + 4 * group.
- Golden mouse: crash fix on Dreamcast-only installs, "50" marker no longer mirrored, environment-mapped body.
- Parity: 132 cases, all within the full-frame limit (with a BIOS in the local test caches). Asset version 5 (re-run setup).

## Done 2026-11-25

- Flycast banner captures, Challenge bracket phase, Normal 03 case (see Next tasks 3-6). `flyhost` gained `FLY_POKE_ONCE`. Tutorial gate follows `puzzlestage_endflag`; tap shortcut (Input flag 4 writer) still unfound.
- Tests run: tutorial_test, puzzle_pause_test, userdata_test, input_regression_test pass; port-vs-port only for The Basics.

## Next tasks

1. **Pian right mice crop:** 1.036 against the per-element limit of 1 (no off-edge pixels). Left passes. The ignore-light strip uses the measured 0.912; its origin is not traced.
2. **Golden mouse:** texture, UV range and vertex intensities match Flycast (gk03400.state), but a colour-mask comparison says the body is ~15% brighter. Needs an aligned golden-mouse crop (force with `FLY_POKE=0:1ae8f8=3f800000` in flyhost and `CCR_GOLDEN_P=1` in the port).
3. **Challenge bracket phase:** grey pulse measured (period 64, `dimOffset` 18, 90-frame series); the size pulse is not re-measured.
4. **Time-left / 3-2-1 Battle banners:** Flycast frames captured with `FLY_POKE_ONCE=3000:1ae8e0=<BCD clock>` (flyhost); 2:00, 1:00, 0:30 and the "3" fit `4 - 0.033 t` / `8 - 0.13 t` and the blend follows the texture alpha. Open: count2/count1 digits, absolute pixel diff.
5. **START banner crop:** 2.39, placement exact; residue is partial-alpha edge texels (+9 R/G at 150 px). Battle and Challenge pause have no parity case.
6. **Puzzle coverage:** `puzzle_normal03` added (full 0.99, board 1.07 / 1 off-edge px). The residue is the pad cursor tip (about 4% too large; its pulse counter is not the game clock; a consecutive-frame series is in local/pz3s, tip area fits period 16, phase unresolved). Other groups' later stages, star twinkles, launch per element open.
7. **The Basics** (mobile tutorial, HD 1.0 `PuzzleGameScreen` tutorial): ported in the mobile look (`game/core/tutorial.hpp`, `PuzzleMode` with `basics`, Main Menu item 0, `progress.bin` fifth word gates Puzzle/Challenge/Battle). Played to the cleared flag headless (port-vs-port; roadmap 2026-11-24 "played end to end" has the arrows and script). Open: no mobile-original frame diff, the tap shortcut (Input flag 4), the lesson-index source on a stage change (inferred), the press sparkle (image 0x9f), the 0x109/0x20a branches, the Continue label/scale. Dreamcast mode 16 (`0x8c058292`) is a network battle, not a tutorial.
8. **Languages:** French Help title plate and footer unverified; the Puzzle tap-timing writer and MANATEE.DRV command 0x8a (Monaural) stay open.

Capture recipes (flyhost): Puzzle `START@1350-1360;START@1510-1520;DOWN@1800-1804;DOWN@1840-1844;DOWN@1880-1884;START@1950-1960;START@2120-2130`; Challenge drops one DOWN and adds `START@2300-2310`; Battle `START@1350/1510/1800/2400/2550`. Keys: X places the north arrow, R2 = R trigger. RAM pokes: style 0x1ae8d0, Puzzle masks 0x22d8a4.., golden 0x1ae8f8. Language: resume `local/star-trace/opt/o03050.state`.

Look separation: `py tools/look_leak.py <exe> <one-platform cache> local/e2e-20261124/cfg-both/assets <out> --look dreamcast|mobile` must report 0 differing cases after UI changes.

## Key evidence and paths

- Decompilation: `analysis/decomp/dc_1st/1ST_READ.BIN.c`; SH-4 disassembly with literal pools: `py tools/shdis.py <start> <end>` (needs capstone; the system `py` has it). REA does not support SH-4.
- Pad records are Shinobi `PDS_PERIPHERAL` (52 bytes at `0x8c1aee88`): +8 held, +0x10 pressed; bits C 1, B 2, A 4, Start 8, Up 0x10, Down 0x20, Left 0x40, Right 0x80, Z 0x100, Y 0x200, X 0x400, R 0x10000, L 0x20000.
- Fresh caches: `local/e2e-20261124/cfg-{dc,mobile,both}/assets`; older `local/goal-dc-fresh-setup/assets`; full dev cache `local/cache/assets`.
- Launch saved states: `local/session-resume/puzzle-clear/s00070.state`, `s00085.state`, `s00100.state`. Aligned captures: `local/star-trace/lau`.
- Status docs: `docs/goal.md`, `docs/audit.md` (coverage), `docs/roadmap.md` (evidence), `docs/verification.md`, `docs/audio.md`. Do not claim parity from harness coverage alone.
- Build: `build.cmd --target <targets>` (pinned Zig/CMake/Ninja into `build/game`). Python with Pillow: `local/tools/windows/python-3.12.10-pillow-12.2.0/python.exe`; tools needing numpy (`pair_assets.py`) run with the system `py`.

## Constraints

Read the decompile before any behavioural change and record addresses; distinguish harness coverage from verification. Do not use the user's screen or audio. Keep caches and disc assets out of commits; build and capture outputs go under `local/` (`build`, `dist`, `analysis` are junctions to D:). Commits use the repo's git identity (TideGear) with no AI attribution, and fixes get a one-line "why" in the message body.
