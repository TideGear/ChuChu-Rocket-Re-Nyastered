# Original UI art inventory (2026-11-13)

Goal item 7: every menu/HUD/transition must use original art, fonts and animations. The current app menu is a **placeholder** (plain text on a flat colour). Sources found:

## Mobile (iOS 1.1.2 `ccrphn_png`/`ccrret_png`, Android 1.15 `main_png`; 142-124 PNG sprites per build, names `NNN_recXXXX_WxH.png`)
- Gameplay sprite sheets (`ccrret`): cat/mouse turntables, rockets, scoreboard digits, explosions ("Draw!" banner, spiky burst), character costumes (pink, gold, blue, etc.).
- UI sheets (Android `main_png`, in `ccrphn` for iPhone): SEGA, Binary Hammer and SONIC TEAM logos; the title/menu backgrounds (blue planet with the orange cat, a ringed planet, a pale yellow rocket pattern, a molecule pattern); purple/orange rounded menu bars in several lengths; left/right arrow buttons; rocket buttons (incl. the Game Center rocket); speech bubbles and white panels; "TAP THE SCREEN!" text; the help/tutorial diagram; store screenshots ("145 Cheese-erific Puzzles!", "Frantic 1-4 Multiplayer Battles", ...); Japanese text atlases and font atlases.
- Layout/positions of these pieces are in the original code (Android `TitleScreen`/`MenuScreen`/`StageSelectScreen`... classes, iOS equivalents), not yet read.

## Dreamcast (`ENGLISH/*.PRS`, `prs_png/`)
- `TITLE_newtitle*` (logo "ChuChu Rocket!" and background tiles that must be assembled), `TITLE_pressstart`, `MENU_modeback0-4` (mode backgrounds), `MENU_selectmoji0-8` and `MENU_fukidasimoji0-8` (menu text and speech-bubble graphics), `MENU_middleneko0/1`, rocket sprites, `SEGALOGO_segalogo0-5` (tiled).
- The Dreamcast art is 640x480 tiled textures; the placement is code/3D-scene driven (SH-4 code not yet read for this).

## Plan
1. Read the title/menu/stage-select screen code (Android decomp: `TitleScreen`, `MenuScreen`, `PlayerSelectScreen`, ...) for layout, animation timing and transitions.
2. Implement a data-driven UI layer in the app that draws these sheets at the original coordinates/timings, resolution-independent (logical 768x640 for the mobile iPad layout, per-device layouts as options).
3. Replace the placeholder menu, add the original HUD (scoreboard bars, timer) and transitions; compare against screenshots of the original sheets.
