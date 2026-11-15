# Handoff (2026-11-13)

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
- Main-menu items "The Basics", "Stage Challenge" and "Options" do nothing yet (they play the buzz sound); Android's options defaults are music 75, sfx 100 and eight flags (`initializeOptionsData` 0x682ec); `handleSoundMenuItemSelection` is empty.
- Build on Windows from a plain bash: use a .cmd that calls `vcvars64.bat` (VS 18 BuildTools) then `cmake --build build/game --target ccr`.

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
1. Trace render (0x35155), then wire a PlayersMode screen from stage select to battle (today "BATTLE" goes straight to BattleMode).
2. Then the rest of phase A from docs/roadmap.md: roulette wheel, celebration rockets, tutorial, Stage Challenge, Puzzle Edit, Costumes. Phases B–G follow the roadmap.

State 0x23 now has a standalone port and a headless differential test. The original constructor fills its list by calling `loadBattleGraphics` (0xc104) at 0x34bf2. The port accepts the ordered texture IDs and issues one upload per tick, then releases the entries in reverse and signals 0x24. The live PlayersMode will need to supply the list and connect those operations to the renderer.

Build from bash or PowerShell: `cmd.exe /c "\"c:\Dev\ChuChu Rocket\build.cmd\" --target ccr"` (build.cmd passes its arguments to `cmake --build`). Python is `py -3`.
