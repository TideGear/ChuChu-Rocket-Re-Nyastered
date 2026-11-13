# Verification against the original code (Android libccrjni.so, emulated)

Method (tools/oracle/, development only, needs the user's own library, nothing from it is committed or shipped):
the library is loaded into a Unicorn ARM Thumb emulator; its own functions are called with the original setup order
(`SmpTskInit`, `GA_SetGameType(3)`, `FI_InitFieldCollision`, `AR_StartArrowPzManager`, `RO_StartRocketPzManager`,
`MO_PutMousePuzzle`, `CA_PutCatPuzzle`, `AR_PutArrowPz`) and the original frame loop (`SmpColLoopInit`,
`SmpTskExeServer`, `SmpColAnalyze`). Sound entry points are patched to no-ops. The C++ simulation (game/core/sim.hpp)
is compared with it.

## Results (Android 1.15 code vs game/core/sim.hpp)
- Single entity movement: cat and mouse, 200 random walled boards x 400 ticks each: 0 differences (position, cell, heading, every tick).
- Whole puzzle stages (GBA stage data with the stored solution arrows placed at tick 0): save timeline (the tick of every mouse
  reaching a rocket, 3000-tick horizon): **600 of 600 stages identical** (all 100 main puzzles + 500 random GBA user puzzles; includes
  cats, holes, wrapping edges and arrow strikes).

## Rules confirmed by the comparison (puzzle game type 3)
- Speeds: cat 1.0, mouse 1.5 world units per tick; cell = 15.0; at-centre threshold 0.51*speed (cat), 0.52*speed (mouse).
- Heading encoding 0 south, 1 west, 2 north, 3 east; blocked -> try +1 (right), +3 (left), +2 (back); dead end -> no movement.
- Turning snaps the entity to the cell centre. Edge warp: x wraps by 195, z by 150 outside [-7.5, 187.5] x [-7.5, 142.5].
- Cat arrives head-on to an arrow: strike (hit counter +1); second strike deletes the arrow. **The cat still obeys the arrow on the tick
  that destroys it** (the tick uses the collision word read before the strike).
- Cat-mouse contact: registered end-of-tick positions closer than 5.0; the mouse is flagged and is eaten at the start of its next tick.
- Puzzle arrows come from per-direction stock counts; AR_PutArrowPz on a cell that already has an arrow removes it, and places a new one only
  if the direction differs. Puzzle arrows do not expire (the puzzle arrow manager task is a no-op); each carries TTL 600 but nothing counts it down.

## Not yet compared
- Hole deaths and cats entering rockets are exercised implicitly by the stages but their event ticks are not compared separately.
- Battle mode, challenge mode, roulette events, rocket/generator rules, iOS builds, GBA code, Dreamcast code.

## Battle generator (added)
- RNG: MT19937 with `state[0]=seed|1`, `state[i]=69069*state[i-1]`; matches the original for three seeds.
- Generator spawn logs (frame, mouse/cat, cell, direction, special type) for 15 stage/seed pairs over up to 1200 frames: **15 of 15 identical** in `game/tests/gen_test.cpp`
  (details in docs/rules_battle.md).
- Scoreboard (SC_AddScore / SC_CatHasCome): 3000 random operations vs the original, 0 divergences on the score, team and cat-counter fields; C++ golden test `score_test` replays 1500 operations: 0 divergences.
- Roulette selector: 4000 random calls (rank, time bucket, previous outcomes, exclusion) vs the original, 0 mismatches; C++ golden test `roulette_test` replays 3000: all identical. The 128-entry threshold table equals the first 128 `njRandom` draws after seeding.
