# Check of "ChuChu Rocket! Version Comparison (AI Deep Research)" against the user's own files (2026-11-13)

Method: each checkable claim compared with the extracted files, the decompiles (`analysis/decomp/`), the stage registry and the verification tools. Claims about dates, prices, reviews, store listings and marketing text cannot be checked from the game files and are marked **not testable**.

## Refuted
| Claim in the document | What the files show |
|---|---|
| Android has no Puzzle Edit | `EditorGameScreen` (Puzzle Edit) is present in Android 1.14 and 1.15 ([modes.md](modes.md)). |
| iOS has no Puzzle Edit | True only for iOS 1.0.2 and HD 1.0. iOS 1.1.2 contains `EditorGameScreen`; the editor and `CommsTypeMenu` appear from iOS 1.1.x. |
| Android's Challenge Mode is "undocumented" / may be missing | Android has `ChallengeSelect` / `ChallengeGame` and the 25-stage challenge resource (byte-identical to the Dreamcast `CHSTAGE25.DAT`). |
| Android ships "over 500 puzzles" only (no breakdown) / iOS reached 500+ only by April 2011 | The stage sets are identical: 524 stages (503 unique boards) in iOS 1.1.2 and Android 1.14/1.15; iOS 1.0.2 has 324, iOS 1.1 has 424, HD 1.0 has 103 ([stages.md](stages.md)). The count grows by exactly 100 per iOS build. |
| GBA has 2,600 Puzzle Mode stages (2,625 with Challenge) | The ROM holds 100 main stages plus 2,466 valid user-puzzle records (2,462 unique boards): **2,566 puzzle stages**. The 25 challenge stages were not found as a separate GBA set. |
| Dreamcast / mobile Battle has 24 boards | The Dreamcast disc has `BTSTAGE25.DAT`: **25** battle stages, byte-identical to the mobile battle resource. |
| iOS Game Center online play only arrived on 20 Dec 2010 | Not refuted by the files but not supported either: every iOS build we have, including 1.0.2 and HD 1.0, already contains `GameCenterScreen` and `NetFourBattleGameScreen`. We do not have the launch build, so the chronology cannot be checked. |

## Verified
| Claim | Evidence |
|---|---|
| Dreamcast: 100 puzzle + 25 challenge + 25 battle stages | `PZSTAGE100.DAT`, `CHSTAGE25.DAT`, `BTSTAGE25.DAT` ([stages.md](stages.md)); the mobile builds contain the same 100 + 25 + 25. |
| Dreamcast CD audio is the source of the mobile music | Track mapping, 2.0 s lead-in, 4x loop lengths ([audio.md](audio.md)). |
| Dreamcast and mobile share the same eight roulette outcomes | The Dreamcast selector reads an 8-column weight table; its 12 rows are byte-identical to Android's and iOS's, and the selector gives identical results in 3,000 random cases (`tools/oracle/dc_roulette.py`). So no GBA-only events exist in the mobile builds or the Dreamcast build. |
| GBA has 4P Battle, Team Battle, Stage Challenge, Puzzle, stage/character editor, data exchange | ROM menu screens ([gba_notes.md](gba_notes.md)); "Night Time!" was seen in the title battle demo, consistent with a GBA-only roulette event. The count of 13 events is not testable from text (event names are not stored as strings). |
| GBA user-puzzle pack comes from the Dreamcast server stages (about 2,500) | 2,466 valid records of roughly 2,483 slots, same cell format family as the Dreamcast/VMS puzzle slot. |
| Android build is about 16.9 MB | The APKs are 17,731,347 bytes (1.14) and 17,746,115 bytes (1.15) = 16.91 / 16.92 MiB. |
| Android has no working human multiplayer | The network-battle classes exist but no transport ships ([modes.md](modes.md)). Local split-screen classes (`SplitFourBattle...`) exist in all builds; whether they are reachable on Android phones was not tested. |
| Dreamcast online used a modem server on UDP 9789 and is revived by private servers | Dreamcast Live connection guide (external, read 2026-11-13). |

## Not testable from the game files (outside the software, or builds we do not have)
Release dates and prices, delisting dates, review quotes, Wikipedia-derived facts, Dreamarena subscriber numbers, server statistics (4,000+ user stages), the DS *Project Rub* NiGHTS hat (a different cartridge), Retina update date, the "145 puzzles at launch" figure (marketing text; our oldest iOS build already has 324) and the Game Center chronology (no launch build).

## Testable, still pending (to be settled with the existing tools)
- GBA roulette count (13 claimed): **first measurement: the ROM's event dispatcher has 12 distinct outcome handlers (jump table indices 0..11)**, not 13 ([rules_events.md](rules_events.md)); still to confirm which index is which event and whether a 13th exists elsewhere.
- GBA control schemes (3 claimed): press keys in each scheme in the GBA harness.
- Dreamcast button/keyboard mappings and the Chao / Pian unlockable skins with their unlock conditions: in the Dreamcast executable (input code, save flags).
- Android local multiplayer: whether the split-screen battle classes are reachable from the Android menus.

## New facts from the files that the document lacks
- Dreamcast build differs from mobile in the battle speed-option table: last entry 4.0 (mobile 2.0).
- Mobile builds embed the Dreamcast stage files unchanged, plus 424 extra puzzle stages (24 tutorial + 16 groups of 25).
- iOS 1.1.2, 1.0.2 and HD 1.0 are identical to the port on all 2,548 puzzle runs; Android 1.15 likewise.
