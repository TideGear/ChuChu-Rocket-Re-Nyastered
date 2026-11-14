# Known gaps a player will notice (kept current; 2026-11-13)

Honest list of what the running game (`ccr.exe`, web build) does not yet do the way the originals do. Each line names the original behaviour, where it is documented, and its state.

## Looks
- **Menus/title/HUD are placeholders** (plain text on a flat colour, plain coloured score bars). The original art, layouts and transitions are inventoried in [ui_art.md](ui_art.md); layout constants for the title screen and the state machine are read, the rebuild is not done.
- **Roulette is not drawn.** The simulation runs it (wheel timing, events, music, sound), but the 3D wheel at the rocket and the event announcements are not shown ([rules_events.md](rules_events.md)).
- **Character animation is turning only.** Turning follows the original (verified); walking, rocket entry, hole fall, being eaten, spawning, and win/lose poses are not animated ([animation.md](animation.md)).
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
