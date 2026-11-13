# Battle roulette: findings so far

Sources: Android `libccrjni.so` (1.14, 1.15) and iOS `CCR` (1.0.2, HD 1.0, 1.1, 1.1.2), ARM decompiles in `analysis/decomp/`.
Dreamcast and GBA have NOT been audited yet.

## Selector
- Android `FUN_0003c2bc`, iOS `RL_GetDeme(int player, int exclude)`; called from `RL_RollRoulette4`.
- Picks one of 8 outcomes (0..7) by walking a row of 8 weights: cumulative sum is compared with a
  threshold read from a 128-entry random table indexed by `(TI_GetGameTime() + attempt) & 0x7f`.
- Up to 128 re-rolls: an outcome equal to `exclude` is rejected (so the same result is not repeated),
  and some outcomes (indices 2..5) are rejected when they match a stored "last" value.
- The weight table is chosen by remaining time (`TI_GetBCDTime`): iOS thresholds `< 0x3000` and
  `< 0x10000`. Which row is used comes from a per-player lookup.
- Outcome 5 calls `RO_GetNetShuffleRocketsAssign` (rocket shuffle). The other outcome meanings are still unmapped.

## Weight table: 12 rows x 8 weights, each row sums to 1.0
Same 12 rows in every mobile build. Verified by scanning all six binaries
(`analysis/roulette_tables.json`):

| Build | Table offset | Rows identical to iOS 1.1.2 |
|---|---|---|
| iOS 1.0.2 / HD 1.0 / 1.1 / 1.1.2 | various | yes, same order |
| Android 1.14 / 1.15 | 0x6a614 | same 12 rows, rotated by 4 |

Android's row order differs (a rotation), so the per-player row index mapping must be compared too
before calling the behaviour identical. Not done yet.

## Conclusion so far
No extra roulette outcomes exist between the mobile builds. Any added possibilities are not visible
in this data, so they may be in the Dreamcast or GBA versions, in the outcome handlers rather than
the table, or in a game mode not yet examined. TODO: audit the Dreamcast `1ST_READ.BIN`/`2_DP.BIN`
and the GBA ROM; map outcomes 0..7 to events via `RL_RouletteExec` and its switch table.
