# Requirement audit against docs/goal.md (2026-11-16, interim)

Status words: **done** (implemented and checked, evidence named), **partial** (what exists and what is missing), **open** (nothing built). This is a working audit, not a completion claim.

## A. Presentation and UI
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
## F. Platforms, controls, play
- 60 Hz fixed simulation: **done**; interpolated rendering **done**; mouse aim, WASD/arrows: **done**; four-player hotseat: **done**.
- Controller remap, quit combo: **done** (logic tested, no hardware run).
- Wireless local play, online lockstep: **partial** (netplay core and 19,518-iteration loopback test; no screens, no phone pairing).
- 4K GPU measurement: **done for the current 2D scene** (4K 8.1 ms/frame, ~122 fps uncapped, 1080p 1.85 ms, RTX 3060, load-guarded CLEAN runs, `docs/verification.md`); **open** for the 3D models once drawn and for a presented display window.
- Linux/macOS releases: v2026.11.18 carries CI-built `linux-x64` and `macos-arm64` archives (green builds and unit tests on GitHub runners; `macos-13` x64 never got a runner); not run on a real machine; launcher archive selection unconfirmed.
- Linux/macOS: **partial; a real user report (2026-11-17) showed v2026.11.17 could not extract on Linux (Windows-only `--prepare`); fixed in a3287c6, not yet confirmed on a real Linux PC**.
- (older note) Linux/macOS: **partial** (main.cpp compiles for x86_64/aarch64 Linux and macOS with zig; `.github/workflows/build.yml`: Linux **built and unit-tested green on a GitHub runner** (no human run of the game on Linux); macOS job cancelled before starting (no runner provided), so macOS is unverified).
- Android arm64 emulator test, WebAssembly PWA headless test: **open** (build targets exist, no recorded run).
## G. Releases and docs
- Versioned GitHub releases with ZIPs and notes: **done** for Windows (v2026.11.16, v2026.11.17); Linux/macOS **open**.
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
