# ChuChu Rocket! Re-Nyastered

> **Not affiliated with SEGA.** This is an unofficial, fan-made reimplementation. *ChuChu Rocket!* and all related marks, art, music
> and stages are the property of SEGA. **You must own the original game** (this project reads your own copies of the iOS, Android,
> Game Boy Advance and Dreamcast releases). Please buy them where you still can.

A faithful, best-of-all-versions reimplementation of ChuChu Rocket! This repository is **source code only**: no game data, no original
code, and nothing derived from either. Assets are extracted on your machine from your own files into a local cache.

## Status
Work in progress. What exists today:
- A deterministic 60 Hz puzzle simulation (`game/core/sim.hpp`) that matches the original game's code tick for tick on the stages tested
  (see [docs/verification.md](docs/verification.md)).
- Extractors for the iOS/Android resource packs, Dreamcast disc files/textures/CD audio, GBA stage data and the Dreamcast DLC
  (`tools/extract_all.py`), plus a master stage registry ([docs/stages.md](docs/stages.md)).
- Rules notes reverse-engineered from the originals ([docs/](docs/)).
- A development viewer (`game/viewer`, SDL2) that draws a puzzle with the extracted tile atlas on the verified simulation (`viewer <gba_stages.bin> <atlas dir> [stage]`; characters are placeholders there).
Not done yet: the playable game (renderer, UI, audio, menus, netplay) and the Android/web builds.

## Build and setup (Windows)
1. Install the Visual Studio C++ Build Tools, CMake, Ninja and Python 3.12 (extraction only).
2. Run `setup.cmd`, point it at the folder holding your game files; it extracts assets to `%APPDATA%\ReNyastered` and builds.
3. `build.cmd` alone rebuilds the code.

## Layout
- `game/` C++ code (portable simulation core + tests)
- `tools/` extractors, stage registry, development-time verification oracle (`tools/oracle/`, uses your own copy of the Android library in an emulator; nothing from it is distributed)
- `docs/` rules specification, verification results, version comparisons, stage registry
