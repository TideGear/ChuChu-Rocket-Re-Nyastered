// Transcription check for ccr::Tutorial (core/tutorial.hpp) against the step table read from the HD 1.0 decompile (setTutorialStep 0x3d03c).
// This compares the port with the decompile's constants, not with a running original, so it does not count as verification.
#include "../core/tutorial.hpp"
#include <cstdio>
using namespace ccr;
static int bad = 0;
#define CHECK(c) do { if (!(c)) { printf("FAIL line %d: %s\n", __LINE__, #c); ++bad; } } while (0)
int main() {
    Tutorial t; t.enabled = true; t.reset(0);
    CHECK(t.next == 0 && t.pending && t.mode == -1);
    t.process(false, false);                      // starts step 0
    CHECK(t.step == 0 && t.mode == 4 && t.mask == 0xff && t.next == 1 && t.text == -1);
    t.process(true, false);                       // a tap: waits delayInit (30 frames, the first counted in the same call) before step 1
    CHECK(t.pending && t.delay == 29.0f);   // the same call already counts one frame down
    for (int i = 0; i < 29; ++i) { t.process(false, false); CHECK(t.mask == 7); }
    t.process(false, false);
    CHECK(t.step == 1 && t.text == 0x1be && t.a34 == 0 && t.mode == 0 && t.next == 2);
    // step 3 waits for an arrow, auto-advances to step 2 after 0x1a4 ticks, and on a valid arrow the screen triggers step 4
    t.setStep(3, -1);
    CHECK(t.mode == 1 && t.t4c == 0x1a4 && t.to58 == 2 && t.f64 && t.f6c && t.next == 4);
    for (int i = 0; i < 0x1a4; ++i) t.process(false, false);
    CHECK(t.next == 2 && t.pending && t.sfx == 2);
    t.setStep(4, -1); CHECK(t.deleteArrows && t.text == 0x1c0 && t.next == 5);
    t.setStep(0x108, -1); CHECK(t.mode == 3 && t.t54 == 0x4b0 && t.to60 == 0x109 && t.next == 0x201);
    t.setStep(0x209, -1); CHECK(t.next == -1 && t.to60 == 0x20a);
    t.a78 = 0x300; t.setStep(0x1000, -1); CHECK(t.text == 0x1c9 && t.next == 0x300);
    t.reset(-1); CHECK(t.lesson == 1 && t.next == 0x100);   // retry/skip moves to the next lesson
    printf("tutorial: %s\n", bad ? "FAILED" : "ok"); return bad ? 1 : 0;
}
