# Asset handling and distribution

Re-Nyastered is an unofficial fan project. SEGA and the other rights holders retain their rights in the original games. The project uses the original title to identify the game it reimplements. Keep the unofficial-project notice with any release and use project-created branding for public release art and app icons.

## Local development

- Keep lawfully obtained originals in `Original Game Files/` or an external folder. Setup normally writes its extracted assets, original-code analysis inputs and reports to `%APPDATA%\ReNyastered`. Repository-local research and build outputs belong under the ignored `local/`, `analysis/` and `build/` folders.
- Keep development captures under `local/`. The three in-game screenshots in `docs/screenshots/` illustrate the port’s progress in the README. The game can capture them from your own exported assets using `CCR_SHOT` and `CCR_TICKS`. Keep decompiler dumps, extracted art, music, text, boards, saves and game binaries local. Commit implementation code, tools and documentation of behavior and provenance.
- `RN_WEB_ASSETS` embeds local game data in the browser build output. Use it only for local testing. For a hosted build, configure with `RN_WEB_ASSETS` empty and check the entire publish directory for preloaded data, copied caches and icons derived from original artwork. Browser-side asset import is still planned.

## Before distributing a release

- Review the outgoing Git history as well as the current tree. Removing an asset from the latest revision leaves it reachable through earlier commits.
- Review the source and release contents for copied game material. Keep third-party materials that have redistribution permission with their required notices. Choose a license for the project's own code before describing it as open source. Third-party dependency licenses cover their respective components.
- The pinned native build uses SDL2 2.30.9 under its zlib license and `stb_vorbis.c` under a choice of MIT or the public-domain dedication in its source footer. Preserve the applicable notices when redistributing these components. The build fetches Zig, CMake and Ninja separately. Review their notices if shipping those tools with a release. [SDL2 2.30.9 license](https://github.com/libsdl-org/SDL/blob/release-2.30.9/LICENSE.txt) · [Pinned stb_vorbis source and license](https://github.com/nothings/stb/blob/ae721c50eaf761660b4f90cc590453cdb0c2acd0/stb_vorbis.c)
