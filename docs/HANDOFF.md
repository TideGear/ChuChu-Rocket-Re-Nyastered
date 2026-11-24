# Handoff — Dreamcast-only fidelity

## Current state

Branch `main`; check `git log` for latest. Preserve and do not stage/commit the user-owned `game/tests/determinism_test.cpp` and `.vscode/`. No original Dreamcast image descriptor/tracks are present in this checkout; retained extracted files under `local/goal-dc-fresh-setup/assets` are not a substitute for a fresh image-to-cache run.

Latest setup fix (2026-11-24): Dreamcast extraction previously reused cached files/exports, allowing stale assets after changing discs. It now extracts into a temporary tree first and only replaces Dreamcast-derived outputs after the image extraction succeeds; mobile assets and saves remain intact. The version-4 marker is atomically published only when model and SFX exports succeed. Tests cover invalidation, preservation, failed/successful extraction and marker publication. Pinned Python tests passed: `test_extract_all.py` (4), `test_gdi_extract.py` (9), `test_dc_sfx_render.py` (7); compilation and diff checks passed. Fresh image-to-cache verification is unavailable because original descriptor/tracks are absent here.

## Latest verified gameplay/UI work

- Dreamcast-only setup has previously passed clean Windows source setup/build from a USA GDI/CUE alone, exporting 128 models, 15 CD WAVs, 128 SFX cues and Puzzle/Battle/Stage Challenge. CUE outputs matched equivalent GDI files and audio hashes. Packaged Windows and Linux userland setup/route checks also passed. These older checks do not exercise the new stale-cache refresh; repeat from a real image when available.
- Character selector: disc-derived Chao/Pian models, original Challenge/Mania unlock masks, persistence/reset and General Settings selection are implemented. Model/export/input tests pass; costume pixel parity, exact labels/timing, Download and full Costume screen remain open.
- Options works without optional BIOS font atlases using embedded 5x7 text (readability, not parity). Records A/B return and L+R+A clears only Challenge save; original deletion callback/controller mapping remains unverified.
- Music Test 0–14 / SE Test 0–127, Battle Arrow own-panel reset behavior, and Puzzle pause controller-event flow have regressions. Their respective original input-loop/physical-controller or audio-loop parity remains open.
- Puzzle launch full-frame sweep ages -9..80 passed <=3 mean RGB, but only age -1 dome element crops pass per-element checks. Continue isolating body/flame/smoke/lid from TA packets; do not adjust renderer from broad full-frame results alone.

## Next tasks

1. Re-run image-only setup from a fresh cache using the original Dreamcast descriptor/tracks when available; specifically verify refreshed files/assets and version marker, then `ccr --prepare`/build route smoke.
2. Continue Puzzle launch per-element parity using saved TA packets; resolve the rocket scale writer before renderer changes.
3. Trace Battle trigger-taunt callbacks and phrase selection before implementing controls. `GAMEVOICE` textures are roulette/battle announcement art, not proof of trigger phrases. US `VOICE.AFS` entries tested as silent; do not map phrases speculatively.
4. Prioritize remaining Dreamcast gameplay/UI and image-only gaps; keep `docs/HANDOFF.md` current. Commit/push validated work as requested.

## Key evidence and paths

- Decompilation: `analysis/decomp/dc_1st/1ST_READ.BIN.c`; Dreamcast models and selectors: `tools/export_dc_models.py`, `game/app/main.cpp`, `game/tests/input_regression_test.cpp`.
- Retained DC assets: `local/goal-dc-fresh-setup/assets`; model pack at `dreamcast/models.bin`; current marker at `ret_all/dc_assets_version.txt`.
- Launch saved states: `local/session-resume/puzzle-clear/s00070.state`, `s00085.state`, `s00100.state`; TA packet neighborhood `0x19bdc7b`. Aligned captures: `local/star-trace/lau`.
- Manuals, measured parity, open scope, and older evidence are in `docs/goal.md`, `docs/audit.md`, `docs/roadmap.md`, `docs/verification.md`, and `docs/audio.md`. Do not claim parity from harness coverage alone.
- Pinned Windows build/tests: `local/tools/windows/ninja-1.12.1/ninja.exe -C build/game-zig ...`; Python/Pillow: `local/tools/windows/python-3.12.10-pillow-12.2.0/python.exe`.

## Constraints

Use decompile/source and original runtime evidence before behavioral changes; distinguish harness coverage from full-feature verification. Do not use the user's screen/audio or interfere with shared processes. Keep generated caches and disc assets out of commits. Build/capture outputs belong under `local/`; `build`, `dist`, and `analysis` are junctions to D:. The test change in `game/tests/determinism_test.cpp` and untracked `.vscode/` are user-owned.
