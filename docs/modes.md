# Mode and screen differences between versions (first pass)

Method: compared C++ `*Screen` / `*Menu` class symbols in the Ghidra decompiles
(`analysis/decomp/`). Class presence suggests a mode or feature exists, but each one still needs
confirming in the code and in play. Dreamcast and GBA are NOT covered yet (different engine, no symbols).

| Screen/class | Android 1.14/1.15 | iOS 1.0.2 | iOS HD 1.0 | iOS 1.1.2 |
|---|---|---|---|---|
| EditorGameScreen (Puzzle Edit) | yes | no | no | yes |
| CommsTypeMenu (choose connection type) | yes | no | no | yes |
| UpsellScreen | yes | yes | no | yes |
| DownloadScreen (downloaded puzzles) | yes | no | no | no (not found) |
| NetNameDispFontScreen | yes | no | no | no (not found) |
| NetFourBattleGameScreen (network battle) | yes | yes | yes | yes |
| GameCenterScreen | yes | yes | yes | yes |
| Split{Four,Team}BattleGameScreen, TeamBattleGameScreen | yes | yes | yes | yes |

Common to all: Title, Menu, PlayerSelect, StageSelect, ChallengeSelect, PuzzleGame, ChallengeGame, FourBattle,
TeamBattle, Help, HelpOptions, Credits, End, Sega, SonicTeam.

## Observations
- The puzzle editor and the connection-type menu appear only in iOS 1.1.x and Android, not in 1.0.2 or HD 1.0.
- Android has two classes no iOS build has: `DownloadScreen` and `NetNameDispFontScreen`. `FI_GetEdDlPuzzleFromVM`
  is a stub returning 1, so the Dreamcast downloaded-puzzle path appears present but disabled. Needs a closer look.
- The Android build contains network-battle classes but ships no transport (see the netplay notes).
- `NetFourBattleGameScreen` exists in every iOS build, including 1.0.2 and HD 1.0.

## TODO
Audit the Dreamcast (`1ST_READ.BIN`, `2_DP.BIN`) and GBA for modes, including Stage Challenge and team play.

## Local multiplayer input (app, 2026-11-13)
Battle mode supports 1-4 human players: `CCR_HUMANS=1..4` makes that many slots human (the rest CPU level 3; levels via the 5th argument). Mouse = player 1 (click places, click again rotates); keyboard sets WASD+Q (P1), IJKL+U (P2), keypad 8/4/5/6+0 (P3); gamepads in connection order (D-pad moves the cursor, Dreamcast-style face buttons Y/A/X/B place up/down/left/right). Verified headless with injected keys (player 2 moved and placed two arrows; screenshot checked). Gamepad path compiled but not exercised (no pad attached). Not done: a player-select screen (humans are chosen by the environment variable), puzzle co-op, Challenge/Team modes.

## Challenge mode, first reading (Android 1.15, 2026-11-14; not implemented, the rules below are NOT yet derived)
- Data: 25 challenge stages (`CHSTAGE25.DAT` on the Dreamcast), saved per stage as a best time (`Data::getChallengeTime`, 25 words), cleared flags (`isChallengeCleared`, `clearChallenge`), `isChallengeFinalAvailable` (all earlier stages cleared: the 25th stage, index 0x18, is the final one) and `isChallengeClearedAll`.
- `ChallengeInit` (0x30a6c) sets `GA_SetGameType(2)` and `Core::changeGlobalMode(0xe)`. `ChallengeGameScreen::process` dispatches the screen states 0x3e (load), 0x3f (fade), 0x40 (play: calls `ChallengeLoop` unless paused), 0x41 (exit); the play state reads `getChallengeInternalMode()` and treats values 5 and 6 specially (a countdown field at +0xa20 that triggers a handler).
- `ChallengeLoop` (0x30388, 7-phase jump table, 1,574 bytes) mixes the puzzle and battle engines: its phases call `SC_InitScoreBoard`, `RO_StartRocket4Manager` + `CU_StartCursorCh0213Manager` (a battle-style set-up) or `RO_StartRocketPzManager` + `MO_PutMousePuzzle` + `CA_PutCatPuzzle` + `CU_StartCursorCh02Manager` (a puzzle-style set-up), `GE_StartGenerator4Manager`, `GE_SetProhibitGenerator`, `GE_SetCatFever`, `RL_StartRoulette4Manager`, `TI_SetBCDTimer`/`TI_CountDownBCDTimer` with the same 5..0 s tick sounds as the battle, `CA_CatHallIn`, `MO_GetEatenMouse`, `MO_GetRocketMouse`, `MO_GetKilledMouse`, `CA_CatRocketIn`, `RO_GoGoRocketPz`, `clearChallenge` + `save`, and `GA_GetStageNum() == 0x18` branches; the stage's challenge type (`GetChallengeType`), mouse count, cat/team scores (`getChallengeCatScore(i)`, `getChallengeTeamScore(i)`) and internal mode (`getChallengeInternalMode`, values 3, 5, 6 seen in input code) select between those set-ups. Human arrow placement in the challenge is allowed only in internal mode 3 (`ChallengeGameScreen::handleInput` -> `AR_PutArrow(0, ...)`).
- To do: decode the seven phase bodies and the table that fills type/internal mode per stage, then port and diff-test against the Android code like the battle.

### Challenge set-up, decoded further (Android 1.15 `ChallengeLoop` phase 0 at 0x304ac, 2026-11-14)
- The jump table of `ChallengeLoop` (at 0x7332c): phase 0 -> 0x304ac (set-up), 1 -> 0x30552, 2 -> 0x305a2, 3 -> 0x3065a, 4 -> 0x305c4, 5 -> 0x305f8, 6 -> 0x30460 (running; the common running code at 0x30428 steps the collision/task server, counts a 0x78-tick intro and plays song 0xc when it ends).
- Phase 0: `setDeformerFlag(1)`, `GA_OnGameFlag`, `SmpTskInit`, `createPlayfield` with the stage (`FI_GetFIPSptr(2, stage)`), `GA_SetCharaSpeed(0)`, `FI_InitFieldCollision`, then **the challenge type is `stage index mod 5`** (`__aeabi_idivmod(stage, 5)`, stored as the internal mode read by `getChallengeInternalMode`), except the last stage (index = `GA_GetStageNumberTotal(2) - 1` = 24), which branches to its own set-up (0x308ac); the countdown is `TI_SetBCDTimer(0x3000)` (30 s by the BCD layout noted in rules_events.md).
- A second jump table (at 0x73348) by internal mode: modes 0, 1, 2 -> 0x3078c (`RO_StartRocketPzManager`, `MO_PutMousePuzzle`, `CA_PutCatPuzzle`, `CU_StartCursorCh02Manager`, `AR_StartArrow4Manager`: puzzle-style set-up with the stage's mice and cats), mode 3 -> 0x3077a (`SC_InitScoreBoard`, `RO_StartRocketPzManager`, `CU_StartCursorCh02Manager`, `AR_StartArrow4Manager`: only rocket, cursor and arrows, the generator supplies the rest), modes 4 and 5 -> 0x30700 (`SC_InitScoreBoard`, `RO_StartRocket4Manager`, `CU_StartCursorCh0213Manager`, `AR_StartArrow4Manager`: battle-style with four rockets and four cursors). Later in the phase the generator (`GE_StartGenerator4Manager`, `GE_SetProhibitGenerator`, `GE_SetCatFever`) is started for modes 3, 4 and 5 only, and `RL_StartRoulette4Manager` appears in one branch.
- Running phase: the 5..0 s tick sounds `ChuSECall(0x13 - seconds)` as in the battle, at 0 `PA_SetPauseDisable`, `GA_OffGameFlag` and a result function (`FUN_0002fb54`) chosen by internal mode (value 4 goes to 0x30a00, values above 4 to 0x3096a).
- Still to decode: what ends each mode successfully (the rules for 0..2 vs 3 vs 4/5, score targets `getChallengeCatScore` / `getChallengeTeamScore`, mouse count `getChallengeMouseCount`), the stage-24 set-up at 0x308ac, and the result functions. No Challenge code is ported yet.

### Challenge win/lose branches (Android 1.15 `ChallengeLoop` running phase, read from the disassembly 0x30428..0x30a20; the mapping of each branch to a stage type is NOT yet established)
- Outcome functions: success `FUN_0002fb24` (0x2fb24: `PA_SetPauseDisable`, `GA_OffGameFlag`, `ChuSECall(0x15)`, `ChuSECall(0x1c)`, phase := 4), failure `FUN_0002fb54` (0x2fb54: same two calls, `ChuSECall(0x1b)`, phase := 6, input data 0 := -1). Phase 4 (0x305c4) and phase 5 (0x305f8) then run the result display (`clearChallenge(stage, BCD time left)` + `save`, `isChallengeClearedAll`, random bonus value from the sum of the 25 best times, the 25th stage's special path) and phase 6 the fail return.
- Timer: `TI_CountDownBCDTimer` each tick except while the roulette runs in internal mode 5; at 5..0 s the tick sounds play; at 0 the game ends: modes 0..3 -> failure (`FUN_0002fb54`); mode 4 -> success if score field +0x30 > +0x34 (0x30a00), else failure; mode 5 -> success if field +0x20 > +0x24 (0x3096a), else failure. The score-board object is the one behind GOT slot 0x3a4.
- Mouse-based branches seen: (a) rocket mice count equals the stored target (`MO_GetRocketMouse` == value at +8 of the mode block) -> `RO_GoGoRocketPz` + success; a killed mouse (`MO_GetKilledMouse`) or a cat entering a rocket (`CA_CatRocketIn`) -> failure with `FocusInit` on the offender and `GA_SetCharaSpeed(0)`; (b) `MO_GetEatenMouse` differs from the stored count -> failure (0x309bc: `ChuSECall(0x1b)`, `ChuSECall(0x1c)`, phase := 5); a cat `CA_CatHallIn` (cat in a hole) -> failure with focus; `MO_GetHoleInMouse` is checked too; (c) score field +0x30 non-zero and +0x34 zero -> success (the generator modes). Which of these belongs to which stage type (mod 5) is still to be mapped.

### Challenge: stage type -> rule (Android 1.15, third jump table of `ChallengeLoop` at 0x73360, read 2026-11-14)
Phases: 0 set-up, 1 intro banner (waits for a tap/flag or 360 ticks, then `ChuSECall(0x10)`), 2 ready/go countdown (sounds 0x11 at 36/72/108-tick marks: values 0x48, 0x6c, 0x24 of a counter), 3 play, 4 success display (210-frame counter, then phase 5), 5 result (`clearChallenge(stage, BCD time left)`, `save`, tap, next stage = (stage + 1) mod 25, the last stage branches to the final/ending path), 6 failure display. In phase 3 the stage type (stage index mod 5) selects the check:
| type | check each tick | outcome |
|---|---|---|
| 0, 1 | `MO_GetRocketMouse()` equals the target count stored in the mode block (+8) | success (`RO_GoGoRocketPz`); a killed mouse (`MO_GetKilledMouse`) or a cat entering a rocket (`CA_CatRocketIn`) -> failure |
| 2 | `MO_GetEatenMouse()` equals the target stored in the block (+8) | success (phase 5, sounds 0x1b, 0x1c); a cat falling into a hole (`CA_CatHallIn`) or a mouse in a hole (`MO_GetHoleInMouse`) -> failure |
| 3 | player score (score object +0x00) >= 100 | success (score clamped to 100, `RO_GoGoRocketPz`) |
| 4 | score fields +0x30 non-zero and +0x34 zero | success; at time out success if +0x30 > +0x34, else failure |
| 5 | roulette battle: the timer does not run while the roulette spins | at time out success if +0x20 > +0x24, else failure |
Time out in types 0..3 is failure. The meaning of the score-object fields (+0x00, +0x20/+0x24, +0x30/+0x34) and the target values come from the stage data and are not yet mapped; the success/failure labels of the sound ids are inferred from which function sets phase 4 (success) or phase 6 (failure).

### Challenge input and targets (Android 1.15 `ChallengeGameScreen::handleInput` and `ChallengeLoop` phase 0, read 2026-11-14)
- **Target counts:** for the types that use the puzzle set-up the target stored in the mode block (+8) is the return value of `MO_PutMousePuzzle()`, i.e. the number of mice the stage puts on the board; the rocket-count and eaten-count rules above compare against it.
- **The player does not place arrows in most Challenge types.** `handleInput` (touch down/up/move, pause buttons) only drives the arrow origin/preview/`AR_PutArrow` when `getChallengeInternalMode() == 3` (so the arrow-placing type is stage index mod 5 == 3). The other types are choice or timing games: in type 1 a tap sets input flag 1; in types 5 and 6 two on-screen buttons (rects 0xe and 0xf) choose one of two answers (`Input::setData(0, 0 or 1)`, then input flag 2 or 8) and the tap position is remembered; types 0, 2 and 4 take no tap beyond pause. The checks in `ChallengeLoop` read those flags (`getFlag(8)`, `getFlag(2)`, `getFlag(1)`, `getFlag(4)`), so Challenge is a set of watch-and-answer scenarios on top of the puzzle/battle engine, not a plain puzzle: porting it needs the flag handling of each type in the loop (0x3047c..0x304aa shows flag 8 and flag 2 handling with `ChuSECall(2)` and `setData(10, 1)`), which is not decoded yet.
