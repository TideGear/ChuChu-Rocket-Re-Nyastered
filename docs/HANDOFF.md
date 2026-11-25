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

## Done 2026-11-24 (evidence in archive/roadmap_2026-11-12_to_11-25.md, "2026-11-24 session notes")

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

- Puzzle cat walks in place during arrow placement (was frozen); start tick 32 measured from a scan, not traced. Hard 05 board 1.24 -> 0.87.
- Dimmed cursor bracket has no size pulse (`0x8c01480c`); Challenge pad pointer pulse phase `cticks + 2`; pad aim confirmed against RAM `0x8c186cfc` (DcCursor already exact).
- Count2/count1 banner scales fit `8 - 0.13 t`. New parity cases: `puzzle_normal08` (board passes), `puzzle_hard05`, `challenge_play_a1_dim_bracket` (partial). Headless hook `CCR_PAD_AIM=x,y` (Challenge).
- goal.md: current milestone (Dreamcast Puzzle end to end), "pass (rounding)" rule, honest-reporting and visible-gaps-first working style.

## Next tasks (milestone: Dreamcast Puzzle end to end)

1. **Stream tool: done** (`tools/oracle/ta_dump.py info|list|tex|render`). Open in it: how characters are ordered (all their vertices have z = 0.005; Flycast draws the rocket dome over the mouse, the tool's depth test does not).
2. **Puzzle visible-gap sweep:** one Flycast shot per Puzzle state (select, placing, run, pause, clear, fail, launch, result/save) against the port; list gross differences (missing animation, pose, effect) before any residue work. Star twinkles are known missing.
3. **Re-measure under "pass (rounding)":** Pian right mice (1.036; signed +1.6 R / +0.2 G / +1.5 B, 0 off-edge px) and other elements near 1; update audit.md.
4. **Hard 05 cat shading:** body strips at 0x269cd0 / 0x269f30 in `local/hd5/p_02390.state` (intensity 0.30-0.85); a single light vector does not fit, so trace the cat normal transform (draw `0x8c0119fe`, morph `0x8c0e673e`).
5. **Puzzle pad tip:** about 4% too large on Normal 03, pulse counter not the game clock (series in local/pz3s).

Other open (outside the milestone): Challenge dim-bracket crop 7.46 (pointer edges, rocket pose); golden mouse (face colour 2.0 acts as 1.0, so the port's intensity is right; the crop's 31.5 is draw ordering); START banner 2.39 (alpha-0 colour, texel precision and vertex colour ruled out; left: 4444 filter order).

## Blocked (needs an input first)

- **Languages:** French Help plate/footer need a non-USA dump.
- **The Basics:** needs mobile-original frames to diff (port is port-vs-port only).
- **Banner pixel diff (3-2-1, time-left):** needs a clean background; the board moves behind every Flycast banner frame (geometry already fits).
- **Battle captures:** flyhost Battle runs differ between invocations; dump (`FLY_DUMP`) in the same run as the shot you need.

Capture recipes (flyhost): Puzzle `START@1350-1360;START@1510-1520;DOWN@1800-1804;DOWN@1840-1844;DOWN@1880-1884;START@1950-1960;START@2120-2130`; Challenge drops one DOWN and adds `START@2300-2310`; Battle `START@1350/1510/1800/2400/2550`. Keys: X places the north arrow, R2 = R trigger. RAM pokes: style 0x1ae8d0, Puzzle masks 0x22d8a4.., golden 0x1ae8f8. Language: resume `local/star-trace/opt/o03050.state`.

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
