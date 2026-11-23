#include "../core/padmap.hpp"
#include <cstdio>
using namespace ccr;
static int fails = 0;
#define CHECK(c) do { if (!(c)) { printf("FAIL line %d: %s\n", __LINE__, #c); fails++; } } while (0)
int main() {
    PadMap d; PadMap r = parsePadMap(padMapText(d));
    CHECK(!memcmp(r.arrow, d.arrow, sizeof d.arrow) && r.pause == 6 && r.quitA == 4 && r.quitB == 6 && r.quitHoldTicks == 120);
    PadMap e = parsePadMap("arrow_up = Left_Shoulder # shoulder\narrow_down=dpad_down\npause = back\nquit_hold_ticks = 5\narrow_left = nonsense\n");
    CHECK(e.arrow[2] == 9 && e.arrow[0] == 12 && e.arrow[1] == 2 && e.pause == 4 && e.quitHoldTicks == 30);
    CHECK(parsePadMap("quit_hold_ticks = typo").quitHoldTicks == d.quitHoldTicks);
    CHECK(parsePadMap("quit_hold_ticks = 240\nquit_hold_ticks = 5 seconds").quitHoldTicks == 240);
    CHECK(parsePadMap("quit_hold_ticks = +240").quitHoldTicks == 240);
    CHECK(parsePadMap("quit_hold_ticks = 999999999999999999999").quitHoldTicks == 600);
    CHECK(padButtonLabel(0) == "A" && padButtonLabel(6) == "Start" && padButtonLabel(99) == "?");
    QuitHold q; bool done = false; for (int i = 0; i < 119; i++) done |= q.tick(true, true, 120); CHECK(!done); CHECK(q.tick(true, true, 120));
    q.tick(true, false, 120); CHECK(q.held == 0);
    DreamcastTitleChord chord;
    for (int button : {0, 1, 2, 3}) CHECK(!chord.button(10, button, true).activate);
    CHECK(!chord.button(11, 6, true).activate); // Chords cannot combine buttons from different pads.
    auto title = chord.button(10, 6, true);
    CHECK(title.consume && title.activate && chord.active);
    CHECK(chord.button(10, 1, false).consume && !chord.active); // Consume release; a later full hold can trigger again.
    CHECK(chord.button(10, 1, true).activate && chord.active);
    chord.disconnect(10);
    CHECK(!chord.active && !chord.button(10, 6, false).activate);
    printf("padmap test: %s\n", fails ? "FAILED" : "ok"); return fails;
}
