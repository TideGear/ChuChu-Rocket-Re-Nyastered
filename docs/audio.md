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

## Dreamcast sound containers (corrected 2026-11-18)

- `DPETC/VOICE.AFS`: 383 ADX entries decoded to silence on the tested USA disc. This does not establish where every Dreamcast voice lives.
- `MANATEE.DRV` is the AICA ARM7 sound driver. Its channel setup, playback rates, envelopes and cancellation still need runtime verification.
- `tools/mlt_extract.py` reads the SMLT header and its count of 32-byte section entries. Each entry contains tag (+0), bank (+4), sound-RAM address (+8), RAM allocation size (+12), **file offset (+16)** and file size (+20). A file offset of 0xffffffff reserves RAM without a payload.
- The old extractor used the RAM address as a file offset. Earlier waveform smoothness, duration, rate and mobile-envelope comparisons used incorrect payloads and are invalid. Those assessments have been removed. The legacy `mlt_samples.py` also guesses SOSP address/format fields and must not supply gameplay audio.
- Corrected extraction checked all six MLT files on this disc (DP2SOUND plus five language banks): six file-backed sections apiece, with matching payload signatures. English CHU2_SE has 29 sequences in bank 0 and 99 in bank 1; DP2SOUND has 17 in bank 1. SOSB, SMPB and SMDB are distinct structured bank types, not interchangeable sample-data banks.

## Dreamcast sequence inventory (2026-11-18)

`tools/mlt_sequences.py <bank.MLT> <inventory.json>` exports event offsets, raw sequence-step times, notes/gates, program changes, controllers, pitch, tempo, references and loop markers. It follows format facts in [Manatools' sequence format notes](https://github.com/dakrk/manatools/blob/d61b1e34182d02dd3dd545ca7db15e6529a666ae/docs/msb%2Bmsd.hexpat) and header constants. Manatools was built locally as an independent comparison tool; none of its source is bundled into the game.

All 657 file-backed sequences across the six MLT files parsed. The English bank's 2,509 non-terminal events (all 128 sequences) matched Manatools' event dump field for field. Five synthetic regression tests cover note widths, post-event steps, extensions, reference expansion, cycles, truncation and bank pointer bounds. This verifies structural parsing against a second implementation, not original-driver execution or final audio.

| Bank 0 sequence | File offset in English CHU2_SE.MLT | Programs selected | Notes |
|---|---|---|---|
| 21 | 0x60d20 | 30, 31 | Four notes on channels 6/7 with pitch changes |
| 27 | 0x615b8 | 27 | Two notes: channel 2/key 69, then channel 1/key 72 |
| 28 | 0x61608 | 8, 15, 28, 25, 29, 24 | Multi-instrument jingle, including referenced event blocks |

## Dreamcast instruments and live channel registers (2026-11-18)

`tools/mlt_programs.py <bank.MLT> <inventory.json>` follows program pointers, four optional layers and 48-byte splits in SMPB/SMDB. It records note/velocity ranges, sample file and sound-RAM addresses, format flags, loops, layer delay, root key, and raw envelope/pitch/LFO fields. Format reference: [Manatools MPB notes](https://github.com/dakrk/manatools/blob/d61b1e34182d02dd3dd545ca7db15e6529a666ae/docs/mpb.hexpat). All six disc banks parse: 846 program entries and 1,567 splits. Nine synthetic tests across the sequence/program parsers check field widths, references, truncation and sample bounds.

`tools/oracle/dc_aica_state.py <snapshot.state> <loaded.MLT> <report.json>` checks the observed Flycast raw state header 0x356, locates sound RAM by matching all supplied bank headers, verifies every referenced sample range against the disc, and reads channel registers. It supports this tested state layout only. The layout and register fields are cross-checked with Flycast's [AICA serialization](https://github.com/flyinghead/flycast/blob/master/core/hw/aica/aica_if.cpp) and [channel register definitions](https://github.com/flyinghead/flycast/blob/master/core/hw/aica/sgc_if.cpp). A key-on bit alone does not establish that a channel is still audible.

English program 27 uses PCM16 at file offset 0x3f06a / sound RAM 0x66f6a, root key 84, no loop, endpoint 26,544. In A1 failure frame 4250, channels 0 and 2 both reference that address and endpoint in PCM16 mode; their pitch words are 0x72ba and 0x7800. All 98 distinct sample ranges in the loaded English banks match the disc bytes. The C1 clear frame 4350 state also passes the sample check, with no key-on flags then. Across failure-motion `g_04205.state` through `g_04250.state`, program 27's channels appear by frame 4210 and remain key-on through 4250; frame 4205 has none. Other channels briefly overlap. State-header and loaded-sample corruption controls are rejected.

Success programs 30/31 reference ADPCM samples at sound RAM 0x7d8a8/0x7ea1a, with roots 89/88. These are bank references, not yet live success-channel verification. Program 28 and the other jingle instruments include both PCM16 and ADPCM splits, delayed layers and drum mappings.

Next: verify driver tempo, controller-to-bend paths, modulation, envelopes and channel mixing against indexed Flycast audio. Base pitch calculation is verified below. A preliminary fixed-rate PCM correlation did not validate the failure waveform; its captured LFO settings must be accounted for. No guessed-rate WAVs or numerically matching mobile clips should be treated as Dreamcast playback parity.

## Original-driver pitch calculation (2026-11-18)

`tools/dc_sound_pitch.py` reads the tested MANATEE driver's own tables and reproduces ARM routine 0x1c30. The 32-byte SDRV wrapper is excluded from ARM addresses. Table pointers are at ARM 0x2144/0x2148; fractional thresholds are at 0x1cc8, 0x1ccc and 0x1cd0. The calculation preserves byte wrapping, signed fine tuning and truncation; it does not replace the tables with equal-tempered floating-point frequencies. A SHA-256 guard rejects unverified driver variants.

`tools/oracle/dc_pitch_probe.py <MANATEE.DRV> [<failure.state> <loaded.MLT>]` executes the original ARM routine under Unicorn with synthetic note/split records, no hardware stubs. All 48,640 cases matched: every pair of 128 note/root values, plus fine-tune boundary bytes and positive/negative raw bend values on four roots. With the live A1 failure snapshot, the parsed program root/fine fields produce exactly the captured 0x72ba/0x7800 pitch words. This is a direct-routine verification plus two live-channel observations; it does not verify every call site's bend accumulation or audible synthesis.

Ghidra independently decompiled the driver into `local/handoff-check/sound-banks/decomp/manatee-arm.bin.c` (58 discovered functions). The writable project is `local/handoff-check/sound-banks/ghidra-project/ccr_dc_sound`; use installed `D:/ghidra-trial/ghidra/ghidra_12.2_PUBLIC/support/analyzeHeadless.bat`. Reimport the driver after removing its first 32 bytes, processor `ARM:LE:32:v4`, base 0, pre-script `tools/SeedDcSound.java`, post-script `tools/ExportC.java <output directory>`. The existing SH-4 decompile remains the source for game-side cue callers. Keep projects and generated decompiles local.

## Sound-effect ids (2026-11-13)
Android 1.15 `ChuSECall(id, _)` (0x3d508) calls `AppData::playSFX(table[id].first)`; the 8-byte table at 0x63a00 maps ids 0..28 to themselves (ids 29..39 map to 40..50, the extra effects). Id 7 (cat enters rocket) is dropped when it fires less than 3 global ticks after its previous call. The app now follows this (battle hook: arrow placed 1, mouse home 6, cat in rocket 7 with the 3-tick rule, roulette 10, refused 0x13). Still to do: the sound index -> file mapping for ids >= 29, per-screen music selection and loop points, and the same tables for iOS/Dreamcast.

### “Zero!” trigger audit (2026-11-14)

`App::loadAudio` loads the iOS clip `019.ogg` into SFX slot 19 (0x13). All six extracted iOS copies have identical SHA-256 hashes. The current app can request the slot through these paths:

| Action | What the sound indicates |
| --- | --- |
| Confirm **The Basics** or **Stage Challenge** on the main menu | The tutorial and Challenge entry are unfinished. |
| Confirm **Help & Options** | The iPad menu refuses entry if the Options screen's required assets are unavailable. The fallback menu has no Options route, even if it can display the label. |
| Confirm **Costumes** in Help & Options | The costume submenu is unfinished. This happens before any per-costume unlock check. |
| Confirm **How to Play** or **Credits** in Help & Options | These screens exist. They use the same refusal path when their asset checks fail. |
| Confirm a language whose exported text table is missing | The port plays the confirmation sound, then 0x13 and retains the current language. This includes Japanese with the current HD assets, and applies to any missing locale export. |
| Press **Previous** on the first iPad puzzle page, or **Next** on the last page or when progress still locks the next page | Intentional page refusal. The original iPad `StageSelectScreen::handleInput` uses 0x13 on these paths. Other stage sets use the plain list. |
| Attempt a refused arrow placement as battle player 1 | The port uses the clip for an invalid cell (existing arrow that cannot be rotated, rocket, hole, generator) or a placement rejected by the core during cursor lock or after the round. The intro and pending roulette checks can discard input before it reaches this hook. In Android, `AR_PutArrow` (0x286ac) plays 0x13 for local-player collision refusal in one branch. Its other branch delegates to 0x2859c, which rejects collisions without directly playing a sound. The port's individual refusal branches still need parity checks. |
| The battle clock reaches zero | Intentional countdown voice. `BattleGame::tick` evaluates `0x13 - secondsLeft`. The original HD battle timer also requests 0x13 at zero. |

Scope: the current port's SFX call sites and dispatch, checked against the local original code for stage-page refusal and the countdown. The original tutorial-completion gate refuses Puzzle, Stage Challenge and Battle with SFX 3. The port currently bypasses that gate. Its Stage Challenge button still cannot enter the mode. iPod Music and Game Center are hidden by the Options hit test and cannot trigger 0x13 there.

### iPad roulette cues

During Cat Mania, HD 1.0 `RL_Eve_NekoFever` (0x1dbbc) checks the gameplay flag and rolls once on each multiple of 16 before the event expires. A roll strictly below 0.3 requests effect 27 (`027.ogg`). This is separate from effect 7 for a cat entering a rocket. The port now plays effect 27 from its existing RNG check. A Unicorn probe covered 30 cases for the game flag, frame boundary, event expiry, and both sides of the threshold, including equality.

### Ordinary cat cues

The GBA mouse update at 0x08002c28 takes separate paths for a catch and a hole fall. In `tools/oracle/gba_mouse_death.py`, neither path requested audio directly during the handoff or through the tested death animation. The probe forced the contact flag or hole collision, ran the original task logic, and logged focus allocation and sprite submission. Catch and hole paths respectively requested the focus task in internal modes {2, 3, 7, 8} and {2, 3, 4, 7, 8}, unless a focus was pending. In the tested mode-0 fixture, a catch submitted 83 sprite updates across two tasks and a fall submitted 54 before deletion. The focus task and mode-level result audio still need tracing.

The GBA cat update at 0x08003140 sends a hole collision and a rejected rocket entry to the fall initializer at 0x08004570. `tools/oracle/gba_cat_fall.py` forces both outcomes in all nine internal modes and with focus already pending. Each fixture submitted 54 sprite updates and retired on the next update. A hole in mode 4 requests focus at the cat's location when no focus is pending. The rejected rocket path does not request focus. The forced-removal mask instead deletes the task immediately. None of these tested cat task paths called the monitored sound dispatchers (0x08024930, 0x0802495c). Focus-task and mode-level sounds are still open.

For an accepted rocket entry, the same probe forces the arrival helper's successful return and runs the original animation tasks. The initializer at 0x08004698 requests cue 36 for a normal cat or 43 for a large cat. The update at 0x08004640 submits three poses for 6, 6, and 5 updates, then retires the task on update 18. Both fixtures had a single sound request at entry. The arrival helper's score and mode side effects are outside this probe.

The shared GBA death marker requested by eligible mouse and cat paths does play sound. Its initializer at 0x080048e4 requests cue 62 once, which resolves to sequence 0x08081f5c. The update at 0x0800488c alternates no sprite submission and submission at priority 0 in 16-update blocks, yielding six blinks at the original position with sprite data at 0x080878a8. It retires on update 192 and leaves the pending byte at 0xff. `tools/oracle/gba_death_focus.py` verified this at three positions, stopping at sprite submission, deletion, and mixer start. In a separate booted-ROM fixture, `tools/oracle/gba_cat_playback.py` dispatched cue 62 and verified that it changed the digital mixer buffers, with a PCM voice at 0x08059768 active for 85 frames. Puzzle-specific timing and display behavior are recorded below.

In a running GBA Puzzle fixture (internal mode 8), a forced mouse catch or hole collision set the pending byte to 0xff and dispatched cue 62 that frame. The catch writes the byte from 0x08002e7c and the hole path from 0x08002eac. The remaining mode and input traces matched for both paths. The mode let the marker update only 120 times before clearing the pending byte at 0x08000f00, interrupting its standalone 192-update lifetime. No further cue played without input in the observed window. Tested taps of A, B, Start and R during the marker left its duration unchanged. A tapped one frame before the clear was ignored even though the button remained held across the transition. Starting on the clear frame, A or B requested cue 4 with the panel in stock (return address 0x0800c12f) or cue 6 with the panel placed under the cursor (0x0800c0b3). Start on the clear frame requested cue 35, and R requested cue 5 and resumed play, with subsequent mouse rescues requesting cue 37. The no-catch controls never set the pending byte. Cue 37 played when the placed panel routed mice into rockets. Run `tools/oracle/gba_puzzle_failure.py` without arguments to boot the local ROM and verify both failure paths and panel states across 74 cases. Other game modes remain open.

Normal Puzzle stages 8, 13 and 18 reach the hole failure naturally without arrows. Stages 14, 17, 20 and 22 reach the catch failure the same way. Stage 21 reaches a third failure when a cat enters a rocket. That stage sets the pending byte at 0x080035fe and dispatches both cue 36 (cat rocket entry) and cue 62 (death marker), in that order on the same frame. In all eight stages the marker runs for 120 updates before the mode clears the pending byte. Display OAM shows eight entries throughout each of three full 16-frame blinks and the 10-frame final blink. Headless pixel comparisons with those entries hidden confirm the marker bounds on stages 8, 14 and 21, including clipping at the top and bottom. The debug renderer has limited hardware priority and window support.

GBA Stage Challenge keeps the death marker active after its failure transition. Forced mouse catches on A1 and B1 and forced mouse and cat hole falls on C1 each dispatched cue 62. At frame 120 after the event, the mode at 0x0800823a wrote 0xff to the pending byte again. With no input the marker retired after its full 192 updates. In the tested C1 cat-hole case, A or Start at frame 151 after the event played cue 5 from 0x080082d2, then cleared the pending byte and interrupted the marker after 152 updates. Cue 59 followed when the stage restarted. B at the same time left the full marker sequence and pending byte intact. Natural failures with no arrows on A4 (mouse hole) and B5 (cat rocket entry) confirmed the same 192-update lifetime. B5 requested cue 36 before cue 62. The earliest accepted A or Start tap in the C1 fixture begins 135 frames after the collision, 15 frames after the mode rewrites the pending byte. Cue 5 follows one frame later. A tap begun one frame earlier remains ignored even when held across the boundary. The same A boundary holds on A4 and B5. See `tools/oracle/gba_challenge_failure.py` for 27 fresh-boot cases. Other Challenge groups remain open.

The GBA cat update (0x08003140) has separate cues for changing size and entering a rocket. A catch that crosses 50 plays cue 42 if the mode gates permit it. Catches below that threshold did not request a cue in the tested branch. Normal rocket entry plays 36 and large-cat rocket entry plays 43. Reaching 100 in the catch counter also takes the reset path and plays 43. The normal and large entry effects share the handler at 0x08004698. `tools/oracle/gba_cat_audio.py` exercised 12 cases under Unicorn, forcing collision and arrival results and running the original update, sound selection, and song table lookup at 0x08024930. Cues 36, 42, and 43 point to sequence headers 0x080816e4, 0x080818ac, and 0x080818c8, starting with programs 5, 67, and 30.

`tools/oracle/gba_cat_playback.py` also ran the original player and mixer. Cue 36 used the digital voice at 0x0803a9bc for 105 active video frames, and cue 43 used 0x080621f4 for 38. Both changed the PCM mix buffers compared with the same menu state without an injected cue. Cue 42 used the GBA hardware wave channel for 46 active frames and changed its registers and wave RAM. The PCM output timer was set to about 10,512 Hz. The headless harness measures mixer memory and register writes. Synthesizing the wave channel's final output, comparing assets across versions, and tracing remaining callers are still open.

Dreamcast `1ST_READ.BIN` also calls its sound dispatcher (0x8c01203a) with cue 7 at 0x8c011532 and 0x8c01d444, and with cue 27 at several sites including 0x8c01ce66, 0x8c02a8b2, and 0x8c02a8e2. SH-4 execution verified bank 0 sequence indices 7 and 27. A repeated cue-7 probe confirmed the cooldown refreshes for suppressed calls and only submits another request after at least three ticks. This verifies sequence dispatch and timing. The sample mapping, playback rate and remaining indirect call sites still need tracing.

The cat update requests `007.ogg` on the rocket-entry branch when the gameplay flag is set. The corresponding paths are HD 1.0 `CA_CatExe` (0x14524), iOS 1.0.2 (0x160e0), iOS 1.1.2 (0x126e8), and Android `FUN_00028ffc`. The walking and hole branches in these routines have no direct call to that cue. Cat Attack also requests slot 7. The iPad dispatcher refreshes its timestamp on every request, including suppressed requests, and requires three ticks since the last request. The port now keeps this cooldown on a clock that continues across rounds. A headless battle queued the decoded clip 17 times. The Dreamcast and GBA cat audio paths and indirect mobile callers still need tracing.

HD 1.0 `PuzzleLoop` (0x18294) has a separate ordinary-play use of the Cat Mania clip `027.ogg`. The running phase checks `MO_GetKilledMouse`, then `CA_CatRocketIn`. Either branch calls `FocusInit`, disables pause, clears the gameplay flag, requests cue 27 once at 0x184b0, and enters phase 6. The task server runs on the transition and subsequent ticks. Thus a cat catching a mouse can be followed by a cat sound in Puzzle through the failure handler even though the eaten-mouse task itself does not play it. Verified under Unicorn with each condition forced and a no-failure control. The port now uses that cue on the next Puzzle tick after detection. The iPad focus effect and automatic reset timing are now in the port. The one-frame teardown preserves the HUD while removing the board. The animated stars are present during gameplay and the board teardown.

HD 1.0 `RL_RouletteExec` plays `010.ogg` on the first visible tick and `011.ogg` 30 ticks later, when the drum stops. At tick 60 it plays the outcome voice. In outcome order, the file numbers are 119, 120, 117, 118, 122, 121, 123, and 124. `ChuSECall` maps the numbers 117–124 to AudioItem slots 32–39. The Japanese group uses the same files with a `J` prefix. Place Arrows Again also plays `013.ogg` on the event task's first tick. The port uses these original clips from the local iOS extraction. The original requests event music on the first visible roulette tick and passes a 60-tick transition to `BGM_Change` where applicable. The port's event music selection still follows the gameplay event state, and timed music transitions remain open.

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
- **Android** (1.14 and 1.15): 66 Ogg files in each `res/raw`, **all 66 byte-identical** to the matching iOS files (51 effects and all 15 songs). A SHA-256 comparison on 2026-11-14 identified `J024.ogg` as the one iOS effect absent from both APKs.
- **Best source per class**: songs = Dreamcast CD audio (lossless stereo; mobile is the re-encoded mono copy); sound effects = the mobile files for now (52 mono ~70 kbps Vorbis), since the Dreamcast AICA sample banks (`DP2SOUND.MLT`, `CHU2_SE.MLT`) are not decoded and validated yet (see the corrected container and sequence inventory above); the Dreamcast effects may be higher quality or different; `VOICE.AFS` on the US disc is silent.

## Flycast reference recording

Set `FLYHOST_WAV=<output.wav>` when running `tools/oracle/flyhost.cpp` to record the core's stereo 16-bit PCM at its declared sample rate. The companion `<output.wav>.frames.csv` records each video frame's first and end sample offsets. Both audio callback forms feed the same file. The host checks write/finalization errors and RIFF size limits. It continues to run without opening an audio device.

A 4,310-frame Challenge navigation/run/failure capture produced 3,259,242 stereo frames at 44,100 Hz with nonzero audio across menu and gameplay segments. A separate 180-frame run verified contiguous CSV ranges and exact equality between its last sample index and the WAV sample count (145,000). The delivered sample count exceeds nominal video time in these runs, so cue comparisons must use the frame index. These checks verify capture infrastructure. Cue identification, looping, fades and playback parity remain open.

## Dreamcast Challenge transition requests

The Ghidra decompile and direct SH-4 execution of the three transition routines agree on the following calls to sound dispatcher 0x8c01203a. Run `tools/oracle/dc_challenge_sound.py <Flycast .ram>` with the interpreter's numpy dependency. The probe executes each routine and the dispatcher, stubs its two cleanup calls, and records AICA submissions without playing audio.

| Transition routine | State written at 0x8c22d804 | Requested cues in order | AICA bank/sequence |
|---|---|---|---|
| 0x8c02a81a | 4, success | 21, 28 | (0,21), (0,28) |
| 0x8c02a8a0 | 5, result | 27, 28 | (0,27), (0,28) |
| 0x8c02a8d0 | 6, failure | 27 | (0,27) |

Both clear C1 frame 4350 and failed A1 frame 4250 RAM snapshots passed. The dispatcher maps cues below 29 to bank 0 in 0x8c012024, then submits through 0x8c0ed2f0. These are direct-routine checks, with no proof yet of every live entry route or timing. The port's mobile-clip hook currently requests 21 for both Success and Result and 27 for Failure. Mapping those numeric IDs directly to mobile clips is insufficient for Dreamcast parity. Decode sequences 21, 27 and 28 and validate them against indexed Flycast audio before changing playback.
