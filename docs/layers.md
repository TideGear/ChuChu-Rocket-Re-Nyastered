# Draw layers of the Dreamcast original (from real Flycast streams)

Tool: `tools/oracle/dc_layers.py <state> [--list opaque|2d|all]` lists every PowerVR primitive of a `FLY_DUMP` state in submission order with texture word, TSP blend, 1/w depth and screen box. Submission order inside a list is the game's own draw order; depth (1/w, larger = nearer) decides overlap between lists. `dc_match_packets.py` names the 2D textures.

Frames used (all local, never committed): Puzzle `local/star-trace/star02390.state`, Challenge play `local/dc_ref/ch1/p_02500.state`, Challenge pause `cp1`, Team Battle `tb1/t_03600.state`, Battle `hud/live_03100.state`, Team pause `tp1`.

## Findings so far (2026-11-19)

| Element | List / order | Depth 1/w | Blend | Notes |
|---|---|---|---|---|
| Floor quad | opaque, first (0x253e10) | 0.0046 | opaque | one 12 x 9 quad, texture word `080af?f8` (yuka01..06 per mode) |
| Wall pieces | opaque, right after the floor | 0.0046-0.0047 | opaque | texture `080b0?f8`; share the depth buffer with floor, holes, domes and mice |
| Holes, arrow icons | opaque | 0.0046-0.0051 | opaque | Puzzle arrow-stock icon `080b0bf8` sits at z 0.0051 |
| Rocket domes | opaque, after walls | 0.0046 | opaque | see below: two stacked pieces per dome in Challenge and Team Battle |
| Mice, cats | opaque, after domes | 0.0045-0.0048 | opaque | per-mouse pieces (`0804a900`, `0804aa00` in Puzzle; `08073530`/`08073630` in Challenge) |
| Cell corner bracket | 2D list, translucent poly `000adcf8` | 0.0046 | srcA -> 1-srcA | depth-tested at floor depth, so walls (nearer) hide parts of it: fixed in the port 2026-11-19 (App::queueBracket, drawn between floor and walls) |
| Arrow cursor | 2D list, `100ad4f8` | 0.0055 | srcA -> 1-srcA | nearer than everything on the board: always on top |
| HUD sprites | 2D list | 0.005 (panels) to 0.2 (overlays) | mostly srcA -> 1-srcA | the START word is 0.1 |

## Rocket domes: two pieces, two colours

Dome textures are one per player colour: `080ac4f8` (player 1, blue), `080ac8f8`, `080accf8` (red), `080ad0f8`.

* Battle (live_03100): four domes, one piece each, each in its player's colour.
* Team Battle (tb1): eight pieces, two per colour texture: every dome is an upper hemisphere in one team member's colour over a lower hemisphere in the other's (team 1 blue over red, team 2 green/orange).
* Challenge A1 (ch1): the goal dome is `080ac4f8` (blue, y 135-156) over `080accf8` (red, y 152-177).
* Puzzle: a single piece (blue `080ac4f8`) per dome.

Both pieces in the Challenge stream have the same geometry (6 strips, 40 vertices = the 21-vertex, 28-triangle `lid` model, one per colour texture); the port's `drawDcRocketDome` already built a dome from two lid copies (yaw 90 and 270, Battle task 0x8c01b4e0) but both used the same lid. Fixed 2026-11-19: `drawFieldObjects` takes a partner-lid table: Challenge's solo rocket pairs lid 1 (blue) with lid 3 (red), Team Battle pairs 1<->3 and 2<->4, other modes stay single-colour. The Challenge A1 dome now matches Flycast pixel for pixel in a zoomed crop (blue upper, red lower; play frame 1.93 -> 1.82). Which player's rocket sits where in Team Battle (the Flycast frame has blue/red at top-right and bottom-right, green/orange on the left) is not yet compared; the port's sim assigns its own layout.

## Open in the layer audit

* Port draw order per mode versus these tables: Puzzle, Challenge and Battle brackets fixed; arrows, holes, domes, mice, cat, effects (smoke, flames, hit stars), result banner and pause overlays still to compare mode by mode, including Team Battle and the Puzzle launch and pause states.
* Dome pieces: find the lower-hemisphere model in the object table and the rule that picks the two colours per mode (the Ghidra side: the rocket draw task that submits both pieces).
* The Ghidra decompile only reaches these tasks through indirect calls (`PTR_FUN_...`), so the stream is the reliable source; each fix is checked with `tools/parity.py` heatmaps.
