# Handoff (2026-11-17)

Read first: `docs/goal.md` (the plan, keep under 5,000 characters), `docs/audit.md` (current status per requirement and per claim of the version-comparison document), then the newest entries of `docs/roadmap.md` (dated findings; large, should be summarised). Rules: no AI attribution in commits (global CLAUDE.md), test headlessly (never use the user's screen or audio), read the original code before implementing behaviour, report only what changed and the next step. **Timing tests go through `tools/quiet.ps1 -Run '<cmd>'`** (other projects share this PC; only CLEAN runs count).

## State
- Windows build works (`build.cmd --target ccr`; tests are CMake targets in `game/`). Releases v2026.11.16 and v2026.11.17 exist (the latter predates Challenge stage 24, unlock-all, imports and the Settings page; cut a new one before announcing anything).
- Whole-battle comparison through the real loop (task mask by roulette status): free-for-all and Team Battle 26/26 for all eight forced outcomes, plus Team Everybody Move at game times 1/3/4/7. Stage Challenge: 24 of 25 stages playable; types 3 and 4 identical to the original; stage 24 seeds 1000 and 2000 identical, seed 3000 identical to f2779. There the original's player 1 makes no decision from f2322 while the port's picks (5,4): path check, heat, collisions, rockets and global time are all equal, so the cause is still unknown (probes in `challenge_probe.py`: TRACKCPU, PATHTEST, HEATFULL, COLLDUMP, ARRSLOTS; the ATTACKDBG label hooks fire only once, fix them).
- Phase G/F items built: portable mode, `settings.ini`, `controls.ini` (remap, quit combo), rotating log, Options > Settings page (display, log, remap, CPU style, unlock all), `.VMS` puzzle pack import (`<data>/imports`) and `core/vms.hpp` + `tools/vms_pack.py` writer (checked against the real DLC packs), load-guarded 4K timing (8.1 ms/frame, RTX 3060). CI: `.github/workflows/build.yml`: Linux green; macOS runners were never provided on `macos-14`, `macos-latest` and `macos-13` were just tried (check the Actions tab).

## Next, in order
1. Stage 24 seed 3000 from f2779 (above). Challenge and Team Battle result screens.
2. Puzzle Edit: read `EditorGameScreen` (tools, test play, the "solved" gate), build the screen, save format, in-app `.VMS` export with `core/vms.hpp`.
3. Costumes screen (unlock conditions in `docs/unlockables.md`), DLC character skins, PuzzleP stock, CHD/GDI input.
4. GBA: map the ROM's 12 roulette handlers, GBA CPU vs mobile, the 171 vs 521 score gap, Character Edit.
5. Android emulator (ask before installing an image) and PWA headless runs, netplay screens, native macOS verification, Linux/macOS releases.
6. Summarise `docs/roadmap.md` (large) and re-read `README.md` before the next release.

## Practical notes
- Original-code oracle tools are in `tools/oracle/` (Unicorn; ghidra address = file vaddr + 0x10000).
- `\n` inside shell heredoc Python strings often becomes a real newline; use `chr(92)` or the Edit tool.
- Local, git-ignored: `local/` (cache/assets, testdata goldens), `analysis/`, `Original Game Files`.
