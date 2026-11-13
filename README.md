# ChuChu Rocket! Re-Nyastered

> **Not affiliated with SEGA.** This is an unofficial, fan-made reimplementation. *ChuChu Rocket!* and all related marks, art, music
> and stages are the property of SEGA. **You must own the original game** (this project reads your own copies of the iOS, Android,
> Game Boy Advance and Dreamcast releases). Please buy them where you still can.

A faithful, best-of-all-versions reimplementation of ChuChu Rocket! This repository is **source code only**: no game data, no original
code, and nothing derived from either. Assets are extracted on your machine from your own files into a local cache.

## Status
Work in progress (roughly a quarter of the planned scope). What exists today:
- A deterministic fixed 60 Hz simulation of puzzle and battle play (`game/core/`), matching the original code of Android 1.15 and iOS 1.1.2 / 1.0.2 / HD tick for tick on all 2,548 puzzle stages, whole battles, scoring, roulette selection and the CPU players ([docs/verification.md](docs/verification.md), [docs/version_matrix.md](docs/version_matrix.md)). Android 1.14 and the Dreamcast build are covered function by function (scoring, roulette selector, speeds); movement and CPU AI for those are still to do.
- A playable slice (`game/app`, SDL2): menu, puzzle and battle modes with CPU opponents, music and effects, resolution-independent (tested headless at up to 8K, any refresh rate) with interpolated rendering.
- Extractors for the iOS/Android packs, Dreamcast disc files, textures, 3D models and CD audio, GBA stage data and the Dreamcast DLC packs including the character skins (`tools/`), plus a master stage registry ([docs/stages.md](docs/stages.md)).
- Rules and comparison notes ([docs/](docs/)), including [docs/provenance.md](docs/provenance.md) (which version each asset class comes from) and [docs/research_check.md](docs/research_check.md).
Not done yet: original-art menus and HUD, Dreamcast 3D models and animation in the game, sound-effect extraction from the Dreamcast, all other modes (challenge, team, Puzzle Edit, 4-player input), netplay, DLC loading in the game, and the Android and web builds.

## Build and setup (Windows)
1. Install the Visual Studio C++ Build Tools, CMake, Ninja and Python 3.12 (extraction only).
2. Run `setup.cmd`, point it at the folder holding your game files; it extracts assets to `%APPDATA%\ReNyastered` and builds.
3. `build.cmd` alone rebuilds the code.

## Layout
- `game/` C++ code (portable simulation core + tests)
- `tools/` extractors, stage registry, development-time verification oracle (`tools/oracle/`, uses your own copy of the Android library in an emulator; nothing from it is distributed)
- `docs/` rules specification, verification results, version comparisons, stage registry
- `docs/provenance.md` which version each asset class and rule comes from, with the measurements behind each choice
