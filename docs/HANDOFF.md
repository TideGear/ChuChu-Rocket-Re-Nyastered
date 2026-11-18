# Handoff (2026-11-17, end of session)

Read first: `docs/goal.md` (plan, under 5,000 characters; now has a Completeness rule: list every routine, effect, trail and screen of each original in `docs/audit.md` as open until verified), `docs/audit.md`, then the newest `docs/roadmap.md` entries and `docs/dreamcast_models.md` (all Dreamcast findings). Standing goal: Dreamcast-image-only setup/play and Dreamcast look matching Flycast.

## Just done
- Release **v2026.11.20** (tag pushed; release created by hand, because CI only uploads to an existing release; Linux/macOS jobs were re-run, check they attached their archives: `gh release view v2026.11.20`). Fixes: missing-assets message per platform, `setup.log` always written with its path printed, launcher start shows an error instead of exiting.
- Dreamcast Battle board: floor is yuka01 on every stage (read from the 25 stage previews), outer wall frame always drawn, walls darker. The "wall" model (0xa20fc, kabetx01) was right; the c_* candidates were HUD pieces.
- Tools: `flyhost` (FLY_DUMP=1) dumps main RAM and a save state; `tools/oracle/ta_parse.py` decodes the game's PowerVR stream; `dc_ram_trace.py` runs game SH-4 code on the RAM dump with stubs that log Ninja calls; `dc_callers.py` finds callers (bsr and pointers).

## Linux player (RecompLauncher report, CachyOS): still unresolved
They were on v2026.11.17, said Easy Setup rejected their ipa/gba/DC files, then "Game assets not found". Cause not reproduced. Needs from them: v2026.11.20, `~/.config/ChuChuRocketReNyastered/setup.log`, `python3 --version`. Reply drafted: update, pick the folder (launcher refuses single files), install `python-pillow`, or run `./ccr --prepare "<folder>"`.

## Dreamcast HUD work (next)
- The HUD is a 3D scene of flat Ninja models (camera from the game: njPerspective focal 554.297, centre 320,240, found by tracing), exported as `h_<offset>` (0xaa370-0xb16bc, `HUD_TEX` = FOURADV list). The decoded game states 0x80-0x8a (dispatcher 0x8c034c60) draw these at (90,10,144), (-14,8,80), (100,50,100): that is a menu/result screen, NOT the live Battle HUD. The live Battle HUD task has not been found yet.
- Method that works: load `d3_03100.ram` into `sh4.py`, call a function, stub failing callees and log njTranslate (0x8c0e1028), njDrawObject (0x8c0fc308), njPerspective (0x8c0ebd98). Next: find the Battle per-frame entry (callers chain from cat draw 0x8c0119fe: bsr callers 0x8c011060/0x8c011120/0x8c0117c0, `dc_callers.py 8c0119fe`), run it on the RAM dump, log every draw, place models in the port with the 554.3 camera, diff against `local/dc_ref/shots/n3_03100.bmp`.
- Real-frame capture script for the Battle frame at 3100: keys `START@1800-1806` then `START@t-(t+6)` for t=2400,2550,...; `FLY_DUMP=1`.

## Open (also in audit.md)
Cursor trail / arrow ghost (original has separate callbacks; port has none; trace and capture Flycast frames); character camera pitch/scale, lighting, animation phase vs real frames; rocket pad ball and base; Dreamcast 2D UI path (fonts, backgrounds, cursors, arrows, holes); Puzzle/Challenge/Team Dreamcast floor colours (need frames); stage 24 seed 3000 from f2779; Puzzle Edit screen; Linux/macOS real-desktop tests.

Rules to keep: no AI attribution trailers in commits (user's global CLAUDE.md); timing tests through `tools/quiet.ps1`; headless tests only; read original code before implementing; keep goal.md under 5,000 characters.
