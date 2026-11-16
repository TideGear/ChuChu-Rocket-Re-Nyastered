# Handoff

## Resume here (2026-11-15)

The [README status table](../README.md#status-and-plan) summarizes the project goal, and the [roadmap](roadmap.md) records the evidence. The previous conversation used the full objective at `C:/Users/Tideg/.codex/attachments/615441e7-65bf-4203-92e3-0f9f11e4c08e/goal-objective.md`. Its final goal was to prepare this handoff. Use the file's project objective if it is available in the next conversation.

- A single supported mobile archive supplies Puzzle and Battle. iPad HD 1.0 is the most complete single source for presentation. Add the Dreamcast disc for CD music and title art, the GBA ROM for extra puzzles, and `DEPuzzle.VMS` for the 25 playable Express puzzles. The other VMU saves are collected locally for future support. [Setup details](../README.md#which-original-files-do-i-need)
- Standalone Dreamcast setup extracts the 100 main puzzles, 25 Battle boards, music and original art. Loading the Dreamcast boards with mobile art and replaying all 100 stored puzzle solutions have been verified. Dreamcast-only play and live Dreamcast model rendering remain open.
- The latest headless probe executes the original Dreamcast cat dispatcher, mouse preparation, and mouse draw dispatcher. It verifies 100 cat cases, 24 prepared mouse models, and 256 mouse draws. Use `python tools/oracle/dc_character_draw.py` with Python 3.12 and the extracted US disc executable in `local/cache/assets/dreamcast/files/1ST_READ.BIN`. The probe records draw commands and uses controlled inputs. [Model details](dreamcast_models.md)
- Resume the model audit at the callers of mouse draw `0x8c019e26`. Find the task field that supplies frame 0–7 and verify progression and wrap. Then trace camera transforms, depth and occlusion before integrating the extracted meshes. The normal renderer still uses mobile sprites. Cross-check [known gaps](known_gaps.md) against the dated roadmap entries before relying on older status notes.
- Build with `build.cmd --target ccr`. The offline archive cache for this workspace is `local/tools/archives`. Keep tests headless and silent, keep original files and derived assets local, and commit verified changes without AI attribution.

## Historical handoff (2026-11-13)

Goal text: `local/goal.txt` (not committed) / the 9-item goal pasted via /goal. Working rules: no AI attribution in commits (user CLAUDE.md); headless tests only; never claim "verified" without a measured diff; audit per-frame screen loops, not just the sim (memory: audit-screen-loops).

## State
- Verified: puzzle movement all 2,548 stages (Android 1.14/1.15, iOS 1.0.2/HD/1.1/1.1.2/ORBiT); battle/CPU/score/roulette selector (Android, iOS); DC speed/roulette/score/CPU task pieces (SH-4 interpreter); GBA reference solutions 2,548/2,548; stage validity 50 DLC + 2,566 GBA; determinism, netplay, native-vs-WASM.
- New this session: GBA CPU player fully transcribed (`game/core/cpu_gba.hpp`) and every routine diff-tested against the ROM (0 differences; `tools/oracle/gba_cpu_gen.py`, `game/tests/cpu_gba_test.cpp`), wired into battle with `CCR_CPU=gba` (smoke test only; scores lower than the old CPU, unexplained). Walk cycles drawn (3 views), roulette blocks human arrows and pauses the round timer, countdown tick sounds, functional puzzle stage select (+Tab for 2,466 more GBA stages), next-stage after clear, `docs/asset_quality.md` (mobile texture sizes), `tools/callgraph.py`, `tools/thumbdis.py`.
- Docs to read first: docs/known_gaps.md, docs/verification.md, docs/gba_notes.md, docs/rules_events.md, docs/version_matrix.md.

## In progress when stopped
- iOS 1.1 (`v11`) CPU diff: `py -3.12 tools/oracle/ios_cpu_diff.py v11 local/testdata/cpu_golden2_0.txt` (run from tools/oracle). I added underscore aliases for function names in `ios_battle.py`; it now fails at frame 748 in SmpTskExeServer (unmapped write, pc 0x17d96) - needs a stub/mapping fix. ORBiT/iPhone 1.0 not run either.

## Next, in priority order
1. Missing in play (user playtest): HUD (needs the per-device layout struct filled as the original start-up does, then run the draw functions in the emulator with a drawImage hook), rocket animation (docs/animation.md), roulette wheel art, result screen, real stage-select art.
2. GBA: whole-battle comparison needs the GBA battle rules diff-tested (only puzzle stage 1 is); explain the 171 vs 521 score gap; check direction-code mapping.
3. DC: heat-map builder + whole-battle placements; SFX decode (samples are 4-bit ADPCM, rate unknown; read MANATEE.DRV playback setup); DLC arrow counts (not in the obvious header fields, docs/dlc.md); .VMS/.VMI import, skins.
4. Modes: Challenge, Team Battle, Puzzle Edit, options, unlockables (check GameFAQs), 4-player UI, netplay lobby.
5. Android needs a system image/emulator (none on this machine); iOS Safari/PWA test; README provenance table; DC/GBA entries in asset_quality.

## Update 2026-11-14
- Done since the handoff above: iOS older-build CPU diff fixed (all five iOS builds identical to the Android goldens); Dreamcast cursor/arrow input read (docs/known_gaps.md, `tools/shdis.py` SH-4 disassembler with literal resolution); Dreamcast "PRESS START BUTTON!" title prompt; rocket size growth in battle (`BattleGame::puku`); GBA direction-code experiment (no mapping explains the score gap); Challenge mode structure read (docs/modes.md: type = stage mod 5, win/lose checks per type, phases), with two corrections noted there.
- Challenge: the player's role in the types other than mod-5 == 3 is unexplained by static reading; do a runtime trace (Android emulator harness, inject touches into `ChallengeGameScreen`) before porting.
- The Basics and Stage Challenge still play the “Zero!” clip without entering a mode. Help & Options opens in the iPad menu when its assets are available. See [the SFX trigger audit](audio.md#zero-trigger-audit-2026-11-14) for other refusals and incomplete features. Android's options defaults are music 75, sfx 100 and eight flags (`initializeOptionsData` 0x682ec). Its `handleSoundMenuItemSelection` is empty.

## Update 2026-11-14 (evening) — battle setup / player select (HD 1.0)
Done and verified this session (details and dates in docs/roadmap.md, entries dated 2026-11-14):
- Players pane input, all 14 cases: `tools/players_input_diff.py` (0 mismatches). Case 12 is the team toggle (+0xa40, 0<->1). It is gated by +0xd20 == 0 or the network flag (`tools/oracle/team_toggle_probe.py`).
- Player select states 0x24–0x27: `playersFlowStep` / `playersRouteOps` in game/app/main.cpp. `tools/players_state_diff.py` covers 201 cases against `tools/oracle/players_state_probe.py` (Unicorn) with 0 mismatches. States:
  - 0x24 fade-in, then song 5 and state 0x25.
  - 0x25 routes to the players or settings pane.
  - 0x26 fades to Menu (4) when +0xa3c is set.
  - 0x27 picks the battle screen: 0x13 / 0x14 for team, 0xf / 0x10 for four battle (split flag +0xa7d), 0x11 for network, gated by state timer & 7 > 4.
- Oracle facts to remember:
  - `process(float)` takes dt in r1.
  - The frame loop (`EAGLView_drawView` 0x97b8) also leaves dt in d6, which state 0x23 reads, so the harness must set D6.
  - The network flag for process is the byte pointed to by global 0xeb450. Case 12 reads a different pointer, via 0x32170 -> 0xeb494 -> 0x175010.

Open, next in order:
1. Wire the iPad player-select renderer and panes into a live PlayersMode. The HD 1.0 menu requests PlayerSelectScreen (0x0a) directly for Battle. The stage grid is on its Settings pane, which opens through players-pane item 14. That input and the local iPad Players pane render now match the original. The separate StageSelectScreen (0x09) is the Puzzle route. Next, port the iPad Settings pane's drawing and actions before changing the main-menu Battle route.
2. Then the rest of phase A from docs/roadmap.md: roulette wheel, celebration rockets, tutorial, Stage Challenge, Puzzle Edit, Costumes. Phases B–G follow the roadmap.

State 0x23 now has a standalone port and a headless differential test. The original constructor fills its list by calling `loadBattleGraphics` (0xc104) at 0x34bf2. The port accepts the ordered texture IDs and issues one upload per tick, then releases the entries in reverse and signals 0x24. The live PlayersMode will need to supply the list and connect those operations to the renderer.

`PlayersFrame` ports the iPad drawing around the panes in states 0x23–0x27. `tools/players_render_diff.py` compares it with the original render at 0x35154, recording which pane the original calls. In state 0x23, the cat uses frame +0xa60 and x +0xa4c. The costume mascot uses frame +0xa78 and x +0xa64. The app's HD image exporter includes the six image slots used by the renderer.

On Windows, run `build.cmd --target ccr` from Command Prompt or `.\build.cmd --target ccr` from PowerShell. The script downloads pinned Zig, CMake and Ninja into `local/tools/windows` on first use. Its CMake cache is `build/game-zig`, with executables in `build/game`. Python is `py -3`.

## Update 2026-11-16 — whole-battle roulette verification, Challenge trace
Done and verified this session (details in docs/roadmap.md entries dated 2026-11-16 and docs/modes.md):
- Android handset Puzzle arrow-stock panel (`renderPuzzleHudiPhone`, `tools/oracle/android_puzzle_hud_calls.py`); `puzzlestage_endflag` trace (label and number branch unreachable in 1.15).
- Whole-battle forced roulette outcomes against the original, 26 battles x 8 outcomes: `tools/oracle/make_battle_forced_golden.py <0-7>` (env `TEAM=1`, `GT=<t>`) and `FULL=1 FORCE=<k> GT=<t> [TEAM=1] battle_full_test.exe ../local/testdata/battle_[team_]forced_<k>[_gt<t>].txt`, run from `game/`. Identical: 26 for every outcome except Mouse Mania (25, stage 5 seed 1085). Team Battle: outcomes 0, 5, 6, 7 and Everybody Move at game times 1/3/4/7. Natural selector: `make_battle_natural_golden.py` and `NATURAL=1 FULL=1`, 26/26 free-for-all and team. The goldens live in `local/testdata` (git-ignored); regenerate with the recorders (about 25 minutes for eight in parallel; never run two recorders with the same output name, one overwrote four files once).
- Root causes found: the original runs tasks in creation order (linked list in `SmpTskEntry`), not pool-slot order (`Ev::ord`, `Sim::spdSlot`/`monoEnd` are entity indices); the generator's mouse counter is per type and lags spawns by a frame and removals by two ticks; rolls run after the generator task; recorded arrow placements bypass the event cursor lock.
- Stage Challenge: `tools/oracle/challenge_probe.py` runs the original phase machine for all 25 stages (docs/modes.md, "runtime trace").
Open next, in order:
1. Stage Challenge: scripted arrows per type to confirm the win rules, Android's own challenge boards (the probe uses Dreamcast `CHSTAGE25.DAT`), then port the loop and result path; Puzzle Edit; Mouse Mania stage 5; team score display and end-of-round result.
2. Phase A leftovers: phone name frame (0x73 frame 5), A800/Retina layouts, tutorial highlights, split-screen, roulette wheel art, celebration rockets, Costumes.
3. Phases C-G as listed in docs/roadmap.md; no final audit has been done.
Environment notes: tests run from `game/` (`../build/game/<test>.exe`); in Python edit scripts a `\n` inside a C++ string becomes a real newline (fix with `chr(92)`); Unicorn caches translated blocks, so memory patches must be applied before execution.
