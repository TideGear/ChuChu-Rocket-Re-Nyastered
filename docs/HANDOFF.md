# Handoff (2026-11-17, end of session)

Read first: `docs/goal.md` (plan, under 5,000 characters; now has a Completeness rule: list every routine, effect, trail and screen of each original in `docs/audit.md` as open until verified), `docs/audit.md`, then the newest `docs/roadmap.md` entries and `docs/dreamcast_models.md` (all Dreamcast findings). Standing goal: Dreamcast-image-only setup/play and Dreamcast look matching Flycast.

## Just done
- Release **v2026.11.20** has verified downloads for Windows x64, Linux x64, macOS arm64 and macOS x64. Fixes include a platform-specific missing-assets message, `setup.log` with its path printed, and a visible launcher error.
- Dreamcast moving player cursors: traced the live Battle effect, including the trail texture and 24-tick fade. Battle and Puzzle draw the pointer and trail from the disc. Native camera alignment and other original modes remain open.
- Dreamcast Battle board: floor is yuka01 on every stage (read from the 25 stage previews), outer wall frame always drawn, walls darker. The "wall" model (0xa20fc, kabetx01) was right; the c_* candidates were HUD pieces.
- Tools: `flyhost` (FLY_DUMP=1) dumps main RAM and a save state; `tools/oracle/ta_parse.py` decodes the game's PowerVR stream; `dc_ram_trace.py` runs game SH-4 code on the RAM dump with stubs that log Ninja calls; `dc_callers.py` finds callers (bsr and pointers).

## Linux player (RecompLauncher report, CachyOS): still unresolved
They were on v2026.11.17, said Easy Setup rejected their ipa/gba/DC files, then "Game assets not found". Cause not reproduced. Needs from them: v2026.11.20, `~/.config/ChuChuRocketReNyastered/setup.log`, `python3 --version`. Reply drafted: update, pick the folder (launcher refuses single files), install `python-pillow`, or run `./ccr --prepare "<folder>"`.

## Dreamcast HUD work (next)
- Live Battle draw callback `0x8c0272a0` is in the task list walked by `0x8c01efd2`. Frame 3100 has 32 sprite submissions through `0x8c0e4bec`, followed by the board draw. Their matching PowerVR quads start at state offset `0x19d1cc3`. See `docs/dreamcast_models.md` for the layout and texture names.
- The port now draws the four-player sprite HUD in screen coordinates, including CPU labels and the countdown column. Frames 3600, 4250 and 4950 exercise live scores and elapsed time. Next trace human tags and crown layers and capture roulette and Team Battle. The FOURADV 3D objects from dispatcher `0x8c034c60` belong to a different screen.
- Real-frame capture script for the Battle frame at 3100: keys `START@1800-1806` then `START@t-(t+6)` for t=2400,2550,...; `FLY_DUMP=1`.

## Open (also in audit.md)
Arrow-placement ghost, cursor alignment and other modes, character camera pitch/scale, lighting, animation phase vs real frames, rocket pad ball and base, Dreamcast 2D UI path (fonts, backgrounds, brackets, arrows, holes), Puzzle/Challenge/Team Dreamcast floor colours, stage 24 seed 3000 from f2779, Puzzle Edit screen, Linux/macOS real-desktop tests.

Rules to keep: no AI attribution trailers in commits (user's global CLAUDE.md); timing tests through `tools/quiet.ps1`; headless tests only; read original code before implementing; keep goal.md under 5,000 characters.
