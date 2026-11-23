#define main ccrApplicationMain
#include "../app/main.cpp"
#undef main

static void check(bool passed, const char* name) {
    if (!passed) { fprintf(stderr, "FAILED: %s\n", name); std::exit(1); }
    printf("passed: %s\n", name);
}

int main(int argc, char** argv) {
    if (argc != 2) { fprintf(stderr, "usage: input_regression_test <assets>\n"); return 2; }
    SDL_setenv("SDL_VIDEODRIVER", "dummy", 1);
    check(SDL_Init(SDL_INIT_VIDEO | SDL_INIT_GAMECONTROLLER) == 0, "headless SDL initialization");
    int device = SDL_JoystickAttachVirtual(SDL_JOYSTICK_TYPE_GAMECONTROLLER,
        SDL_CONTROLLER_AXIS_MAX, SDL_CONTROLLER_BUTTON_MAX, 0);
    check(device >= 0, "virtual controller attachment");
    App app;
    app.headless = true;
    app.root = argv[1];
    gApp = &app;
    app.win = SDL_CreateWindow("test", 0, 0, GW, GH, SDL_WINDOW_HIDDEN);
    app.ren = SDL_CreateRenderer(app.win, -1, SDL_RENDERER_SOFTWARE);
    check(app.ren != nullptr, "software renderer creation");
    {
        PuzzleMode puzzle;
        check(puzzle.load(app.root, 0), "Puzzle load");
        check(puzzle.pad != nullptr, "Puzzle adopts an already-connected controller");
        puzzle.curX = 4; puzzle.curY = 4;
        puzzle.sim.removeArrow(4, 4);
        puzzle.stock[0] = 100;
        SDL_Event button{};
        button.type = SDL_CONTROLLERBUTTONDOWN;
        button.cbutton.which = SDL_JoystickInstanceID(SDL_GameControllerGetJoystick(puzzle.pad));
        button.cbutton.button = app.padMap.arrow[0];
        puzzle.event(app, button);
        check(puzzle.used(0) == 1, "controller places arrow before run");
        for (int phase : {1, 3}) {
            puzzle.state = phase;
            puzzle.sim.removeArrow(4, 4);
            puzzle.sim.placeArrow(4, 4, 1);
            puzzle.event(app, button);
            check(puzzle.used(0) == 0 && puzzle.used(1) == 1,
                  "controller preserves arrows during run and failure");
        }
        puzzle.state = 2;
        puzzle.clearFrames = 211;
        SDL_Event accept{};
        accept.type = SDL_CONTROLLERBUTTONDOWN;
        accept.cbutton.which = button.cbutton.which;
        accept.cbutton.button = SDL_CONTROLLER_BUTTON_A;
        puzzle.event(app, accept);
        check(puzzle.cur == 1, "already-connected controller advances after Puzzle clear");
        puzzle.state = 1;
        puzzle.running = true;
        puzzle.pauseState.press();
        for (int i = 0; i < 5; ++i) puzzle.pauseState.tick(true);
        puzzle.paused = true;
        SDL_Event click{};
        click.type = SDL_MOUSEBUTTONDOWN;
        click.button.button = SDL_BUTTON_LEFT;
        click.button.x = 200; click.button.y = 350;
        puzzle.hudButton(app, click);
        check(puzzle.pconf && puzzle.paused, "mouse opens resume confirmation");
        puzzle.hudButton(app, click);
        check(!puzzle.paused && !puzzle.pconf && !puzzle.pauseState.freeze &&
              !puzzle.pauseState.overlay && puzzle.pauseState.ticks < 0,
              "mouse resume clears held-Start pause state");
        int before = puzzle.sim.now;
        puzzle.tick(app);
        check(puzzle.sim.now > before, "simulation advances after mouse resume");
    }
    {
        BattleMode battle;
        app.settings.battleTime = 2;
        ccrSetEnv("CCR_MINUTES", "1", 1);
        check(battle.load(app.root, 0, 1), "Battle load with timer override");
        check(battle.game.roundFrames == 3600, "explicit timer overrides saved settings");
        // An absent environment variable uses the saved duration.
#ifdef _WIN32
        _putenv_s("CCR_MINUTES", "");
#else
        unsetenv("CCR_MINUTES");
#endif
        check(battle.load(app.root, 0, 1), "Battle load with saved duration");
        check(battle.game.roundFrames == 7200, "saved duration applies without override");
    }
    SDL_JoystickDetachVirtual(device);
    SDL_DestroyRenderer(app.ren); app.ren = nullptr;
    SDL_DestroyWindow(app.win); app.win = nullptr;
    gApp = nullptr;
    SDL_Quit();
}
