// The Basics (HD 1.0 PuzzleGameScreen tutorial): the step state machine, transcribed from the decompile
// (analysis/decomp/ios_hd10/CCR_ios_hd10.c): setTutorialStep 0x3d03c, triggerTutorial 0x3d524, processTutorial 0x3d568, resetTutorial 0x3d674.
// Field names give the original's PuzzleGameScreen offset. Logic only: the stage setup, input and drawing live in the app.
// Status: partial (no Flycast/mobile frame diff exists for it; the original's state per step is checked only against the decompile).
#pragma once
#include <cstdint>

namespace ccr {

struct Tutorial {
    bool enabled = false;      // +0xa22 (AppData +0x378 at screen entry)
    int next = 0;              // +0xa24 step to run when the current one triggers
    int delayInit = 0;         // +0xa28 frames of delay a non-immediate trigger waits
    int lesson = 0;            // +0xa2c
    int text = -1;             // +0xa30 text resource id shown in the dialog, -1 none
    int a34 = 0, a38 = 0;      // +0xa34/+0xa38 (set per step; consumers not traced yet)
    int mask = 0;              // +0xa3c bit 4 blocks arrow input, other bits are step flags
    int mode = -1;             // +0xa40 0 text, 1 wait for a valid arrow, 2 timer, 3 auto, 4 tap
    float delay = 0;           // +0xa44 countdown until the pending step starts
    bool pending = false;      // +0xa48
    int t4c = -1, t50 = -1, t54 = -1;   // +0xa4c/+0xa50/+0xa54 countdown timers
    int to58 = -1, to5c = -1, to60 = -1;   // +0xa58/+0xa5c/+0xa60 step each timer jumps to
    bool f64 = false, f6c = false, f74 = false, f7c = true;
    int step = 0;              // +0xa68 current step
    int a70 = 0, a78 = 0;      // +0xa70 / +0xa78 (step to return to for the end texts)
    bool deleteArrows = false; // set when the step calls AR_DeleteArrowsPuzzle
    int sfx = 0;               // number of ChuSECall(2, 0) calls made (the dialog tick sound), for tests

    // PuzzleGameScreen::triggerTutorial (0x3d524)
    void trigger(bool sound, bool immediate) {
        if (sound) ++sfx;
        delay = immediate ? 0.0f : (float)delayInit;
        pending = true;
    }

    // PuzzleGameScreen::resetTutorial (0x3d674)
    void reset(int n) {
        const bool fromLesson = n < 0;
        if (fromLesson) n = lesson;
        text = -1;
        if (fromLesson) ++n;
        mode = t4c = to58 = t50 = to5c = t54 = to60 = -1;
        next = n << 8; lesson = n;
        a34 = a38 = 0; delay = 0; mask = 0;
        f64 = false; pending = false; delayInit = 0; f6c = false; f74 = false; a70 = 0;
        trigger(false, true);
    }

    // PuzzleGameScreen::setTutorialStep (0x3d03c)
    void setStep(int s, int delayFrames) {
        if (!enabled) return;
        text = mode = t4c = to58 = t50 = to5c = t54 = -1;
        a34 = a38 = mask = 0;
        f64 = f6c = f74 = false; f7c = true; deleteArrows = false;
        delayInit = delayFrames < 0 ? 0x1e : delayFrames;
        step = s;
        int nx = 0x107;
        auto textStep = [&](int t, int c34, int c38, int m, int n) { text = t; a34 = c34; a38 = c38; mask = m; mode = 0; nx = n; };
        switch (s) {
        case 0x000: mode = 4; mask = 0xff; nx = 1; break;
        case 0x001: textStep(0x1be, 0x10, 0x10, 7, 2); break;
        case 0x002: textStep(0x1bf, 1, 1, 7, 3); break;
        case 0x003: mode = 1; t4c = 0x1a4; f6c = f64 = true; to58 = 2; nx = 4; break;
        case 0x004: deleteArrows = true; textStep(0x1c0, 2, 2, 7, 5); break;
        case 0x005: a38 = 2; mask = 2; mode = 2; t50 = 0x1a4; nx = 6; to5c = 4; break;
        case 0x006: text = -1; mask = 2; mode = 3; nx = 0x100; break;
        case 0x100: mode = 4; mask = 0xff; nx = 0x101; delay = 0; break;
        case 0x101: text = 0x1c1; mask = 7; mode = 0; nx = 0x102; break;
        case 0x102: textStep(0x1c2, 1, 1, 7, 0x103); break;
        case 0x103: mask = 2; t4c = 0x1a4; mode = 1; a38 = 1; f64 = f6c = true; to58 = 0x102; nx = 0x104; break;
        case 0x104: textStep(0x1c7, 0x20, 0x20, 7, 0x105); break;
        case 0x105: text = 0x1cc; mode = 0; mask = 7; nx = 0x106; break;
        case 0x106: textStep(0x1c0, 2, 2, 7, 0x107); break;
        case 0x107: a38 = 2; mode = 2; t50 = 0x1a4; to5c = 0x106; mask = 4; nx = 0x108; break;
        case 0x108: to60 = 0x109; mode = 3; t54 = 0x4b0; nx = 0x201; break;
        case 0x109: textStep(0x1c7, 0x20, 0x20, 0xff, 0x108); break;
        case 0x200: mode = 4; mask = 0xff; nx = 0x201; delay = 0; break;
        case 0x201: textStep(0x1c3, 8, 8, 0xff, 0x202); break;
        case 0x202: textStep(0x1c4, 4, 4, 7, 0x203); break;
        case 0x203: textStep(0x1c5, 1, 1, 7, 0x204); break;
        case 0x204: mask = 2; t4c = 0x1a4; to58 = 0x203; mode = 1; f64 = f6c = true; nx = 0x205; break;
        case 0x205: textStep(0x1c8, 0, 0, 7, 0x206); break;
        case 0x206: textStep(0x1c0, 2, 2, 0xff, 0x207); break;
        case 0x207: textStep(0x1cb, 2, 2, 0xff, 0x208); break;
        case 0x208: a34 = 2; a38 = 2; mode = 2; t50 = 0x1a4; mask = 6; to5c = 0x206; nx = 0x209; break;
        case 0x209: t54 = 0x4b0; to60 = 0x20a; mode = 3; nx = -1; break;
        case 0x20a: textStep(0x1c7, 0x20, 0x20, 0xff, 0x209); break;
        case 0x1000: text = 0x1c9; mode = 0; mask = 0xff; nx = a78; break;
        case 0x1001: text = 0x1ca; mode = 0; mask = 0xff; nx = a78; break;
        default: a34 = 0; return;   // unknown steps leave +0xa24 alone (the original jumps to its common exit)
        }
        next = nx;
        a34 = 0;
    }

    // PuzzleGameScreen::processTutorial (0x3d568), once per frame. tapFlag = Input flag 0x20, skipFlag = Input flag 0x40 (both consumed).
    void process(bool tapFlag, bool skipFlag) {
        if (!enabled) return;
        if (tapFlag && mode == 4) trigger(true, false);
        if (f74) { if (t54 > 0) t54 = 0x4b0; f74 = false; }
        if (skipFlag) t54 = -1;
        if (delay > 0.0f) { delay -= 1.0f; mask = 7; return; }
        if (pending) { pending = false; setStep(next, -1); return; }
        if (t4c > 0 && --t4c == 0) { next = to58; trigger(true, true); }
        if (t50 > 0 && --t50 == 0) { next = to5c; trigger(true, true); }
        if (t54 > 0 && --t54 == 0) { next = to60; trigger(true, true); }
    }
};

}  // namespace ccr
