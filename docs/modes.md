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
