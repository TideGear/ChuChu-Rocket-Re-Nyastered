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

## Next tasks

1. **Mouse pose clock: done** (Puzzle only; Battle and Challenge still use `sim.now`, untraced there). puzzle_pause full frame 1.95, mice pass.
2. **Puzzle pause overlay: done**, every element passes (audit.md). Battle/Challenge pause have no parity case yet.
3. **Battle cursor cell marker: done** (draw `0x8c0146e6`: cell word & 0xF00 -> bracket colour 0xc0 alpha, grey 0x80 + trunc(16 sin((task+32) >> 2)), task+32 += 0x1000 per pass in `0x8c0145ee`; else white). Pixels match Flycast 3100 within 1 level; battle_3100 2.30 -> 2.13. `battle_3100` alignment: tick 30 is the best of a 10-80 sweep; the residue is the missing START text over the board centre, the cursor pointers' pulse size, and the stars. Still open: whether Puzzle/Challenge brackets share this rule.
3b. **Dreamcast Battle banners:** countdown/START done (load `0x8c028ee0`: count1-3, ato30, ato1, ato2, start.pvr; task update `0x8c028d40` lifetimes 60/120/45, draw `0x8c028d90` NJS_SPRITE `0x8c0bc514` at (360,208), scales 8-0.13t / 4-0.033t / 0.09t; exported as `dc_battle_count`). battle_3100 realigned to tick 94 (2.02); start_banner crop 2.39, shift 0,0, no off-edge px (not yet <= 1). Round panel done too (draw `0x8c028fd8`: "Round" at (375 - 1.67t, 224), digits at 375 + 0.33t / 375 + 1.4t, y 224 - 0.21t, scale 0.02t, 75 ticks; sheet `dc_battle_round`): tag frame 3020 = port tick 14 (round crop 1.06), 3050 = tick 44 (10.5: "Round" matches (x 199-341 vs port 195-339 at tick 46), but Flycast's "0" is 42 x 57 px against the port's 32 x 52 and its "1" 13 px wide against 9; the WINNO PVRs are plain 32 x 32 twiddled ARGB1555 and decode correctly (19-texel glyph at the left), so the original draws the digits wider than texanim 64 x 64 at 0.02t implies; look for a per-digit scale or UV in the sprite call 0x8c0e4268). Open: the time-left/3-2-1 banners have no Flycast frame yet.
4. **Remaining Flycast checks:** Chao/Pian costumes (need a save with all Challenge or Mania clears) and the golden mouse frame by frame.
5. **Puzzle coverage:** Hard, Special and Mania stages; star twinkles; launch per element. **Tutorial** (mode 16, `0x8c058292`) and The Basics: not implemented.
6. **Dreamcast-look language:** export the disc's fr/de/es/ja art and fall back to English for Italian. The Puzzle tap-timing writer and MANATEE.DRV command 0x8a (Monaural) stay open.

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
