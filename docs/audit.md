# Requirement audit against docs/goal.md (2026-11-16, interim)

Status words: **done** (implemented and checked, evidence named), **partial** (what exists and what is missing), **open** (nothing built). This is a working audit, not a completion claim.

## A. Presentation and UI
- Startup, main menu, Options (Sounds, Language, Credits, How to Play), Help: **partial** (iPad HD 1.0 layouts reproduced and diffed against the original for several screens; The Basics, Costumes, roulette wheel art, celebration rockets, phone/larger-device HUD layouts, tutorial highlights, split-screen are open; see roadmap "Phase A leftovers").
- Port Settings page and controller remap: **done** (screenshot read; pad remap untested on hardware).
- Pad prompts in the HUD: **open** (`padButtonLabel` exists).
## B. Rules and modes
- 26 whole-battle cases per forced roulette outcome: **done in the harness** (26/26 for outcomes 0-7, natural, Team); **open** against the real loop: the original freezes the action while the wheel spins (task mask 0x1f / 0x13), the harness never did; the port applies it only in Challenge stage 24 and the battle screen, not in the recorded goldens.
- Rank thresholds: **partial** (covered by the 26 cases; no separate check).
- Team Battle: **done** in the harness; end-of-round result and score screens: **open**.
- Stage Challenge: types 0-4 (24 stages) **done** (stage types 3/4: 8 of 8 runs identical); stage 24 **partial** (seed 1000 identical; seed 2000 identical to f1540; seed 3000 identical to f1286, computer players then place one arrow a frame early).
- Puzzle Edit: conversion and CRC **done**; screen, save format, validity rules, VMS/VMI export **open**.
## C. Version differences
- Dreamcast input, heat maps, SH-4 whole-battle CPU: **open** (CPU placement 10/10 cases from a recorded set only).
- MANATEE.DRV SFX rates, GBA battle diff and score gap, iOS-specific differences: **open / partial** (see roadmap).
## D. Content and options
- Unlockables/secrets from code and saves, unlock-all: **open** (menus are not gated except the tutorial).
- Stage sets: main 100, GBA extras, Dreamcast Express selectable (**done**); PuzzleP stock **open**.
- DLC skins, .VMS/.VMI import, CHD/GDI input with per-input dump verification: **open** (VMS reader exists as tools/vms_skin.py).
## E. Sound, animation, assets
- Full inventory with version/address/asset ID/gates: **open** (pieces in roadmap and docs/*.md).
## F. Platforms, controls, play
- 60 Hz fixed simulation: **done**; interpolated rendering **done**; mouse aim, WASD/arrows: **done**; four-player hotseat: **done**.
- Controller remap, quit combo: **done** (logic tested, no hardware run).
- Wireless local play, online lockstep: **partial** (netplay core and 19,518-iteration loopback test; no screens, no phone pairing).
- 4K GPU measurement: **open** (CCR_BENCH exists; no recorded 4K/60 result in docs).
- Linux/macOS: **partial** (main.cpp compiles for x86_64/aarch64 Linux and macOS with zig; no link, no run, no CI).
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
