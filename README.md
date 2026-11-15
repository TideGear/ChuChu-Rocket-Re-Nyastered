# ChuChu Rocket! Re-Nyastered

> **Not affiliated with SEGA.** This is an unofficial, fan-made reimplementation. *ChuChu Rocket!* and all related marks, art, music
> and stages are the property of SEGA. **You must own the original game** (this project reads your own copies of the iOS, Android,
> Game Boy Advance and Dreamcast releases). Please buy them where you still can.

A faithful, best-of-all-versions reimplementation of ChuChu Rocket! in portable C++ (SDL2) for Windows, 64-bit Android and the web.
This repository is **source code only**: no game data, no original code, and nothing derived from either. Assets are extracted on
your machine from your own files into a local cache and are never committed or shipped.

## Status (work in progress)
The project is well short of its goal; the honest, current list is in [docs/known_gaps.md](docs/known_gaps.md). Summary:

**Done and verified (evidence in [docs/verification.md](docs/verification.md) and [docs/version_matrix.md](docs/version_matrix.md))**
- A deterministic fixed 60 Hz simulation of puzzle and battle play (`game/core/`). Against the original code of each build, run unmodified in an emulator:
  puzzle movement on all 2,548 stages for Android 1.14 and 1.15 and iOS 1.0.2, HD 1.0, 1.1 and the 1.0 ORBiT build; battle scoring, roulette selection and CPU players
  for the Android and iOS builds; for the Dreamcast, the speed table, roulette selector, scoring and the CPU task (decisions, cursor and arrow stage) in an SH-4 interpreter. GBA puzzle stage 1 matches the real ROM.
- Replays and lockstep netplay: the simulation is bit-exact across runs and across native/WebAssembly; the lockstep protocol survives 30-60% packet loss with no desync (loopback UDP tested).
- Extractors for the iOS and Android packs, Dreamcast files/textures/3D models/CD audio, GBA stage data and the Dreamcast DLC (including the character skins), a master stage registry, and a localization table for six languages (`tools/`).

**Playable now (Windows, `ccr.exe`; also builds for the web)**: title screen and main menu in the original iPad layout with the best-quality art found,
Puzzle and Battle (CPU opponents, 1-4 local players via `CCR_HUMANS`), music following the original's triggers, battle sound effects, 4K-capable resolution-independent rendering.

**Still in progress**: the roulette wheel and character animations, The Basics, Stage Challenge, full Team Battle setup, Puzzle Edit, costumes and unlockables, in-game netplay screens, Dreamcast sound effects, the Android app and browser import. Puzzle stage select, parts of Help & Options, the battle countdown and parts of the HUD are in the current build.

## Build and setup (Windows)
1. Install Python 3.12 for asset extraction. Setup installs Pillow if needed.
2. Choose the [original files](#which-original-files-do-i-need) for the modes you want. Run `setup.cmd` and point it at the folder holding those files. Setup unpacks them to `%APPDATA%\ReNyastered` by default and records the inputs, hashes and extraction errors in `manifest.json`. On the first build it downloads and verifies portable Zig 0.14.1, CMake 4.0.3 and Ninja 1.12.1, then keeps them in `local/tools/windows` for future builds.
3. [Export the assets for play](#export-assets-for-play), then run `build\game\ccr.exe`. Pass the exported asset folder as the first argument or use `CCR_ASSETS`. Run `build.cmd` to rebuild the code. Useful switches include `CCR_CPU=gba` for GBA-style battle AI, `CCR_LANG=en|fr|de|es|it`, `CCR_HUMANS=1..4`, `CCR_SIZE=3840x2160` and `CCR_FULLSCREEN=1`.
4. Tests never open a window or play audio when run headless (`CCR_HEADLESS`, `CCR_SHOT`, `CCR_BENCH`); the C++ tests are CMake targets in `game/` (`determinism_test`, `battle_full_test`, `cpu_test`, `netplay_test`, ...).

For an offline build, set `CCR_TOOL_ARCHIVES` to a folder containing `zig.zip`, `cmake.zip`, `ninja.zip`, `SDL2-2.30.9.tar.gz` and `stb_vorbis.c` from the pinned upstream releases. Zig uses its own CMake cache in `build/game-zig`. Executables still go in `build/game`.

Other platforms: the core and tests cross-compile for Android arm64 (NDK) and build for WebAssembly (Emscripten; see [docs/roadmap.md](docs/roadmap.md)); neither has been run on a device yet.

### Which original files do I need?

Put the files you own under `Original Game Files` next to `setup.cmd`, or give setup the path to your own folder. Group the archives as shown below. One file per needed release is enough. In particular, choose one Android version and one copy of each iOS release you use.

| To get | Original files | Why |
| --- | --- | --- |
| Base playable graphics | **iOS 1.1.2** `.ipa` in `iOS\` | The `ccrret` pack supplies the board, character, digit and font sheets the current executable requires. The iOS archives also supply the mobile music, effects and voice clips. |
| Puzzle | **iOS 1.1.2** plus the **GBA** ROM in `Game Boy Advance\` | Setup accepts a raw `.gba` or a `.zip` containing it at the archive root. The ROM provides 100 main puzzles and 2,466 additional puzzles. Use Tab in stage select to switch sets. Dreamcast Express needs its own export. |
| Battle | **iOS 1.1.2** plus the **Dreamcast** disc in `Dreamcast\` | Use a `.zip` of a GDI dump with its numbered `Track NN.bin` files at the archive root. The tested dump is the multilingual US release. It supplies the 25 battle boards and the stereo CD soundtrack. `CCR_CPU=gba` selects code already built into the game and does not require the GBA ROM. |
| iPad menus, HUD and localized artwork | Add **iOS ChuChu Rocket! HD 1.0** `.ipa` | Its `ccrpad` pack supplies the iPad-specific screens, fonts and layout data. Check for “HD” in the release name when selecting an iOS 1.0 archive. |
| Title and phone-menu assets | Add **Android 1.14 or 1.15** `.apk` in `Android\` | Supplies the phone title sprites, phone menu art and fallback menu strings. The title currently needs this export to enter its title screen. The Dreamcast export supplies the preferred logo and prompt. |
| Dreamcast Express puzzles | Add `DEPuzzle.VMS` and `PuzzleP.VMS` under `Dreamcast\DLC\` | The current DLC exporter reads both archives. Only the Express set is offered in play. Setup also copies any paired `.VMI` files. The skin saves and PuzzleP boards are reference material for now. |

For both Puzzle and Battle with the current iPad presentation, use **iOS 1.1.2 + iOS HD 1.0 + one Android APK + GBA + Dreamcast**. The other iOS builds (1.0, 1.0.2 and 1.1) are useful for version comparisons. They are not required for this combination.

### What if I have fewer releases?

- With the base iOS sprite export and GBA stages, you can launch Puzzle directly. Add the Dreamcast stage export to launch Battle. Each mode reports an error if its own stage data is missing.
- Without the HD 1.0 exports, the available Android art supplies the phone-style menus. HD-specific overlays and screens that require those assets may be missing. Without the exported Android title sheets, the executable skips the title and tries the available menu. With neither menu art set, start a mode directly.
- Without the Dreamcast CD tracks, music falls back to the mobile Ogg files from the extracted iOS archives. The mobile assets also supply the sound effects and voices.
- Without the required base sprite sheets, the current executable stops at startup. Android, Dreamcast and GBA files alone can be extracted, but they cannot replace those sheets in the current build.

### Export assets for play

Setup currently unpacks the original files and exports the GBA puzzles. Run the relevant exporters below to turn the remaining extracted resources into the sheets and stage files the game loads. These files stay in your local cache.

For example, from the repository root in PowerShell, prepare the base sheets and run Puzzle after setup has extracted the GBA ROM:

```powershell
$assets = Join-Path $env:APPDATA 'ReNyastered\assets'
$retina = Join-Path $assets 'ios\SEGA_ChuChu_Rocket_v1_1_2_iPad_iPhone_iPod_Touch\ccrret'
py -3 tools/export_sprites.py "$retina" "$assets/ret_all" all
.\build\game\ccr.exe "$assets" puzzle
```

Use the extracted iOS 1.1.2 folder shown in `assets\ios` if its name differs. If setup used a custom cache, set `$assets` to that cache's `assets` subfolder.

- **Battle:** run `py -3 tools/export_battle.py "$assets/dreamcast/files/ENGLISH" "$assets/battle_stages.bin"`, then launch with `battle` in place of `puzzle`.
- **Phone menus and title:** run `export_android_ui.py` with your extracted build folder under `assets/android` and `$assets/ret_all` as the output. To add menu strings, run `export_strings.py` with that build's `libccrjni` subfolder, a local JSON output path, and `$assets/strings` for the translated tables.
- **iPad menus and HUD:** see the [UI art notes](docs/ui_art.md) for HD exporters and input packs. These use the HD 1.0 `ccrpad` resources under `assets/ios`, with the matching thinned `.armv7` executable under the cache's `work/ios` when required. Run `py -3 tools/export_dc_ui.py "$assets/dreamcast/prs_png" "$assets/ret_all" "$assets/dreamcast/png"` to add the Dreamcast logo and prompt.
- **Dreamcast Express:** export to `assets/gba/dlc_stages.bin` using [`tools/export_dlc_stages.py`](tools/export_dlc_stages.py) and see the [DLC notes](docs/dlc.md). The exporter currently expects the repository's original-files layout.

## Where each asset and rule comes from
[docs/provenance.md](docs/provenance.md) lists, per asset class and per piece, the version used and the measurements behind the choice (music: Dreamcast CD audio; title logo: Dreamcast; backgrounds and sprites: iPad HD pack; strings: Android resources; rules: each version's own code). [docs/version_matrix.md](docs/version_matrix.md) compares every subsystem across all versions.

## Layout
- `game/` C++ code: portable simulation core (`core/`), the SDL2 app (`app/`), tests (`tests/`), web shell (`web/`)
- `tools/` extractors, the stage registry, and the development-time verification oracles (`tools/oracle/`: your own copies of the original code run in emulators; nothing from them is distributed)
- `docs/` rules specification, verification results, version comparisons, provenance, UI art notes, known gaps
