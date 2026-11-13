# Asset and feature provenance (living document, 2026-11-13)

For each asset class: the source chosen, the evidence, and what is still unmeasured. "Measured" means a number produced by a script in `tools/`.

| Class | Chosen source | Fallback | Evidence | Status |
|---|---|---|---|---|
| Music | Dreamcast CD audio tracks 4-18 (lossless stereo 44.1 kHz; four loop repetitions on tracks 12, 13, 15) | iOS/Android Ogg mono ~48 kbps (identical in every iOS build and Android) | [audio.md](audio.md): track mapping, 2.0 s lead-in, 4.02x length ratios, envelope correlation 0.86-0.94 on clean matches | measured; loop points still to find |
| Sound effects | iOS/Android 52 effects (mono ~70 kbps) until the Dreamcast AICA banks decode | Dreamcast `DP2SOUND.MLT` / `CHU2_SE.MLT` | MLT sections split (`tools/mlt_extract.py`); AICA ADPCM not decoded | not yet compared |
| Voices | iOS/Android voice lines | none on the US Dreamcast disc | `VOICE.AFS`: 383 entries, all decode to silence ([audio.md](audio.md)) | measured (disc voices are empty placeholders) |
| 2D graphics | Dreamcast PVR textures (up to 512x512, 954 PVM textures + 1,081 in 2DP) for menus/UI where complete; iOS HD (up to 1024x548) for gameplay sprites | iOS 1.1.2 (up to 808x800), Android 1.15 (142 PNG, up to 1024x536; the rest in packs) | counts and maximum sizes measured on the extracted caches (2026-11-13) | partly measured; pixel-level comparison per sprite pending |
| 3D models | Dreamcast Ninja chunk models with original textures (`1ST_READ.BIN`, `2_DP.BIN`) | none (mobile versions are 2D) | [dreamcast_models.md](dreamcast_models.md): export, UVs, textured render | models exported; animation mapping in progress |
| UI, fonts, logos | to be chosen per screen (Dreamcast menus are 640x480 textures; iOS HD are native) | the other source | not measured | open |
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
