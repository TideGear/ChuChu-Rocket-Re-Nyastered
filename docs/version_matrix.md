# Cross-version comparison matrix (living document, updated 2026-11-13)

Legend: **EXACT** = original code of that build executed in an emulator and compared with the port / the Android reference on recorded scenarios, 0 differences;
**STATIC** = constants/structure compared only; **TODO** = not examined.

| Subsystem | Android 1.15 | Android 1.14 | iOS 1.1.2 | iOS 1.0.2 | iOS HD 1.0 | iOS 1.1 / ORBiT | GBA | Dreamcast |
|---|---|---|---|---|---|---|---|---|
| Puzzle movement/arrows/rockets (save timelines) | EXACT, all 2,548 stages (port vs original) | EXACT, all 2,548 stages (1.14's own libccrjni.so, 3 chunks of 850/850/848, 0 differences) | EXACT, all 2,548 stages | EXACT, all 2,548 stages | EXACT, all 2,548 stages | TODO | EXACT on stage 1 (30 exits, 820 frames; docs/gba_notes.md) | TODO |
| Battle generator + spawn logs | EXACT (15 cases) | n/a | EXACT (spawn log identical on the case compared) | same | same | TODO | TODO | TODO |
| Battle scoring (`SC_AddScore`, `SC_CatHasCome`) | EXACT (1,500 + 3,000 ops) | EXACT 3,000 ops (1.14's own libccrjni.so, `score_diff.py`) | EXACT 3,000 ops | EXACT 3,000 ops | EXACT 3,000 ops | TODO | TODO | EXACT 4,000 ops (SH-4 interpreter, `tools/oracle/dc_score.py`; SC_AddScore chunk 0x8C01E6A0, SC_CatHasCome 0x8C01E712) |
| Roulette selection weights | EXACT selector (3,000 calls) | EXACT selector (4,000 calls, 1.14's own code, `roulette_diff.py`) | table byte-identical (12 rows) | table byte-identical | table byte-identical | TODO | TODO | EXACT selector (3,000 calls, SH-4 interpreter; `tools/oracle/dc_roulette.py`) |
| Whole-battle score timelines + entity trajectories | EXACT 26/26 battles | TODO | covered by CPU placements below | covered | covered | TODO | TODO | TODO |
| CPU players (arrow placements, 50 battles, 2,000-3,000 frames) | EXACT 50/50 | EXACT 10/10 | EXACT 50/50 | EXACT 50/50 | EXACT 50/50 | TODO | TODO | TODO |
| Roulette event handlers (Cat Mania etc.) | partial (see rules_battle.md) | TODO | exercised through CPU runs (Cat Mania rolls identical) | same | same | TODO | TODO | TODO |
| Speeds (cat 1.0, mouse 1.5 puzzle; battle option table) | EXACT | - | EXACT (GA_GetCatSpeed/MouseSpeed 0.25/0.375 with unset option, same as Android) | same | same | TODO | TODO | EXACT getters (cat = base x scale, mouse = 1.5 x that; scales 0.25/0.75/1.0/1.25/**4.0**; `GA_GetCatSpeed` 0x8C016BB0, `GA_GetMouseSpeed` 0x8C016B90, run in the SH-4 interpreter) |
| Frame rate / logic rate | 60 Hz tick (stepped per frame) | - | 60 Hz in the harness; device display interval to confirm | - | - | - | TODO | TODO |

Notes
- iOS and Android builds share one C++ code base compiled for two ABIs; the harnesses (`tools/oracle/`) run each build's own code under Unicorn. Differences found so far are cosmetic: function names (`MC_*` in old iOS builds, `Core::*` later), the idle CPU target marker (0xFF iOS vs 0x10 Android), one extra argument of `GA_SetStageNum`, puzzle arrow placement through `AR_PutArrowPzSp` (iOS) instead of `AR_PutArrowPz` (Android).
- iOS HD 1.0 is non-PIC (absolute literals) and its sin/cos tables are static arrays rather than pointer slots; the harness handles both.
- Everything above is for the English-language, US-region files provided; other regions of the Dreamcast disc (language folders) differ only in text/voice assets so far.

## Dreamcast emulation options (2026-11-13)
- The user's RetroArch install has `flycast_libretro.dll` and the Dreamcast BIOS; `tools/oracle/libretro_host.py` can load it headlessly via ctypes, but the Flycast core requires a hardware renderer (OpenGL/Vulkan/D3D11: `required_hw_api` in its info file) and crashes in `retro_load_game` without one (BIOS copied to local/dcsys, never to the repo, and saves redirected away from the user's RetroArch folders). A hidden GL context would be needed.
- Chosen route instead: a small SH-4 interpreter for the oracle (no graphics, no audio, exact function-level control), plus locating the Dreamcast equivalents of the Android functions by their float constants.

## Dreamcast code location notes (2026-11-13)
- `tools/oracle/sh4.py` (interpreter) and `tools/oracle/sh4dis.py` (disassembler) work on `1ST_READ.BIN` (base 0x8C010000). REA cannot open SH-4.
- Float-constant hits for 195/150/-7.5/187.5/142.5 (0x8C016768..) are a UI/cursor bounds helper, and 15.0 near 0x8C013F80 is a quad/sprite builder: neither is gameplay. Stage files referenced: `pzstage100.dat`, `btstage25.dat`, `chstage25.dat` (strings at 0x8C075CD4..). Next: follow xrefs from those strings to the stage loader, then to the grid/movement code.
- **First Dreamcast function identified**: `GA_OnGameFlag` equivalent at 0x8C016AD4 (checks `GA_GetMode` at 0x8C01907C for modes 12/13, reads option indices from 0x8C052038, then sets two scale values). Tables: int table @0x8C075D60 = {0x10000, 0x20000, 0x30000}; battle speed scale table @0x8C075D6C = **{0.25, 0.75, 1.0, 1.25, 4.0}** (Android/iOS: {0.25, 0.75, 1.0, 1.25, 2.0}) — a measured Dreamcast difference to become a version option. Table @0x8C075D4C = {25, 25, 25, 150, 1} (meaning to be determined).
- The SH-4 interpreter now executes real Dreamcast code: `tools/oracle/dc_ga_flag.py` runs `GA_OnGameFlag` for options 0..4 and gets scales 0.25 / 0.75 / 1.0 / 1.25 / **4.0** (Android/iOS: last = 2.0). Next: movement, scoring and roulette selector functions.
