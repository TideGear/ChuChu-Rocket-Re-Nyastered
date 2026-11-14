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

## Resolution and refresh-rate check (2026-11-13, headless)
`ccr` with `CCR_BENCH=<frames> CCR_HZ=<simulated display rate> CCR_SIZE=WxH` renders offscreen with SDL's software renderer (dummy video/audio drivers; the user's monitor is 60 Hz only, so higher rates are always simulated). The simulation ticks at a fixed 60 Hz and the picture is drawn with interpolation at every presented frame.
| Output size | Simulated display rate | Sim ticks per second | Draw time (software renderer, battle scene) |
|---|---|---|---|
| 3840x2160 | 30 Hz | 60.0 | 16.8 ms/frame |
| 3840x2160 | 60 Hz | 60.0 | 16.9 ms/frame |
| 3840x2160 | 144 Hz | 58.8 (49 ticks in 0.833 s: accumulator rounding over a short run) | 16.6 ms/frame |
| 3840x2160 | 240 Hz | 60.0 | 16.1 ms/frame |
| 1280x720 | 60 Hz | 60.0 | 0.75 ms/frame |
| 2560x1440 | 60 Hz | 60.0 | 7.35 ms/frame |
| 7680x4320 | 60 Hz | 60.0 | 72.9 ms/frame (needs the GPU renderer) |
Saved frames have exactly the output pixel size (checked from the BMP sizes). Logic speed is independent of display rate; even the CPU renderer reaches about 60 fps at 4K, the GPU renderer has far more headroom. Not yet measured: the GPU (accelerated) path, since that needs a visible window.

### GPU path (2026-11-13, hidden window, nothing displayed)
`CCR_GPU=1` with `CCR_BENCH` uses the accelerated renderer on a hidden window (a 1x1 pixel read each frame forces the GPU to finish, so the time includes the GPU work). Same battle scene, 300 frames, vsync off:
| Output size | Draw time | Share of the 16.7 ms frame budget |
|---|---|---|
| 1920x1080 | 0.08 ms | 0.5% |
| 3840x2160 | 0.17 ms | 1% |
| 7680x4320 | 0.53 ms | 3% |
This is the current 2D scene only (tiles, sprites, HUD). The Dreamcast 3D models are not drawn by the app yet, so their cost is not included; it has to be measured again when they are added (target: 4K at 60 fps with at least 2x headroom on the 3D pass).

## Determinism and replay (2026-11-13)
`game/tests/determinism_test.cpp` (`determinism_test.exe <battle_stages.bin>`): each of the 25 Dreamcast battle stages is played for a full 3-minute round with roulette, three level-3 CPU opponents and scripted human arrows while the input log is recorded; the log is replayed on a fresh game, and a third run does unrelated work between ticks (what a renderer does). A 64-bit hash of all entity positions and scores after every tick is compared: 25 stages x 3 runs, 180,000 replayed ticks, **0 divergences**. Together with the render-rate table above (60 ticks/s at every display rate) this covers the replay / lockstep requirement for the simulation; wire protocol and netplay are not built yet.

## Lockstep netplay core (2026-11-13)
`game/core/netplay.hpp` (`Lockstep`): transport-agnostic deterministic lockstep (input delay 6 ticks, a tick runs only when every human's input for it is known, each packet repeats all unacknowledged inputs, so loss/reordering/duplication only cause waiting). `game/tests/netplay_test.cpp` runs 2-4 peers, each with its own `BattleGame`, over a simulated hostile network and compares the per-tick state hash of every peer (positions of all entities and all scores): 5 battle stages x 3 full rounds of 3,600 ticks each: **2 peers/30% loss, 4 peers/30% loss, 3 peers/60% loss, all with jitter 1-8 iterations and 10% duplication: 0 desyncs, no stalls**. Not yet done: real UDP sockets (desktop/Android) and WebRTC data channels (web), lobby/matchmaking, the Dreamcast-compatible wire format ("modeled on SERVER_/CLIENT_"), join/leave handling and CPU takeover, in-game UI.

### Real UDP sockets (2026-11-13)
`game/core/udp.hpp` (non-blocking IPv4 UDP; Winsock / BSD sockets, so it also builds for Android) and `game/tests/udp_netplay_test.cpp`: N peers, one real UDP socket each, bound to 127.0.0.1 only (nothing leaves the machine, no firewall prompt), each running its own `BattleGame` through `Lockstep`; per-tick state hashes compared. 3 peers: 3,600 ticks, 21,600 packets, 0 desyncs; 4 peers: 3,600 ticks, 43,200 packets, 0 desyncs. Still not done: lobby/matchmaking, WebRTC for the web build, the Dreamcast-compatible wire format, an in-game netplay screen, LAN broadcast discovery.

## Solution replays (2026-11-13, `game/tests/solve_test.cpp`, data `local/testdata/gba_stages.bin` from the GBA ROM)
Every stored GBA reference solution (arrow positions, not timing; the arrows are placed in the stored order before the run) is replayed in the port: **2,566 stages loaded, 2,548 with a solution, 2,548 solved (100%)**; 0 failures of any kind (mice killed by cats 0, by holes 0, unfinished 0, cat in a rocket 0, broken arrow 0). 392 stages have no cats and 2,156 have cats. 18 stages have no stored solution and are only loaded (not solved). This covers the 100 main stages and the 2,466 user puzzles; the battle stages are loaded and played by the determinism, battle and netplay tests (25 stages), and the DLC puzzle stages and the mobile-only stages are validated by the registry (loaded and fingerprinted) but not yet solved by replay (no stored solutions for them).

## Stage validity (2026-11-13, `game/tests/stage_valid_test.cpp`, data from `tools/export_dlc_stages.py` and `tools/export_testdata.py`)
All boards load into the simulation and run 60 s without error with only known tile codes, at least one mouse and one rocket: **50/50 Dreamcast DLC puzzles (PuzzleP 25, DEPuzzle 25) and 2,566/2,566 GBA stages**. DLC boards are checked for validity, not solved (no stored solutions). The mobile pack stages and battle stages are not yet in this test.
