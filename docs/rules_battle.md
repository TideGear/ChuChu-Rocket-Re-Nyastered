# Rules spec: battle mode generators (Android 1.15, verified against the emulated original)

## Game types and modes (from `FourBattleInit`, `PuzzleInit`)
- Free-for-all battle: `GA_SetGameType(0)`, `Core::changeGlobalMode(0xC)`. Team battle: type 1, mode 0xD. Puzzle: type 3, mode 0xF.
- Speed: for types 0..2 cat speed = scaleA * scaleB (both 1.0 by default) and mouse speed = 1.5 * that; for types >= 3 the speed is the "chara speed"
  set by events. `GA_OnGameFlag` adjusts the speed scale from game settings for modes 12, 13 and 16 (settings-dependent table; values not yet extracted).

## Battle stage format
ASCII 25x19 maps (`BTSTAGE25.DAT`, 25 stages): cells are `char - 0x40`. Tile codes in battle stages: 1..4 player rockets, 5..8 mouse generators facing
south/west/north/east (`code - 5` = heading), 0 floor. Generators are listed in row-major order.

## RNG (BHLib_SeedRNG / GetRandomNumber / njRandom)
MT19937; seeding: `state[0] = seed | 1`, `state[i] = 69069 * state[i-1]` (mod 2^32); output is the standard tempered word. `njRandom` = (float)word / 2^32 (float32).
Verified for several seeds (and via the spawn logs below).

## Generator (per frame, each generator in list order) — `game/core/generator.hpp`
Parameters (free-for-all): caps mice 100, special-1 2, special-2 1; probabilities spawn 0.0125, special-1 0.01, special-2 0.1, cat 0.05.
State: prohibit flags (1 no normal mice, 2 no special 1, 4 no special 2, 8 no cats), locks (15 frames) per special type, alive counts, `catOut`, `timer`.
1. Locks decrement once per frame.
2. If cats are allowed, no cat is out and `timer > 299`: spawn a cat at this generator (no RNG used), `catOut = true`.
3. If the alive mouse count >= cap: stop for this frame.
4. `r = njRandom()`; if `r >= 0.0125` skip this generator. Else `r2 = njRandom()`:
   - special mouse 1 if allowed (flag 2 clear, lock 0, count < 2) and `r2 < 0.01` (lock = 15);
   - else special mouse 2 if allowed (flag 4 clear, lock 0, count < 1) and `r2 < 0.01 + 0.1` (lock = 15);
   - else a cat if allowed (flag 8 clear, none out) and `r2 < 0.11 + 0.05`;
   - else a normal mouse unless flag 1 is set.
5. End of frame: `timer = catOut ? 0 : timer + 1`. `catOut` is cleared by the game when the cat is lost (`GE_CatIsLost`).
Mouse type argument to `MO_PutMouse`: 0 normal, 1 / 2 the special mice.

## Verification
`tools/oracle/make_spawn_golden.py` records the original's spawn log (frame, type, cell, direction) for 15 stage/seed pairs over 1200 frames plus the per-frame externally driven state;
`game/tests/gen_test.cpp` replays them: **15 of 15 identical** (up to the end-of-round event). At the end of the round (state seen: all prohibit flags set, all mice removed, cats at every generator)
the original does something not covered by the generator: round timer / end sequence, not yet analysed.

## Open
- The end-of-round sequence, rocket scoring, roulette trigger conditions, cursor/arrow rules for four players, CPU opponents, the team-battle and mode-dependent parameter changes
  (`GE_StartGenerator4Manager` changes the block for mode 0xE and for stage 3 of 5).

## Rocket entry and scoring (Android mouse tick, `SC_AddScore`, `SC_CatHasCome`) — `game/core/score.hpp`
- A mouse that reaches a rocket cell at its centre: the **owner is the low two bits of the cell's collision word** (rocket 1..4 -> player 0..3);
  the rocket-mouse counter is incremented and `SC_AddScore(owner, value[type])` is called with value **normal mouse 1, special type 1 = 50 (golden mouse), special type 2 = 1**;
  a type-2 mouse also spins the roulette for that owner (`RL_RollRoulette4(owner)`).
- `SC_AddScore(p, d)`: `score[p] += d` and `team[p & 1] += d`, each floored at 0 and capped at 999. In free-for-all type 0 the demerit uses the player's score, in team mode the team score.
- `SC_CatHasCome(p)` (a cat enters player p's rocket): `score[p] += (score[p] + 2) / -3` (integer division truncating toward zero, i.e. the cat takes a third, rounded up) and the same for `team[p & 1]`;
  a per-team counter (initialised to 20) is decremented, floored at 0. `SC_GetCatDemerit(p) = (score + 2) / 3`.
- Another routine sorts the scores for ranking (indices 4..7 and 10..11 of the score array hold ranks): not ported yet.
- Verification: 1500 random operations recorded from the original (`tools/oracle/make_score_golden.py`) replayed in `game/tests/score_test.cpp`: 0 divergences (and 3000 random operations in `score_diff.py`).

## Roulette (type-2 special mouse enters a rocket -> `RL_RollRoulette4(owner)`)
`game/core/roulette.hpp`; verified: **3000 random selector calls identical** (`tools/oracle/roulette_diff.py`, `game/tests/roulette_test.cpp`).
- **Outcome numbering** (from the dispatch table in the Android roulette exec): 0 Cat Mania, 1 Mouse Mania, 2 Speed Up, 3 Speed Down, 4 Place Arrows Again (deletes all arrows),
  5 Everybody Move (rockets shuffled, `RO_ShuffleRockets`), 6 Cat Attack (cursors locked, speed 0, all spawning blocked), 7 Mouse Monopoly (`MO_StartHitorijime`, special spawn blocked, mouse fever).
- **Start of battle** (`RL_StartRoulette4Manager`): fills a 128-entry threshold table with 128 consecutive `njRandom()` draws; the previous two outcomes start at -1.
- **Selection**: weight row = (remaining BCD time bucket: `<= 0x2fff`, `<= 0xffff`, otherwise) x (the player's score rank 0..3, from the scoreboard's rank array); cumulative weights of outcomes 0..6
  are compared with `table[(gameTime + attempt) & 127]` (outcome 7 is the remainder); up to 128 attempts; an attempt is rejected if the outcome equals the excluded one, or (outcomes 2..5) repeats the previous outcome,
  or (outcomes 0, 1, 6, 7) would be the same outcome three times in a row. Weights are in `core/roulette.hpp`; late-game rows favour Cat Mania for the leader (35%) and trailing players get different mixes.
- Event durations and effects (frames): see docs/rules_events.md; handler identities above refine that table (outcome 2 sets speed 2.0 and prohibits special mouse 2; outcome 6 locks cursors and sets speed 0).

## Battle speed setting (GA_OnGameFlag, modes 12 and 13)
`GA_OnGameFlag` sets the second speed scale from a settings value (`Core::getOptions(3)`): multiplier table **[0.25, 0.75, 1.0, 1.25, 2.0]** for modes 12/13
(another table [0.5, 1.5, 2.0, 2.5, 4.0] is used for mode 16). With the unset (zero) option the original reports cat 0.25 and mouse 0.375 per tick; at level 2 it is the same as puzzle speed
(cat 1.0, mouse 1.5). The default level and the first settings value (`getOptions(1)`, selects an int table at 0x732b8 starting 0x10000) are still to be determined.

## Whole-battle differential (2026-11-12, `tools/oracle/make_battle_golden.py`, `game/tests/battle_full_test.cpp`)
26 recorded battles (25 Dreamcast battle stages + 1 repeat, 3000 frames, scripted arrow placements via the original `AR_PutArrow`, no roulette handler). Compared: frame of every score change up to the first roulette trigger.
- Battle speed: in the original harness (`GA_OnGameFlag`, mode 0xC, speed option unset) cat 0.25 / mouse 0.375 per tick (BattleGame::baseScale = 0.25).
- Mice and cats spawned in a frame first move on the next frame (found by measurement; cuts the first-score offset from +1 frame to 0).
- Mouse destruction (`FUN_00035004`, decrements the per-type counter) runs 1 frame after our eaten event; positions of eaten mice match exactly (82.5,85.9 at frame 634 etc.).
- Further measured rules (all in `game/core/battle.hpp`, `game/core/sim.hpp`):
  - Arrow placement (`FUN_0002859c`): any cell with an object bit (rocket, hole, generator 0x1000 or **any arrow**) refuses in the emulated setup (a flagged branch that would rotate your own arrow exists; flag byte is 0 in the harness, so `rotateOwn` is off by default - to be confirmed for real play). 3 slots per player, round-robin ring, new arrow frees the slot at the ring index, TTL 600.
  - **A cat that enters a rocket or falls into a hole does not leave the game**: 30-tick animation (counter 1.0 += 1.0 * -0.033333335f per tick, done when <= 0; Android `FUN_000292c0`), then it respawns at generator `floor(n * 0.99f * njRandom())` (same RNG stream as the generator) with that generator's heading. Rocket entry scores `SC_CatHasCome`; a hole costs nothing. The cat stays "out" for the generator (no forced cat).
  - Task order inside a frame: generator first, then entities (mouse/cat movement and contacts), spawned entities first move on the next frame.
  - A mouse is destroyed (per-type counters decremented) one frame after the eat/rocket event.
- **Result: 26 of 26 recorded battles identical** (score timelines up to the first roulette trigger, spawn logs, and per-frame entity positions on the cases inspected), plus the earlier generator/score/roulette goldens.
- Open: roulette trigger conditions (the emulated original rolls only sometimes after a type-2 mouse), roulette event handlers beyond the constants, end of round, CPU players.
