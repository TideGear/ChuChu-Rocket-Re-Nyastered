# ChuChu Rocket! Re-Nyastered

**This is a fully human-driven, AI-powered reimplementation of SEGA's ChuChu Rocket!** I direct the project and set the standard for accepting changes. AI assists with reverse engineering, implementation, testing and documentation. When a feature is verified against an original release, the documentation shows how the comparison ran and which cases it covered.

### Work-in-progress screenshots

<img src="docs/screenshots/title-wip.png" width="50%" alt="Title screen with the Dreamcast logo and iPad background">

| Puzzle | Battle |
| --- | --- |
| ![Puzzle stage 25, Gang of cats](docs/screenshots/puzzle-wip.png) | ![Battle against three CPU opponents](docs/screenshots/battle-wip.png) |

**This is very much a work in progress.** These captures show the current development build. Menus, visuals, and gameplay will continue to change as more of the original releases are reproduced and verified.

> **Unofficial fan project.** This project has no affiliation with SEGA. The artwork shown in the screenshots, along with the original games’ music, stages and marks, belongs to the respective rights holders. Use your own lawfully obtained game files to generate the assets required to play. See [asset handling and release notes](docs/distribution.md).

The project brings together the strongest parts of the Dreamcast, Game Boy Advance, iOS and Android releases in a portable C++ and SDL2 implementation. The current build pairs the iPad layout with the Dreamcast title logo and CD music when those assets are available. Each [asset and rule source](docs/provenance.md) is documented separately.

[Build and play](#build-and-setup-windows) · [Original files needed by mode](#which-original-files-do-i-need) · [Status and plan](#status-and-plan) · [Verification results](docs/verification.md)

## Status and plan

**Playable now on Windows:** Puzzle with stage select, Battle with local hotseat for up to four players on one machine and CPU opponents, the title and main menu, and parts of Help & Options.

**Planned multiplayer:** Wireless local play via mobile devices and online play.

The goal is a faithful Windows, Android arm64 and web reimplementation. Each phase compares the originals’ code, data, and runtime behavior with the port. The roadmap records verified cases and gaps, including alternate routes, rare events, and asset fallbacks.

| Phase | What’s in place | What’s planned |
| --- | --- | --- |
| **A. Original presentation and UI** | iPad startup logos, title and menus, Puzzle stage select, parts of both HUDs, pause, Battle round banners, and animated backgrounds. With the iPad assets, the Battle menu opens Players and Settings and launches local shared-screen matches on all 25 boards. | Finish split-screen setup, previews and locks, HUDs and results, The Basics and Options, and the remaining roulette, character, rocket and cursor effects. Verify timing, draw order, depth ties, overlaps, wall joins and clipping against the original. |
| **B. Rule parity** | Puzzle movement matches the 2,548 tested mobile stages. Mobile battle scoring, roulette selection and CPU placement have separate comparisons. Some forced roulette outcomes already have whole-battle results. | Match all eight forced roulette outcomes across all 26 cases each, including per-rank thresholds. Finish and verify Team Battle, trace and port all 25 Stage Challenge stages, and implement Puzzle Edit with the original editor rules and support for sharing custom puzzles. |
| **C. Version differences** | Dreamcast input and speed, scoring, roulette and parts of the CPU task are documented or compared. GBA puzzle stage 1 and individual CPU routines have ROM comparisons. Several iOS releases have their own runs. | Verify Dreamcast heat maps and full-battle CPU placement, determine Dreamcast effect playback rates, match GBA battle rules and full CPU placement, explain the GBA score gap, and cover remaining iOS-specific differences. |
| **D. Content and options** | Asset extractors and a cross-version stage registry exist. The current build can play the main puzzles, GBA extras and the Dreamcast Express set with the corresponding exports. Some sound and language options work. | Verify original unlocks and options, add unlock-all, import DLC skins and VMU saves, determine PuzzleP arrow stock, and make every stage set selectable. |
| **E. Audio, animation and assets** | Dreamcast CD music is preferred when available. Mobile files supply effects and voices. Some triggers, effects and animations have original-runtime comparisons. Dreamcast models are extracted and render offline. | Audit every sound, voice, song, animation and effect across versions, including indirect triggers, timing and cancellation. Verify loops and fades, document source quality, and integrate the Dreamcast models into live play. |
| **F. Platforms and play** | Windows build, fixed 60 Hz simulation with interpolation, headless 2D GPU measurements at 4K, local hotseat for up to four players, and headless WebAssembly runs. Deterministic replays and loopback UDP lockstep have been tested. | Verify sustained and uncapped 4K performance as rendering is completed, implement wireless local play via mobile devices and online play, build and test the Android arm64 app, and finish the web app’s asset import and PWA checks in a headless browser and on iOS Safari. |
| **G. Documentation and setup** | Cross-version matrix, asset provenance, original-file requirements, and a portable Zig build. Setup unpacks originals and records their hashes. | Complete the evidence and provenance for each version, automate the remaining asset exports, and verify the full setup-to-play process on a clean machine. |

See the [roadmap and dated work log](docs/roadmap.md), [verification results](docs/verification.md), [per-version matrix](docs/version_matrix.md) and [known gaps](docs/known_gaps.md) for the evidence behind each row.

## Build and setup (Windows)

1. Put your [original game files](#which-original-files-do-i-need) in `Original Game Files` beside `setup.cmd`, then run `setup.cmd` from the checkout. If that folder is absent, setup asks for the path. To specify both paths directly from PowerShell, run `.\setup.cmd -GameFiles 'D:\My Game Files' -Cache 'D:\ReNyastered'`.
2. Setup uses Python 3.10 or later if it can import Pillow. Otherwise it downloads and verifies private copies of Python 3.12.10 and Pillow 12.2.0 and caches them in `local\tools\windows`. Setup extracts into `%APPDATA%\ReNyastered\assets` by default and writes `manifest.json` and `setup.log` beside `assets`.
3. Setup builds `build\game\ccr.exe`. The first build downloads and verifies portable Zig 0.14.1, CMake 4.0.3, Ninja 1.12.1, SDL2 2.30.9 and `stb_vorbis.c`. It uses the checkout's `local\tools\windows` and `build\game-zig` folders. Visual Studio C++ Build Tools are unnecessary.
4. Launch `build\game\ccr.exe`. Setup reports which modes are playable from the files in your cache. Pass the `assets` folder as the first argument or set `CCR_ASSETS` if you use a custom cache.

Run `build.cmd --target ccr` to rebuild only the game. For an offline build, set `CCR_TOOL_ARCHIVES` to a folder containing `zig.zip`, `cmake.zip`, `ninja.zip`, `SDL2-2.30.9.tar.gz` and `stb_vorbis.c`. For offline extraction without an existing Python and Pillow installation, include `python-3.12.10-embed-amd64.zip` and `pillow-12.2.0-cp312-cp312-win_amd64.whl` too. The pinned URLs and hashes are in the [build script](tools/build-windows.ps1), [Python setup script](tools/setup-python.ps1), and [CMake configuration](game/CMakeLists.txt).

Runtime options include `CCR_CPU=gba` for GBA-style battle AI, `CCR_LANG=en|fr|de|es|it`, `CCR_HUMANS=1..4`, `CCR_SIZE=3840x2160` and `CCR_FULLSCREEN=1`. Use `CCR_HEADLESS`, `CCR_SHOT` or `CCR_BENCH` for silent runs without a visible window. The C++ tests are CMake targets in `game/`, including `determinism_test`, `battle_full_test`, `cpu_test` and `netplay_test`.

Other platforms: the core and tests cross-compile for Android arm64 (NDK) and build for WebAssembly (Emscripten; see [docs/roadmap.md](docs/roadmap.md)); neither has been run on a device yet.

### Which original files do I need?

**Start with one mobile release.** iPad HD 1.0, iPhone 1.0, 1.0.2, 1.1, iOS 1.1.2, and Android 1.14 or 1.15 each supply the base graphics and audio, 100 main puzzles, and all 25 Battle boards. Setup exports these automatically. The iPad release also supplies the original startup screens, title, menus and HUD.

**For the richest setup today, use iPad HD 1.0, the Dreamcast disc and the GBA ROM.** The iPad archive supplies the menus and HUD, the disc adds stereo CD music and the Dreamcast title artwork, and the GBA ROM adds extra puzzles. Add `DEPuzzle.VMS` for the 25 Dreamcast Express puzzles. Setup accepts a paired `.VMI` when available. Other VMU saves can be collected for future support. An Android APK or a second iOS release is optional.

Put whichever originals you have under `Original Game Files` beside `setup.cmd`, or pass your own folder to setup. Subfolders are optional. Setup searches recursively and accepts loose files or ZIPs, including an enclosing ZIP around a package. Keep the numbered files of each Dreamcast dump together in their own folder or ZIP. Use a fresh cache if you want to test a different file combination in isolation.

| Original | Accepted input | What it adds |
| --- | --- | --- |
| **iOS 1.1 or 1.1.2** | `.ipa` or unpacked `.app`, loose or in a ZIP | Either release supplies Retina gameplay art, mobile audio and both playable modes on its own. |
| **iPad ChuChu Rocket! HD 1.0** | `.ipa` or unpacked `.app`, loose or in a ZIP | Supplies both playable modes, iPad gameplay art, mobile audio, menus, layouts, fonts and startup artwork. |
| **iPhone iOS 1.0 or 1.0.2** | `.ipa` or unpacked `.app`, loose or in a ZIP | Either release supplies phone gameplay art, mobile audio and both playable modes on its own. |
| **Android 1.14 or 1.15** | `.apk` or unpacked APK folder, loose or in a ZIP | Either release supplies phone gameplay art, title and menu art, mobile audio and both playable modes on its own. |
| **Game Boy Advance** | `.gba`, loose or in a ZIP | 2,466 additional puzzles and the GBA versions of the 100 main puzzles, including two board variants. Setup uses the GBA main set when available. Tab in stage select cycles available sets. |
| **Dreamcast** | Numbered `.bin` tracks and their `.cue`, loose or in a ZIP | Provides the original 100 main puzzles, 25 Battle boards, stereo CD music and original Dreamcast art. |
| **Dreamcast VMU DLC** | `.VMS` with its optional paired `.VMI`, loose or in a ZIP | `DEPuzzle` adds 25 playable Express puzzles. Setup also collects the `PuzzleP`, `Cartoony`, `DEChar` and `UFOCow` saves for future support. |

For Dreamcast, a dump whose track checksums match the **USA multilingual ChuChu Rocket!** entry in [Redump.org](https://redump.org/) and contains **19 `.bin` files and one `.cue` file** is the tested layout. [Redump catalog listing](https://data.spludlow.co.uk/redump/redump/Sega%20-%20Dreamcast#:~:text=ChuChu%20Rocket!%20(USA))

### What if I have fewer releases?

- **Phone-only setups** use the available menu and gameplay art. Some HUD panels and effects still require the iPad assets. In Puzzle, use Space or the controller's Start button to run the puzzle.
- **Dreamcast only** supplies both sets of boards and the original models, textures and music. Setup can extract these and compile the executable. To launch with just that disc, the port needs to render the Dreamcast gameplay assets, including the field, characters and HUD. Dreamcast-only play remains planned.
- **Game Boy Advance only** supplies puzzles. A GBA graphics path is still needed for standalone play.
- **All four platforms shipped Battle.** The old Dreamcast requirement came from the stage exporter. Setup now recognizes the byte-identical mobile Battle maps. The GBA Battle boards are still outside the stage importer. `CCR_CPU=gba` enables the port's GBA-style AI with any exported Battle boards and needs no GBA ROM. [Stage format notes](docs/stages.md)
- **Missing optional files** reduce the available art, music or stage sets. The mobile Ogg soundtrack plays if Dreamcast CD tracks are absent. For presentation the port uses the iPad assets when available, then the Android phone art. With neither set, it opens a simple Puzzle and Battle menu.

### Launching a mode directly

The core gameplay exports are automatic. To refresh your cache, rerun setup. To launch a specific mode directly, pass the mode after the asset cache path.

```powershell
$assets = Join-Path $env:APPDATA 'ReNyastered\assets'
.\build\game\ccr.exe "$assets" puzzle
.\build\game\ccr.exe "$assets" battle
```

In Puzzle and Battle, aim with the mouse and press **WASD** or the **arrow keys** to place an arrow in the hovered cell. Mouse dragging also places arrows. On a controller, move with the left stick or D-pad and use the four face buttons in their directional positions, as on Dreamcast.

The default launch plays the iPad startup logos when available. Pass `title` to skip the logos. If you supply a Dreamcast disc, setup also exports its title logo and Start prompt for the desktop build.

The [presentation audit](docs/presentation_audit.md) tracks missing startup screens, effects, and animation. Live gameplay currently uses mobile sprites. The [Dreamcast models](docs/dreamcast_models.md) have been extracted and rendered offline.

## Where each asset and rule comes from
[docs/provenance.md](docs/provenance.md) lists, per asset class and per piece, the version used and the measurements behind the choice (music: Dreamcast CD audio; title logo: Dreamcast; backgrounds and sprites: iPad HD pack; strings: Android resources; rules: each version's own code). [docs/version_matrix.md](docs/version_matrix.md) compares every subsystem across all versions.

## Layout
- `game/` C++ code: portable simulation core (`core/`), the SDL2 app (`app/`), tests (`tests/`), web shell (`web/`)
- `tools/` extractors, the stage registry, and the development-time verification oracles (`tools/oracle/`: your own copies of the original code run in emulators; nothing from them is distributed)
- `docs/` rules specification, verification results, version comparisons, provenance, UI art notes, known gaps
