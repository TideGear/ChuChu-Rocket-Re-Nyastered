# Handoff (2026-11-16, end of session)

Read first: `docs/goal.md` (the plan, keep under 5,000 characters), `docs/audit.md` (current status per requirement and per claim of the version-comparison document), then the newest entries of `docs/roadmap.md` (dated findings; it is large and should be summarised). Rules: no AI attribution in commits (global CLAUDE.md), test headlessly (never use the user's screen or audio), read the original code before implementing behaviour, report only what changed and the next step.

## State
- Windows build works (`build.cmd --target ccr`, tests are CMake targets in `game/`). Releases v2026.11.16 and v2026.11.17 are published; the repo is source-only.
- Whole-battle comparison through the real loop (task mask by roulette status): free-for-all 26/26 for all eight forced outcomes (`MASK=1 make_battle_forced_golden.py <k>`, then `FREEZE=1 FULL=1 FORCE=<k> battle_full_test.exe ../local/testdata/battle_forced_<k>_mask.txt` from `game/`). Team Battle through the real loop: 26/26 for all eight outcomes (`TEAM=1 MASK=1` recordings; they equal the free-for-all ones except outcome 6 Cat Attack, as expected at game time 0). Everybody Move at game times 1/3/4/7 with the mask is being recorded (`mask_team_gt*.log`).
- Stage Challenge: 24 of 25 stages playable. Types 3 and 4 identical to the original. Stage 24 (`ChallengeBattleGame` type 5): seeds 1000 and 2000 fully identical; seed 3000 identical to f2779. There the CPU heat sum drops by 196 in one step in the original (`HEATW=2762,2781` in `challenge_probe.py`, `HEATSUM=2762` in the port test) but by 90 at f2779 and 106 at f2785 in the port: two heat sources should leave at f2779 (a cat's footprint moving a cell plus something else; cat at (44.5,22.5) moving left at speed-up speed).
- Also built this session: roulette freeze (`freezeOnRoll`, `cpuRunsOnFreeze`), `core/userdata.hpp` (portable mode, `settings.ini`, rotating log), `core/padmap.hpp` (`controls.ini`, quit combo), Options "Settings" page, Battle CPU style setting.

## Next, in order
1. Stage 24 seed 3000 from f2779 (and Everybody Move at game times 1/3/4/7 through the mask for Team Battle).
2. Challenge and Team Battle result screens; Puzzle Edit screen with VMS/VMI export (format notes in `docs/modes.md`, `docs/dlc.md`).
3. Unlock-all and gating, VMS import and skins, PuzzleP stock, CHD/GDI input.
4. GBA: map the ROM's 12 roulette handlers to events, compare the GBA CPU with the mobile one, explain the 171 vs 521 score gap (see the claims table in `docs/audit.md`).
5. Linux/macOS builds (only a Zig compile check so far), 4K measurement, Android emulator and PWA runs (ask before installing an emulator image), netplay screens.
6. Summarise `docs/roadmap.md` (159 KB) and re-read `README.md` before the next release.

## Practical notes
- Original-code oracle tools are in `tools/oracle/` (Unicorn; ghidra address = file vaddr + 0x10000). `challenge_probe.py` env switches: SEED, ARROWS, TRACKWORDS, TRACKARR, TRACKUP, TRACKW4, TRACKCPU, RNGDRAWS, FORCE, MPOS, CPOS.
- Editing strings with `\n` through the shell heredocs often turns them into real newlines; use `chr(92)` in Python or the Edit tool.
- Local, git-ignored: `local/` (cache/assets, testdata goldens), `analysis/`, `Original Game Files`.
