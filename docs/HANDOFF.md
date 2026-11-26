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
- Parity: 132 cases, all within the full-frame limit (with a BIOS in the local test caches). Asset version 6 (re-run setup).

## Done 2026-11-25

- Puzzle cat walks in place during arrow placement (was frozen); start tick 32 measured from a scan, not traced. Hard 05 board 1.24 -> 0.87.
- Dimmed cursor bracket has no size pulse (`0x8c01480c`); Challenge pad pointer pulse phase `cticks + 2`; pad aim confirmed against RAM `0x8c186cfc` (DcCursor already exact).
- Count2/count1 banner scales fit `8 - 0.13 t`. New parity cases: `puzzle_normal08` (board passes), `puzzle_hard05`, `challenge_play_a1_dim_bracket` (partial). Headless hook `CCR_PAD_AIM=x,y` (Challenge).
- goal.md: current milestone (Dreamcast Puzzle end to end), "pass (rounding)" rule, honest-reporting and visible-gaps-first working style.

## Next tasks (milestone: Dreamcast Puzzle end to end)

0. **Hole fall pose (time-boxed):** the "3 passes late" was Flycast display latency, not port timing: the RAM dump leads the shown frame by 3 passes (ring age 21 in RAM, the shown ring matches the port's age 18; ring formula identical, no rotation in draw `0x8c02c4f8`), which the case tick already absorbs. Open: the frozen pose is 6 in RAM; the port's (clock - passes since fall) gives 3, and +3 (pose 6) brings the hole crop from 5.38 to 1.12, but the clock relation behind the +3 is not derived, so it is not committed. Flycast runs also differ between invocations (local/hole vs local/hole-ram).

1. **Stream tool: done** (`tools/oracle/ta_dump.py info|list|tex|render`). Open in it: how characters are ordered (all their vertices have z = 0.005; Flycast draws the rocket dome over the mouse, the tool's depth test does not).
2. **Puzzle visible-gap sweep:** done for stage select (1.82), placing, run (0.73), Dash (keyboard Space now dashes, 1.04), pause (Quit selection and sounds from `0x8c01a316`) and failure: Dreamcast focus ring (1.04 / 1.16), now depth-tested against the domes; hole fall (mouse spins and shrinks, `0x8c01952e`; Normal 08 hole case 1.38). Dome bounce on arrival (`0x8c01cbc8` / `0x8c01c380`) and cat-in-rocket cue 7 added. Left: (a) the background sky (task `0x8c01f272`: source confirmed by poking it off in Flycast; model exported as `sky`, renderer `drawDcSky` written with the real view and lighting, not drawn because the streaks land elsewhere; its polygons are in no list `ta_dump.py` finds: next, locate them, e.g. in the translucent list of the other parameter buffer); (b) clear/launch per element (cases exist); (c) the code inventories now in audit.md (Puzzle tasks and sounds are complete apart from the sky). Look separation (2026-11-25): 0 of 21 cases differ in both looks. Fixed: the mobile title used the Dreamcast logo and prompt whenever the disc was installed (30,786 px); `stages` differed only because headless test runs wrote progress.bin into the asset cache they ran from (a cleared tick on stage 1). Test runs (CCR_SHOT / CCR_HEADLESS / CCR_BENCH) now keep progress, Challenge records and options in memory (`App::testRun`).
3. **"Pass (rounding)": done.** `tools/parity.py` now writes `<element>_verdict` (pass / pass (rounding) / fail), `_offset` and `_residual`. Across 140 cases: 95 pass, 9 pass (rounding) (Pian right mice and the Puzzle list box in 8 cases), 101 fail.
4. **Hard 05 cat shading: time-boxed** (cat crop 2.59, 572 off-edge px; pose matches; about 0.02 of the full frame). Ruled out: the light (the game's only setter `0x8c018d9c` writes the block `0x8c2d0600`; the cat draw `0x8c011198` sets none), node scales (all 1), the head normals, the exporter's normal transform, and the mouse light at any tested strength. Remaining route, if reopened: dump the port's per-vertex cat normals, pair them with the stream by UV, and compare per node.
5. **Puzzle pad tip: closed.** Source traced (`0x8c014860`, task+32); the port's `cticks` phase is the best of a 0-15 offset scan and the Normal 03 residue is under 0.005 full-frame (roadmap).

Other open (outside the milestone): Challenge dim-bracket crop 7.46 (pointer edges, rocket pose); golden mouse (face colour 2.0 acts as 1.0, so the port's intensity is right; the crop's 31.5 is draw ordering); START banner 2.39 (time-boxed: alpha-0 colour, texel precision and vertex colour ruled out; the residue is not a rounding offset: +1.17 / +0.35 / +0.75 with residual 2.35; left untested: the 4444 filter order).

## Blocked (needs an input first)

- **Languages:** French Help plate/footer need a non-USA dump.
- **The Basics:** needs mobile-original frames to diff (port is port-vs-port only).
- **Banner pixel diff (3-2-1, time-left):** needs a clean background; the board moves behind every Flycast banner frame (geometry already fits).
- **Battle captures:** flyhost Battle runs differ between invocations; dump (`FLY_DUMP`) in the same run as the shot you need.

Capture recipes (flyhost): Puzzle `START@1350-1360;START@1510-1520;DOWN@1800-1804;DOWN@1840-1844;DOWN@1880-1884;START@1950-1960;START@2120-2130`; Challenge drops one DOWN and adds `START@2300-2310`; Battle `START@1350/1510/1800/2400/2550`. Mode Select entries (DOWN count from the top, then START): 3 Puzzle (15), 4 Puzzle Edit (8), 5 network (9), 6 unknown (mode variable invalid), 7 Options (11), 8 Help (6). Keys: X places the north arrow, R2 = R trigger. RAM pokes: style 0x1ae8d0, Puzzle masks 0x22d8a4.., golden 0x1ae8f8. Language: resume `local/star-trace/opt/o03050.state`.

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
