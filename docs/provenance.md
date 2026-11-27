# Asset and feature provenance (living document, 2026-11-13)

For each asset class: the source chosen, the evidence, and what is still unmeasured. "Measured" means a number produced by a script in `tools/`.

| Class | Chosen source | Fallback | Evidence | Status |
|---|---|---|---|---|
| Music | Dreamcast CD audio tracks 4-18 (lossless stereo 44.1 kHz; four loop repetitions on tracks 12, 13, 15) | iOS/Android Ogg mono ~48 kbps (identical in every iOS build and Android) | [audio.md](audio.md): track mapping, 2.0 s lead-in, 4.02x length ratios, envelope correlation 0.86-0.94 on clean matches | measured; loop points still to find |
| Sound effects | iOS/Android 52 effects (mono ~70 kbps) until the Dreamcast AICA banks decode | Dreamcast `DP2SOUND.MLT` / `CHU2_SE.MLT` | MLT sections split (`tools/mlt_extract.py`); AICA ADPCM not decoded | not yet compared |
| Voices | iOS/Android voice lines | none on the US Dreamcast disc | `VOICE.AFS`: 383 entries, all decode to silence ([audio.md](audio.md)) | measured (disc voices are empty placeholders) |
| 2D graphics | Dreamcast PVR textures (up to 512x512, 954 PVM textures + 1,081 in 2DP) for menus/UI where complete; iOS HD (up to 1024x548) for gameplay sprites | iOS 1.1.2 (up to 808x800), Android 1.15 (142 PNG, up to 1024x536; the rest in packs) | counts and maximum sizes measured on the extracted caches (2026-11-13) | partly measured; pixel-level comparison per sprite pending |
| 3D models | Dreamcast Ninja chunk models with original textures (`1ST_READ.BIN`, `2_DP.BIN`) | none (mobile versions are 2D) | [dreamcast_models.md](dreamcast_models.md): export, UVs, textured render | models exported; animation mapping in progress |
| UI, fonts, logos | Dreamcast title logo, Start prompt and direction panels (`YAJIRUSI_yp01`–`yp04`) where available | Mobile art supplies most menus, HUD, fonts and cursors | `tools/export_dc_ui.py` exports the Dreamcast sheets. Puzzle 01 verifies the blue stock arrow in a headless capture. | partial |
| Localization | each language's own files (Dreamcast per-language folders, iOS/Android string tables) | English | extraction exists; per-language comparison pending | open |
| Stages | master registry ([stages.md](stages.md), `stage_registry.json`): every set from every version, duplicates merged by fingerprint | - | registry built | measured |

## Feature provenance (rules)
Rules come from the original code of each version and are listed per subsystem in [version_matrix.md](version_matrix.md): Android 1.15 and iOS 1.1.2 / 1.0.2 / HD run tick for tick against the port (puzzle, battle, scoring, roulette selector, CPU players); the Dreamcast build is being covered function by function in the SH-4 interpreter (speed table, speed getters, roulette selector and scoring so far; one measured difference: the Dreamcast battle speed table ends in 4.0 where mobile has 2.0).

## Integrity of the mobile builds (2026-11-13)
The Dreamcast and GBA files are clean dumps; the iOS .ipa and Android .apk files come from distribution sites and may have been cracked, re-signed or had content added. Checks so far (no evidence of tampering with game logic, sound or presentation):
- Extra files only: `Payload/CCR.app/ORBiT` in both ORBiT builds, `Lz0PDA.nfo` in the iOS 1.1.2 build, `iTunesMetadata.plist` in most; the 1.14 APK is re-signed with a third-party key (`META-INF/SOAKEY_K.*`), 1.15 has `CERT.*`.
- String scan of all decompiled iOS builds and the Android library for crack/group markers: nothing beyond ordinary text.
- Code identity: the `__TEXT,__text` section of **HD 1.0 ORBiT is byte-identical to HD 1.0** (same SHA-256); iPhone 1.0 ORBiT, 1.0.2, 1.1 and 1.1.2 differ from each other as different releases.
- Audio files (music and effects) are byte-identical in every iOS build and the Android builds, which also matches the Dreamcast CD audio mapping ([audio.md](audio.md)).
- Game-logic code of Android 1.14/1.15 and iOS 1.0.2/HD/1.1.2 reproduces the same results as one another and as the port on all 2,548 puzzle stages and the battle/CPU/scoring tests; the Dreamcast functions checked so far (speed, roulette selector, scoring) agree with them in structure, and the one measured difference (battle speed table ending in 4.0) is a Dreamcast difference, not a cracking artefact.
Policy: where a mobile asset or text differs from the clean Dreamcast/GBA data, the clean source wins unless the mobile one is a documented original change; any mismatch is reported in the version matrix.

## Title / menu / HUD art: source comparison (2026-11-13)
Measured on the extracted files (width x height of the same sprite in each set):
| Piece | Android / iPhone (phone layout) | iPad HD (`ccrpad_png`, iOS HD 1.0) | Dreamcast |
|---|---|---|---|
| "TAP THE SCREEN!" prompt | 152 x 26 | **204 x 34** | "PRESS START BUTTON!" texture (different text) |
| Title rocket | 76 x 109 | **100 x 145** | rocket models/sprites in `ROCKET`/`TITLE` |
| Two-cat decoration | 84 x 61 | **112 x 81** | - |
| Menu bar atlas | 200 x 134 | **340 x 248** (bars 340 wide) | `MENU_selectmoji*`/`modeback*` tiles |
| Player bars, "Challenge", "CLEARED!", "FAILED!", "Winner!", "Draw!", "3 2 1", crowns, rockets, scoreboard pieces | smaller | **present at about 1.3x the phone size** | different art |
| Title logo and full-screen backgrounds | 484 x 322 images (logo = frame of a 1000 x 166 atlas) | **1024 x 768** backgrounds assembled from 128 x 128 tiles (no standalone title logo) | 512 x 512 tiles of a 640 x 480 screen (`TITLE_newtitle*`, `MENU_modeback*`) that must be assembled |
Conclusion so far: the phone sprites I used for the title and menu are the **smallest** version of the art. The iPad HD sprites are about 1.3x larger and also hold the HUD/result art (the placeholder HUD should use them). Neither mobile set is large enough for 4K without scaling; the Dreamcast screens are 640 x 480 native with tiles up to 512 x 512, so the Dreamcast logo/background art is not clearly higher quality than the iPad's. A best-of-all-versions choice per piece (largest source, scaled with high-quality filtering) still has to be made: the sprites from iPad HD, the backgrounds from the iPad tile maps once decoded (otherwise the phone images or Dreamcast tiles).

### Title logo: Dreamcast chosen (2026-11-13)
Measured: the Dreamcast logo (`TITLE_newtitle0`, ChuChu Rocket! speech-bubble logo with the mouse) is **510 x 244 pixels** of content; the phone logo is frame 0 of the Android atlas at **158 x 106**, and the iPad HD pack has no standalone title logo. The title screen now draws the Dreamcast logo (`tools/export_dc_ui.py`), scaled into the phone logo's place; the phone logo remains as a fallback when the Dreamcast files are missing. The title background stays the phone image until the iPad layout is implemented (the 1024 x 768 tile-map background is exported, see ui_art.md).

## Per-piece mobile texture sizes (2026-11-13)
[asset_quality.md](asset_quality.md), produced by `tools/measure_assets.py`, lists every mobile texture record with its size in each Android/iOS build: iPad HD (`ccrpad`) is the largest source for 125 of the 136 records it has, Android 1.14/1.15 for 82, the 1.1/1.1.2 character packs hold 109 and 100 records no other source has; 194 of 428 records present in more than one folder are the same size everywhere. The Dreamcast and GBA pieces are not yet in the table.

## Additions 2026-11-14
- **Playfield art** (floor tiles, pits, generator rings, rocket bases, wall bars, arrows, cursors, closed rocket spheres, digits): iPad HD pack sheets `r0930`, `r0645`, `r0732`, `r0651/r0663/r0675/r0687`, `r0729`, chosen because the iPad pack is the largest source for these records ([asset_quality.md](asset_quality.md)); placement and colours from the Android/iOS draw code ([ui_art.md](ui_art.md)).
- **Title prompt**: Dreamcast `ENGLISH/PRESSSTART` on keyboard/pad platforms, phone/iPad "TAP THE SCREEN!" on Android.
- **Puzzle sets**: main 100 and extra stages from the GBA ROM and mobile packs; Dreamcast Express (`DEPuzzle`) with the arrow stock decoded from the Dreamcast slot format ([dlc.md](dlc.md)). PuzzleP is selectable with stock derived from its VMS count/direction fields; verify live stock behavior against the original game.
- **Dreamcast sound effects**: decoded (4-bit AICA ADPCM) but not used in play: the sample rate is unknown ([audio.md](audio.md)); the mobile effect files are used.
- **GBA**: stages (2,566 boards) and the CPU player (transcribed from the ROM, diff-tested per routine) only; GBA art and sound are not used yet.

## Fallback text fonts (2026-11-18)
Without a BIOS image the Dreamcast's ROM-font text (Puzzle hint, Challenge clock) is drawn from glyphs `tools/export_dc_ui.py` rasterises at setup from two bundled, unmodified fonts (licence texts beside them in `tools/fonts/`; Google Fonts metadata lists `license: "OFL"` for both):
- `RobotoMono.ttf`: Roboto Mono, (c) 2015 The Roboto Mono Project Authors (Christian Robertson), SIL OFL 1.1, https://github.com/googlefonts/robotomono. Hint text at weight 400, squeezed to the BIOS cell's narrow proportions; its single-storey `g` and open `t` match the BIOS font.
- `MPLUSRounded1c-Regular.ttf`: M PLUS Rounded 1c, (c) 2016 The Rounded M+ Project Authors (Coji Morishita), listed OFL by Google Fonts; the OFL text shipped is the upstream M+ FONTS project's (see `NOTICE-MPLUSRounded1c.txt`; Google's repository carries no licence file for this family). Clock digits, chosen by the project owner by eye as the closest of the rounded sans fonts tried.
Chosen by scoring about 20 free fonts against the BIOS glyph bitmaps and by eye (Share Tech Mono, DotGothic16, Open Sans, Anonymous Pro, Oxygen Mono, Fira Mono, Space Mono, Inconsolata, Source Code Pro, Overpass Mono, Lato, Arimo, Nunito, Varela Round, Noto Sans and others were tried; commercial fonts such as HG Dot Gothic B are not redistributable). OFL permits bundling unmodified fonts with software and embedding rasterised output; the fonts are not sold on their own. A user-supplied BIOS replaces these stand-ins with the exact glyphs.
