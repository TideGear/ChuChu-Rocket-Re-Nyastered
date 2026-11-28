# Handoff — Dreamcast-only fidelity

## Current state

- Branch `main`; latest change: Puzzle preview dome orientation plus complete TA capture tooling (follows pushed `ec40139` projection-centre fix).
- Follow `docs/goal.md`; `docs/audit.md` owns coverage, `docs/roadmap.md` owns detailed evidence/recipes, `docs/verification.md` owns setup/test results. Preserve untracked `.vscode/` and `local-empty-structure-before-junction/`. Do not stage generated assets, images, states, binaries or caches.
- Clean image-only setup last checked 2026-11-27 under `local/fresh-dc-only-20261127/`: one USA Dreamcast ZIP, no BIOS/mobile/DLC/GBA; extraction and pinned Zig build completed without input errors. Eleven direct modes were nonblack (90-tick reachability only). Current ccr/input regression build and all 30 game tests pass on these assets. No full-game parity claim.
- Current Puzzle comparison: all 18 full frames <=3 RGB mean (0.9530..1.9630). This does not imply element completeness. No-BIOS hint/label fallback, some label/model/edge sampling, natural final-stage clears and save failures remain open.

## Renderer evidence and next work

- Font provenance: `dc_bios_ansi` is also the normal **no-BIOS generated fallback** (Roboto Mono, `export_dc_ui.export_dc_fallback_fonts`); the filename does not prove a BIOS was supplied. `extract_all.py` overwrites it only when a user BIOS is found. Check `manifest.json` field `dreamcast_bios_font` and atlas dimensions/provenance before attributing a text gap to BIOS absence. Missing atlas is a separate error path. The earlier statement that a normal image-only Create dialog was blank was incorrect.

- Preview centre is global (320,240), not inferred from the translated floor corner. Original wall vertices match within 0.00002009 px (old 1.081233 px); checker `tools/oracle/dc_preview_projection.py`.
- Puzzle preview lid halves use yaw 0/180 (`0x8c015fac..15fd6`), Battle/Challenge 90/270 (`0x8c015f60`). New Puzzle-only path matches all 12 original raw TA halves within 0.000035153 world units and light within 4.17232513e-08. Two-half Challenge control passes. Source/stream evidence; no fitted orientation.
- Combined preview fixes: full Puzzle selector error 1.9605 -> 1.5472 -> 1.5344; preview crop 4.8114 -> 2.7205 -> 2.6557; off-edge >8 count 184 -> 10 -> 0, shift (0,0). Six source-bounded dome crops still fail mean/residual thresholds (means 1.2231..3.0805), so sampling/edge residue remains partial. Other 17 Puzzle BMPs and Challenge selector are pixel-identical after the orientation fix.
- Next: use complete TA capture for remaining renderer gaps, then return to natural Puzzle result/unlock/save paths. Do not repeat the solved hole-fall pose investigation (crop 0.93). Time-box residue; close visible gaps first.

## Complete TA capture (development only)

- End-of-frame states can omit already-rendered TA contexts; a failed model match in such a state proves nothing. `tools/oracle/patch_flycast_ta_capture.py` patches pinned local Flycast `3a5267a` at QueueRender, before consumption. Local core at `local/handoff-check/flycast-reference/flycast_libretro.dll` is rebuilt with this optional hook (previous DLL: `local/preview-stream-20261127/flycast-before-ta.dll`). Hook-enabled Puzzle shot 30 vs pre-hook control: 0 differing RGB pixels.
- Enabled only by `FLYCAST_TA_CAPTURE=<absolute prefix>`; `FLYCAST_TA_FIRST` / `LAST` bound render-call indices, not general flyhost frame numbers. Raw output `<prefix>00030_00.ta` is the complete command stream, including linked contexts separately. Leave the env unset for normal references.
- Evidence: `local/preview-stream-20261127/` contains 35 82944-byte Puzzle streams (107 headers, including 12 complete lid halves), control shots/logs and three Challenge streams. Checker: `python tools/oracle/dc_preview_lids.py local/preview-stream-20261127/raw_00030_00.ta local/preview-stream-20261127/p_00030.ram`; Challenge control uses `challenge_raw_00002_00.ta`, `local/dc_ref/cs1/p_02100.ram`, `--quarter --halves 2`.
- Rebuild core with vcvars64 and Ninja `-j 2` in `local/handoff-check/flycast-reference`; detailed setup/capture recipe in roadmap.md. Do not ship emulator binaries/source, BIOS or captures.

## Functional state

- Puzzle pause accepts A/Start on selected Resume/Quit, ignores B/Y in Dreamcast look; keyboard B/Escape also stays paused. Mobile B-to-leave remains. Eight original-loop cases pass without RAM pokes (`dc_puzzle_pause_inputs.py`). Entry/exit overlay animation and other devices remain open.
- Puzzle clear: `recordClear` honors the Special/Mania sole-uncleared override (pending -1) before current-group unlock (pending 0). Five original-loop arrival/clear/update-mask/B-input fixtures pass (`dc_puzzle_clear_pending.py`). These prove RAM progress bits, not physical VMU persistence.
- Puzzle replay: `0x8c02c93e` progress gate controls stage-25 A/Start -> plain credits; B leaves. Twelve original-loop fixtures pass for Normal-only/all-four masks, pending -2/-1 and A/B/Start (`dc_puzzle_result_routes.py`). Natural final-stage clears and end-of-roll text pixels remain open.
- Challenge: advancing stage 24 requires first-24 clear mask for stage 25, else wraps to stage 1. Mouse final-stage Next shares A/Start route. First/repeat final clears distinguish pre-save pending 1/-1; repeat A/Start -> plain credits, repeat B -> selection. Six original-loop branch fixtures pass (`dc_challenge_result_routes.py`); natural final-stage gameplay remains open.
- Puzzle Edit: rocket/hole Set toggles and 30-rocket cap match source; imported VMS Load and local-only Delete, solution editing, capacity feedback and round-trip regressions exist. VMS reader now rejects solution coordinates outside its 12x9 board so loading and rewriting cannot silently drop malformed arrows; synthetic VMS regression passes. Original VMU acceptance/failure and populated-screen parity remain open. PuzzleP DLC stock remains slot-format-derived; original live stock/gameplay evidence is open.

## Open evidence / cautions

- Puzzle Edit Create dialog: text origins and ARGB1555 colour now come from 0x8c0321d0..2206; gold-box vertices/UVs come from complete original TA (raw offsets 0xe0a0/0xe180, local/editor-dialog-20261127/). Missing-atlas fallback shares the staff-roll bitmap helper. All 30 game tests and four TA tooling tests pass; normal no-BIOS capture has readable generated-font text. Exact glyph stamping and element parity remain partial; old 5.5 full/10.5 dialog errors predate this fix and are not current measurements.
- Team Battle result packets appear by tick 1200 and persist through 1890; creation/transition/order still open (`local/battle-result-probe/`). Phrase task caller 0x8c027a6c, predicate 0x8c025592, ctor 0x8c056a64, updater 0x8c0565e0; full text/voice mapping/lifetime/rendering remain open (`local/phrase-probe/`).
- The Basics intro skip has only mobile flag-4 evidence, not Dreamcast pad evidence. Real-USA-CHD file/audio parity, native MANATEE mono semantics, staff-roll residues, other regions, Android runtime and BIOS fallback edge cases remain open. BIOS stays optional and user-supplied.
- Never infer Dreamcast parity from port-vs-port tests or static assets alone. Whole-mode totals remain unchanged; scope every claim to its evidence.

## Useful commands and paths

- Python: `C:/Users/Tideg/AppData/Local/Programs/Python/Python312/python.exe` (the Windows py launcher may not find it).
- Build: set ZIG_GLOBAL_CACHE_DIR to local/tools/windows/zig-cache, then `local/tools/windows/ninja-1.12.1/ninja.exe -j 2 -C build/game-zig ccr input_regression_test`. MSVC game tree lacks stddef.h; use Zig.
- Tests: `python tools/run_tests.py --assets local/fresh-dc-only-20261127/cache/assets`. Parity: `python tools/parity.py <assets> --only puzzle --out <scratch>` (CCR_GPU=1 in manifest). Latest orientation crops: `local/puzzle-preview-lid-crops-20261127/`; full cases: `local/puzzle-parity-20261127-lid-fixed/`.
- Clean setup: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools/setup-wizard.ps1 -GameFiles <image/folder> -Cache <fresh cache>` (same wizard/build as setup.cmd).
- Original code: `analysis/decomp/dc_1st/1ST_READ.BIN.c`; SH-4: `python tools/shdis.py <start> <end>`. Flycast disc: `local/dc_ref/disc/ChuChu Rocket! (USA) (En,Ja,Fr,De,Es).cue`, use absolute path, not ZIP. Host: `build/game/flyhost.exe`, headless only.
