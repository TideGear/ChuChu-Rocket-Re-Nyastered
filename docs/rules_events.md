# Rules spec: battle roulette events (draft, iOS 1.1.2 `CCR`, ARM Thumb-2)

Evidence: annotated disassembly (`analysis/asm/ios_events.asm`, made with `tools/ExportAsm.java`). Event handlers run once per
game frame; counters below are frames. Frame rate is not yet measured (60 fps assumed, to be confirmed from the main loop).

| Event (internal name) | Effect set on start | Duration | Notes |
|---|---|---|---|
| Speed Down (`RL_Eve_SpeedDown`/`Dest`) | `GA_SetCharaSpeed(0.3)` | 0x1E0 = 480 frames | on end speed returns to 1.0 (`RL_Eve_SpeedDownDest`) |
| Speed Up (`RL_Eve_SpeedUp`/`Dest`) | `GA_SetCharaSpeed(2.0)`, `GE_SetProhibitGenerator(4)` | 480 frames | generators un-blocked (`SetProhibitGenerator(0)`) at frame 0x12C = 300; speed back to 1.0 at the end |
| Mouse Mania / "Chu2 Fever" (`RL_Eve_Chu2Fever`) | `TI timer 2`, `GE_SetProhibitGenerator(0xC)`, `GE_SetChu2Fever()` | 0x258 = 600 frames | `GE_CancelChu2Fever` on end |
| Cat Mania / "Neko Fever" (`RL_Eve_NekoFever`) | `TI timer 3`, `GE_SetProhibitGenerator(0xF)`, `GE_SetCatFever()` | 0x258 = 600 frames, scaled in some game types by a table value (multiplier 2.0 seen) | a cat sound plays every 16 frames with ~30% chance (random < 0.3) |
| Mouse Monopoly (`RL_Eve_Hitorijime`) | not yet read | not yet read | `MO_StartHitorijime` / `MO_StopHitorijime` |
| Cat Attack (`RL_Eve_NekoPresent`) | not yet read | not yet read | cat intro animation `RL_Eve_NekoPreEnsyutsu*` |
| Everybody Move (`RL_Eve_Hikkoshi`) | not yet read | not yet read | rockets move; `RO_ShuffleRockets` |
| Place Arrows Again (`RL_Eve_Replace`) | not yet read | not yet read | |

Outcome index -> event mapping and the roulette weights are in `docs/roulette.md` (index 5 calls `RO_GetNetShuffleRocketsAssign`,
i.e. the rocket shuffle). The index order of the other seven still has to be read from the `RL_RouletteExec` switch table.

## Version audit (iOS)
Event, timer, generator and game-state functions (40 compared: `RL_Eve_*`, `GA_*`, `TI_*`, `GE_*`) have identical compare/move
immediates and float constants in iOS 1.0.2, HD 1.0 and 1.1.2. The only flagged difference is `GE_Generator4Exe` in HD 1.0
(identical constant set, different order or count: needs a closer look). Android and the Dreamcast/GBA code are not yet compared.

## Roulette presentation (what the player sees; not yet in the app, 2026-11-13)
In the original a pink "?" mouse entering a rocket starts the roulette: `RL_RollRoulette4` creates a roulette task that flies in over the rocket (30 ticks), spins (90 ticks), then the event task starts at tick 121 (the app's simulation does all of this; only the picture is missing). The wheel is drawn by `RL_RouletteDraw2D` / `RL_RouletteDrawPriority` -> `Render::drawRoulette(x, y, z, angle)` at the rocket's position, rotating with the task's angle field (+0x20 * constants), as a **3D object** (`set3DView`, textures from the battle texture space; the Dreamcast has `BATTLEMODELS_sphere_tx` and `EFFECT_*`/`GAMEVOICE_*` banks). The event announcement art/voice, the cat pre-show of "Cat Mania" (`RL_Eve_NekoPreEnsyutsuDraw2D/3D`) and the per-event effects are separate draw callbacks. None of this is drawn in the app yet, so a roulette currently shows only its effect (music change, sound 10, behaviour), which is a gap.
