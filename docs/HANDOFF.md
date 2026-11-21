# Handoff — Dreamcast-only fidelity continuation

The continuing goal is a Dreamcast-only ChuChu Rocket! build from a user-owned Dreamcast image, matching Flycast's models, interface, and animation. This is a checkpoint, not completion; the user asked to stop here and continue in a new conversation.

## Start here in the next conversation

Read [goal.md](goal.md), [audit.md](audit.md), and the latest entries in [roadmap.md](roadmap.md). Coverage belongs to the audit; a harness case passing does not close a whole feature. The published release notes and prior handoff sections below remain useful history, not the current stopping point.

Current branch is `main`, pushed to `origin/main` (release commit `1a2c148`, tag `v2026.11.23`; check `git log` for anything newer). User-owned changes to `game/tests/determinism_test.cpp` (line-ending noise only) and untracked `.vscode/` remain untouched and unstaged; do not commit them. Start with the **Audio (2026-11-20)** bullet under "Other retained work" for the sound next steps.

## Latest verified changes

- Puzzle prelaunch: `PuzzleMode::willClearNextFrame()` predicts the next simulation frame so the age -1 dome scale is applied before the clear; age 0 still hides the launch scene. Original Flycast frames 9/10 match their references pixel-for-pixel, and RAM shows launch flag `0x8c1af1e4` changing 0->1 with six body/lid task instances created at age 0. The full 90-age sweep remains partial: age -1 full-frame mean 8.9896 and dome-band mean 8.8372; age 0 full-frame mean 8.0300 and dome-band mean 0.7438; no full-frame age meets the <=3 goal. Details are in the latest rocket entry in [roadmap.md](roadmap.md).
- Puzzle Cancel panel: old exported art was alpha-cropped to 126x73 but stretched into the original 128x128 quad. It now renders at the loaded texture dimensions times the original 1.6 scale (201.6x116.8 for old art; current 128x128 art remains 204.8 square). The stale-art check now runs after Puzzle art is loaded. A headless capture with the old unstamped cache logged version 0/need 2; the current version-2 cache did not warn. Both 640x480 captures showed the Cancel art at the Flycast frame-2390 height. The overall HUD still does not meet parity thresholds.
- Validation: `tools/build-windows.ps1 --target ccr` passed; `build/game/puzzle_pause_test.exe` passed all checks. The Cancel panel was visually checked in `CCR_GPU=1 CCR_SIZE=640x480 CCR_MODELS=1 CCR_TICKS=200` captures using both old and current disc-only caches. The direct MSVC CMake build lacks its include environment; use the pinned Zig build script above.

## Published release

[v2026.11.23](https://github.com/TideGear/ChuChu-Rocket-Re-Nyastered/releases/tag/v2026.11.23) is the **first full (non-preview) release** since v2026.11.20 (user decision, 2026-11-20: no more previews; the label says "full" even though much is unbuilt, the notes list the gaps). Tag `v2026.11.23` at `1a2c148`; tag build [44847369563](https://github.com/TideGear/ChuChu-Rocket-Re-Nyastered/actions/runs/44847369563) succeeded on all three runners; draft=false, prerelease=false, Latest. Assets: Windows x64 zip (built locally with `tools/package-release.ps1 -Version v2026.11.23 -SkipBuild`, uploaded with `gh release create`), Linux x64, macOS arm64, macOS x64 (attached by CI) and `SHA256SUMS.txt` (made from the published assets with `sha256sum`):

| Platform | SHA256 |
| --- | --- |
| Windows x64 | d39ac99a15f3b3f5ff4ac35279da09893dbc032f3dbb1631129f47fb20157d30 |
| Linux x64 | 9cbd7ec6bc50b8ac632ac0ee131f10527d1cda7050af8889abab98355f87e22a |
| macOS arm64 | 668575e644db0f7fe696b66d880dab6b472513c925cb08d651111bd62ad7a6df |
| macOS x64 | 63f016c87f8a96ddcb6721315a0b0e705c6cc5b3a29b79c3c2e35907fbbde0f6 |

Release gates run this time: clean setup from the disc image alone with the **packaged** tools (2.9 minutes, 128 cue WAVs), `kDcAssetsVersion` bumped to 3 (existing installs are told to rerun setup), unit tests (puzzle_pause, determinism, battle, challenge_sim, cpu, dc_rng) pass, all four archives contain the 13 sound tools. Lesson: `tools/package-release.ps1` and `.github/workflows/build.yml` hold explicit tool lists; any new import used by `extract_all.py` must be added to both or packaged setups silently skip it. Release notes: [v2026.11.23](releases/v2026.11.23.md). Earlier: previews 1-3 (`v2026.11.21-preview.1` ... `v2026.11.22-preview.3`) and `v2026.11.20`.

## Next concrete task: close the rocket prelaunch discrepancy

Continue the code-first trace of the active mouse/rocket draw state at age -1, using [age_00009.ram](../local/rocket-age-packets/age_00009.ram), [age_00010.ram](../local/rocket-age-packets/age_00010.ram), the paired Flycast screenshots, and [ta_parse.py](../tools/oracle/ta_parse.py). The known TA packet offset `0x253e10` yields no polygons in these newer saved states; do not assume those dumps contain the render list. Identify the original active mouse task/frame and its draw ordering before changing model or scale. The diagnostic crop `[396,8,453,72]` remains 22.6865; per-element closure is open.

Puzzle pause input/controller logic is implemented. Its timing helper tests pass, but a port-vs-Flycast paused-frame pixel comparison is not retained yet; do not treat the whole pause screen as verified.

## Other retained work and corrections

- Battle START sprite: still undrawn. Prior claims that it lasted until a button press were withdrawn: the measured orange pixels were the pause menu's RESUME button. A clean 4P run without the pause press showed no START word in the sampled start interval. Reference `local/dc_ref/hud/live_03100.state` has ENGLISH__START at packet 0x19d3843, texture 140e4300, quad (325.98,199.9), 69.1x17.3, z 0.1. That capture's menu timing is unknown. Trace the original round-start task; do not invent a timer.
- Jump Pack: Options toggle is inert. Flycast rumble logging and Purupuru core instrumentation observed only stop commands (VIBSET 0x10), including with Jump Pack On, no vibration start. Find the pdVib state structure/API writers; no rumble event is verified. Patched core/pristine backups and logs are described in the roadmap (`local/star-trace/rm`).
- Options General and 4P/Team pages now exist, alongside Language/Records. Most General/4P values are session-only and not wired to game behavior; music test must actually play. Keyboard F-key page is analysed but unbuilt; it serves chat shortcuts, and the earlier question about a local-only picker versus deferral with online remains unresolved. See manual findings and roadmap; do not silently drop scope.
- Last recorded parity harness result: 121/122 full-frame cases <=3, launch age 0 about 3.78. Element crops and complete animation coverage still need their own checks. Retain Help strip-edge residue, tick-aligned dome/pause/failure cases and star twinkles. Look-alike fonts for disc-only installs were accepted by the user.
- The launch-age packet parser found 69 polygons in the older baseline state at `0x253e10`, but none in the newer age -1/0 states. The current RAM dumps confirm launch timing; the captured screenshots match the original references, but the active dome discrepancy is unresolved.
- Audio (2026-11-20): Dreamcast SFX are in the port. `tools/dc_sfx_render.py` (setup runs it) renders all 128 CHU2_SE cues from MANATEE.DRV + CHU2_SE.MLT with the pure-Python `tools/arm7_interp.py`; `App::loadAudio` plays `dreamcast/sfx/cueNNN.wav` first (ids 0..116), cue 7 is throttled as in `FUN_8c01203a`. Verified vs Flycast: voice renderer bit-exact for 128/128 cues, dispatch identical for 120/128 (docs/audio.md "All-cue comparison"). Music: Dreamcast tracks loop [2.0 s, end] and songs 7, 12, 13, 14 play once (verified for track 6); song 14 = track 18; Music test plays. Next: (1) explain the note differences in cues 5, 8, 13, 21, 22, 23, 26, 28; (2) model ARM latency and the five-slot cut (sixth overlapping cue cuts the oldest, measured); (3) voices (VOICE.AFS), music fades and per-mode start/stop, other tracks' loops (record each in Flycast like track 6), FLAC for CD tracks (user asked; decoder dr_flac, encoder needs a bundled flac or Python). Captures: `python tools/oracle/dc_se_capture.py <pre02415.state> local/se-cap` (state = Options > General Settings, SE test row, built from frames 1350/1510 START, 7 DOWN, START, START, 4 DOWN; about 11 s per cue) then `dc_se_verify.py`. Headless port check: `CCR_HEADLESS=1 CCR_AUDIO_TEST=1 CCR_PLAY_SFX=<ids> CCR_AUDIO_CAPTURE=<raw> ccr <assets> MENU`.

## Working commands and constraints

Use headless captures and `tools/quiet.ps1`; do not use the user's screen/audio or interfere with shared processes. Derive behavior and constants from the decompile/real stream before changing code. `FLY_WATCH` numbers run one ahead of screenshots. `tools/parity.py <assets>` uses the accelerated renderer and `tools/parity_manifest.json`; retain heatmaps and per-element results.

Build with `tools/build-windows.ps1` through cmd with output redirected when PowerShell native-stderr handling aborts on CMake warnings. Run test binaries from `game/` for their default `../local/testdata`; argument-driven tools require arguments. Previously reported no-argument `cpu_gba_test` crash remains uninvestigated. Pass assets first: `ccr <assets> <MODE>`. Flycast libretro B means Dreamcast A. The pinned core has no software renderer.

`build`, `dist` and `analysis` are junctions to D:; use `local/` for new outputs. Do not bundle local fixtures. For this handoff update, commit only `docs/HANDOFF.md`, push `main`, verify the remote branch matches, and stop.
