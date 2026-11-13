# Cross-version comparison matrix (living document, updated 2026-11-13)

Legend: **EXACT** = original code of that build executed in an emulator and compared with the port / the Android reference on recorded scenarios, 0 differences;
**STATIC** = constants/structure compared only; **TODO** = not examined.

| Subsystem | Android 1.15 | Android 1.14 | iOS 1.1.2 | iOS 1.0.2 | iOS HD 1.0 | iOS 1.1 / ORBiT | GBA | Dreamcast |
|---|---|---|---|---|---|---|---|---|
| Puzzle movement/arrows/rockets (save timelines) | EXACT, all 2,548 stages (port vs original) | TODO (same ISA, layout addresses identical: instruction diff pending) | EXACT on 100 stages; full 2,548 running | EXACT on 100 stages; full run pending | EXACT on 100 stages; full run pending | TODO | EXACT on stage 1 (30 exits, 820 frames; docs/gba_notes.md) | TODO |
| Battle generator + spawn logs | EXACT (15 cases) | n/a | EXACT (spawn log identical on the case compared) | same | same | TODO | TODO | TODO |
| Battle scoring (`SC_AddScore`, `SC_CatHasCome`) | EXACT (1,500 + 3,000 ops) | TODO | EXACT 3,000 ops | EXACT 3,000 ops | EXACT 3,000 ops | TODO | TODO | TODO |
| Roulette selection weights | EXACT selector (3,000 calls) | table byte-identical | table byte-identical (12 rows) | table byte-identical | table byte-identical | TODO | TODO | TODO |
| Whole-battle score timelines + entity trajectories | EXACT 26/26 battles | TODO | covered by CPU placements below | covered | covered | TODO | TODO | TODO |
| CPU players (arrow placements, 50 battles, 2,000-3,000 frames) | EXACT 50/50 | EXACT 10/10 | EXACT 50/50 | EXACT 50/50 | EXACT 50/50 | TODO | TODO | TODO |
| Roulette event handlers (Cat Mania etc.) | partial (see rules_battle.md) | TODO | exercised through CPU runs (Cat Mania rolls identical) | same | same | TODO | TODO | TODO |
| Speeds (cat 1.0, mouse 1.5 puzzle; battle option table) | EXACT | - | EXACT (GA_GetCatSpeed/MouseSpeed 0.25/0.375 with unset option, same as Android) | same | same | TODO | TODO | TODO |
| Frame rate / logic rate | 60 Hz tick (stepped per frame) | - | 60 Hz in the harness; device display interval to confirm | - | - | - | TODO | TODO |

Notes
- iOS and Android builds share one C++ code base compiled for two ABIs; the harnesses (`tools/oracle/`) run each build's own code under Unicorn. Differences found so far are cosmetic: function names (`MC_*` in old iOS builds, `Core::*` later), the idle CPU target marker (0xFF iOS vs 0x10 Android), one extra argument of `GA_SetStageNum`, puzzle arrow placement through `AR_PutArrowPzSp` (iOS) instead of `AR_PutArrowPz` (Android).
- iOS HD 1.0 is non-PIC (absolute literals) and its sin/cos tables are static arrays rather than pointer slots; the harness handles both.
- Everything above is for the English-language, US-region files provided; other regions of the Dreamcast disc (language folders) differ only in text/voice assets so far.
