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
