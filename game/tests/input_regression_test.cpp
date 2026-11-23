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
    SDL_setenv("SDL_AUDIODRIVER", "dummy", 1);
    check(SDL_Init(SDL_INIT_VIDEO | SDL_INIT_AUDIO | SDL_INIT_GAMECONTROLLER) == 0, "headless SDL initialization");
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
    check(dcMouseModelName(0, 3) == "mouse3" &&
          dcMouseModelName(1, 3) == "mouse_b" &&
          dcMouseModelName(2, 3) == "mouse_a",
          "Dreamcast 3D mouse type selects normal, golden, and roulette models");
    {
        const Settings savedSettings = app.settings;
        DcOptionsMode options;
        SDL_Event dpad{};
        dpad.type = SDL_CONTROLLERBUTTONDOWN;
        dpad.cbutton.button = SDL_CONTROLLER_BUTTON_DPAD_RIGHT;
        options.page = 1;
        options.bRow = 0;
        options.bTime = 1;
        options.event(app, dpad);
        check(options.bTime == 2, "D-pad right adjusts Dreamcast Battle play time");
        options.bRow = 1;
        options.bSpeed = 3;
        options.event(app, dpad);
        check(options.bSpeed == 4, "D-pad right adjusts Dreamcast Battle speed");
        options.bRow = 2;
        options.bMice = 0;
        options.event(app, dpad);
        check(options.bMice == 1, "D-pad right toggles high-mouse setting");
        options.bRow = 3;
        options.bArrow = 0;
        options.event(app, dpad);
        check(options.bArrow == 1, "D-pad right toggles arrow reset");
        options.page = 0;
        options.genRow = 3;
        options.genMusic = 0;
        options.event(app, dpad);
        check(options.genMusic == 1, "D-pad right selects a Dreamcast music test track");
        dpad.cbutton.button = SDL_CONTROLLER_BUTTON_DPAD_LEFT;
        options.event(app, dpad);
        check(options.genMusic == 0, "D-pad left selects the previous Dreamcast music test track");
        options.genMusic = 1;
        options.genRow = 3;
        options.page = 0;
        App::Song savedSong = app.songs[1];
        app.songs[1].tried = true;
        app.songs[1].pcm.assign(8, 123);
        app.songs[1].loopStart = 0;
        app.songs[1].loopEnd = app.songs[1].pcm.size();
        SDL_AudioSpec want{};
        want.freq = 44100;
        want.format = AUDIO_S16SYS;
        want.channels = 2;
        want.samples = 64;
        want.callback = App::audioCb;
        want.userdata = &app;
        app.adev = SDL_OpenAudioDevice(nullptr, 0, &want, nullptr, 0);
        check(app.adev != 0, "dummy audio device for Dreamcast Music Test");
        SDL_PauseAudioDevice(app.adev, 1);
        SDL_Event confirm{};
        confirm.type = SDL_CONTROLLERBUTTONDOWN;
        confirm.cbutton.button = SDL_CONTROLLER_BUTTON_A;
        options.event(app, confirm);
        check(app.curTrack == 1 && app.musOn && app.musPos == 0,
              "confirm plays selected Dreamcast Music Test track 5");
        app.stopSong();
        SDL_CloseAudioDevice(app.adev);
        app.adev = 0;
        app.songs[1] = std::move(savedSong);
        app.settings = savedSettings;
    }
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
        puzzle.state = 1;
        puzzle.running = true;
        SDL_Event start{};
        start.type = SDL_CONTROLLERBUTTONDOWN;
        start.cbutton.which = button.cbutton.which;
        start.cbutton.button = app.padMap.pause;
        const int tapStartFrame = puzzle.sim.now;
        puzzle.event(app, start);
        for (int i = 0; i < 5; ++i) puzzle.tick(app);
        const int tapOverlayFrame = puzzle.sim.now;
        check(puzzle.paused && !puzzle.pauseState.freeze && tapOverlayFrame == tapStartFrame + 5,
              "Start tap shows the overlay after five advancing Puzzle ticks");
        puzzle.tick(app);
        check(puzzle.sim.now > tapOverlayFrame,
              "Puzzle board continues moving beneath the tap-triggered pause overlay");
        puzzle.paused = false;
        puzzle.pauseState.resume();
        puzzle.pauseState.press();
        puzzle.pauseState.freeze = true; // PuzzlePauseState's held-button timing is checked by puzzle_pause_test.
        puzzle.paused = true;
        const int beforeHeldPause = puzzle.sim.now;
        puzzle.tick(app);
        check(puzzle.pauseState.freeze && puzzle.sim.now == beforeHeldPause,
              "frozen Puzzle pause state stops the board");
    }
    {
        ChallengeMode challenge;
        check(challenge.load(app.root, 4), "Team Battle Challenge stage load");
        check(challenge.battle && challenge.bgame.game.teamMode,
              "Challenge team stage enables Team Battle lid pairing");
        const int* soloPartners = ChallengeMode::rocketPartnerLids(false);
        const int* teamPartners = ChallengeMode::rocketPartnerLids(true);
        check(soloPartners[0] == 2 && soloPartners[1] == -1 &&
              soloPartners[2] == -1 && soloPartners[3] == -1,
              "solo Challenge keeps only its blue/red goal dome");
        check(teamPartners[0] == 2 && teamPartners[1] == 3 &&
              teamPartners[2] == 0 && teamPartners[3] == 1,
              "Team Battle Challenge pairs both team lid colours");
        challenge.begin(24);
        check(challenge.battle && challenge.bgame.game.teamMode,
              "final Challenge battle also enables Team Battle lid pairing");
    }
    {
        BattleMode cpuBattle;
        cpuBattle.lv[0] = -1;
        cpuBattle.lv[1] = cpuBattle.lv[2] = cpuBattle.lv[3] = 0;
        check(cpuBattle.load(app.root, 0, 1), "CPU cursor Battle load");
        cpuBattle.dcProjection = true;
        cpuBattle.field = dcBattleField;
        const int startX = cpuBattle.game.cpu[1].cx;
        const int startY = cpuBattle.game.cpu[1].cy;
        cpuBattle.intro = 120;
        for (int i = 0; i < 240; ++i) cpuBattle.tickBattle(app);
        check(cpuBattle.cursorCell(1) != std::pair<int, int>{startX, startY},
              "Dreamcast CPU cursor tracks AI movement during live Battle");
    }
    {
        BattleMode battle;
        app.settings.battleTime = 2;
        ccrSetEnv("CCR_MINUTES", "1", 1);
        check(battle.load(app.root, 0, 1), "Battle load with timer override");
        battle.dcProjection = true;
        battle.field = dcBattleField;
        battle.game.cpu[1].cx = 5;
        battle.game.cpu[1].cy = 6;
        check(battle.cursorCell(1) == std::pair<int, int>{5, 6},
              "Dreamcast Battle CPU cursor follows its AI cell");
        battle.game.gbaCpu = true;
        battle.game.gbaEnv.curx[1] = 16;
        battle.game.gbaEnv.cury[1] = 10;
        check(battle.cursorCell(1) == std::pair<int, int>{7, 4},
              "Dreamcast Battle GBA CPU cursor follows its ROM cell");
        battle.game.gbaCpu = false;
        battle.dcProjection = false;
        check(!battle.unassignedPads.empty(), "Battle adopts an already-connected controller");
        const auto instance = SDL_JoystickInstanceID(
            SDL_GameControllerGetJoystick(battle.unassignedPads.front()));
        SDL_Event join{};
        join.type = SDL_CONTROLLERBUTTONDOWN;
        join.cbutton.which = instance;
        join.cbutton.button = SDL_CONTROLLER_BUTTON_A;
        battle.event(app, join);
        check(battle.pads[0] != nullptr,
              "Battle assigns an adopted controller on press-to-join");
        battle.intro = 120;
        bool freeCellFound = false;
        for (int y = 0; y < kRows && !freeCellFound; ++y) for (int x = 0; x < kCols; ++x) {
            if (!(battle.game.sim.coll[y][x] & (kRocket | kHole | kArrow | kGenerator))) {
                battle.curX[0] = x;
                battle.curY[0] = y;
                freeCellFound = true;
                break;
            }
        }
        check(freeCellFound, "Battle stage has a free arrow cell");
        battle.event(app, join);
        check(std::any_of(battle.game.sim.arrows.begin(), battle.game.sim.arrows.end(),
                          [](const auto& arrow) { return arrow.live && arrow.owner == 0; }),
              "joined Battle controller places an arrow");
        join.cbutton.button = app.padMap.pause;
        battle.event(app, join);
        check(battle.paused, "assigned Battle controller pauses the round");
        const int frozenFrame = battle.game.sim.now;
        battle.tick(app);
        check(battle.game.sim.now == frozenFrame, "Battle simulation stays frozen while paused");
        size_t arrowCount = std::count_if(battle.game.sim.arrows.begin(), battle.game.sim.arrows.end(),
                                          [](const auto& arrow) { return arrow.live; });
        bool secondCellFound = false;
        for (int y = 0; y < kRows && !secondCellFound; ++y) for (int x = 0; x < kCols; ++x) {
            if ((x != battle.curX[0] || y != battle.curY[0]) &&
                !(battle.game.sim.coll[y][x] & (kRocket | kHole | kArrow | kGenerator))) {
                battle.curX[0] = x; battle.curY[0] = y; secondCellFound = true; break;
            }
        }
        check(secondCellFound, "Battle has another free cell while paused");
        join.cbutton.button = app.padMap.arrow[0];
        battle.event(app, join);
        check(std::count_if(battle.game.sim.arrows.begin(), battle.game.sim.arrows.end(),
                            [](const auto& arrow) { return arrow.live; }) == arrowCount,
              "paused Battle rejects controller arrow placement");
        join.cbutton.button = app.padMap.pause;
        battle.event(app, join);
        check(!battle.paused, "assigned Battle controller resumes the round");
        battle.tick(app);
        check(battle.game.sim.now > frozenFrame, "Battle simulation advances after controller resume");
        battle.togglePause();
        SDL_Event restart{};
        restart.type = SDL_KEYDOWN;
        restart.key.keysym.sym = SDLK_r;
        battle.event(app, restart);
        check(!battle.paused && battle.game.frame == 0,
              "restarting a paused Battle resumes the new round");
        check(battle.game.roundFrames == 3600, "explicit timer overrides saved settings");
        check(battle.game.baseScale == 1.0f &&
              battle.game.generatorParams.pSpecial2 == GenParams{}.pSpecial2 &&
              !battle.game.rotateOwn,
              "default Dreamcast Battle options apply");
        // An absent environment variable uses the saved duration and the other 4P/Team settings.
#ifdef _WIN32
        _putenv_s("CCR_MINUTES", "");
#else
        unsetenv("CCR_MINUTES");
#endif
        app.settings.battleSpeed = 5;
        app.settings.battleMice = 1;
        app.settings.battleArrow = 1;
        check(battle.load(app.root, 0, 1), "Battle load with saved options");
        check(battle.game.roundFrames == 7200, "saved duration applies without override");
        check(battle.game.baseScale == 2.0f &&
              battle.game.generatorParams.pSpecial2 == GenParams{}.pSpecial2 * 5.0f &&
              battle.game.rotateOwn,
              "saved speed, high-mouse frequency, and arrow reset apply");
    }
    SDL_JoystickDetachVirtual(device);
    SDL_DestroyRenderer(app.ren); app.ren = nullptr;
    SDL_DestroyWindow(app.win); app.win = nullptr;
    gApp = nullptr;
    SDL_Quit();
}
