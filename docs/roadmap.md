# Roadmap and evidence log

Dated evidence for work in progress: the frame, address and measured error behind each change, plus what is still open. Keep entries short. Record each negative result or retraction in one line, and replace an entry when it is corrected instead of appending a contradiction. Coverage lives in [audit.md](audit.md), and the current state and next tasks live in [HANDOFF.md](HANDOFF.md).

The full log from 2026-11-12 to 2026-11-25, which holds every capture recipe, address trace and measurement, is in [archive/roadmap_2026-11-12_to_11-25.md](archive/roadmap_2026-11-12_to_11-25.md). Search it before re-deriving anything.

## 2026-11-25

Puzzle:
- The Puzzle cat walks in place while arrows are placed. Flycast Hard 05 shots 2300-2418 (local/hd5s) show it; the port used to freeze it at frame 0. The port now steps the cat phase (+0.25 per pass, task `0x8c0113f0`) from tick 32. That tick comes from a CCR_TICKS scan (period 96, best at 200 - 31) and from the walk being visible at frame 2300, which rules out 127. The cat-creation code is not traced. Results: `puzzle_hard05` full 1.091 -> 0.901, board 1.243 -> 0.872, cat crop 9.3 -> 2.59.
- The Hard 05 cat's remaining residue is body shading: 572 off-edge px, while the pose matches. Its body strips are at 0x269cd0 and 0x269f30 in local/hd5/p_02390.state, with base intensity 0.30-0.85 and white face colour. Pairing 20 vertices by (u, v) gives a port rms of 0.13, and no single light vector fits (residual 0.10). Next: the cat normal transform (draw `0x8c0119fe`, morph `0x8c0e673e`).
- New cases: `puzzle_normal08` "Lots of mice" (full 0.871, board 0.842 with 0 off-edge px: passes) and `puzzle_hard05` "Loopy" (all four clear masks poked, then R2 and RIGHT x4). Capture scripts are in HANDOFF.md.

Cursor bracket and pad:
- A dimmed bracket (cell & 0xF00) has no size pulse: `0x8c01480c` skips the njScale when r11 != 0. Over 90 Flycast Challenge frames its edges never move. The white bracket's pulse is centred: the quad at `0x8c085778` is +-7.5 with `1 + 0.075 sin`. (The apparent corner anchor was the wall drawn over the bracket.)
- The Challenge pad aim is the float at `0x8c186cfc` / `0x8c186d04`: 82.5 -> 68.1 -> 53.7 after two LEFT taps, which `DcCursor::tick` reproduces exactly. The pointer pulse is period 16 and the port ran 2 ticks late, so it now uses `cticks + 2`. New case `challenge_play_a1_dim_bracket` (headless hook `CCR_PAD_AIM=53.7,52.5`): full 2.103, bracket crop 7.46, 0 off-edge px. Partial: pointer edges and rocket pose differ.

Battle banners:
- count2/count1 (`FLY_POKE_ONCE=3000:1ae8e0=203`, local/ato_c2b) were fitted with the port's own sprite over a median background. The scale goes 7.40 (3008) ... 1.90 (3050) with slope 0.132 per frame, so `8 - 0.13 t` holds, and count1 repeats 60 frames later. A pixel diff is blocked: the board moves behind every banner frame.
- START banner edges (crop 2.39, 0 off-edge px) are not caused by alpha-0 texel colour (zeroing them gave 2.47), texel precision (all values are k x 17), or vertex colour (the quad is white at intensity 1.0, with the offset word unused). Left untested: the order of 4444 filtering and expansion.

Golden mouse:
- Only the golden mouse's strips (textures 080e5700 / 080e5b00) have face colour 2.0 per channel; every other polygon has 1.0. The VRAM base of local/gold5/g_03180.state is 0x271414 (from `local/findbase.py`). The body crop does not saturate (max red 208). A centroid texel check fits neither factor, so the strips need to be rasterised before the port changes.
- flyhost Battle runs differ between invocations, so dump in the same run as the shot.

Pian:
- The right mice crop is 1.036 with 0 off-edge px. The bias is uniform: +1.6 R, +0.2 G, +1.5 B. It is a candidate for "pass (rounding)" under the goal.md rule; re-measure it.
