# Handoff — 2026-11-19

The user requested: after release, find a stopping place, wrap up for a new conversation, commit, push, and stop. This is that stopping point. Do not resume implementation in this conversation. No gameplay changes were made during this wrap-up.

## Start here in the next conversation

Read [goal.md](goal.md), [audit.md](audit.md), and the latest entries in [roadmap.md](roadmap.md). This file supersedes the stale opening guidance and priority list in [NEXT_SESSION.md](NEXT_SESSION.md) and the preview-1 status in [PREVIEW_HANDOFF.md](PREVIEW_HANDOFF.md); retain those files for historical evidence and capture recipes. Use [audio.md](audio.md), especially its final scoping entry, for audio work. Coverage belongs to the audit; a harness case passing does not close a whole feature.

Before this handoff commit, main was at `29a23ad` (Puzzle pause research), following `dfdc341` (preview-3 release notes) and `51065e6` (mouse conversion fix). User-owned `game/tests/determinism_test.cpp` and `.vscode/` are intentionally left untouched and unstaged. Do not commit them.

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

## Next concrete task: Puzzle pause

The controller path to the Puzzle pause menu is still missing. The latest research is committed in `29a23ad` and the last roadmap entry. Pause artwork names are resource descriptors, not logic: strings `pauseboard0/1`, `yameru`, `tudukeru`, `fukidasi10..12` at 0x8c07ec20..0x8c07ec70 point into four 12-byte descriptor groups at 0x8c0b547c, 0x8c0b5520, 0x8c0b5594 and 0x8c0b5650. Text search did not locate the pause task. FUN_8c02d09e is a two-argument confirm/transition helper, not yet tied to Puzzle play; FUN_8c01a174 draws a PAUSE text overlay.

Next: find writers of the Start-press RAM-watch candidates with `tools/oracle/dc_ram_trace.py` on a state at the press: 0x30ef54 (0->5), 0x30ef74 (0->1), 0x30e914 (0->4); pad edge 0x1aee98 / 0x2d09b0. Read the original code first, then confirm the path headlessly. Earlier trace saw the board continue about three ticks, with the whole overlay visible at +5 frames.

## Other retained work and corrections

- Battle START sprite: still undrawn. Prior claims that it lasted until a button press were withdrawn: the measured orange pixels were the pause menu's RESUME button. A clean 4P run without the pause press showed no START word in the sampled start interval. Reference `local/dc_ref/hud/live_03100.state` has ENGLISH__START at packet 0x19d3843, texture 140e4300, quad (325.98,199.9), 69.1x17.3, z 0.1. That capture's menu timing is unknown. Trace the original round-start task; do not invent a timer.
- Jump Pack: Options toggle is inert. Flycast rumble logging and Purupuru core instrumentation observed only stop commands (VIBSET 0x10), including with Jump Pack On, no vibration start. Find the pdVib state structure/API writers; no rumble event is verified. Patched core/pristine backups and logs are described in the roadmap (`local/star-trace/rm`).
- Options General and 4P/Team pages now exist, alongside Language/Records. Most General/4P values are session-only and not wired to game behavior; music test must actually play. Keyboard F-key page is analysed but unbuilt; it serves chat shortcuts, and the earlier question about a local-only picker versus deferral with online remains unresolved. See manual findings and roadmap; do not silently drop scope.
- Last recorded parity harness result: 121/122 full-frame cases <=3, launch age 0 about 3.78. Element crops and complete animation coverage still need their own checks. Retain Help strip-edge residue, tick-aligned dome/pause/failure cases and star twinkles. Look-alike fonts for disc-only installs were accepted by the user.
- Audio is not connected to gameplay. The old handoff's named component commits were reported missing from this clone; check actual source/history before relying on those commit IDs. Latest `docs/audio.md` scopes an offline disc-derived SFX renderer: boot MANATEE.DRV ARM7 with vectors/timer interrupts, reproduce the SH-4 mailbox/FIFO and SMLT load, route ARM reads/writes through SampledVoiceBank, sample at 44.1 kHz, compare cue WAVs against Flycast (start English 21/27/28). Existing single-routine harnesses do not boot the driver. Preserve the four discarded monitor-latch reads at 0x159c..0x15a8 and post-store Unicorn bus semantics. No renderer implementation has started; synthetic component checks are not whole-cue verification.

## Working commands and constraints

Use headless captures and `tools/quiet.ps1`; do not use the user's screen/audio or interfere with shared processes. Derive behavior and constants from the decompile/real stream before changing code. `FLY_WATCH` numbers run one ahead of screenshots. `tools/parity.py <assets>` uses the accelerated renderer and `tools/parity_manifest.json`; retain heatmaps and per-element results.

Build with `tools/build-windows.ps1` through cmd with output redirected when PowerShell native-stderr handling aborts on CMake warnings. Run test binaries from `game/` for their default `../local/testdata`; argument-driven tools require arguments. Previously reported no-argument `cpu_gba_test` crash remains uninvestigated. Pass assets first: `ccr <assets> <MODE>`. Flycast libretro B means Dreamcast A. The pinned core has no software renderer.

`build`, `dist` and `analysis` are junctions to D:; use `local/` for new outputs. Do not bundle local fixtures. This wrap-up changes documentation only, so no app rebuild or gameplay test was needed. Commit and push the handoff, verify the remote branch matches, and stop.
