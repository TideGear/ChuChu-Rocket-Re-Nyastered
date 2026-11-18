# Requirement audit

Status words: **done** (implemented and checked, evidence named), **partial** (what exists and what is missing), **open** (nothing built). This is a working audit, not a completion claim.

## A. Presentation and UI
- Dreamcast gameplay presentation is **partial**. Live Puzzle, Battle, Team Battle and Challenge use the disc models, measured floor and wall projection, near-depth-tested parked domes, and per-vertex lighting. Verified captures include the standard Battle and Team HUDs, Puzzle Normal 01/02 and 08, Challenge A1, and pause screens in all four modes. The [rendering notes](dreamcast_models.md) give exact measurements and scope. Shared depth across separate field objects, event/result variations, other stage groups, and animation timing remain open.
- Dreamcast player cursor trails are **partial**. Battle frames 3124, 3130 and 3140 show the original 24-tick trail from `0x8c014100` and `0x8c01406a`, which the port uses. Moving-controller parity, hardware, CPU and alternate-mode trails, and the placement ghost need coverage.
- Challenge select clocks are **done** for all ten digits: BIOS ROM font glyphs match Flycast with 0 differing pixels for 00:00, 00:19, 23:45, 56:48, 07:27 and 77:27 (needs a user-supplied BIOS at setup; without one the exact zero and substitute art are used).
- Dreamcast-only Mode Select and Stage Challenge selection are **partial**. The Mode Select 4P Battle and Challenge selections are compared at 640×480, and the Challenge selector was compared on A1, B1 and B2. Dreamcast startup, Puzzle stage-select art, Battle player setup, and unavailable Mode Select routes still need work. Challenge clock glyphs and clear marks, final-stage gating, transition timing and sound need original-code verification.
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
- MANATEE.DRV SFX pitch and sequence timing: **partial** (original ARM pitch, context setup, event timing and pending-gate checks in audio.md; complete playback and gameplay integration remain open). GBA battle diff and score gap, iOS-specific differences: **open / partial** (see roadmap).
## D. Content and options
- Unlockables from code: puzzle groups open sequentially (all 25 cleared in group n-1; ported in stage select via `maxStage`) and costumes 1/2 by Mania/Challenge clears (decoded for Android, iOS, Dreamcast: `docs/unlockables.md`). **Unlock-all: done** for puzzle groups (setting `unlock_all`, Options > Settings row; costumes and Challenge need the Costumes screen). Cross-check against GameFAQs, GBA/Dreamcast-only unlocks, achievements and the costume screen: **open**.
- Stage sets: main 100, GBA extras, Dreamcast Express selectable (**done**); PuzzleP stock **open**.
- DLC skins, CHD/GDI input with per-input dump verification: **open**. .VMS/.VMI reader and writer for puzzle packs: **done**: core reader/writer (`core/vms.hpp`, `vms_test`, `tools/vms_pack.py`) and in-app import (packs in `<data>/imports/*.VMS` appear as the Imported Packs stage set, checked headlessly with DEPuzzle.VMS and a character pack present). Export from the app, DLC character skins and PuzzleP's arrow stock remain open.
## E. Sound, animation, assets
- Full inventory with version/address/asset ID/gates: **open** (pieces in roadmap and docs/*.md).
- Challenge intro cards use disc art, with A1 and B2 compared against Flycast. Failure Retry/Stage Select and C1 clear Next/Stage Select now use disc art and have headless checks. Alternate clear types, End, runtime clocks, countdown/in-play art and remaining text presentation still need coverage (HANDOFF.md).
- Dreamcast sound is **partial**. Trace the original call sites and MANATEE.DRV for cue, pitch, volume, channel, priority, looping, fade and cancellation. The headless Flycast host records WAV and frame sample offsets. Start cue comparisons with Challenge selection, countdown, goal, clear and fail.
- Dreamcast model inventory is **partial**. The [mesh inventory](dreamcast_meshes.md) and [captured poses](dreamcast_mesh_poses.md) track the observed families. Character clock rules, costumes, KapuKapu, the focus ring and unseen meshes remain open.
## F. Platforms, controls, play
- 60 Hz fixed simulation: **done**; interpolated rendering **done**; mouse aim, WASD/arrows: **done**; four-player hotseat: **done**.
- Press-to-join in local Battle: **implemented and checked headlessly**. Virtual SDL controllers claimed human slots in button order, skipped CPU slots, and reclaimed a slot after disconnect. Physical controllers remain untested.
- Controller remap, quit combo: **done** (logic tested, no hardware run). The Windows Release tests also verify that malformed hold-time settings preserve the last valid value and oversized integers clamp to 600 ticks.
- Wireless local play, online lockstep: **partial** (netplay core and 19,518-iteration loopback test; no screens, no phone pairing). The simulated network test detected a score divergence injected on peer 1 at tick 120 on all five boards. With the same four peers and 30% packet loss, the baseline finished without divergence.
- 4K GPU measurement: **done for the hidden-window Battle renderer** (2D 8.1 ms/frame; 3D 4.20 ms at simulated 60 Hz and 4.54 ms at simulated 240 Hz, load-guarded CLEAN runs, `docs/verification.md`). Display presentation and frame pacing remain **open**.
- Linux/macOS releases: v2026.11.20 has `linux-x64`, `macos-arm64` and `macos-x64` archives from the tag workflow. The Intel runner uses `macos-15-intel` and the workflow checks both macOS architectures before packaging. Local platform testing and launcher archive selection remain unverified.
- Linux/macOS: **partial; a real user report (2026-11-17) showed v2026.11.17 could not extract on Linux (Windows-only `--prepare`); fixed in a3287c6, not yet confirmed on a real Linux PC**.
- Android arm64 emulator test: **open**. Existing `battle_test`, `determinism_test` and `score_test` artifacts are AArch64 ELF64 executables with the Android dynamic linker. The SDK has no emulator image or configured virtual device. A fresh build of the settings and controller tests hit a permission error launching the NDK compiler.
- WebAssembly PWA headless browser test: **open**. The PWA manifest and service worker now use the emitted `ccr.html` entry point. A Node worker test checked the cache entries against the local WebAssembly build and served the launch page, JavaScript, and WebAssembly with network fetch disabled. Browser installation and offline startup with user-provided assets remain unverified.
## G. Releases and docs
- Versioned GitHub releases with notes: **done** for Windows x64, Linux x64, macOS arm64 and macOS x64 (downloads verified on v2026.11.20).
- Portable mode, commented settings, rotating logs: **done** (userdata_test; headless app check).
- Version matrix, asset provenance, README, unofficial-project statement: **partial** (README and distribution notes exist; matrix not regenerated for this audit).

## Dreamcast mode inventory (read from the game's mode table, 2026-11-18)
The table at `0x8c0b373c` (pointer at `0x8c0190e8`) lists 23 modes; each entry points to a descriptor whose first word is the mode's init function. Entries 23-39 and up are data, not modes. Status words as above; every row stays open until its screens are matched against Flycast frames.
| Mode | Init function | What it is | Status |
|---|---|---|---|
| 0 | 0x8c0235ea | SEGA logo | **partial**: layout and fades match Flycast (mean error 0.97); music request not played |
| 1 | 0x8c023776 | Sonic Team logo | **partial**: 0.66 mean error; fades timed from one-frame captures |
| 2 | 0x8c0264d2 | Title (idle timeout 588/600 ticks) | **partial**: background, logo, prompt blink and flying rocket done (1.6-2.5 mean error); drop-shadow pieces, music, attract demo (KEY_STAGE000.BIN, srand 0xdead0cab) open |
| 3 | 0x8c0265da | unidentified | open |
| 4 | 0x8c022432 | unidentified | open |
| 5 | 0x8c022f24 | unidentified | open |
| 6 | 0x8c02cd80 | unidentified | open |
| 7 | 0x8c024290 | unidentified | open |
| 8 | 0x8c02dc50 | unidentified | open |
| 9 | 0x8c034fa0 | unidentified | open |
| 10 | 0x8c04ffc0 | unidentified | open |
| 11 | 0x8c051b9a | unidentified | open |
| 12, 13 | 0x8c0278cc | shared init (field with `yuka01` floor; Puzzle/Battle play) | partial: Puzzle, Battle, Team Battle and Challenge A1 captures compared |
| 14 | 0x8c02a33e | unidentified | open |
| 15 | 0x8c02b97e | unidentified | open |
| 16 | 0x8c058292 | tutorial per the style variable (`FUN_8c016bd4`) | open |
| 17 | 0x8c0507e0 | unidentified | open |
| 18-22 | 0x8c05cfba, 0x8c05d39a, 0x8c05d55a, 0x8c05dc80, 0x8c05df12 | unidentified | open |
Screens already compared outside this table (Mode Select, Challenge select/intro/failure/result, Puzzle HUD) belong to the modes above that are not yet named. Next: identify each mode by the PRS archives and textures its init loads, then give every screen of every mode its own row.

## Next work

- Finish the Dreamcast presentation gaps above, beginning with exact Challenge clocks, alternate clear states and sound. Keep capture and Ghidra details in the [handoff](HANDOFF.md).
- Resolve the remaining Challenge seed 3000 divergence, finish Puzzle Edit and in-app export, and verify unlocks, DLC skins and Dreamcast input formats.
- Test native Linux/macOS, Android and PWA operation beyond builds and harnesses.

## Claims from "ChuChu Rocket Version Comparison (AI Deep Research)" and where they stand
The goal text covers them only through its general version-comparison duties; this list keeps each one visible. See also `docs/research_check.md` (2026-11-13).
| Claim | Status |
|---|---|
| Eight roulette events on Dreamcast, same on mobile | **verified** (selector, weights and handlers; Dreamcast selector exact; mobile 26/26 whole-battle) |
| GBA adds five roulette events (13 total): Mouse Mania (Special), KapuKapu Kittens, Stealing Mania, Blindfold the Winner, Night Time | **open**: the ROM's dispatcher has 12 handlers (not 13); which index is which event is not mapped; "Night Time!" was seen in the title demo |
| GBA KapuKapu grow after 50 mice eaten | **open** |
| GBA multiplayer handicap system | **open** |
| Mobile builds do or do not carry the GBA events | **open** (mobile selector has eight outcomes and identical weight tables, so no extra events found there) |
| Dreamcast Puzzle Edit with VMU save and online sharing | **partial** (storage decoded from Android and the Dreamcast writer matches the original packs; editor UI and in-app export are open) |
| GBA Puzzle Edit with link-cable trading; Character Edit (four custom sprite groups) | **open** (goal.md covers it only through its "also cover what the claims imply" line) |
| Chao swap after all 25 Stage Challenge stages; Pian swap after all 25 Mania puzzles | **open** (unlockables phase) |
| NiGHTS hat via a DS plus Project Rub | **open**, hardware-dependent, likely not testable |
| Dreamcast online via modem, UDP 9789, revived by private servers | **external source only**; port's netplay modelled on SERVER_/CLIENT_ code, no Dreamcast server tested |
| iOS lacked level editing; Android had only costumes | **partial** (editor code exists in Android 1.15 `Editor`/`EditorGameScreen`; screen presence per build not checked) |
| Prices, reviews, release dates, store listings | **not testable** from game files |

## Public-repo check (2026-11-17)
The repo is public. Scan of all 459 commits: no game binaries, extracted assets, saves or dump files were ever committed (no `.bin/.dat/.ogg/.wav/.vms/.vmi/.gba/.apk/.ipa/.so/.tex/.pvr/.prs`; largest blobs are `main.cpp` and `roadmap.md`). The only game-derived files are three gameplay screenshots in `docs/screenshots/` (README states the artwork belongs to the rights holders). `docs/stage_registry.json` is not tracked. Re-run this scan before each release.
