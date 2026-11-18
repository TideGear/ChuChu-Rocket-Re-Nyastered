# Handoff

Read [goal.md](goal.md) for scope and [audit.md](audit.md) for status. Use [Dreamcast rendering notes](dreamcast_models.md) for measurements, [mesh inventory](dreamcast_meshes.md) for model addresses, and [captured poses](dreamcast_mesh_poses.md) for verified usage. Use the Ghidra decompile at `analysis/decomp/dc_1st/1ST_READ.BIN.c` when it answers a question faster than fitting a frame. Derive numbers from original code or the stream. Test headlessly, run timing tests through `tools/quiet.ps1`, and push verified commits without attribution trailers.

## Current Dreamcast work

- Windows setup and live play work with the tested USA CUE/BIN disc alone. Fresh extraction, build, Battle, Team Battle, Challenge A1 and Puzzle captures passed. Other image formats and platforms need their own checks. The D: build junction was readable but compilation needed a writable local build directory.
- Mode Select and Stage Challenge select now use disc art. Next reproduce the Challenge intro card and result/failure screens, replace the in-play placeholder line, and audit remaining mode placeholders. The A1 intro composes a 512×256 texture at runtime. See `local/dc_ref/pz4` and the rendering notes. Stage selection still needs exact clock glyphs, clear marks, and unlock/transition verification.
- Audit Challenge audio first: stage-select move/confirm/back, intro, countdown, goal, clear, fail, voices and BGM. Then inventory all Dreamcast cues with SH-4 caller, bank/program or CD track, volume, pan, pitch, priority/channel, loop points, fade and cancellation. Use `MANATEE.DRV`, `MLT_*`, GAMEVOICE and CD tracks 04–18. Add headless WAV capture to `flyhost` and compare against port output.
- Audit menu, result and roulette draw order and seams. The floor, walls, pits, generator pads and parked domes are already measured. Keep the fuller mouse ear the user prefers unless exact shared-depth occlusion is offered as an option. Remaining visual differences include mouse tail and foot colour, cat and mouse clock rules, the focus ring, KapuKapu, and Chao/Pian variants. The mesh inventory records unseen models.
- Linux CachyOS report needs a retest on v2026.11.20, `~/.config/ChuChuRocketReNyastered/setup.log`, and `python3 --version`. Easy Setup takes the folder containing the disc. The CLI equivalent is `./ccr --prepare "<folder>"`. The released fix still needs a real machine check.

## Headless captures

Run `build\game\flyhost.exe <core> local\dcsys <save-dir> <cue> <frames> <prefix> <shot[,shot...]> "<keys>"`. Core is `C:\Users\Tideg\My Drive\RetroArch\Cores\flycast_libretro.dll`. The disc is in `local/dc_ref/disc`. `FLY_DUMP=1` adds RAM and state. `FLYHOST_RES=1280x960` sharpens the image while preserving 640×480 stream coordinates. Flycast inputs are libretro names. `B` confirms and `A` goes back on the Challenge selector. `R2` is Puzzle Start/Dash.

- Mode Select: `START@1350-1360;START@1510-1520`. Shot 2750.
- Challenge: append `DOWN@1800-1804;DOWN@1840-1844;START@1950-1960`. Shot 2100. `START@2120-2130` opens A1, `START@2300-2310` skips its intro, and `START@2600-2606` pauses. Shots 2390, 2500 and 2700 are in `pz4`, `ch1` and `cp1`.
- Puzzle: add a third Down at 1880 before START at 1950. After the selection opens, `START@2120-2130` opens Normal 01. Shot 2390. A Right at 2040 picks Normal 02 and a Left picks Normal 25. Use `R2@2300-2310` to run.
- Battle: after the initial two Start presses, use Start at 1800, 2400, 2550, 2700, 2850 and 3000. Down at 2640 before these later confirmations selects Team Battle.
- Decode saved polygons with `tools/oracle/ta_parse.py`. Board list starts at `0x253e10` in the reference gameplay frames. The 2D list uses alignment 3 modulo 32. `dc_fit.py` unprojects vertices and `dc_ram_trace.py` executes routines on the live RAM snapshot.
- Port captures use `CCR_MODELS=1 CCR_TICKS=n CCR_SHOT=x.bmp` and `ccr <assets> puzzle 0`, `battle 0 1 -1,3,3,3`, or `challenge 0`. Use `CCR_KEYS=DDE` with `MENU` for Challenge Select and `CCR_PAUSE_TICK=n` for pause. Regenerate disc UI with `tools/export_dc_ui.py <prs_png> <ret_all> <png>` after exporter changes.
