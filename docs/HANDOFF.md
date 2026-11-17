# Handoff (2026-11-16, end of session)

Read first: `docs/goal.md` (the plan, keep under 5,000 characters), `docs/audit.md` (current status per requirement and per claim of the version-comparison document), then the newest entries of `docs/roadmap.md` (dated findings; it is large and should be summarised). Rules: no AI attribution in commits (global CLAUDE.md), test headlessly (never use the user's screen or audio), read the original code before implementing behaviour, report only what changed and the next step.

## State
- Windows build works (`build.cmd --target ccr`, tests are CMake targets in `game/`). Releases v2026.11.16 and v2026.11.17 are published; the repo is source-only.
- Whole-battle comparison through the real loop (task mask by roulette status): free-for-all 26/26 for all eight forced outcomes (`MASK=1 make_battle_forced_golden.py <k>`, then `FREEZE=1 FULL=1 FORCE=<k> battle_full_test.exe ../local/testdata/battle_forced_<k>_mask.txt` from `game/`). **Team Battle is not confirmed**: the team masked recordings equal the free-for-all ones, so `TEAM=1` has no effect there; find out why.
- Stage Challenge: 24 of 25 stages playable. Types 3 and 4 identical to the original. Stage 24 (`ChallengeBattleGame` type 5): seed 1000 identical, seed 2000 identical to f1540, seed 3000 identical to f1286 then both computer players place one arrow a frame early (original decides at f1281 from `TRACKCPU` in `challenge_probe.py`; port decides a frame sooner; heat at the target cell is the suspect).
- Also built this session: roulette freeze (`freezeOnRoll`, `cpuRunsOnFreeze`), `core/userdata.hpp` (portable mode, `settings.ini`, rotating log), `core/padmap.hpp` (`controls.ini`, quit combo), Options "Settings" page, Battle CPU style setting.

## Next, in order
1. Team Battle through the real loop (above), then stage 24 seed 3000.
2. Challenge and Team Battle result screens; Puzzle Edit screen with VMS/VMI export (format notes in `docs/modes.md`, `docs/dlc.md`).
3. Unlock-all and gating, VMS import and skins, PuzzleP stock, CHD/GDI input.
4. GBA: map the ROM's 12 roulette handlers to events, compare the GBA CPU with the mobile one, explain the 171 vs 521 score gap (see the claims table in `docs/audit.md`).
5. Linux/macOS builds (only a Zig compile check so far), 4K measurement, Android emulator and PWA runs (ask before installing an emulator image), netplay screens.
6. Summarise `docs/roadmap.md` (159 KB) and re-read `README.md` before the next release.

## Practical notes
- Original-code oracle tools are in `tools/oracle/` (Unicorn; ghidra address = file vaddr + 0x10000). `challenge_probe.py` env switches: SEED, ARROWS, TRACKWORDS, TRACKARR, TRACKUP, TRACKW4, TRACKCPU, RNGDRAWS, FORCE, MPOS, CPOS.
- Editing strings with `\n` through the shell heredocs often turns them into real newlines; use `chr(92)` in Python or the Edit tool.
- Local, git-ignored: `local/` (cache/assets, testdata goldens), `analysis/`, `Original Game Files`.
