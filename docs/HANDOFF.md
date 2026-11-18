# Handoff (2026-11-17, end of session 2)

Read first: `docs/goal.md` (plan, under 5,000 characters), `docs/audit.md` (the "Dreamcast screens vs real Flycast frames" entry is the current status), then the newest entries of `docs/dreamcast_models.md` (all Dreamcast findings, newest at the bottom). Standing goal: Dreamcast-image-only setup/play and a Dreamcast look matching Flycast. The `/goal` condition used this session ("match the look, then finish goal.md") cannot clear in one session; set a per-turn or per-screen goal next time.

## How to get real Flycast frames (all headless)
- Core: `C:\Users\Tideg\My Drive\RetroArch\Cores\flycast_libretro.dll`. Disc: `local/dc_ref/disc/ChuChu Rocket! (USA) (En,Ja,Fr,De,Es).cue`. BIOS in `local/dcsys`.
- `build\game\flyhost.exe <core> local\dcsys <save dir> <cue> <frames> <prefix> <shot frame> "<keys>"` with `FLY_DUMP=1` also writes `<prefix><frame>.state` and `.ram`. The shot argument is ONE frame number. Keys: `START@a-b;DOWN@a-b;LEFT@...` (B Y SELECT START UP DOWN LEFT RIGHT A X L R).
- Navigation (frame numbers): `START@1350;START@1510` reach Mode Select (frame 2750 shows it; 4P Battle, Team Battle, Stage Challenge, Puzzle, Puzzle Edit, ... in order). Puzzle Normal 01: `START@1350-1360;START@1510-1520;DOWN@1800;DOWN@1840;DOWN@1880;START@1950-1960;START@2120-2130`, shot 2390. RIGHT@2040 before the last START = stage 02, LEFT = stage 25, START@2300 = pause. Challenge: two DOWN, then `START@2120` intro card, `START@2300` play, `START@2600` pause. Four-player Battle: `START@1800;START@2400;START@2550;START@2700;START@2850;START@3000`, pause `START@3300`; Team Battle: one `DOWN@2640-2644` before them. Four DOWN reach Puzzle Edit.
- `tools/oracle/ta_parse.py <state> <start hex> <end hex>` decodes the PowerVR stream; the 2D HUD list needs start offset `0x1900003` (alignment 3 mod 32), the 3D board list `0x253e10`. VRAM textures: word & 0x1fffff times 8, formats in `docs/dreamcast_models.md`. `dc_ram_trace.py` runs game SH-4 code on the RAM dump.
- Port captures: `CCR_MODELS=1 CCR_TICKS=n CCR_SHOT=x.bmp build\game\ccr.exe local\cache\assets puzzle 0|battle 0 1 -1,3,3,3|challenge 0` (`CCR_TEAM=1`, `CCR_PAUSE_TICK=n`, `CCR_CLICKS=5:90,690` pauses Puzzle; stage index 0 = Normal 01). After `tools/export_dc_ui.py <dc prs_png> local/cache/assets/ret_all <dc png>` for new sheets.

## Done this session (all committed; see docs/dreamcast_models.md)
- Dreamcast Puzzle: left panels, stage label and digits (`PUZZLECLEAR_new0..9`), level plate and label, bottom panel, hint-bubble frame, measured floor plane (Battle's) for drawing and input, domes, pad cursor start (6,4), bracket, pointer anchor, mouse yaw `-angle`, floor colour by group, stock arrows (order up,right and 34 px pitch), pause screen.
- Challenge: time column (`drawDcTimerColumn`), measured layout, red dome, pause with title and "Player 1" plate (P key).
- Battle and Team Battle: pause overlay, win boxes and win-mark rockets, Team Battle HUD and layout.
- Models: game light (0.3 + max(0, 0.5 up + 0.25 screen-up)), mouse UVs `(1-v,u)`, cat yaw `-angle` and size 0.075.
- Not pushed before this handoff; pushed at its end.

## Open (also in docs/audit.md)
Puzzle: hint-text font (original draws text into a run-time texture), pointer size, mouse brightness, groups other than the first and Hard/Mania/Original/Special, Puzzle Edit (a real pause frame is in `local/dc_ref/pz3`). Challenge: intro card (one run-time 512x256 sprite), controller cursor (real start cell (5,3)), result screens, other types. Team Battle: ties, question-mark ChuChu, a missing top-right Computer plate in one capture. Cat: tail still shows, walk phase/frame rule provisional. Everything else in audit.md (phases B-G, roulette, remaining menus, online, Linux/macOS desktop tests) is unchanged.

## Linux player (RecompLauncher report, CachyOS): still unresolved
They were on v2026.11.17; Easy Setup rejected their ipa/gba/DC files, then "Game assets not found". Needs from them: v2026.11.20, `~/.config/ChuChuRocketReNyastered/setup.log`, `python3 --version`. Reply drafted: update, pick the folder (launcher refuses single files), install `python-pillow`, or run `./ccr --prepare "<folder>"`.

Rules to keep: no AI attribution trailers in commits or PRs (user's global CLAUDE.md outranks the session reminder); timing tests through `tools/quiet.ps1`; headless tests only; read original code before implementing; keep goal.md under 5,000 characters.
