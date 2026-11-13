# Roadmap and status against the goal (updated 2026-11-12)

Legend: DONE = built and verified; PARTIAL = built or measured in part; TODO = not started.

| # | Goal item | Status | Notes |
|---|---|---|---|
| 1 | Rules spec from every version's code | PARTIAL | Android puzzle mode verified tick-for-tick (docs/verification.md). iOS: event/timer/generator constants diffed across 1.0.2/HD/1.1.2 (docs/rules_events.md). Dreamcast SH-4, GBA ARM7, battle/challenge mode, roulette outcomes mapping, scoring: TODO. Cross-version comparison matrix: started (docs/modes.md, docs/stages.md), not complete. |
| 2 | Fixed-tick simulation, decoupled rendering | PARTIAL | Puzzle simulation core at 60 Hz in ticks (game/core/sim.hpp). Frame-rate evidence in docs/rules_movement.md. Interpolating renderer: TODO. Battle simulation: TODO. |
| 3 | Extractors for every container + manifest | PARTIAL | `tools/extract_all.py` tested: iOS packs (all builds), Android packs, Dreamcast disc files/PVR/CD audio, GBA stages, DLC copy, manifest with SHA-256. TODO: DC `DP2SOUND.MLT`/`VOICE.AFS`/`MANATEE.DRV`, embedded DC models, GBA graphics/audio, sprite UV tables as a documented sheet format. |
| 4 | Best source per asset class | PARTIAL | Music DONE (docs/audio.md: Dreamcast CD audio best; mobile = lossy mono re-encode). Graphics: iOS tile atlas resolutions measured (ccrret 600x288, ccrpad 594x282, ccrphn 509x111); full per-asset comparison, DC 3D (models not located), SFX/voices, UI, fonts, localization: TODO. |
| 5 | Union of content/features | PARTIAL | Stage registry: 2,669 unique boards from iOS, Android, Dreamcast, GBA (2,566 stages) and DLC (docs/stages.md). Modes audit first pass (docs/modes.md). Roulette tables identical across mobile (docs/roulette.md). Dreamcast/GBA mode/roulette audits, Puzzle Edit, CPU opponents, 4-player input, LAN/online netplay: TODO. |
| 6 | Dreamcast DLC | PARTIAL | All five packs downloaded (Original Game Files/Dreamcast/DLC); puzzle format decoded (25 puzzles/pack, lattice format, cell codes) and compared to mobile (42 of 50 DLC-only). TODO: character-pack skin format (34-block packs: GBIX/PVRT textures at payload start), importers in the game, identify the Oct 2024 pack, VMU loading code. |
| 7 | No placeholders in UI | PARTIAL | Dev viewer (`game/viewer`, SDL2) draws a puzzle board from the extracted iOS atlas (frames: 6 silo, 7 pit, 8-19 floors, 20-25 rocket spheres, 26-34 rockets, 0-5 arrow strips) with a fixed 60 Hz step and interpolated drawing; cats draw from the real 32-view turntable sheet (ccrret rec 447, frame = heading*8; tools/export_sprites.py), mice from rec 503 (to be confirmed as the standard mouse; 484 gold, 522 red), no menus/HUD yet. |
| 8 | Builds: Windows playable, Android arm64, WebAssembly; automated tests | PARTIAL | Windows build scaffolding (`build.cmd`, CMake, MSVC) builds and runs `solve_test`. Differential tests against the emulated original in tools/oracle. Playable game, Android and web builds: TODO. |
| 9 | README | PARTIAL | README.md, setup.cmd and setup wizard written (not run end to end). Per-asset provenance table: TODO. |

## Verified numbers
- Movement (cat and mouse): 0 differences over 200 random walled boards each x 400 ticks vs the original.
- Puzzle stages: 600 of 600 sampled stages identical save timelines ; full 2,548-stage run: 0 differences in the 1,876 stages the emulator completed, the remaining 672 hit an emulator resource limit and were rerun in fresh processes (local/testdata/oracle_rest.txt).
- RNG: Mersenne Twister, state[0] = seed|1, state[i] = 69069 * state[i-1]; output matches the original for three seeds.
- Music: mobile M00..M13 = Dreamcast CD tracks 04..17 (+2.0 s lead-in; M08/M09/M11 are 4x loops on disc).

## Next steps (in order)
1. DONE: battle generator + RNG ported and verified (15/15 golden logs; docs/rules_battle.md). Next: end-of-round sequence, rocket scoring, roulette triggers.
2. DONE: scoring (score.hpp) and roulette selector + outcome mapping (roulette.hpp), both verified. Next: rocket entry in a battle simulation, roulette trigger (type-2 mouse), roulette outcome handlers, end-of-round sequence, arrows per player, cursors.
3. Extract and document the sprite sheet UV tables; build the SDL renderer and a vertical slice (puzzle board with real art).
4. Audio (SFX/voice comparison, loop points), menus/UI, game modes, input, netplay, DLC skins/puzzles in the game.
5. Android arm64 and WebAssembly builds; remaining version comparisons (iOS movement via oracle, GBA ARM7, Dreamcast SH-4).

## Dreamcast models (see docs/dreamcast_models.md)
Located baked vertex data in 1ST_READ.BIN (morph-frame tables, pos+normal arrays); DPMODEL is empty on disc. Mesh topology/UVs not decoded yet.
Update: models decoded and exported (tools/dc_models.py, 128 OBJ models from 1ST_READ.BIN, wired into extract_all); hierarchy, texture mapping and morph animation remain.

## Menus and animations (status 2026-11-12: NOT STARTED beyond the tile/sprite viewer)
Needed for goal item 7 (no placeholders): every menu screen (title, mode select, options, stage select, puzzle edit, network lobby, DLC/VMU screens) with the original layouts, fonts, transitions and audio; all gameplay animations with their original frame counts (roulette fly-in = 30 ticks + 90 ticks before the event starts, cat rocket-in/hole fall = 30 ticks, mouse/cat turntable sprites, rocket launch, fever/event overlays, score and timer HUD, result screens). The battle roulette sequence timings are being decoded now because they affect game state (event start is 121 frames after the roll); the remaining UI flow and screen layouts will be extracted per version (iOS ccrphn/ccrret/ccrpad layouts, Dreamcast 2D screens in DPTEX/PVR, GBA tilemaps) and compared.

## Game-file requirements (design decision 2026-11-12)
Rules/logic are in our code; game files supply only assets. Any one complete version (iOS 1.1.2, Android 1.14/1.15, or the Dreamcast disc) will be enough to play; each additional version adds its unique content (GBA user puzzles, Dreamcast CD music/3D/voices, DLC) and the best source per asset class is used with fallback. To verify: whether any single version contains every UI screen/font needed for all modes (to be measured during the menu work; minimum set documented in README).

## Playable slice (2026-11-12): `ccr.exe` (game/app/main.cpp)
Battle mode vs CPU players on the 25 Dreamcast battle stages with the verified 60 Hz BattleGame, interpolated drawing, extracted iOS art (tile atlas, cat/mouse turntable sprites, digit font), mouse arrow placement for player 1 and the verified CPU AI for the others. Missing: title/menus, roulette overlay and event visuals, round timer and results screen, sound, 4-player input, puzzle/challenge modes in the same app, original UI layouts. Run: `tools/export_sprites.py <ccrret dir> <cache>/ret_all all`, then `build\game\ccr.exe <cache assets dir> [stage] [seed] [cpu levels]`.

Update 2026-11-12 23:20: `ccr.exe` now has Menu / Puzzle / Battle modes (game/app/main.cpp). Puzzle: 100 main stages from the GBA stage set, arrow stock = reference-solution counts, plan then SPACE to run, CLEAR/MISS; battle as before. Text uses the extracted glyph sheet (ccrret rec 23, frame = ASCII code). Menu art/layout is still a plain placeholder: real title/menu screens are TODO.

## Online play options (2026-11-13)
Dreamcast Live (dreamcastlive.net) hosts the original ChuChu Rocket! server (Jonas Karlsson, 2016). Real consoles reach it through DreamPi/dial-up/BBA with UDP 9789; nickname registration is bound to one console; the wire protocol is not documented publicly.
1. Primary (planned): our own deterministic lockstep netplay (same 60 Hz sim, input exchange) over UDP for desktop/Android and WebRTC for the web build; LAN + internet via a small relay/rendezvous. Works with no third party.
2. Optional "Dreamcast Live compatibility" client: speak the original CLIENT_/SERVER_ protocol (reverse engineered from the Dreamcast binary with the SH-4 tooling; the sim is exact, so playing on an authoritative server is fine). Needs the protocol RE, an identity scheme compatible with console-bound registration, UDP (native builds only; browsers need a relay), and the operators' agreement before we connect any third-party client to their service.

## Android arm64 (2026-11-13)
The portable core and all test programs now cross-compile for arm64-v8a with the user's Android NDK 27 (`cmake -S game -B build/android-arm64 -DCMAKE_TOOLCHAIN_FILE=<ndk>/build/cmake/android.toolchain.cmake -DANDROID_ABI=arm64-v8a -DANDROID_PLATFORM=android-24 -DRN_BUILD_VIEWER=OFF`); `-ffp-contract=off` is set for non-MSVC compilers so float results are not altered by fused multiply-add. Not yet done: running them on a device/emulator (no Android device or system image is installed here), the SDL2 Android app (activity, asset import, touch input), APK packaging.

## WebAssembly (2026-11-13)
Emscripten 3.1.74 (installed by the user's approval into the git-ignored `local/tools/emsdk`, not system-wide) compiles the portable core and test programs to WebAssembly: `cmake -S game -B build/wasm -DCMAKE_TOOLCHAIN_FILE=<emsdk>/upstream/emscripten/cmake/Modules/Platform/Emscripten.cmake -DRN_BUILD_VIEWER=OFF -DCMAKE_EXE_LINKER_FLAGS="-sNODERAWFS=1 -sALLOW_MEMORY_GROWTH=1"`. Run headless under Node (no browser): `determinism_test` (25 stages, 180,000 replayed ticks, 0 divergences), `battle_full_test` against the original-code golden (26/26 identical), `cpu_test` against the original CPU golden (10/10), `score_test` (1,500 ops, 0 divergences) and `roulette_test` (3,000 calls identical) all give the same results as the native Windows build, so floating-point behaviour is the same in WebAssembly. Not yet done: the SDL2 browser app (Emscripten SDL port, canvas, audio worklet, asset import UI, service worker/PWA manifest for iOS Safari), WebRTC data channels under `Lockstep`, and a real-browser test.
