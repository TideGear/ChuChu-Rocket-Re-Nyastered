# Requirement audit against docs/goal.md (2026-11-16, interim)

Status words: **done** (implemented and checked, evidence named), **partial** (what exists and what is missing), **open** (nothing built). This is a working audit, not a completion claim.

## A. Presentation and UI
- Dreamcast Battle HUD: **partial**. Four-player Battle uses the disc panels, score digits, clock, rocket column, CPU name plates, human intro tags and score crowns. Flycast replay and headless port captures cover the countdown, nonzero scores, tag bob and fall, and score crown blink. Tag placement follows the port's cursor projection. The in-field leader crown, match win marks, board alignment, background, and Team, roulette and result variants remain open.
- Dreamcast player cursor trails: **partial**. Flycast Battle frames 3124, 3130 and 3140 contain the trail tasks from `0x8c014100` and the textured quads from `0x8c01406a`. The port uses the disc textures and the original 24-tick fade in Battle and Puzzle. Four-player Battle controller cursors start at their rocket cells and use the observed quad anchor and trail plane. Full moving-controller parity, CPU cursors, original Puzzle and Team captures, other inputs, and the separate placement ghost remain open.
- Dreamcast four-player Battle board projection: **partial**. The port uses the floor bounds from Flycast's PowerVR stream and projects walls onto the original nearer plane. Cell-aligned rendering and pointer hit testing share the board's measured dimensions. Other modes, height-dependent character and object projection, lighting and occlusion remain open.
- Startup, main menu, Options (Sounds, Language, Credits, How to Play), Help: **partial** (iPad HD 1.0 layouts reproduced and diffed against the original for several screens; The Basics, Costumes, roulette wheel art, celebration rockets, phone/larger-device HUD layouts, tutorial highlights, split-screen are open; see roadmap "Phase A leftovers").
- Settings page and controller remap: **done** (screenshot read; pad remap untested on hardware).
- Pad prompts in the HUD: **open** (`padButtonLabel` exists).
## B. Rules and modes
- 26 whole-battle cases per forced roulette outcome: **done in the harness** (26/26 for outcomes 0-7, natural, Team); **done** against the real loop too: the original freezes the action while the wheel spins (task mask 0x1f / 0x13); recordings through the mask (`MASK=1`) are 26/26 for all eight outcomes.
- Rank thresholds: **partial** (covered by the 26 cases; no separate check).
- Team Battle: **done** through the real loop (26/26 for all eight forced outcomes; Everybody Move at game times 1, 3, 4 and 7 also 26/26 through the mask); end-of-round result and score screens: **open**.
- Stage Challenge: types 0-4 (24 stages) **done** (stage types 3/4: 8 of 8 runs identical); stage 24 **partial** (seeds 1000 and 2000 identical on every score word and computer-player arrow; seed 3000 identical to f2779, then a second heat source leaves the computer players' heat map at f2779 in the original but at f2785 in the port).
- Puzzle Edit: conversion and CRC **done**; Dreamcast .VMS/.VMI **writer done and checked against the real packs** (`tools/vms_pack.py`, 50/50 slots and both .VMI identical; acceptance by an emulator untested); screen, save format, validity rules, in-app export **open**.
## C. Version differences
- Dreamcast input, heat maps, SH-4 whole-battle CPU: **open** (CPU placement 10/10 cases from a recorded set only).
- MANATEE.DRV SFX rates, GBA battle diff and score gap, iOS-specific differences: **open / partial** (see roadmap).
## D. Content and options
- Unlockables from code: puzzle groups open sequentially (all 25 cleared in group n-1; ported in stage select via `maxStage`) and costumes 1/2 by Mania/Challenge clears (decoded for Android, iOS, Dreamcast: `docs/unlockables.md`). **Unlock-all: done** for puzzle groups (setting `unlock_all`, Options > Settings row; costumes and Challenge need the Costumes screen). Cross-check against GameFAQs, GBA/Dreamcast-only unlocks, achievements and the costume screen: **open**.
- Stage sets: main 100, GBA extras, Dreamcast Express selectable (**done**); PuzzleP stock **open**.
- DLC skins, CHD/GDI input with per-input dump verification: **open**. .VMS/.VMI reader and writer for puzzle packs: **done**: core reader/writer (`core/vms.hpp`, `vms_test`, `tools/vms_pack.py`) and in-app import (packs in `<data>/imports/*.VMS` appear as the Imported Packs stage set, checked headlessly with DEPuzzle.VMS and a character pack present). Export from the app, DLC character skins and PuzzleP's arrow stock remain open.
## E. Sound, animation, assets
- Full inventory with version/address/asset ID/gates: **open** (pieces in roadmap and docs/*.md).
- Dreamcast 3D models in live play (user priority 2026-11-17): **partial**; lighting: models carry vertex normals and are lit per vertex (light fitted to the mobile art, error 0.080; the game's own light vector not read); board: floor and walls drawn from the disc's models/textures (holes, markers, arrows still mobile art);: cat (24-frame head morph exported), basic mouse (8 keyframes by the clock rule), four rocket colours, rocket lids, exhaust and a wall piece are exported and drawn (`ccr <assets> models`; cats and mice in Puzzle/Battle behind the `models_3d` setting). Open: camera/scale/lighting from the original, the cat's frame rule, per-state animations, rockets/walls/floor in the field, effects, golden mice, and a Dreamcast-only 2D path (field, HUD, menus).
## F. Platforms, controls, play
- 60 Hz fixed simulation: **done**; interpolated rendering **done**; mouse aim, WASD/arrows: **done**; four-player hotseat: **done**.
- Press-to-join in local Battle: **implemented and checked headlessly**. Virtual SDL controllers claimed human slots in button order, skipped CPU slots, and reclaimed a slot after disconnect. Physical controllers remain untested.
- Controller remap, quit combo: **done** (logic tested, no hardware run). The Windows Release tests also verify that malformed hold-time settings preserve the last valid value and oversized integers clamp to 600 ticks.
- Wireless local play, online lockstep: **partial** (netplay core and 19,518-iteration loopback test; no screens, no phone pairing). The simulated network test detected a score divergence injected on peer 1 at tick 120 on all five boards. With the same four peers and 30% packet loss, the baseline finished without divergence.
- 4K GPU measurement: **done for the hidden-window Battle renderer** (2D 8.1 ms/frame; 3D 4.20 ms at simulated 60 Hz and 4.54 ms at simulated 240 Hz, load-guarded CLEAN runs, `docs/verification.md`). Display presentation and frame pacing remain **open**.
- Linux/macOS releases: v2026.11.20 has `linux-x64`, `macos-arm64` and `macos-x64` archives from the tag workflow. The Intel runner uses `macos-15-intel` and the workflow checks both macOS architectures before packaging. Local platform testing and launcher archive selection remain unverified.
- Linux/macOS: **partial; a real user report (2026-11-17) showed v2026.11.17 could not extract on Linux (Windows-only `--prepare`); fixed in a3287c6, not yet confirmed on a real Linux PC**.
- (older note) Linux/macOS: **partial** (main.cpp compiles for x86_64/aarch64 Linux and macOS with zig; `.github/workflows/build.yml`: Linux **built and unit-tested green on a GitHub runner** (no human run of the game on Linux); macOS job cancelled before starting (no runner provided), so macOS is unverified).
- Android arm64 emulator test: **open**. Existing `battle_test`, `determinism_test` and `score_test` artifacts are AArch64 ELF64 executables with the Android dynamic linker. The SDK has no emulator image or configured virtual device. A fresh build of the settings and controller tests hit a permission error launching the NDK compiler.
- WebAssembly PWA headless browser test: **open**. The PWA manifest and service worker now use the emitted `ccr.html` entry point. A Node worker test checked the cache entries against the local WebAssembly build and served the launch page, JavaScript, and WebAssembly with network fetch disabled. Browser installation and offline startup with user-provided assets remain unverified.
## G. Releases and docs
- Versioned GitHub releases with notes: **done** for Windows x64, Linux x64, macOS arm64 and macOS x64 (downloads verified on v2026.11.20).
- Portable mode, commented settings, rotating logs: **done** (userdata_test; headless app check).
- Version matrix, asset provenance, README, unofficial-project statement: **partial** (README and distribution notes exist; matrix not regenerated for this audit).

## Next, in order
1. Re-record whole-battle goldens through the real task-mask loop; port the mask into the battle sim by default.
2. Finish stage 24 seed 3000; Challenge HUD/result art; Team Battle result screen.
3. Puzzle Edit screen and VMS/VMI export; unlock-all and gating; VMS import and skins; CHD/GDI.
4. Linux/macOS CI builds, 4K measurement, Android and PWA test runs.

## Claims from "ChuChu Rocket Version Comparison (AI Deep Research)" and where they stand
The goal text covers them only through its general version-comparison duties; this list keeps each one visible. See also `docs/research_check.md` (2026-11-13).
| Claim | Status |
|---|---|
| Eight roulette events on Dreamcast, same on mobile | **verified** (selector, weights and handlers; Dreamcast selector exact; mobile 26/26 whole-battle) |
| GBA adds five roulette events (13 total): Mouse Mania (Special), KapuKapu Kittens, Stealing Mania, Blindfold the Winner, Night Time | **open**: the ROM's dispatcher has 12 handlers (not 13); which index is which event is not mapped; "Night Time!" was seen in the title demo |
| GBA KapuKapu grow after 50 mice eaten | **open** |
| GBA multiplayer handicap system | **open** |
| Mobile builds do or do not carry the GBA events | **open** (mobile selector has eight outcomes and identical weight tables, so no extra events found there) |
| Dreamcast Puzzle Edit with VMU save and online sharing | **partial** (storage and sharing format decoded from Android; no screen, no VMS export) |
| GBA Puzzle Edit with link-cable trading; Character Edit (four custom sprite groups) | **open** (goal.md covers it only through its "also cover what the claims imply" line) |
| Chao swap after all 25 Stage Challenge stages; Pian swap after all 25 Mania puzzles | **open** (unlockables phase) |
| NiGHTS hat via a DS plus Project Rub | **open**, hardware-dependent, likely not testable |
| Dreamcast online via modem, UDP 9789, revived by private servers | **external source only**; port's netplay modelled on SERVER_/CLIENT_ code, no Dreamcast server tested |
| iOS lacked level editing; Android had only costumes | **partial** (editor code exists in Android 1.15 `Editor`/`EditorGameScreen`; screen presence per build not checked) |
| Prices, reviews, release dates, store listings | **not testable** from game files |

## Public-repo check (2026-11-17)
The repo is public. Scan of all 459 commits: no game binaries, extracted assets, saves or dump files were ever committed (no `.bin/.dat/.ogg/.wav/.vms/.vmi/.gba/.apk/.ipa/.so/.tex/.pvr/.prs`; largest blobs are `main.cpp` and `roadmap.md`). The only game-derived files are three gameplay screenshots in `docs/screenshots/` (README states the artwork belongs to the rights holders). `docs/stage_registry.json` is not tracked. Re-run this scan before each release.
