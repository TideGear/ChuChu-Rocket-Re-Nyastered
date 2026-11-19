# Preview release handoff — November 18, 2026

The user requested a preview release after a clean build and smoke checks, then a final commit/push and a stop for handoff. Do not silently continue the old unbounded goal after finishing that release. The longer-term objective remains in goal.md; read its no-placeholder, original-code, capture and verification rules before resuming in a new conversation.

## Changes in this preview

- Cursor atlas sampling: added duplicated edge gutters and power-of-two atlas slots for the four Dreamcast cursors/trails. Original `FUN_8c014860` sets scale to `1 + 0.1*sin(angle)`; update `0x8c0146d0` adds 0x1000 each tick (16-tick pulse). A detached vertical line at the upper right was reproduced on hidden SDL Direct3D11: old atlas differs from the original separate texture at 158 pixels over 16 phases, maximum channel error 86. Padded atlas: zero differing pixels over all phases. `tools/oracle/cursor_atlas_probe.cpp` is the reproducible accelerated-renderer check; it hooks no game logic. This is an atlas fix, not a full original-loop animation verification.
- Dreamcast Puzzle Stage Select replaces the generic 5x4 fallback grid for the main 100 puzzles when Dreamcast art is active. It uses the disc's backing, capsules, numeric atlas, check marks, difficulty labels, hint bubble and 3D board preview. Original captured via the normal result-to-selector route: `local/session-resume/puzzle-select/a_00249.bmp`, state `a00249.state`. Actual 2D packets at 0x19bd59b..0x19bee9b (alignment 27 modulo 32). Native 640x480 full-frame mean RGB error 2.24575; header 0.58631, capsule grid 0.60662. Hint and preview retain residue. BIOS runtime text uses the existing optional BIOS glyph sheet or documented bundled Roboto Mono fallback, not the built-in 5x7 font. Other stage sets still use the existing non-Dreamcast route and remain open.
- Selector input checked against original frames: Left and Up from 01 both wrap to 25 (`left00049.state`, `up00049.state`); Right, Down, Left reaches 06 (`move00049.state`). Normal group controls, keyboard, mouse and controller routes are connected; other groups and transitions need further original-loop checks.
- Puzzle clear now shows the native result artwork after the original phase-4 hold, 210 ticks or 105 under Dash (`0x8c02bf00`), with Next and Stage Select controls on keyboard/controller/mouse. Natural disc-only replay at aim (385,117), keys `U `, saves all 40 mice at tick 1521 and enters Result at 1731. Banner crop mean RGB error 0.66950; controls 0.11961. Those are isolated-art measurements, not zero-pixel text certification. Save notification timing and the launch/smoke sequence remain open.
- Battle arrows now use the original 13.5-unit quad inside each 15-unit cell. Battle draw is 0x8c0103e2, quad 0x8c075aac (x/z +/-6.75, y 0.5), manager entries at 0x8c186178, player stride 0x4c, three 0x18-byte entries. Hit scaling 0.7 is additional. At native 640x480, DC_DEMO tick 1772 versus Flycast watch frame 3550: full mean RGB 5.94951 -> 5.50016. Still partial, above the goal.md full-frame limit.
- Windows/native release packages include the BIOS font exporter and bundled font files/licenses needed by the disc-only setup path. The packaging script accepts explicit executable, dependency and output directories for isolated builds.

## Captures and tests

- Native app build: `local/preview-release/build/ccr.exe`; package and fresh extraction checks are recorded under `local/preview-release/`.
- Cursor evidence: `local/session-resume/cursor-edge/probe.log`, `gpu-comparison.png` (old left / fixed right), `gpu-0.bmp`, `gpu-1.bmp`, `gpu-2.bmp` (original separate texture).
- Puzzle clear evidence: `local/session-resume/puzzle-clear/`. Original prefix `q` resumes `local/dc_ref/pz/p_02390.state`, with `LEFT@2-6;UP@10-24;X@30-32;R2@60-65`. X in libretro is the Dreamcast up-arrow face button. Arrow lands at cell (6,2) and naturally solves the stage. Original watch `qwatch.bin` covers RAM 0x22d894, 16 bytes, with phase transitions at watch frames 61 (play), 1582 (clear hold), 1792 (result). Original prefix `s` resumes `q01500.state`; it includes launch, settled result and next-stage frames.
- Regression checks passed before release: dc_rng_test (10 frames/8 starts, zero mismatches), determinism_test (180000 ticks, zero diverging runs), battle_test (25 boards, zero invariant failures), battle_full_test (26/26), cpu_test (10/10), userdata_test, padmap_test, vms_test (data-free cases; unavailable external packs skipped).
- `docs/goal.md` remains unchanged at 7903 characters. No coverage totals were increased from isolated checks.

## Next original-code work: Puzzle rocket sequence

The user explicitly asked to prioritize reported Puzzle issues while retaining the complete original scope. Missing disc-only SFX and shuttle launch remain reported defects. The cursor line is the reproduced atlas issue above.

Ghidra source is `analysis/decomp/dc_1st/1ST_READ.BIN.c`; several callbacks were not recognized as functions in that export, so their SH-4 instructions were checked directly with `tools/oracle/sh4dis.py`.

- Original Puzzle success `0x8c02bd28` compares saved mice against the target at 0x8c22d894+0xc, calls `0x8c01cbc0` and requests cues 21 and 28. `0x8c01cbc0` sets flag 0x8c1af1e4 to 1.
- Puzzle rocket manager `0x8c01c26e` consumes the flag, creates launch update/draw callbacks `0x8c01b8a0` / `0x8c01b940`, a base task `0x8c01b976` / `0x8c01b97a`, and lid update/draw `0x8c01b9a0` / `0x8c01bb2e`, then retires the parked-dome task. Creator literals are at 0x8c01c348..0x8c01c36c.
- Launch update increments height (+0x18) by 1 and yaw (+0x24) by 0x200 per task pass, wraps flame phase (+0xc) at 16, emits smoke when `TI_GetGlobalTime() & 7 == 0`, retires above height 200. Global clock is RAM 0x8c1ae8d8, read by 0x8c016cd2.
- Live launch state s00085/s00100/s00125/s00150: height 4/19/44/69; yaw 2048/9728/22528/35328; flame phase 4/3/12/5. Callback pointers at task +0x40/+0x44. First found launch task s00100 is 0x8c1d9b88.
- Lid phase 0 increases angle (+0x20) by 0x200 through 0x4000 and writes sin(angle) to opening (+0x30). Phase 1 holds 120 updates. It then chooses phase 2 or 3 using `(globalTime + cellX + 12*cellY) & 255`. Phase 2 decreases opening by 0.005 to zero. Phase 3 decreases to below 0.5, phase 4 oscillates `0.5 - (timer & 15)*0.006666666828095913` for >60 updates, phase 5 holds >60, phase 6 adds 0.01 until >=0.8 then returns to 2. Constants at 0x8c01ba18/1c and 0x8c01bbe0/e4/e8.
- Lid draw 0x8c01b628 uses TranslateZ(+/-opening), RotateY(+/-0x4000), RotateX(-int(opening*12743.111328125)). Compare actual matrix order through the stream before integrating: the exploratory projection did not match and was removed.
- IMPORTANT: rocket table 0x8c0b4a50 points at **bare models** 0x8c0aa328 / 0x8c0ab478 / 0x8c0ac5c8 / 0x8c0ad718. Existing `rocket_blue` exporter root 0x8c0aa340 adds node translation y=9.5. An exploratory use double-counted that offset. Export dedicated bare-model variants for the original launch drawer instead of changing shared models blindly. No experimental launch rendering remains in the preview source.
- Flame draw 0x8c01b7e4 uses object 0x8c0b0258 with motion 0x8c0b02a4 and morph motion 0x8c0b1e08. The latter has 16 frames, type 0x30, mdata at 0x8c0b1df8; nine vertex-key pairs at 0x8c0b1db0 reference frames 0,2,...16, first vertex array 0x8c0b02b0. Smoke creator 0x8c01cc62; its Ghidra output is present. Neither flame morph nor smoke has been integrated/verified.
- Sound: App::loadAudio still only populates SFX from iOS/Android `audio_sfx`. Existing driver/sequence research is in docs/audio.md and tools/dc_sound_*.py. Disc-only music and SFX are separate; do not claim sound parity.

## Workspace ownership

`game/tests/determinism_test.cpp` and `.vscode/` were already locally changed/untracked at session start. Leave them alone; they are not part of this preview. `build`, `dist`, `analysis` are junctions to D:. Use `local/` for new build/capture/package outputs. Never bundle the user's disc, extracted assets, BIOS, RAM dumps or save states into a release.

## Release verification

- Windows archive prepared as `local/preview-release/packages/ChuChuRocketReNyastered-v2026.11.21-preview.1-windows-x64.zip` with a static MSVC C/C++ runtime. Fresh build directory, pinned local SDL/stb dependencies; no compilation outputs through the D: junction. Archive SHA256: `5a4dbc29eb901e681e5eab03f0fa0ad5f9c9db4774862f8ff7bc232e6e9dd8c1`.
- Ran the archive's `tools/prepare.ps1` against only `local/dc_ref/disc` into `local/preview-release/fresh-disc`, using an installed Python/Pillow runtime. Completed with Puzzle, Battle and Stage Challenge playable; no mobile input or BIOS. The Python-download path, full setup.cmd/RecompLauncher UI and other image formats were not tested by this run.
- Final archive executable passed STARTUP, MENU, STAGES, DC_DEMO tick 1772, CHALLENGE_SELECT and Challenge 0 headless captures. Natural Puzzle 01 clear, Next to 02, and Stage Select with a saved check mark were captured and visually inspected in smoke-review.png. Fresh-disc Battle frame mean error 5.48125; the older-cache comparison was 5.50016. Screenshot verification is not an audio pass.
- Archive inspection found no .bin/.cue/.gdi/.chd/.wav/.ogg/.png/.state/.ram entries. It contains only the program, setup sources, launcher manifest, README, licenses and openly licensed fonts. Packaged executable SHA256 equals the final clean-build executable.
- Release notes: `docs/releases/v2026.11.21-preview.1.md`. Publication and final repository state are recorded below.


## Published preview and stopping point

Published [v2026.11.21-preview.1](https://github.com/TideGear/ChuChu-Rocket-Re-Nyastered/releases/tag/v2026.11.21-preview.1) as a prerelease. All four platform archives and SHA256SUMS.txt are uploaded. The release API reports draft=false and prerelease=true; GitHub asset digests match the final local archives. Their README was corrected to explain disc-only setup; native archive binaries were preserved from CI, and the Windows executable still matches the clean-build hash.

Source commit/tag: a20f0e85f5bbd6ce81a9535b50742e0d1fdbb323 / v2026.11.21-preview.1. Both the [main build](https://github.com/TideGear/ChuChu-Rocket-Re-Nyastered/actions/runs/44481758711) and [tag build](https://github.com/TideGear/ChuChu-Rocket-Re-Nyastered/actions/runs/44481804388) completed successfully. Tag jobs built/tested/packaged Linux x64, macOS arm64 and macOS x64; macOS architecture checks passed. Windows was built/tested locally with a static runtime (dumpbin shows Windows system DLLs only).

The final follow-up commit contains this publication record and the corrected README, not further gameplay changes. Existing user changes to game/tests/determinism_test.cpp and .vscode/ remain uncommitted. The requested release-and-handoff task is complete after that commit is pushed. Stop here; begin the rocket/audio/remaining-screen work only when the user resumes it in a new conversation.
