"""Check the cat cues in the original GBA mixer, without physical audio output."""
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_R0, UC_ARM_REG_SP

from gba_oracle import STOPADDR
from gba_session import boot_to_menu


def main():
    gba = boot_to_menu()
    uc = gba.uc
    initial = gba.save_state()
    table = gba.r32(0x08024958)
    players = gba.r32(0x08024954)
    mix_a = gba.r32(0x040000bc)
    mix_b = gba.r32(0x040000c8)
    mix_bytes = 2 * (mix_b - mix_a)
    assert mix_bytes == 3168
    timer_reload = gba.r16(0x04000100)
    assert timer_reload == 0xf9c4

    def run(cue=None):
        gba.load_state(initial)
        track = None
        if cue is not None:
            player = gba.r32(players + 12 * gba.r16(table + 8 * cue + 4))
            track = gba.r32(player + 0x2c)
            context = uc.context_save()
            uc.reg_write(UC_ARM_REG_R0, cue)
            uc.reg_write(UC_ARM_REG_SP, 0x03007a00)
            uc.reg_write(UC_ARM_REG_LR, STOPADDR | 1)
            uc.emu_start(0x08024931, STOPADDR, count=50000)
            uc.context_restore(context)
            assert gba.r32(player) == gba.r32(table + 8 * cue)

        output = []
        voices = set()
        active_frames = 0
        for _ in range(130):
            gba.run_frames(1)
            output.append((bytes(uc.mem_read(mix_a, mix_bytes)),
                           bytes(uc.mem_read(0x04000070, 6)), bytes(uc.mem_read(0x04000090, 16))))
            channel = gba.r32(track + 0x20) if track else 0
            if channel:
                active_frames += 1
                voices.add((gba.r8(channel + 1), gba.r32(channel + 0x24), gba.r8(channel + 8)))
        return output, voices, active_frames

    baseline, _, _ = run()
    cases = [
        (36, (0, 0x0803a9bc, 60), 105),
        (42, (3, 0x08029818, 65), 46),
        (43, (0, 0x080621f4, 60), 38),
    ]
    for cue, voice, duration in cases:
        output, voices, active_frames = run(cue)
        assert voices == {voice} and active_frames == duration, (cue, voices, active_frames)
        pcm_changed = any(a[0] != b[0] for a, b in zip(output, baseline))
        wave_changed = any(a[1:] != b[1:] for a, b in zip(output, baseline))
        assert (pcm_changed, wave_changed) == (voice[0] == 0, voice[0] == 3)
        print(f'cue {cue}: {active_frames} active frames, '
              f'{"digital mixer" if pcm_changed else "hardware wave channel"}, voice {voice[1]:#010x}')
    print(f'PCM output rate from timer 0: {16777216 / (65536 - timer_reload):.3f} Hz')


if __name__ == '__main__':
    main()
