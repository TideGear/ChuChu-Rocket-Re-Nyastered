# Known gaps a player will notice (kept current; 2026-11-13)

Honest list of what the running game (`ccr.exe`, web build) does not yet do the way the originals do. Each line names the original behaviour, where it is documented, and its state.

## Looks
- **Title screen is real** (iPad-class layout when the iPad art is exported: 1024x768 tile-map background, Dreamcast logo, iPad rocket/prompt; the phone layout is the fallback; background, logo, orbiting rocket, blinking prompt, fades, song 0; `TitleMode` in `game/app`; the prompt still reads "TAP THE SCREEN!" as on the phones, a keyboard/mouse/pad wording is not yet chosen). **Main menu is real in the iPad layout (phone layout as fallback)** (original bars, labels from the localized strings, `CCR_LANG=en|fr|de|es|it`; the Japanese strings need the glyph mapping; the speech bubbles and the corner/back button are missing, and only Puzzle and Battle do anything: The Basics, Stage Challenge and Options are shown but inactive). **The in-game HUD is a placeholder** (plain coloured score bars, own font placement). The original art, layouts and transitions are inventoried in [ui_art.md](ui_art.md); layout constants for the title screen and the state machine are read, the rebuild is not done.
- **Roulette is not drawn.** The simulation runs it (wheel timing, events, music, sound), but the 3D wheel at the rocket and the event announcements are not shown ([rules_events.md](rules_events.md)).
- **Character animation: turning and walking are in; the rest is not.** Walk cycles use the original's three views per character (side/back/front chosen by the smoothed angle, 20-frame cat cycle advanced 0.45 per tick, 11-frame mouse cycle on the global tick, frame offsets from the sheet's frame records; [animation.md](animation.md)). Mouse hop height, rocket entry, hole fall, being eaten, spawning and win/lose poses are not animated; the west-facing mirror of the side view is an unverified assumption.
- **Characters/costumes:** only the default characters; no unlockable costumes, no DLC skins ([unlockables.md](unlockables.md), [dlc.md](dlc.md)).
- **Dreamcast 3D models** are extracted and render offline, but the game draws the mobile 2D sprites ([dreamcast_models.md](dreamcast_models.md)).

## Sounds
- Music follows the original's triggers for the title/menu, puzzle and battle (including roulette events and the last-30-seconds switch); fades, the countdown/result songs, volume changes and loop-point refinements are missing ([audio.md](audio.md)).
- Sound effects: only the battle events wired so far (arrow placed/refused, mouse home, cat in rocket, roulette start). Puzzle-mode effects, UI sounds and voices are missing.

## Modes and controls
- Modes present: Puzzle (one stage at a time), Battle with CPU opponents and 1-4 local humans (chosen with `CCR_HUMANS`, no player-select screen). Missing: stage select, Challenge, Team Battle, Puzzle Edit, options/settings, tutorial/help, stage sets (DLC, GBA user puzzles), online/LAN screens.
- The lockstep netplay protocol and UDP transport exist and are tested, but there is no in-game lobby or connection screen.
- Touch controls (web/Android) are not implemented.

## Platforms
- Windows: runs. Web: builds and renders the (placeholder) menu in headless Chrome; no asset import, touch, or iOS Safari test. Android arm64: the core cross-compiles, no app and nothing run on a device.

## Battle screen audit (2026-11-13, from a headless frame)
- The timer ("2: 45") is drawn over the first row of the board and the four score bars are plain coloured boxes with digits: placeholder HUD. In the original the HUD is not one screen function: it is a set of render-node callbacks added by tasks (`DrawTimeWatch`, `drawClockSplit`, `CU_PlayerTagDraw2D`, `RoundCountDraw2D`, `BattleCountDraw2D`, the scoreboard tasks) that call `Render::drawImage(imageId, frame, x, y, ...)` with ids from a global image table (e.g. 0x6d, 0x68, 0x75, 0x9e in the pause screen). To rebuild it faithfully: extract that image-id table (id -> sprite sheet and frame), then read each callback's positions per device class. The iPad pack already contains the art at the best size (player name plates, score bars, digits, crowns, "Draw!", "Winner!", "321", "Pause" panels).
- Cats are drawn about one and a half cells tall and some are shown rotated sideways at turn time; the turn frames follow the original's angle logic, but the sprite scale/anchor against the cell grid has not been compared with the original.
- No cursor/tag for the human players' own cursors other than a thin square for players 2-4; the original draws coloured player tags (`CU_PlayerTagDraw2D`) and a ghost cursor (`CU_ZanzoCursorDraw2D`).
