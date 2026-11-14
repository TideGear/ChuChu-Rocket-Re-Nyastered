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
