# Audio: source comparison (music)

Method: `tools/audio_compare.py` decodes the 15 mobile music files (Ogg Vorbis, mono, 44.1 kHz, ~48 kbps nominal; byte-identical in every
iOS build and in Android) and the Dreamcast CD audio tracks (raw PCM, stereo, 44.1 kHz), and correlates 10 Hz band-energy envelopes.

## Mapping (mobile file -> Dreamcast track)
M00->04, M01->05, M02->06, M03->07, M04->08, M05->09, M06->10, M07->11, M08->12, M09->13, M10->14, M11->15, M12->16, M13->17.
- Every Dreamcast track starts with **2.0 s of extra lead-in** compared with the mobile file (lengths differ by exactly 2.0 s for the 1x tracks).
- **M08, M09 and M11: the Dreamcast tracks are 4.02x longer** (327 s, 334 s, 372 s vs 81, 83, 93 s): the disc stores four repetitions of the loop that the mobile files ship once.
- **M14** (a 5.2 s jingle) matches the final 5 s of Dreamcast track 04 (track 04 = M00 + the jingle).
- Envelope correlations: 0.86-0.94 for tracks with clean matches (04, 05, 14, 17), lower (0.36-0.74) on short or sparse pieces where the metric is weak; the 2.0 s offset and the
  exact 4x/1x length ratios are the stronger evidence. The mobile files are the Dreamcast recordings, trimmed and re-encoded.
- Unmatched: Dreamcast track 02 (9 s) and track 18 (7 s), probably stings/jingles; mobile has no counterpart identified yet.

## Conclusion
The Dreamcast CD audio is the **highest-quality music source** (lossless stereo; 4x loops give correct loop material). Mobile files are a lower-fidelity
re-encode of the same music. Loop points (where each piece loops) still have to be found, from the Dreamcast sound driver or from the mobile files' ends.
SFX and voices (iOS/Android 52 effects, mono ~70 kbps; Dreamcast `DP2SOUND.MLT`, `VOICE.AFS`) are not compared yet.

## Dreamcast sound containers (2026-11-12)
- `DPETC/VOICE.AFS`: AFS archive, 383 entries of 6,264 bytes (22,050 Hz mono ADX, 0.5 s). **All 383 decode to silence**: they are empty placeholders on this (US) disc, not voice lines (`tools/afs_extract.py`, `tools/adx.py`; ADX decoder verified on structure only because no audible data exists). Voices therefore come from elsewhere (the SMLT banks or the executable) or do not exist on the DC build; mobile voice lines have not been compared yet.
- `DPETC/DP2SOUND.MLT`, `ENGLISH/CHU2_SE.MLT` (per language): `SMLT` banks = 0x20-byte header + 8 section entries (tag, offset, size ...): SOSB, SMPB (sample bank, the AICA waveform data, ~1 MB), SMDB, SMSB, SFPB, SFOB, SFPW / SPSR. `tools/mlt_extract.py` splits them. AICA ADPCM decode and the sample/sequence tables are not decoded yet.
- `DPETC/MANATEE.DRV` (`SDRV`, 36 KB): the sound driver binary that runs on the AICA's ARM7 (next to decode for SFX timing/looping).

## AICA sample decoding attempt (2026-11-13)
`tools/aica_adpcm.py` implements the Yamaha AICA 4-bit ADPCM decoder (step table 230/307/409/512/614, step clamp 127..24576). Applied to the start of `DP2SOUND.MLT`'s SMPB bank (999,424 bytes) it gives loud, rough output (mean |x| ~15,000, roughness 0.36-0.41): not a plausible waveform. Entropy of SMPB blocks is 6.8-7.9 bits/byte and SMDB 6.0-7.5 bits/byte, so the banks may be compressed/encrypted or the samples need the SMDB/SOSB tables for start offsets, loop points and formats (some may be 16-bit PCM or 8-bit). Not validated: SFX still come from the mobile versions until the tables are decoded (next: read the sound driver/loader in `1ST_READ.BIN`).

## Sound-effect ids (2026-11-13)
Android 1.15 `ChuSECall(id, _)` (0x3d508) calls `AppData::playSFX(table[id].first)`; the 8-byte table at 0x63a00 maps ids 0..28 to themselves (ids 29..39 map to 40..50, the extra effects). Id 7 (cat enters rocket) is dropped when it fires less than 3 global ticks after its previous call. The app now follows this (battle hook: arrow placed 1, mouse home 6, cat in rocket 7 with the 3-tick rule, roulette 10, refused 0x13). Still to do: the sound index -> file mapping for ids >= 29, per-screen music selection and loop points, and the same tables for iOS/Dreamcast.

## Localization source (2026-11-13)
The Android resources already hold every UI string per language (`libccrjni/<lang>/NNNN.bin`, 414 files per language; text ones are small null-terminated strings). `tools/export_strings.py` exports them to one table: 6 languages (de, en, es, fr, it, ja); en/fr/de/es/it are UTF-8 or single-byte Latin-1 accented text, Japanese is stored as 16-bit glyph codes into the Japanese font sheet (not text). Example: resource 0125 "Puzzle", 0126 "Challenge"/"Défi"/"Herausforderung"/"Sfida"/"Desafío", 0127 "Battle", 0128 "Help & Options", 0129 the tutorial hint. Next: compare with the iOS and Dreamcast (ENGLISH/FRENCH/GERMAN/SPANISH/JAPANIESE) text, choose a best source per language, and map the glyph codes to Japanese text with the font sheet.
