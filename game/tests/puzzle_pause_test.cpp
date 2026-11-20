#include "../core/puzzle_pause.hpp"
#include "../app/dc_rocket.hpp"
#include <cstdio>
#include <cstdlib>

static void check(bool passed, const char* name) {
    if (!passed) {
        std::fprintf(stderr, "FAILED: %s\n", name);
        std::exit(1);
    }
    std::printf("passed: %s\n", name);
}

int main() {
    check(DcRocketLid::visibleAtLaunchAge(-1), "launch age minus one keeps domes");
    check(!DcRocketLid::visibleAtLaunchAge(0), "launch age zero hides domes");
    check(DcRocketLid::visibleAtLaunchAge(1), "launch age one restores domes");
    check(DcRocketLid::launchScaleAtAge(-1) == 1.25f, "launch age minus one enlarges domes");
    check(DcRocketLid::launchScaleAtAge(0) == 1.0f, "launch age zero has no dome scale");
    ccr::PuzzlePauseState tap;
    tap.press();
    for (int i = 0; i < 4; ++i) tap.tick(false);
    check(!tap.freeze, "tap does not freeze the board");
    check(!tap.overlay, "overlay waits until tick five");
    tap.tick(false);
    check(tap.overlay, "tap shows the overlay at tick five");

    ccr::PuzzlePauseState held;
    held.press();
    held.tick(true);
    held.tick(true);
    held.tick(true);
    check(held.freeze, "held Start freezes at tick three");
    held.tick(true);
    held.tick(true);
    check(held.overlay, "held Start shows the overlay at tick five");

    held.resume();
    check(!held.freeze && !held.overlay && held.ticks < 0, "resume cancels pause state");
    return 0;
}
