#pragma once

struct Startup {
    enum Phase { SegaIn = 2, SegaHold, SegaOut, SonicIn, SonicHold, SonicOut, BHIn, BHHold, BHOut, Title };
    Phase phase = SegaIn;
    float timer = 0;
    bool skipSonic = false;
    static constexpr float fade = 500000.0f;

    bool tick(float elapsed) {
        switch (phase) {
        case BHIn: case SonicIn:
            timer -= elapsed;
            if (timer <= 0) {
                const bool sonic = phase == SonicIn;
                phase = sonic ? SonicHold : BHHold;
                timer = 0;
                return sonic;
            }
            break;
        case SegaIn: case SegaOut: case BHOut: case SonicOut:
            timer += elapsed;
            if (timer >= fade) {
                if (phase == SegaIn) { phase = SegaHold; timer = 0; }
                else if (phase == SegaOut) { phase = BHIn; timer = fade; }
                else if (phase == BHOut && !skipSonic) { phase = SonicIn; timer = fade; }
                else { phase = Title; timer = fade; }
            }
            break;
        case SegaHold: case BHHold: case SonicHold:
            timer += elapsed;
            if (timer >= (phase == SonicHold ? 6000000.0f : 2000000.0f)) {
                phase = static_cast<Phase>(phase + 1);
                timer = 0;
            }
            break;
        case Title: break;
        }
        return false;
    }

    void press() {
        if (phase == BHHold) { phase = BHOut; skipSonic = true; timer = 0; }
        if (phase == SonicHold) { phase = SonicOut; timer = 0; }
    }

    int image() const { return phase <= SegaOut ? 3 : (phase >= BHIn ? 4 : 5); }
    int opacity() const { return phase == SegaIn ? static_cast<int>(timer / fade * 255.0f) : 255; }
    int blackout() const {
        switch (phase) {
        case SegaOut: case BHIn: case BHOut: case SonicIn: case SonicOut:
            return static_cast<int>(timer / fade * 255.0f);
        default: return 0;
        }
    }
};
