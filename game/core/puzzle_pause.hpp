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
