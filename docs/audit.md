# Requirement audit

Status words: **done** (implemented and checked, evidence named), **partial** (what exists and what is missing), **open** (nothing built). This is a working audit, not a completion claim.

## A. Presentation and UI
- Dreamcast gameplay presentation is **partial**. Live Puzzle, Battle, Team Battle and Challenge use the disc models, measured floor and wall projection, near-depth-tested parked domes, and per-vertex lighting. Verified captures include the standard Battle and Team HUDs, Puzzle Normal 01/02 and 08, Challenge A1, and pause screens in all four modes. The [rendering notes](dreamcast_models.md) give exact measurements and scope. Shared depth across separate field objects, event/result variations, other stage groups, and animation timing remain open.
- Dreamcast player cursor trails are **partial**. Battle frames 3124, 3130 and 3140 show the original 24-tick trail from `0x8c014100` and `0x8c01406a`, which the port uses. Moving-controller parity, hardware, CPU and alternate-mode trails, and the placement ghost need coverage.
- Dreamcast 4P Battle setup is **partial**: `DcBattleSetupMode` (Select Players, Stage Select, point match) draws from disc textures laid out from Flycast frames 1900 and 2300 (every packet matched to a disc texture with 0 differing values; depth order z-sorted). Disc-only captures: Select Players full-frame mean error 0.55, Stage Select 2.35 (board preview region 9.6: the floor is one repeating quad in Flycast, per-cell here; domes differ). Open: the CPU-type pop-up list (Enter cycles types now), cursor art and travel, Team Battle: both screens use the same layout with the `stageselecttitle4/5` header (Flycast frame 2000 checked); sounds, stage '?' preview, other languages.
- Challenge select clear marks: **partial**: position, orientation and depth order match Flycast (the quads are depth-sorted: capsules and marks at 1/w 0.4 under the labels at 0.667); mark-region mean error 1.2 (limit 1), one stage checked (C1); End capsule and other stages unchecked.
- Without a BIOS the Puzzle hint uses DotGothic16 and the Challenge clock digits use Open Sans (both SIL OFL, bundled unmodified in `tools/fonts/`, see provenance.md), rasterised 1-bit at setup. Same style and position as the original, not the same glyph shapes; exact only with a user-supplied BIOS.
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
- Dreamcast attract demo: **partial** (2026-11-18). Runs from disc-only Title after 600 idle ticks, replays user KEY_STAGE000.BIN, and returns to SEGA on natural completion / Title on a press with fade. Full 1678-frame original recording matches RNG, scores, entity X/Z/type/movement heading (including pending retirement), arrow owner/cell/direction/TTL/hits, and 120 native roulette transforms. Actual app scores/RNG match all 1678 frames; 6716 observed pad samples match, including original shared-previous-pad edge bug. Native drum region mean RGB error 0.998 at frame 2300; full-frame error 3.89 there and 7.57 at frame 2000: visual animation parity remains open (upper crowns, pose clocks, effects/rasterization, complete transition sequences). Default Dreamcast occupied-arrow refusal now matches manual/attract RAM. General Dreamcast active-clock semantics still open (demo first roll uses measured gtOff=-1). Sources and captures in HANDOFF. Broader CPU battle reuse remains open (15/25 exploratory cases diverged).
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

- Disc-only run (2026-11-18, USA CUE/BIN only, no mobile files, no BIOS): `tools/extract_all.py --game-files local/dc_ref/disc --cache <empty dir>` completed in 87 s (128 models, 50 battle stages, 54 `dc_*` UI sheets, `dreamcast_puzzles.bin`); `ccr` then ran STARTUP, MENU, HELP, OPTIONS, BATTLE, TEAM_BATTLE, CHALLENGE_SELECT, puzzle, challenge and battle play headlessly with no errors. This covers the extraction core only: `setup.cmd`, `--prepare` and the RecompLauncher path were not run (they write to the user's config folder), and the screens were not diffed beyond the earlier per-screen comparisons.

## Dreamcast coverage table (2026-11-18)
Counts items this table lists, not the game's full content (many screens have several states). Status: verified = within the goal's error bar (full frame <= 3, text 0 px); partial = implemented and compared once; open = not built or not compared.

| Item | Kind | Status | Measured error vs Flycast |
|---|---|---|---|
| SEGA logo | screen | verified | 0.97 |
| Sonic Team logo | screen | verified | 0.66 |
| Title (bg, logo, prompt) | screen | verified | 1.6-2.5 |
| Title flying rocket | animation | partial (position exact, edge 1.6-2.5) | 1.6-2.5 |
| Title shadow strip newtitle1 (newtitle2 not in that frame) | screen | partial | edge region 0.6 |
| Title attract demo | animation | open | - |
| Mode Select | screen | partial | 2.98 |
| Challenge select (A1, B1, B2) | screen | verified | 2.2-3.0 |
| Challenge select clock, clear marks | screen | partial | 0 px / 1.2 |
| Challenge intro cards A1, B2 | screen | partial | <=3 |
| Challenge play A1 | screen | partial | see dreamcast_models.md |
| Challenge failure | screen | partial | 4.3 |
| Challenge clear (C1) | screen | partial | 0.7 banner |
| Challenge pause | screen | partial | - |
| Puzzle play Normal 01/02/08 | screen | partial | - |
| Puzzle pause | screen | partial | - |
| Puzzle hint text (BIOS font) | screen | verified | 0 px |
| Battle Select Players (4P, Team) | screen | verified | 0.55 / 1.45 |
| Battle Stage Select | screen | partial | 2.35 (preview 9.6) |
| Battle play HUD, Team Battle HUD | screen | partial | - |
| Battle pause (4P, Team) | screen | partial | - |
| Help Menu | screen | partial | visual match |
| Help pages (21) | screen | partial | 4.8-13 |
| Options menu | screen | partial | 4.48 |
| Options sub-pages (General, 4P Settings, Records, Language, F-key) | screen | open | - |
| Mode 4, 16 (tutorial), 18-22 | screen | open | - |
| Puzzle Edit screens | screen | open | - |
| Network / Homepage | screen | not testable offline | - |
| Unlock/password messages (mode 17) | screen | open | - |
| Mouse walk cycle (8 keyframes) | animation | partial (timing exact, sprite residual) | moving px 11.4 vs 5.4 static baseline |
| Cat motions (position + morph) | animation | partial (not frame-diffed) | - |
| Rocket lid / lift-off / smoke | animation | open (Dreamcast not compared) | - |
| Mouse caught, hole fall, rocket entry | animation | open | - |
| Cursor trail | animation | partial | - |
| Roulette | animation | open (Dreamcast) | - |
| KapuKapu, focus ring | animation | open | - |
| Sound: startup, menu, cues, music | sound | open (driver internals verified, no playback match) | - |

**Totals: 37 items; 6 verified, 19 partial, 12 open or not testable.** Update this table in the same commit as any Dreamcast change.

## Dreamcast mode inventory (read from the game's mode table, 2026-11-18)
The table at `0x8c0b373c` (pointer at `0x8c0190e8`) lists 23 modes (the setter `0x8c019088` rejects values >= 23 and stores the mode at `0x8c1af108`, read from RAM dumps of the captured screens); each entry points to a descriptor whose first word is the mode's init function. Entries 23-39 and up are data, not modes. Status words as above; every row stays open until its screens are matched against Flycast frames.
| Mode | Init function | What it is | Status |
|---|---|---|---|
| 0 | 0x8c0235ea | SEGA logo | **partial**: layout and fades match Flycast (mean error 0.97); music request not played |
| 1 | 0x8c023776 | Sonic Team logo | **partial**: 0.66 mean error; fades timed from one-frame captures |
| 2 | 0x8c0264d2 | Title (idle timeout 588/600 ticks) | **partial**: background, logo, prompt blink and flying rocket done (1.6-2.5 mean error); drop-shadow pieces and music open; attract replay integrated, full rendering checks still partial |
| 3 | 0x8c0265da | after the first Start on the title (frames 1352-1513): save/VMU check, before Mode Select (screen not compared) | open |
| 4 | 0x8c022432 | unidentified (not reached by the Start, Help, Options, Battle or Challenge paths) | open |
| 5 | 0x8c022f24 | Mode Select (mode variable 5 from frame 1519 until a mode is chosen; mode 20 appears for 5 frames just before) | partial: 4P Battle and Challenge selections compared at 640x480 |
| 6 | 0x8c02cd80 | Help: Help Menu (The Basics, 4P Battle, Team Battle, Stage Challenge, Puzzle, Puzzle Edit, Network, Homepage, Options), The Basics pages ('Basic Rule 1/6') and each mode's help pages ('4P Battle 1/2') | partial: Help Menu and all 21 help pages (The Basics 1-6, 4P Battle 2, Team Battle 1, Stage Challenge 2, Puzzle 2, Puzzle Edit 2, Network 4, Homepage 1, Options 1) drawn from layouts read off Flycast frames (`DcHelpMode` pager; page mean error 4.8-13 against Flycast, mostly edge softness from the original's bilinear 255/256 UV sampling, not yet reproduced; spot checks show identical structure). Open: that sampling, the Network page 3 text box edges, localized pages.
| 7 | 0x8c024290 | menus: Mode Select, 4P Battle Select Players and Stage Select, Challenge select (mode variable 7 in all captured menu frames; init loads `yuka01-03` and `kabetx01-03`, VMU removal messages) | partial: Mode Select, Challenge select and Battle setup compared; Puzzle select, Options, Help, Network entries open |
| 8 | 0x8c02dc50 | Puzzle Edit (mode variable 8 in the Edit/pause capture `pz3`; init loads `yuka01/03`, `kabetx01/03`) | open: pause overlay seen; the editor screens are not compared |
| 9 | 0x8c034fa0 | network (string `  Disconnecting...  `) | open, not testable offline |
| 10 | 0x8c04ffc0 | network setup (strings about setting up the Dreamcast for network access) | open, not testable offline |
| 11 | 0x8c051b9a | Options (General Settings, Settings for 4P Battle and Team Battle, Records, Language, Keyboard F-key Settings, Return to Initial Settings) | partial: Options menu drawn from disc art (`DcOptionsMode`, strip = `OPTION_newsousa2`, text in the BIOS font or its fallback; mean error vs Flycast about 5-7, glyph shapes differ without a BIOS); the settings pages behind each entry are open |
| 12, 13 | 0x8c0278cc | shared init with `yuka01` floor: 12 = Battle play, Team Battle and the attract demo (mode variable 12 in the battle, HUD and demo captures); 13 unseen | partial: Battle and Team Battle captures compared; demo and mode 13 open |
| 14 | 0x8c02a33e | Challenge play, pause, failure and clear screens (mode variable 14 in those captures) | partial: A1 play, failure (4.3), clear banner and select compared; other stage types and results open |
| 15 | 0x8c02b97e | Puzzle play (mode variable 15 in the Normal 01 capture) | partial: Normal 01, 02, 08 compared; Hard, Special, Mania and results open |
| 16 | 0x8c058292 | tutorial per the style variable (`FUN_8c016bd4`) | open |
| 17 | 0x8c0507e0 | unlock and password messages ("You can now select Chao / Pians / Mania / Special / Hard", "The password is:") | open |
| 18-22 | 0x8c05cfba, 0x8c05d39a, 0x8c05d55a, 0x8c05dc80, 0x8c05df12 | unidentified | open |
Modes 4, 16 (tutorial per the style variable) and 18-22 are still unidentified (no strings in their init code, none reached by the captures yet). Next: trigger them in Flycast (tutorial, options, help, credits, roulette, results, VMU screens), read `0x8c1af108` for each, then give every screen of every mode its own row. Method: `flyhost` with `FLY_WATCH=1af108:4:<frame>` logs the mode variable every frame while a key script walks the menus; screenshots beside the log name the screen.

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

### KapuKapu mesh nodes and Battle crown (2026-11-18)
- KapuKapu node trees read from `1ST_READ.BIN` (NJS_OBJECT 52 bytes: flags, model, pos, BAMS rot, scale, child, sibling). Root A body `0x8c08e138` (model `0x8c08e120`, pos 0,3,0, scale 1.5) with child chain `0x8c08dd10`->`0x8c08db40`->`0x8c08d970`->`0x8c08d6f8`->`0x8c08d480`->`0x8c08d324`->`0x8c08d1c8` (models `08dcf8, 08db28, 08d958, 08d6e0, 08d468, 08d30c, 08d1b0`). Root B `0x8c0960ec` (model `0x8c0960d4`, pos 0,3,0) with children `0x8c095c80`, `0x8c095af0`, `0x8c095980`, `0x8c095810`, `0x8c0956a4`. Root C parts `0x8c0967c4`, `0x8c096920`, `0x8c096be8` (+`0x8c096a8c`), scale 1.5. Motion (animation) data and the per-mouse-type selection are **not yet found**; port still draws these mice as plain mice. Status: **open** (static pose only).
- Rocket crown (`FUN_8c029340` -> `8c02971c`): **partial**. Drawn from disc art (frame 31 of dc_battle_hud); blink gate `(tick&31)<=10` matches Flycast frame 3550 at port tick 1772. Full-frame mean RGB error there is 9.71 (pass needs <= 3); isolated crown art not yet diffed.
- Correction (2026-11-18): the node trees above are reached from the mouse draw dispatcher `0x8c019e26` (root A `0x8c08e138` at `0x8c019fe0`, root B `0x8c0960ec` at `0x8c019fc4`; task type at +0x08 selects kind 0/1/2, kind 2 swaps textures `c_mouse02/04` and `c_mouse03/05` around the draw). Calling them "KapuKapu" was an unverified label from earlier notes; the Flycast "?" mouse in frame 3550 is a pink mouse variant drawn through this dispatcher. Open: which task type value the sim's roulette mouse (`type 2`) produces, and the per-kind motion routines; the port draws all three kinds as the plain mouse.
- Roulette (pink) mouse, 2026-11-18: `tools/export_dc_models.py` now exports `mouse_a/b/c` (roots `0x8c08e138`, `0x8c0960ec`, `0x8c096be8`) with the full 10-texture list; the port draws sim mouse `type == 2` as `mouse_a` with the dispatcher's texture substitution (c_mouse02->04, c_mouse03->05, material slots 1->4, 2->3; `drawDcCharacter` `texRemap`). Headless tick 1772 vs Flycast frame 3550: pink body and red feet now present at the right cell. **Still open:** the yellow "?" above it (separate object, not found), the node animation (static pose only), heading/tilt of the pose, golden mouse (kind 1, `mouse_b`). Full-frame error unchanged at 9.7 (object is small); crop-level diff not done.

## iPad HD 1.0 coverage table (2026-11-18)
The mobile counterpart of the Dreamcast table. Reference: the iPad HD 1.0 binary run under Unicorn (`tools/oracle/hd_*_probe.py`), compared call for call by the `tools/*_diff.py` scripts. **Verified** = zero differing draw calls / values over the stated cases (the original's own routines as the game runs them). The goal's full-frame RGB bar (mean <= 3) is not measured for mobile: no original iPad frames exist locally, so rendering residue (filtering, blends) is open for every row until a reference frame is captured. Rows marked partial or open give what is missing. Evidence quoted from ui_art.md / roadmap.md; re-run the named tool to re-verify.

| Item | Kind | Status | Evidence |
|---|---|---|---|
| Battle HUD (scores, timer, crowns, blink) | screen | verified | `battle_hud_diff`: 1,384 calls / 64 frames |
| Round banners, 3-2-1 count tasks | animation | verified | `banner_diff`: 48 cases |
| Battle result, free-for-all | screen | verified | `judge_diff`: 30 cases |
| Battle result, Team | screen | verified | `judge_team_diff`: 27 cases |
| Speech bubbles | screen | verified | `bubble_diff`: 11 traces |
| Battle preview boards | screen | verified | `battle_preview_diff`: 50 uploads byte for byte |
| Mouse ghost (overhead draw) | animation | verified | `mouse_ghost_diff`: 564 draws |
| Rocket launch and smoke | animation | verified | `rocket_launch_diff`: 86,400 draws / 72 cases |
| Rocket lid | animation | verified | `rocket_lid_diff`: 92,160 updates |
| Roulette drum mesh | animation | verified | `roulette_mesh_diff`: 432 poses |
| Roulette pose and timing | animation | verified | `roulette_pose_diff`: 3,840 frames |
| Players pane (render) | screen | verified | `players_render_diff`: 1,236 calls / 27 frames |
| Players pad pane (render) | screen | verified | `players_pad_render_diff`: 856 calls / 22 frames |
| Stage select (iPad grid) | screen | verified | `ss_diff`: 6 cases |
| Options > Sounds | screen | partial | `options_diff`: 7 volume / drag cases; other rows unchecked |
| Battle Settings pane | screen | partial | `levellist_diff` 25/25 rows, `fill_diff`, `panels_diff` 4/4, `scroll_diff` 4/4, `hit_diff` 53 points; lists' panels and sheets not ported |
| Startup, main menu | screen | partial | `startup_diff` exists; layouts reproduced, residue not measured |
| Options list, How to Play (Help) | screen | partial | `options_diff`, `help_diff`; The Basics, Costumes open |
| Puzzle pause and banner | screen | partial | traced from `PuzzleGameScreen::render`; no diff script |
| The Basics pages | screen | open | - |
| Costumes | screen | open | - |
| Celebration rockets | animation | open | - |
| Phone / larger-device HUD layouts | screen | open | - |
| Tutorial highlights | screen | open | - |
| Split-screen | screen | open | - |

**Totals: 25 items; 14 verified, 5 partial, 6 open.** Update this table in the same commit as any iPad change. Next: capture or derive an original iPad frame per row so the RGB bar can be applied.
- Newest-build check (2026-11-18, package metadata read from the local files): iOS 1.1.2 universal (newest packaged entry 2013-04-25) is the latest build; then Android 1.15 (2011-12-03), Android 1.14 (2011-11-23), iOS 1.1 (2010-12-19), iOS 1.0.2 (2010-12-04), HD 1.0 and the ORBiT repacks (2010-10-28..30; HD 1.0 store release date 2010-10-28). Zip entry dates are packaging times, not store dates. The iPad table above uses HD 1.0 because its layouts are the ones already diffed; iOS 1.1.2 is the newer reference and should become the oracle for any row where it differs (open: its device class >= 10 resource table does not fit the shipped `ccrret` pack, ui_art.md "Open question found while mapping").
- Battle "?" (2026-11-18, `local/dc_ref/tp1/t_03400.state`, Team pause frame; parse regions 0x253e10 and 0x1900003 work for this state, not for `tasks-full_*.state`): the yellow "?" over the pink mouse is ONE textured quad in the second list at state offset `0x19e3e43`: ctrl `828c000a`, tsp `9491a4db` (64x64 texture, matches the 64x64 `CHALLENGECLEAR_hatena`, not yet matched pixel by pixel), tex word `90051ad8`, 4 vertices at x 569.83..605.81, y 287.30..323.28 (35.975 px square), 1/w 0.0048, UV (0,0)-(1,1), submitted after the opaque pink mouse parts (`0x25e530` n=36 strips 10/8/8/10, and feet/body parts at `0x26b810`..`0x26ce50`). A 36 px quad at this projection (about 2.56 px per unit) is about 14 units, consistent with a 13.5-unit plane at height about 8.5 (the crown plane is also 13.5 units). **Open:** the original routine and its offset from the mouse position (find the callee that submits this quad from the mouse task callback), the texture identity check, then draw it in the port.
- Mouse marker quad, 2026-11-18 (late): routine `FUN_8c056e1e` -> `FUN_8c056d00` decoded from the SH-4 code: position (x, 9.5, z - 10.0), half size 6.75, texture `46 + 3 * kind` of the CHALLENGECLEAR list (kind 0 `plus50` = type 1 golden, kind 1 `hatena` = type 2 roulette), gated by `0x8c016b26() == 1`. The port draws both after the cursor trails and before the cursor arrows. Headless `DC_DEMO` tick 1772 vs Flycast frame 3550: "?" upright, same colours, same cell and size by eye; full-frame mean error 9.67 (was 9.71). **Still open:** pixel diff of the marker, the `plus50` marker (golden mouse) not yet seen in a Flycast frame, the `0x8c016b26` gate meaning, pink mouse pose and animation.
