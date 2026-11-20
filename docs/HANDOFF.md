# Handoff — Dreamcast-only fidelity continuation

The continuing goal is a Dreamcast-only ChuChu Rocket! build from a user-owned Dreamcast image, matching Flycast's models, interface, and animation. This is a checkpoint, not completion; the user asked to stop here and continue in a new conversation.

## Start here in the next conversation

Read [goal.md](goal.md), [audit.md](audit.md), and the latest entries in [roadmap.md](roadmap.md). Coverage belongs to the audit; a harness case passing does not close a whole feature. The published release notes and prior handoff sections below remain useful history, not the current stopping point.

Current branch is `main`, pushed to `origin/main` at `2e8918d` (`Fix Dreamcast Puzzle Cancel panel scaling`), following `e987eb1` (`Fix Puzzle prelaunch dome scale`). User-owned changes to `game/tests/determinism_test.cpp` and untracked `.vscode/` remain untouched and unstaged; do not commit them.

## Latest verified changes

- Puzzle prelaunch: `PuzzleMode::willClearNextFrame()` predicts the next simulation frame so the age -1 dome scale is applied before the clear; age 0 still hides the launch scene. Original Flycast frames 9/10 match their references pixel-for-pixel, and RAM shows launch flag `0x8c1af1e4` changing 0->1 with six body/lid task instances created at age 0. The full 90-age sweep remains partial: age -1 full-frame mean 8.9896 and dome-band mean 8.8372; age 0 full-frame mean 8.0300 and dome-band mean 0.7438; no full-frame age meets the <=3 goal. Details are in the latest rocket entry in [roadmap.md](roadmap.md).
- Puzzle Cancel panel: old exported art was alpha-cropped to 126x73 but stretched into the original 128x128 quad. It now renders at the loaded texture dimensions times the original 1.6 scale (201.6x116.8 for old art; current 128x128 art remains 204.8 square). The stale-art check now runs after Puzzle art is loaded. A headless capture with the old unstamped cache logged version 0/need 2; the current version-2 cache did not warn. Both 640x480 captures showed the Cancel art at the Flycast frame-2390 height. The overall HUD still does not meet parity thresholds.
- Validation: `tools/build-windows.ps1 --target ccr` passed; `build/game/puzzle_pause_test.exe` passed all checks. The Cancel panel was visually checked in `CCR_GPU=1 CCR_SIZE=640x480 CCR_MODELS=1 CCR_TICKS=200` captures using both old and current disc-only caches. The direct MSVC CMake build lacks its include environment; use the pinned Zig build script above.

## Published release

[Preview 3](https://github.com/TideGear/ChuChu-Rocket-Re-Nyastered/releases/tag/v2026.11.22-preview.3) is published, draft=false, prerelease=true. Tag/source: `v2026.11.22-preview.3`, `dfdc3416097751506cde9e37b54d57f6aa6c2666`. The tag [build](https://github.com/TideGear/ChuChu-Rocket-Re-Nyastered/actions/runs/44652273805) succeeded. This wrap-up rechecked the release API, all five uploaded assets and tag-build success.

The release contains Windows x64, Linux x64, macOS arm64 and macOS x64 archives plus SHA256SUMS.txt. GitHub's archive SHA256 digests match the interrupted session's recorded download hashes:

| Platform | SHA256 |
| --- | --- |
| Windows x64 | dc3246bfd677157d8d48c66ca0bd60723187b4f2ad0ecdbe0771f5a3bd411622 |
| Linux x64 | ce3be156e69873bc4aed8d32c9f54a532911079ee16e30877c1f1a37ce2da842 |
| macOS arm64 | b49553e2253cbfcbda04b26e57db4d7d518d596b6251a6cc2a7250a9cbef265d |
| macOS x64 | 80c6ce0cbbef4cfa57f6217841882e2c95ecc21a01c459e9c09ab202891821ef |

Release notes: [preview 3](releases/v2026.11.22-preview.3.md). It fixes double conversion of real mouse events on Dreamcast screens and warns about stale exported art (the invisible-rocket report). Users should rerun Easy Setup / `ccr --prepare` after updating. The user verified stage-25 clicks after the fix. SDL rewrites event coordinates to logical space; the main loop restores window coordinates before screen handlers convert once. Headless injected clicks bypass that SDL rewrite and previously concealed the bug.

Prior-session validation (not rerun during this documentation-only wrap-up): Windows clean package build and unit tests passed; packaged extraction from the disc alone completed with Puzzle, Battle and Stage Challenge playable, art version stamp present and no warning; rocket render checked; downloaded Windows archive byte-identical to local. Linux/macOS were built/tested by CI, not run manually. Local package/download evidence: `local/release-check/dist3`, `local/release-check/dl3`, `local/release-check/tagci3.log`. Never ship original game data, BIOS, states or captures.

## Next concrete task: close the rocket prelaunch discrepancy

Continue the code-first trace of the active mouse/rocket draw state at age -1, using [age_00009.ram](../local/rocket-age-packets/age_00009.ram), [age_00010.ram](../local/rocket-age-packets/age_00010.ram), the paired Flycast screenshots, and [ta_parse.py](../tools/oracle/ta_parse.py). The known TA packet offset `0x253e10` yields no polygons in these newer saved states; do not assume those dumps contain the render list. Identify the original active mouse task/frame and its draw ordering before changing model or scale. The diagnostic crop `[396,8,453,72]` remains 22.6865; per-element closure is open.

Puzzle pause input/controller logic is implemented. Its timing helper tests pass, but a port-vs-Flycast paused-frame pixel comparison is not retained yet; do not treat the whole pause screen as verified.

## Other retained work and corrections

- Battle START sprite: still undrawn. Prior claims that it lasted until a button press were withdrawn: the measured orange pixels were the pause menu's RESUME button. A clean 4P run without the pause press showed no START word in the sampled start interval. Reference `local/dc_ref/hud/live_03100.state` has ENGLISH__START at packet 0x19d3843, texture 140e4300, quad (325.98,199.9), 69.1x17.3, z 0.1. That capture's menu timing is unknown. Trace the original round-start task; do not invent a timer.
- Jump Pack: Options toggle is inert. Flycast rumble logging and Purupuru core instrumentation observed only stop commands (VIBSET 0x10), including with Jump Pack On, no vibration start. Find the pdVib state structure/API writers; no rumble event is verified. Patched core/pristine backups and logs are described in the roadmap (`local/star-trace/rm`).
- Options General and 4P/Team pages now exist, alongside Language/Records. Most General/4P values are session-only and not wired to game behavior; music test must actually play. Keyboard F-key page is analysed but unbuilt; it serves chat shortcuts, and the earlier question about a local-only picker versus deferral with online remains unresolved. See manual findings and roadmap; do not silently drop scope.
- Last recorded parity harness result: 121/122 full-frame cases <=3, launch age 0 about 3.78. Element crops and complete animation coverage still need their own checks. Retain Help strip-edge residue, tick-aligned dome/pause/failure cases and star twinkles. Look-alike fonts for disc-only installs were accepted by the user.
- The launch-age packet parser found 69 polygons in the older baseline state at `0x253e10`, but none in the newer age -1/0 states. The current RAM dumps confirm launch timing; the captured screenshots match the original references, but the active dome discrepancy is unresolved.
- Audio is not connected to gameplay. The old handoff's named component commits were reported missing from this clone; check actual source/history before relying on those commit IDs. Latest `docs/audio.md` scopes an offline disc-derived SFX renderer: boot MANATEE.DRV ARM7 with vectors/timer interrupts, reproduce the SH-4 mailbox/FIFO and SMLT load, route ARM reads/writes through SampledVoiceBank, sample at 44.1 kHz, compare cue WAVs against Flycast (start English 21/27/28). Existing single-routine harnesses do not boot the driver. Preserve the four discarded monitor-latch reads at 0x159c..0x15a8 and post-store Unicorn bus semantics. No renderer implementation has started; synthetic component checks are not whole-cue verification.

## Working commands and constraints

Use headless captures and `tools/quiet.ps1`; do not use the user's screen/audio or interfere with shared processes. Derive behavior and constants from the decompile/real stream before changing code. `FLY_WATCH` numbers run one ahead of screenshots. `tools/parity.py <assets>` uses the accelerated renderer and `tools/parity_manifest.json`; retain heatmaps and per-element results.

Build with `tools/build-windows.ps1` through cmd with output redirected when PowerShell native-stderr handling aborts on CMake warnings. Run test binaries from `game/` for their default `../local/testdata`; argument-driven tools require arguments. Previously reported no-argument `cpu_gba_test` crash remains uninvestigated. Pass assets first: `ccr <assets> <MODE>`. Flycast libretro B means Dreamcast A. The pinned core has no software renderer.

`build`, `dist` and `analysis` are junctions to D:; use `local/` for new outputs. Do not bundle local fixtures. For this handoff update, commit only `docs/HANDOFF.md`, push `main`, verify the remote branch matches, and stop.
