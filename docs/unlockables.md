# Unlockables and secrets (living document, started 2026-11-13)

Goal item 5 requires every unlockable/secret/cheat of every version with its original condition, taken from code and save data and cross-checked with community lists (GameFAQs could not be fetched: HTTP 403; lists to be pasted by the user or saved as files).

## Android 1.15 (decompiled `libccrjni.so`, functions cited)
| Unlockable | Condition (from code) | Function |
|---|---|---|
| Costume 0 (default) | always available | `Data::isCostumeAvailable(0)` @0x3eb7c |
| Costume 1 | `puzzleClearEnum(3)`: all 25 stages of puzzle group 3 (the Mania tier) cleared (25-bit cleared mask, `(mask & 0x1ffffff) + const == 0`) | `isCostumeAvailable(1)`, `puzzleClearEnum` @0x3eaec |
| Costume 2 | `isChallengeClearedAll()`: all 25 Challenge stages cleared (25-bit mask at the challenge save word) | `isChallengeClearedAll` @0x3e940 |
| Puzzle group 1 / 2 / 3 | sequential: group n opens when every stage of group n-1 is cleared (`getPuzzleMaxStage` returns 0..3 from `puzzleClearEnum(0..2)`) | `getPuzzleMaxStage` @0x3eb50 |
| Costume menu | Help/Options screen items (`initCostumeMenuItems`, `handleCostumeMenuItemSelection`, `renderCostumeMenuItems`) | @0x4e618, 0x4b890, 0x4bb20 |
| Achievements | an achievement mask is saved in `AppData::saveAchievementMask` / `initializeAchievementMask` (store achievements; the iOS builds report them to Game Center, `unlockAchievement`, `submitAchievement:percentComplete:`) | @0x6a100 |

This matches the Dreamcast manual as quoted in the research document: unlockable character replacements (Chao after clearing all 25 Stage Challenge stages, Pians after clearing all 25 Mania puzzles).

## To do
- Map costume indices 1 and 2 to the sprite sets and confirm the order (Pian vs Chao) in the costume code; read the achievement list (ids, conditions) from Android/iOS.
- iOS (1.0.2 / HD / 1.1.2), Dreamcast (save flags in `1ST_READ.BIN`, character-replacement unlocks, DLC characters) and GBA (Character Edit, the `Project Rub` NiGHTS-hat bonus claimed by the research document, battle unlocks) unlock logic.
- Cheat codes, if any (none found in the Android strings so far).
- Implement in the game: per-version conditions as options plus an unlock-all switch.

## iOS 1.0.2, HD 1.0, 1.1.2 (`VMU::isCostumeAvailable(int)`, same code in all three)
Costume 0 always; costume 1 = save word at +0x7c (the cleared mask of puzzle group 3, `(3 + 0x1c) * 4 = 0x7c`) has all 25 bits set; costume 2 = save word at +8 (Challenge cleared mask) has all 25 bits set; any other index unavailable. This is the same rule as Android 1.15 (`Data::isCostumeAvailable`), so **costume unlock conditions are identical on iOS and Android**. Remaining to check: Dreamcast and GBA.

## Dreamcast (`1ST_READ.BIN`, found by the 25-bit mask literal 0x01FFFFFF)
- `0x8C02B518`: save word at 0x8C22D824 `& 0x1FFFFFF == 0x1FFFFFF` -> all 25 Stage Challenge stages cleared (same test as mobile `isChallengeClearedAll`).
- `0x8C02B508`: the same save word tested against **0xFFFFFF (24 bits)** -> a Dreamcast-only check that 24 challenge stages are cleared (use not yet identified: possibly gating the last challenge stage or a character-related unlock).
- `0x8C02C808`: `puzzleClearEnum(group)`: word `0x8C22D8A4 + 4*group` `& 0x1FFFFFF == 0x1FFFFFF` -> all 25 stages of that puzzle group cleared (same test as mobile).
So the Dreamcast character-replacement conditions (Chao after all 25 challenges, Pians after all 25 Mania puzzles per the manual) use the same 25-bit cleared-mask tests as mobile. Still to do: callers of these three functions (which costume/feature each gates, and the 24-bit check), then GBA.
