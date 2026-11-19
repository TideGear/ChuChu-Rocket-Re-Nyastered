# Handoff — 2026-11-19

The user requested a stopping point, a committed/pushed checkpoint, and a handoff to a new conversation. The project is **not complete**. Resume the full scope in [goal.md](goal.md), with user-reported Puzzle completion/rocket/sound issues prioritized. Commit, push and release permission was explicitly granted. No new release was made during this wrap-up.

## First reads and current build

- [goal.md](goal.md): fidelity requirements, no placeholders, Dreamcast-image-only setup/play, all platforms/content remain in scope.
- [audit.md](audit.md): authoritative coverage. Component audio checks do not close an audited sound.
- [roadmap.md](roadmap.md#2026-11-19-puzzle-rocket-continuation-development-build-not-released): latest rocket/rendering measurements and known residue.
- [audio.md](audio.md): native sound derivation, original addresses, fixture commands, exact scope and remaining gaps.
- [PREVIEW_HANDOFF.md](PREVIEW_HANDOFF.md): published preview record. Its earlier RotateX/flame-key findings are superseded by the roadmap.

Latest retained development executable: `local/rocket-resume/ccr.exe`, using regenerated `local/preview-release/fresh-disc/assets`. Wrap-up also builds the current source target in `local/handoff-check/cmake/ccr.exe`. Neither is a new published release. Old model/UI caches need both updated exporters. Local binaries, original game files, BIOS and captured states are not committed.

## Rendering checkpoint

The checkpoint includes the previously local Puzzle launch implementation: `game/app/dc_rocket.hpp`, app/model rendering, updated model/UI exporters and their asset/audit/roadmap notes. Bodies, bases, opening lids, flame morph, smoke, shared floor/wall/rocket depth, result input timing and native Save Completed art are implemented in the development build. These are **partial**, not full-animation or full-frame parity passes.

Measured upper-board errors at ages 4/19/44/69 are 3.41750/6.38400/4.40094/2.84307; full-frame errors remain around 8. Result first visible task pass is after hold 211 Normal /106 Dash. Save Completed crop mean is .23197, but its text still has 1,377 differing pixels by one channel level. Do not close those audits. More detail and captures are in the roadmap and `local/rocket-resume`.

Still retain the user's other reports: a separated dark line near the cursor's upper-right during some pulse frames (derive pulse from original code); stage-select font/art must be Dreamcast-derived with no placeholders. Earlier cursor/font work is recorded in the existing handoff/audit; do not lose those requirements.

## Audio checkpoint

Latest verified sound commit before wrap-up: `df653d7` (monitor reads). Earlier checkpoints: `e3e8e10` fresh setup/filter-rate latching; `1100931` ARM word-write truncation; `177cc1f` global key scan; `d74158a` persistent controller changes; `cc8e055` driver voice worker; `0844aec` complete native note-on dispatch; `523b1f4` Timer-A driver sample clock.

Native Python components implement sequence commands/gates, allocation, complete voice/register setup, channel controllers, release, voice worker/status processing, PCM/ADPCM playback, envelopes/filter/periodic pitch LFO, global key scan, fresh register setup and sampled monitor reads. `ChannelCommands` and `SampledVoiceBank` are **not connected yet**, and native C++ gameplay SFX remain unwired. Cold bank/physical-slot initialization, real worker/FIFO latency, all instruments/modes, DSP returns and full original-loop cue WAV comparison remain open.

Latest evidence: 46,120 monitor reads exactly match original ARM read handlers (502 set-loop observations, 234 position-clamp reads), alongside 43,811 exact stereo pairs and 118 writes. Read fixtures use short synthetic loops, explicitly fresh channel history and a parked ARM main loop to exclude competing monitor polls. They are not original-game-loop verification. Missing-latch-consumption and incomplete-trace controls reject. Earlier setup/controller regression matches 175,244 stereo pairs/310 writes. Read `audio.md` for the scope of each result; do not add these overlapping counts into coverage totals.

The pinned reference core's DSP-disabled mode substitutes DSP-send output when a channel's direct output rounds to zero. Native fixture comparisons opt into that behavior explicitly; it is not DSP emulation. AFSEL/FEG monitoring remains unsupported by the pinned core and raises natively. Read hooks have side effects: unset `FLYCAST_AICA_READS`, `FLYCAST_AICA_READS_OUT`, `FLYCAST_AICA_WRITES` and synthetic `FLYCAST_AICA_KEY_ON` for ordinary original-loop observations.

## Next concrete audio step

Connect native dispatch and the voice worker to the playback bank with synchronous read/write callbacks and compare mixed access order against the original ARM instructions, then compare the resulting complete cue WAV against the actual reference core. Start with English cues 21/27/28. Reuse the verified pieces rather than replacing them with approximate WAV timing or mobile assets.

Important new static finding: note-on ARM `0x159c..0x15a8` performs four discarded reads through literal `0x18a4 = 0x802810` before selecting the next monitor at `0xac0`. Those reads consume the loop latch even though their values are unused. They must be included in the connected path. The source main loop selects a monitor, dispatches up to four FIFO commands, observes status, then processes timer flags; timer flags may coalesce. Exact counter edges are not exact dispatch timestamps.

An **untested** callback prototype was saved locally as `local/native-voice-wave/unverified-driver-io-prototype.py` and removed from the tracked code before stopping. It adds synchronous IO, read logging, select/observe methods and the four reads, but was never validated. Do not treat it as completed work. In a Unicorn comparison, hardware register callbacks must restore the bus's halfword/KYONEX effects after the emulated store instruction; an ordinary pre-store hook alone gets overwritten by Unicorn's pending 32-bit store. Compare read order, writes, full relevant RAM/voice records, register state and audio, not only final register words.

## Local tools and fixtures

- Python: `C:/Users/Tideg/AppData/Local/Programs/Python/Python312/python.exe` (Unicorn, NumPy, Pillow, sound tooling).
- Driver: `local/handoff-check/disc-cache/assets/dreamcast/files/ENGLISH/MANATEE.DRV`; English bank: adjacent `CHU2_SE.MLT`. Driver SHA is pinned in `dc_sound_pitch.py`.
- Original states: `local/handoff-check/failure-motion/g_04250.state` and `local/handoff-check/success-audio-source/s_00100.state`.
- Ghidra: `analysis/decomp/dc_1st/1ST_READ.BIN.c`; ARM listing: `local/handoff-check/sound-banks/manatee-arm.asm`.
- Pinned Flycast source: `local/tools/flycast-source-3a5267a`; reference DLL: absolute `C:\Dev\ChuChu Rocket\local\handoff-check\flycast-reference\flycast_libretro.dll`.
- Latest audio fixtures/scripts: `local/native-voice-wave/`: `check-monitor-final.py`, `capture-monitor.ps1`, `check-setup-final.py`, `check-arm.py`, `check-keys-final.py`, and corresponding CSV/state/WAV files. Synthetic fixture creators/capture scripts document the adjustments; do not confuse them with game-loop captures.
- Clock traces: `local/native-clock`; original model/export comparisons: `local/rocket-resume` and `local/session-resume`.
- Rebuild reference core with `local/handoff-check/sound-banks/build-reference.cmd`; fresh source patch must start from pinned pristine `sgc_if-3a5267a.cpp`. Never ship the local emulator/BIOS/game data.

Use `tools/quiet.ps1` for tests/captures. Shared processes such as `f117a`/`Mystify.scr` often taint load samples: retain deterministic functional evidence, not performance measurements, and never touch those processes. Redirect verbose core output inside `cmd.exe` to a file; avoid PowerShell native-stderr errors. Use headless captures, not the user's screen/audio.

## Worktree ownership

User-owned `game/tests/determinism_test.cpp` and `.vscode/` must remain untouched and unstaged. Git may show the test file as dirty from line endings even when its textual diff is empty. The wrap-up stages only this conversation's rendering/export/documentation checkpoint; no original data or local fixtures. The discarded sound callback prototype is outside the tracked tree. No test/capture processes should be left running when this handoff is delivered.
