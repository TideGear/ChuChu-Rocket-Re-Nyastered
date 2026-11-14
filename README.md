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

**Not done yet**: the in-game HUD and start countdown, the roulette wheel and most character animations, Challenge, Team Battle, Puzzle Edit, stage select, options and unlockables,
DLC and skin loading in play, GBA and Dreamcast CPU-AI completion, real cross-machine netplay screens, sound-effect extraction from the Dreamcast, the Android app and a browser-import flow.

## Build and setup (Windows)
1. Install the Visual Studio C++ Build Tools, CMake, Ninja and Python 3.12 (extraction only; Pillow and NumPy for the tools).
2. Run `setup.cmd` and point it at the folder holding your game files. It finds and hash-verifies them, extracts assets to a local cache and builds. Any one complete version is enough to play; the others add unique content.
3. `build.cmd` rebuilds the code. Run `build\game\ccr.exe`; it finds the cache by itself (or pass the asset folder, or set `CCR_ASSETS`). Useful switches: `CCR_CPU=gba` (battle with the GBA CPU players),`CCR_LANG=en|fr|de|es|it`, `CCR_HUMANS=1..4`, `CCR_SIZE=3840x2160`, `CCR_FULLSCREEN=1`.
4. Tests never open a window or play audio when run headless (`CCR_HEADLESS`, `CCR_SHOT`, `CCR_BENCH`); the C++ tests are CMake targets in `game/` (`determinism_test`, `battle_full_test`, `cpu_test`, `netplay_test`, ...).

Other platforms: the core and tests cross-compile for Android arm64 (NDK) and build for WebAssembly (Emscripten; see [docs/roadmap.md](docs/roadmap.md)); neither has been run on a device yet.

## Where each asset and rule comes from
[docs/provenance.md](docs/provenance.md) lists, per asset class and per piece, the version used and the measurements behind the choice (music: Dreamcast CD audio; title logo: Dreamcast; backgrounds and sprites: iPad HD pack; strings: Android resources; rules: each version's own code). [docs/version_matrix.md](docs/version_matrix.md) compares every subsystem across all versions.

## Layout
- `game/` C++ code: portable simulation core (`core/`), the SDL2 app (`app/`), tests (`tests/`), web shell (`web/`)
- `tools/` extractors, the stage registry, and the development-time verification oracles (`tools/oracle/`: your own copies of the original code run in emulators; nothing from them is distributed)
- `docs/` rules specification, verification results, version comparisons, provenance, UI art notes, known gaps
