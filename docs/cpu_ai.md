# CPU players (Android 1.15 `CT_*`, ported in `game/core/cpu.hpp`)

Status (2026-11-12): **10 of 10 recorded battles identical** to the emulated original (arrow placements: frame, player, cell, direction; `game/tests/cpu_test.cpp` vs `local/testdata/cpu_golden.txt`, made by `tools/oracle/make_cpu_golden.py`). 40 more random cases are being recorded (`make_cpu_golden2.py`). Android only; other versions not yet compared.

## How it works
- `CT_StartCompThink(player, level)` creates one task per CPU player. Level 0..3 selects a behaviour flag word from a table (0x55, 0x56, 0x48, 0x2a); level 4 = `(globalTime + player) & 3`. The cursor starts on the player's rocket.
- The task runs every second global frame. States: 0 = think, 1 = move the cursor (one cell per run, x first, then y) and, on arrival, `CU_PutArrow` (same arrow rules as a human: 3 slots, TTL 600). A put is abandoned after 42 runs.
- Private LCG (`x = x*1103515245 + 12345`, output `((x<<1)>>17)/32768`), shared by all CPU tasks, seeded with the global time at start.
- **Heat map** (`SmpColAnalyze`, rebuilt every frame): every registered cat adds -100 on its cell, spread to neighbours along passable directions (halved per step, 8 deep); every mouse adds its value (normal 1, golden 50, roulette mouse 25; table has a 4th entry 85) with the same spread (value 1: its own cell only).
- Think order (flag bits): bit1 always / bit0 with p = 0.005: **defend** - put an arrow on a free cell next to the own rocket (E, W, S, N order) where the heat is negative (cats near); bit5 always / bit4 with p = 0.01: **attack** - search the 9x9 area around an enemy rocket (the leader if you are not first, else the runner-up; team battle: an opposing team's rocket) for the most negative heat divided by squared distance, arrow pointing at the rocket, accepted only if a depth-8 walk along the arrow reaches that rocket; bit3 always / bit2 with p = 0.1: **collect** - same search around the own rocket for the most positive heat (mice); bit6 with p = 0.05 after 200 runs without a target: **random** arrow (up to 10 random cells/directions with non-zero heat; the last one is used even if none fits).
- "Strength": the four levels differ only in which behaviours are always on or probabilistic: level 0 (0x55): defend/attack/collect/random all probabilistic (weakest, most random); level 1 (0x56): always defends, others probabilistic; level 2 (0x48): always collects, plus random; level 3 (0x2a): always defends, attacks and collects (strongest, no randomness, never places random arrows).
- Behaviour depends on the stage only through its layout (walls, rockets, generators, holes) and on the situation through the heat map, ranks and roulette events (arrows are cleared, cursors locked etc.).

## Version comparison (static first pass, 2026-11-12)
iOS has named symbols (`CT_CompThink0Exec`, `CT_CFRec` = the depth-8 walk, `CT_CheckFukuro`, `CT_Random`, `CT_MoveCursorToTargetPos`, `CT_StartCompThink`); Android 1.15's are stripped (`FUN_00029fa8` etc., same structure). `tools/ExportAsm.java` output in `analysis/asm/{ios_v112,ios_hd10,ios_102,android}_cpu.asm`.
- Probability and scale constants are identical in iOS 1.1.2, 1.0.2, HD 1.0 and Android 1.15: 0.005, 0.01, 0.05, 0.1, 11.88/8.91/3.99 (random target), LCG 1103515245/12345 and the 2^-15 scale.
- `CT_MoveCursorToTargetPos`: identical in all three iOS builds (30 instructions, no constant difference).
- iOS 1.0.2 and 1.1.2: same instruction counts in every CPU function (526 in `CT_CompThink0Exec`); differences are only relocated addresses.
- **iOS HD 1.0 differs structurally**: `CT_CompThink0Exec` 518 instructions (vs 526), `CT_CFRec` 109 (vs 116), `CT_CheckFukuro` 34 (vs 41), with different immediates (0x4, 0x304). Needs a dynamic comparison (emulate the iOS code like the Android oracle) to see whether behaviour differs.
- Dreamcast (SH-4) and GBA (ARM7) CPU code: not yet located/compared.
- Behavioural equality across versions is NOT established by this static pass; it needs differential runs of each version's code (iOS oracle, GBA via emulation, Dreamcast via an SH-4 interpreter).

## Task pool (SmpTsk) facts that affect the heat map (measured 2026-11-12)
- `SmpTskEntry` (Android 0x3daa8): takes the FIRST free slot of a 1024 x 0x58 pool, zero-fills it, and appends the task at the TAIL of the execution list, so tasks run in creation order, not slot order.
- `SmpTskDelete` (0x3db0c) only unlinks and clears the exe pointer (destructor runs if flagged); the slot memory is left as is.
- Collision entries (`SmpColColliEntry`) store the task POINTER. `SmpColAnalyze` reads the type and grid cell from that pointer at the end of the frame, so an entry whose task was deleted and whose slot was reused later in the same frame (e.g. fever cats put right after Cat Mania clears the board) reads the NEW task's fields.

## Result (2026-11-12 22:40)
50 of 50 recorded Android 1.15 battles identical (10 hand-picked + 40 random stage/seed/level mixes, 2,000-3,000 frames each) after modelling the task pool: first-free slot allocation, collision entries that keep task pointers, deferred deletion (eaten mouse: effect task of 48 execs if fewer than 12 alive, mouse freed next tick; rocket mouse freed next tick), event and roulette tasks occupying slots, group deletes freeing slots immediately. Regenerate goldens with tools/oracle/make_cpu_golden*.py; run `cpu_test.exe` (env GOLDEN=file).

## Cross-version dynamic result: iOS (2026-11-13)
The user's iOS armv7 builds run under Unicorn (`tools/oracle/ios_oracle.py`, Mach-O loader `tools/macho.py`, harness `ios_battle.py` / `ios_cpu_run.py`, differential driver `ios_cpu_diff.py`) with the same scenario as the Android goldens (battle stage, seed, CPU levels; sound/vibration entry points neutralised; sin/cos tables filled; stage struct injected by patching `FI_GetFIPSptr`).
Result: **iOS 1.1.2, iOS 1.0.2 and iOS HD 1.0 each reproduce all 50 recorded Android 1.15 CPU battles exactly** (every arrow placement: frame, player, cell, direction; 2,000-3,000 frames per case, mixed levels and stages), so the CPU AI, heat map, generator, roulette flow and task model are behaviourally identical on those four builds. Spawn logs also match. Remaining not yet run: iOS 1.1 (os30), ORBiT variants, Android 1.14 (same ISA as 1.15: can be shown identical by normalised instruction diff), GBA and Dreamcast.
Differences seen but behaviourally irrelevant: the idle-target marker is 0xFF on iOS and 0x10 on Android; function names differ per build (`MC_*` vs `Core::*`, `GA_SetStageNumber` in HD).

**Android 1.14** (same ISA and dynsym addresses as 1.15 but different data layout; sin/cos table slots resolved from `njSin`/`njCos`): the 10 hand-picked CPU battles produce byte-identical placement logs to Android 1.15.
