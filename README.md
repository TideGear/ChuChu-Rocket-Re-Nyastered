# ChuChu Rocket! Re-Nyastered

**This is a fully human-driven, AI-powered reimplementation of SEGA's ChuChu Rocket!** I direct the project and set the standard for accepting changes. AI assists with reverse engineering, implementation, testing and documentation. When a feature is verified against an original release, the documentation shows how the comparison ran and which cases it covered.

**This is very much a work in progress.** Menus, visuals, and gameplay will continue to change as more of the original releases are reproduced and verified.

> **Unofficial fan project.** This project has no affiliation with SEGA. The game's artwork, music, stages and marks belong to their respective owners. The repository contains the project source and documentation. Use your own lawfully obtained game files to generate assets and screenshots locally. See [asset handling and release notes](docs/distribution.md).

The project brings together the strongest parts of the Dreamcast, Game Boy Advance, iOS and Android releases in a portable C++ and SDL2 implementation. The current build pairs the iPad layout with the Dreamcast title logo and CD music when those assets are available. Each [asset and rule source](docs/provenance.md) is documented separately.

[Build and play](#build-and-setup-windows) · [Original files needed by mode](#which-original-files-do-i-need) · [Status and plan](#status-and-plan) · [Verification results](docs/verification.md)

## Status and plan

**Playable now on Windows:** Puzzle with stage select, Battle with local hotseat for up to four players on one machine and CPU opponents, the title and main menu, and parts of Help & Options.

**Planned multiplayer:** Wireless local play via mobile devices and online play.

| Phase | What’s in place | What’s planned |
| --- | --- | --- |
| **A. Original UI** | iPad title and menus, puzzle stage select, parts of both HUDs, pause and battle round banners. Battle setup panes have verified drawing and input components. The board uses the original iPad wall order and depth-sorts its moving sprites and rockets. | Wire the battle setup into play, complete the HUDs and results, finish The Basics and Options, and restore the roulette wheel, rocket animations and cursor trails. Verify draw order, overlaps, wall joins and clipping against the original when adding or changing a scene. |
| **B. Rule parity** | Puzzle movement matches the 2,548 tested mobile stages. Mobile battle scoring, roulette selection and CPU placement have separate comparisons. Some forced roulette outcomes already have whole-battle results. | Match all eight forced roulette outcomes across all 26 cases each, including per-rank thresholds. Finish and verify Team Battle, trace and port all 25 Stage Challenge stages, and implement the original Puzzle Edit rules. |
| **C. Version differences** | Dreamcast input and speed, scoring, roulette and parts of the CPU task are documented or compared. GBA puzzle stage 1 and individual CPU routines have ROM comparisons. Several iOS releases have their own runs. | Verify Dreamcast heat maps and full-battle CPU placement, determine Dreamcast effect playback rates, match GBA battle rules and full CPU placement, explain the GBA score gap, and cover remaining iOS-specific differences. |
| **D. Content and options** | Asset extractors and a cross-version stage registry exist. The current build can play the main puzzles, GBA extras and the Dreamcast Express set with the corresponding exports. Some sound and language options work. | Verify original unlocks and options, add unlock-all, import DLC skins and VMU saves, determine PuzzleP arrow stock, and make every stage set selectable. |
| **E. Audio** | Dreamcast CD music is preferred when available. The mobile audio supplies effects and voices. Several music and effect triggers have been traced, and mobile files have been compared by hash. | Match every music, effect and voice trigger, including loop points and fades. Finish the quality evidence for audio, fonts and 3D assets. |
| **F. Platforms and play** | Windows build, fixed 60 Hz simulation with interpolation, headless 2D GPU measurements at 4K, local hotseat for up to four players, and headless WebAssembly runs. Deterministic replays and loopback UDP lockstep have been tested. | Verify sustained and uncapped 4K performance as rendering is completed, implement wireless local play via mobile devices and online play, build and test the Android arm64 app, and finish the web app’s asset import and PWA checks in a headless browser and on iOS Safari. |
| **G. Documentation and setup** | Cross-version matrix, asset provenance, original-file requirements, and a portable Zig build. Setup unpacks originals and records their hashes. | Complete the evidence and provenance for each version, automate the remaining asset exports, and verify the full setup-to-play process on a clean machine. |

See the [roadmap and dated work log](docs/roadmap.md), [verification results](docs/verification.md), [per-version matrix](docs/version_matrix.md) and [known gaps](docs/known_gaps.md) for the evidence behind each row.

## Build and setup (Windows)

1. Put your [original game files](#which-original-files-do-i-need) in `Original Game Files` beside `setup.cmd`, then run `setup.cmd` from the checkout. If that folder is absent, setup asks for the path. To specify both paths directly from PowerShell, run `.\setup.cmd -GameFiles 'D:\My Game Files' -Cache 'D:\ReNyastered'`.
2. Setup uses Python 3.10 or later if it can import Pillow. Otherwise it downloads and verifies private copies of Python 3.12.10 and Pillow 12.2.0 and caches them in `local\tools\windows`. Setup extracts into `%APPDATA%\ReNyastered\assets` by default and writes `manifest.json` and `setup.log` beside `assets`.
3. Setup builds `build\game\ccr.exe`. The first build downloads and verifies portable Zig 0.14.1, CMake 4.0.3, Ninja 1.12.1, SDL2 2.30.9 and `stb_vorbis.c`. It uses the checkout's `local\tools\windows` and `build\game-zig` folders. Visual Studio C++ Build Tools are unnecessary.
4. Complete the [gameplay exports](#export-assets-for-play) for the modes you want, then launch `build\game\ccr.exe`. Pass the `assets` folder as the first argument or set `CCR_ASSETS` if you use a custom cache.

Run `build.cmd --target ccr` to rebuild only the game. For an offline build, set `CCR_TOOL_ARCHIVES` to a folder containing `zig.zip`, `cmake.zip`, `ninja.zip`, `SDL2-2.30.9.tar.gz` and `stb_vorbis.c`. For offline extraction without an existing Python and Pillow installation, include `python-3.12.10-embed-amd64.zip` and `pillow-12.2.0-cp312-cp312-win_amd64.whl` too. The pinned URLs and hashes are in the [build script](tools/build-windows.ps1), [Python setup script](tools/setup-python.ps1), and [CMake configuration](game/CMakeLists.txt).

Runtime options include `CCR_CPU=gba` for GBA-style battle AI, `CCR_LANG=en|fr|de|es|it`, `CCR_HUMANS=1..4`, `CCR_SIZE=3840x2160` and `CCR_FULLSCREEN=1`. Use `CCR_HEADLESS`, `CCR_SHOT` or `CCR_BENCH` for silent runs without a visible window. The C++ tests are CMake targets in `game/`, including `determinism_test`, `battle_full_test`, `cpu_test` and `netplay_test`.

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

From the repository root in PowerShell, set `$python` to the Python executable reported by setup. The example uses the private runtime. Prepare the base sheets and run Puzzle after setup has extracted the GBA ROM.

```powershell
$assets = Join-Path $env:APPDATA 'ReNyastered\assets'
$python = '.\local\tools\windows\python-3.12.10-pillow-12.2.0\python.exe'
$retina = Join-Path $assets 'ios\SEGA_ChuChu_Rocket_v1_1_2_iPad_iPhone_iPod_Touch\ccrret'
& $python tools/export_sprites.py "$retina" "$assets/ret_all" all
.\build\game\ccr.exe "$assets" puzzle
```

Use the extracted iOS 1.1.2 folder shown in `assets\ios` if its name differs. If setup used a custom cache, set `$assets` to that cache's `assets` subfolder.

- **Battle:** run `& $python tools/export_battle.py "$assets/dreamcast/files/ENGLISH" "$assets/battle_stages.bin"`, then launch with `battle` in place of `puzzle`.
- **Phone menus and title:** run `export_android_ui.py` with your extracted build folder under `assets/android` and `$assets/ret_all` as the output. To add menu strings, run `export_strings.py` with that build's `libccrjni` subfolder, a local JSON output path, and `$assets/strings` for the translated tables.
- **iPad menus and HUD:** see the [UI art notes](docs/ui_art.md) for HD exporters and input packs. These use the HD 1.0 `ccrpad` resources under `assets/ios`, with the matching thinned `.armv7` executable under the cache's `work/ios` when required. Run `& $python tools/export_dc_ui.py "$assets/dreamcast/prs_png" "$assets/ret_all" "$assets/dreamcast/png"` to add the Dreamcast logo and prompt.
- **Dreamcast Express:** export to `assets/gba/dlc_stages.bin` using [`tools/export_dlc_stages.py`](tools/export_dlc_stages.py) and see the [DLC notes](docs/dlc.md). The exporter currently expects the repository's original-files layout.

## Where each asset and rule comes from
[docs/provenance.md](docs/provenance.md) lists, per asset class and per piece, the version used and the measurements behind the choice (music: Dreamcast CD audio; title logo: Dreamcast; backgrounds and sprites: iPad HD pack; strings: Android resources; rules: each version's own code). [docs/version_matrix.md](docs/version_matrix.md) compares every subsystem across all versions.

## Layout
- `game/` C++ code: portable simulation core (`core/`), the SDL2 app (`app/`), tests (`tests/`), web shell (`web/`)
- `tools/` extractors, the stage registry, and the development-time verification oracles (`tools/oracle/`: your own copies of the original code run in emulators; nothing from them is distributed)
- `docs/` rules specification, verification results, version comparisons, provenance, UI art notes, known gaps
