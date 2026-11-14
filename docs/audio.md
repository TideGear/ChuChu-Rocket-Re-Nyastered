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

## Music logic (ported 2026-11-13)
Original (Android 1.15): music is chosen by game logic through `BGM_Play(id)` / `BGM_Change(id, fade)` -> `AppData::playSong(id - 4)` -> `java_music_play(song)`; the song number n is the mobile file `Mnn.ogg` and the Dreamcast CD track n + 4 ([audio mapping](audio.md)). Triggers read from the code:
- Title, Menu, Help, Download: song 0. Stage select, Challenge select, Help & Options: song 5. Editor: song 11. Sonic Team splash: song 14 (5 s jingle). End screen: `BGM_Play(0x10)` = song 12.
- Puzzle (`PuzzleInit`): `BGM_Play(0xd)` = song 9. Challenge (`ChallengeLoop`): `BGM_Play(0xc)` = song 8.
- Battle: song 1 while more than 30 s remain, song 2 in the last 30 s (`FUN_0003c534`: `TI_CountDownBCDTimer() > 0x2fff` -> BGM id 5, else 6; in global mode 0xe song 8). While a roulette event runs the song comes from the outcome table at 0x63994: outcomes 0..3 -> BGM ids 10, 9, 7, 8 = songs 6, 5, 3, 4; outcomes 4..7 keep the normal/urgent logic; `BGM_SetVolume(0x7f)` at the event start; at the event end (`FUN_0003c828`) the normal/urgent song returns. The battle countdown (`BGM_Change(6, 0x3c)`) and the result/lobby songs (`BGM_Change(0xb, 0x1e)`, `BGM_Fadeout(0x78)`) are only partly mapped.
App: `App::playSong` (restarts only on a different song), songs loaded on demand from the Dreamcast CD (best source), loop from the end of the disc's 2 s lead-in over the length of the mobile file (the disc stores four repetitions of songs 8, 9, 11), fallback to the mobile Ogg; song 14 plays once. Headless check (`CCR_AUDIO_TEST=1`, dummy audio device): a battle starts with song 1 (track 5) and switches to songs 4, 5, 3 during roulette events and back to 1 afterwards. Not yet ported: fade times (the second argument of `BGM_Change`), `BGM_Fadeout`, volume changes, the result-screen songs.

## Mobile audio: source comparison (2026-11-13, `tools/compare_sfx.py`)
- **iOS**: all six builds (1.0.2, HD 1.0, 1.1, 1.1.2 and both ORBiT builds) carry **byte-identical audio**: 52 sound effects (mono, 44.1 kHz, Vorbis nominal 70 kbps, about 1.0 MB in total) and 15 songs (mono, 44.1 kHz, nominal 48 kbps, about 7.7 MB).
- **Android** (1.14 and 1.15): 66 Ogg files in `res/raw`, **all 66 byte-identical** to the iOS files (52 effects + 14 of the 15 songs, or the same set re-packed). So for the mobile builds there is exactly **one** audio source; neither a re-sign/crack nor a platform difference altered any of it.
- **Best source per class**: songs = Dreamcast CD audio (lossless stereo; mobile is the re-encoded mono copy); sound effects = the mobile files for now (52 mono ~70 kbps Vorbis), since the Dreamcast AICA sample banks (`DP2SOUND.MLT`, `CHU2_SE.MLT`) are not decoded and validated yet (see the unvalidated ADPCM attempt above); the Dreamcast effects may be higher quality or different; `VOICE.AFS` on the US disc is silent.

## AICA sample bank: corrected assessment (2026-11-13)
The earlier note called the decoded bank "loud, rough output". A smoothness test (mean |sample difference| / mean |sample - mean|, white noise = 1.42) on 40,000-byte windows of `01_SMPB.bin`: read as 16-bit PCM 0.9-1.3, as 8-bit PCM 0.9-1.2 (both noise-like), but **as 4-bit AICA ADPCM 0.17-0.25 at offsets 0x0000 and 0x1000** (smooth, i.e. real band-limited audio; high-nibble-first is smoother than low-nibble-first at the start: 0.17 vs 0.25), rising to 0.34-0.43 deeper in the bank (different samples, rates or formats, or accumulated error across sample boundaries because the decoder restarts only at the bank start). So the bank **is** ADPCM and `tools/aica_adpcm.py` decodes real signal; what is missing is the sample directory (start offset, length, loop points, rate, format per effect: in `SMDB`/`SOSB`, not decoded), nibble order per sample, and a listening-free validation (planned: match each decoded effect's envelope against the mobile effect it was re-encoded into, since the mobile effects are the Dreamcast ones).
- Same test on `00_SOSB.bin` (the first MLT section, 393,216 bytes at file offset 0x18000, starts with a run of 0x80 bytes = ADPCM-style silence): as AICA ADPCM it is **very smooth** (roughness 0.03-0.08 at 0x1000 and 0x8000, high-nibble-first; 0.27 deeper in), so SOSB is a second ADPCM sample bank (not 8-bit PCM: 0.8-1.3). The MLT header is 32-byte entries (tag, 0, offset, size, ...): SOSB at 0x18000 size 0x60000, SMPB at 0x78000 size about 0x0F4000. `SMDB` (290,752 bytes, entropy 6-7.5 bits/byte, no 0x80 runs) is the likely sample/sequence directory but is not decoded. Next: parse SMDB as a table of (offset, length, loop, rate) records by looking for monotonically increasing offsets into SOSB/SMPB.
