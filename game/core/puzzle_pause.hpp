#pragma once

namespace ccr {

struct PuzzlePauseState {
    int ticks = -1;
    bool freeze = false;
    bool overlay = false;

    void press() {
        ticks = 0;
        freeze = false;
        overlay = false;
    }

    // Dreamcast pause controller 0x8c01a174: Start sets the paused byte at once, and the main loop (0x8c018546) skips the task pass
    // 0x8c01909c from that frame, so every task (board, sky) stops on the press; there is no hold window.
    void pressNow() {
        ticks = -1;
        freeze = true;
        overlay = true;
    }

    void tick(bool held) {
        if (ticks < 0) return;
        ++ticks;
        if (ticks == 3 && held) freeze = true;
        if (ticks >= 5) {
            overlay = true;
            ticks = -1;
        }
    }

    void resume() {
        ticks = -1;
        freeze = false;
        overlay = false;
    }
};

} // namespace ccr
