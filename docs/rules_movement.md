# Rules spec: movement core (draft, from Android `libccrjni.so`, ARM Thumb)

Source: annotated disassembly (`tools/ExportAsm.java` -> `analysis/asm/*.asm`; literal-pool constants resolved by Ghidra).
Cross-check against iOS 1.1.2 and the other versions is NOT done yet.

## Geometry
- Board 12 columns x 9 rows. `FI_ConvFieldGridToPos`: world position = `(cell + 0.5) * 15.0` on both axes
  (x = column, z = row). One cell = 15.0 world units; positions are floats.
- Angles are 16-bit, 0x4000 per quarter turn; direction index = `(angle >> 14) & 3`. `njSin/njCos` are table lookups on the 16-bit angle.
  `diffAngle` = absolute 16-bit difference.

## Per-cell collision word (`FI_GetFieldCollision`, built by `FI_InitFieldCollision`)
- Wall bits (from the wall layers): `0x40000` = edge above the cell (horizontal edge `i,c`), `0x10000` = edge below (`i+1,c`),
  `0x20000` = edge on the left (vertical edge `r,c`), `0x80000` = edge on the right (`r,c+1`).
- Bits `0x1000` / `0x2000` = a mouse / cat starts here (`MO_PutMousePuzzle`, `CA_PutCatPuzzle` loop over all 12x9 cells and spawn
  one with direction `flags & 3`). Bits 0..1 = direction, bit `0x800` = an arrow is on the cell (`FI_CollisionEntryArrow` /
  `FI_CollisionCancelArrow`); `0xf0000` = any wall.

## Direction correction at a cell (`FI_CheckAndCorrectAngle`)
1. If the cell has an arrow (bit `0x800`), the heading becomes the arrow's direction (`flags & 3`) << 14.
2. If any wall bit is set: test the wall in front of the current heading; if blocked, try heading+1, +2, +3 (a clockwise sequence)
   and take the first free direction (turn-right-first rule). If all four sides are blocked it reports a dead end (returns 1).
3. If there is no wall in front, the heading is kept.

## Speeds (`GA_GetCatSpeed`, `GA_GetMouseSpeed`, `GA_GetCharaSpeed`, `GA_ResetGameParamStr`)
- Game parameter block defaults (`GA_ResetGameParamStr`): `{0, 1.0, 1.0, 0}` -> speed scale 1.0.
- Game types 0..2 (puzzle / challenge / one-player modes): cat speed = `scale_a * scale_b` (both 1.0 by default);
  game types >= 3 (battle): cat speed = the current "chara speed" (`GA_SetCharaSpeed`, changed by the Speed Up / Speed Down events).
- Mouse speed = cat speed * 1.5 (types 0..2) or `chara speed * 1.5` (battle).

## Cat tick (`FUN_00028ffc`)
- Per tick: `speed = GA_GetCatSpeed()`; an animation/phase step `phase_inc = int(speed * 32768 / 12.0)`;
  threshold `speed * 0.51` (clamped to at least 0.01 in modes other than 3..4) decides when the cat is "at" a cell centre
  (distance to the centre via `distanceP2PXZ`).
- At a cell centre: query the collision word, apply arrows (`AR_CatHitArrow`), warps (`FI_CheckWarp`) and the direction rule above,
  then advance `pos += speed * (sin, cos)(heading)`.
- Walk-cycle/animation counters: `* 0.45` decay with a `20.0` wrap, and `* 0.1` decay of a secondary value until below 1.0 (cosmetic).

## Open items
- Exact tick rate / frame time, the mouse tick (`FUN_0003501c`, same structure with `GA_GetMouseSpeed`), pit/rocket entry rules, arrow lifetimes
  (3 per player, the 4th replaces the oldest, fading, cat damage: two hits), the 8 roulette events and their durations, scoring.
- The numeric defaults of Speed Up/Down per event, per game type (still unread: the `RL_Eve_*` handlers pass floats in VFP registers).
- Compare every constant against iOS and the Dreamcast/GBA versions (goal item 1).

## Logic rate (frame timing)
- Android: `renderer.onDrawFrame` sleeps so the 4-frame average interval is at least 16 ms, then calls `jniLib.step(now)` once;
  native `Java_com_sega_ccr_jniLib_step` runs queued input and exactly one `ccr_step()`. No time accumulator: one logic tick per frame,
  capped at ~60 Hz (a slow device slows the game down).
- iOS 1.1.2: `-[CCRViewController awakeFromNib]` sets the display interval to 1/60 s (double `0x3F91111111111111`).
  `-[CCRViewController drawView]` can switch to 1/30 s (`0x3FA1111111111111`, frame interval 2) when AppData flag `+0x27` is set and back
  to 1/60 s when `+0x28` is set; game-state handler `process` (state 0x3A) sets `+0x28`. Which state sets `+0x27` (30 Hz) is still open.
- Conclusion so far: gameplay logic = 60 ticks per second, all timers counted in ticks (arrows 600, Speed Up/Down 480, Mania 600).
  The reimplementation runs a fixed 60 Hz simulation decoupled from rendering (interpolated).
- iOS networking uses GameKit (`m_gk_session`, `m_gk_match`, `-[CCRViewController sendData:ofLength:reliable:]`, peer connection callbacks),
  which is the transport the Android port lacks.
