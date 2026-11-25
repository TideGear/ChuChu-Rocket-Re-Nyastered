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
          dcMouseModelName(2, 3) == "mouse_a" &&
          dcMouseModelName(0, 3, 1) == "chao3" &&
          dcMouseModelName(0, 3, 2) == "pian3",
          "Dreamcast 3D mouse type and costume select the expected model");
    check(dcCharacterChoices(false, false) == std::vector<int>{0} &&
          dcCharacterChoices(true, false) == (std::vector<int>{0, 1}) &&
          dcCharacterChoices(false, true) == (std::vector<int>{0, 2}) &&
          dcCharacterChoices(true, true) == (std::vector<int>{0, 1, 2}),
          "Dreamcast costume selector follows Challenge and Mania unlock availability");
    {
        namespace fs = std::filesystem;
        const Settings oldSettings = app.settings;
        const std::string oldSaveDir = app.saveDir;
        const uint32_t oldChallengeMask = app.challengeMask;
        const bool oldChallengeMaskLoaded = app.challengeMaskLoaded;
        uint32_t oldProgress[4]; std::memcpy(oldProgress, app.clr, sizeof oldProgress);
        const bool oldProgressLoaded = app.clrLoaded;
        const fs::path dir = fs::temp_directory_path() / "ccr_costume_selector_test";
        std::error_code ec;
        fs::remove_all(dir, ec);
        fs::create_directories(dir, ec);
        app.saveDir = dir.string();
        app.settings.unlockAll = false;
        app.settings.characterStyle = 2;
        app.challengeMask = 0; app.challengeMaskLoaded = false;
        std::memset(app.clr, 0, sizeof app.clr); app.clrLoaded = false;
        check(app.dcCharacterStyle() == 0 && app.dcAvailableCharacterStyles() == std::vector<int>{0},
              "locked Dreamcast costumes remain unavailable and fall back to Normal");
        ChallengeMode::Save challenge{}; challenge.mask = 0x1ffffff;
        { FILE* f = fopen((app.saveDir + "/challenge.bin").c_str(), "wb"); if (f) { fwrite(&challenge, sizeof challenge, 1, f); fclose(f); } }
        uint32_t progress[4] = {0, 0, 0, 0x1ffffff};
        { FILE* f = fopen((app.saveDir + "/progress.bin").c_str(), "wb"); if (f) { fwrite(progress, sizeof progress, 1, f); fclose(f); } }
        app.challengeMaskLoaded = false; app.clrLoaded = false;
        check(app.dcCostumeUnlocked(1) && app.dcCostumeUnlocked(2) &&
              app.dcAvailableCharacterStyles() == (std::vector<int>{0, 1, 2}) && app.dcCharacterStyle() == 2,
              "Dreamcast costume availability reads the original Challenge and Mania save masks");
        DcOptionsMode options; options.page = 0; options.genRow = 0; options.genCharacter = 0;
        options.adjust(app, 1);
        check(app.settings.characterStyle == 1 && options.genCharacter == 1,
              "General Settings selects and persists the Chao style");
        options.adjust(app, 1);
        check(app.settings.characterStyle == 2 && options.genCharacter == 2,
              "General Settings advances to the Pian style");
        options.genRow = 5;
        options.accept(app);
        check(app.settings.characterStyle == 0,
              "Return to Initial Settings resets the Dreamcast character style");
        app.settings = oldSettings; app.saveDir = oldSaveDir;
        app.challengeMask = oldChallengeMask; app.challengeMaskLoaded = oldChallengeMaskLoaded;
        std::memcpy(app.clr, oldProgress, sizeof oldProgress); app.clrLoaded = oldProgressLoaded;
        fs::remove_all(dir, ec);
    }
    {
        const std::string packPath = app.root + "/dreamcast/models.bin";
        if (std::filesystem::exists(packPath)) {
            ModelPack costumeModels;
            check(costumeModels.load(app.ren, packPath), "load exported Dreamcast costume models");
            bool allPoses = true;
            for (int i = 0; i < 8; ++i) {
                const Model3D* chao = costumeModels.find("chao" + std::to_string(i));
                const Model3D* pian = costumeModels.find("pian" + std::to_string(i));
                allPoses = allPoses && chao && pian && chao->tris.size() == 100 && pian->tris.size() == 90;
            }
            check(allPoses, "Dreamcast model pack contains all eight Chao/Pian poses with the disc mesh sizes");
        }
    }
    {
        const Settings savedSettings = app.settings;
        const std::string oldOptionsSaveDir = app.saveDir;
        const auto optionsSaveDir = std::filesystem::temp_directory_path() / "ccr_options_settings_test";
        std::error_code optionsEc;
        std::filesystem::remove_all(optionsSaveDir, optionsEc);
        std::filesystem::create_directories(optionsSaveDir, optionsEc);
        app.saveDir = optionsSaveDir.string();
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
        options.genMusic = 14;
        dpad.cbutton.button = SDL_CONTROLLER_BUTTON_DPAD_RIGHT;
        options.event(app, dpad);
        check(options.genMusic == 0, "Dreamcast Music Test wraps after CD track 18");
        dpad.cbutton.button = SDL_CONTROLLER_BUTTON_DPAD_LEFT;
        options.event(app, dpad);
        check(options.genMusic == 14, "Dreamcast Music Test wraps back to CD track 4");
        options.genSe = 127;
        options.genRow = 4;
        dpad.cbutton.button = SDL_CONTROLLER_BUTTON_DPAD_RIGHT;
        options.event(app, dpad);
        check(options.genSe == 0 && app.settings.seTest == 0,
              "Dreamcast SE Test wraps after cue 127");
        dpad.cbutton.button = SDL_CONTROLLER_BUTTON_DPAD_LEFT;
        options.event(app, dpad);
        check(options.genSe == 127 && app.settings.seTest == 127,
              "Dreamcast SE Test wraps back to cue 0");
        app.settings.musicTest = 99;
        app.settings.seTest = 999;
        options.sel = 0;
        options.openRow(app);
        check(options.genMusic == 14 && options.genSe == 127,
              "General Settings restores bounded persisted test selections");
        options.genMusic = 1;
        options.genRow = 3;
        options.page = 0;
        App::Song savedSongs[15];
        for (int i = 0; i < 15; ++i) {
            savedSongs[i] = app.songs[i];
            app.songs[i].tried = true;
            app.songs[i].pcm.assign(8, 123);
            app.songs[i].loopStart = 0;
            app.songs[i].loopEnd = app.songs[i].pcm.size();
        }
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
        bool allTracksPlay = true;
        for (int i = 0; i < 15; ++i) {
            options.genMusic = i;
            options.event(app, confirm);
            allTracksPlay = allTracksPlay && app.curTrack == i && app.musOn && app.musPos == 0;
        }
        check(allTracksPlay,
              "confirm plays all Dreamcast Music Test selections (CD tracks 4-18)");
        app.stopSong();
        SDL_CloseAudioDevice(app.adev);
        app.adev = 0;
        for (int i = 0; i < 15; ++i) app.songs[i] = std::move(savedSongs[i]);
        app.settings = savedSettings;
        app.saveDir = oldOptionsSaveDir;
        std::filesystem::remove_all(optionsSaveDir, optionsEc);
    }
    {
        namespace fs = std::filesystem;
        const std::string oldSaveDir = app.saveDir;
        const fs::path saveDir = fs::temp_directory_path() / "ccr_records_chord_test";
        std::error_code ec;
        fs::remove_all(saveDir, ec);
        fs::create_directories(saveDir, ec);
        app.saveDir = saveDir.string();
        ChallengeMode::Save seed{};
        seed.mask = 0x15;
        seed.best[0] = 91;
        seed.best[24] = 123;
        { FILE* f = fopen((app.saveDir + "/challenge.bin").c_str(), "wb"); check(f != nullptr, "create Challenge save"); if (f) { check(fwrite(&seed, sizeof seed, 1, f) == 1, "seed Challenge records"); fclose(f); } }
        const char unrelated[] = "keep progress";
        { FILE* f = fopen((app.saveDir + "/progress.bin").c_str(), "wb"); check(f != nullptr, "create unrelated progress save"); if (f) { check(fwrite(unrelated, 1, sizeof unrelated, f) == sizeof unrelated, "seed unrelated progress save"); fclose(f); } }
        DcOptionsMode options;
        options.page = 2;
        const SDL_JoystickID instance = SDL_JoystickGetDeviceInstanceID(device);
        SDL_Event trigger{};
        trigger.type = SDL_CONTROLLERAXISMOTION;
        trigger.caxis.which = instance;
        trigger.caxis.axis = SDL_CONTROLLER_AXIS_TRIGGERLEFT;
        trigger.caxis.value = SDL_JOYSTICK_AXIS_MAX;
        options.event(app, trigger);
        trigger.caxis.axis = SDL_CONTROLLER_AXIS_TRIGGERRIGHT;
        options.event(app, trigger);
        SDL_Event button{};
        button.type = SDL_CONTROLLERBUTTONDOWN;
        button.cbutton.which = instance;
        button.cbutton.button = SDL_CONTROLLER_BUTTON_A;
        options.event(app, button);   // 0x8c054600: A is only "Previous"; the delete chord needs Start (the footer's triangle)
        check(options.page == -1 && ChallengeMode::loadSave(app.saveDir).mask == 0x15,
              "Records L+R+A returns without deleting (the chord is L+R+Start)");
        options.page = 2;
        options.event(app, trigger);   // the right trigger is still held; press the left again
        trigger.caxis.axis = SDL_CONTROLLER_AXIS_TRIGGERLEFT;
        options.event(app, trigger);
        app.settings.characterStyle = 1;   // Chao needs every Challenge clear, so the original resets it to Normal
        button.cbutton.button = SDL_CONTROLLER_BUTTON_START;
        options.event(app, button);
        const ChallengeMode::Save cleared = ChallengeMode::loadSave(app.saveDir);
        check(cleared.mask == 0 && std::all_of(std::begin(cleared.best), std::end(cleared.best), [](uint32_t t) { return t == 0; }),
              "Dreamcast L+R+Start clears only Stage Challenge records");
        check(app.settings.characterStyle == 0, "Records delete resets the Chao costume to Normal");
        check(options.page == -1, "Records L+R+Start returns after deleting (Start is also Previous)");
        std::string preserved;
        check(readFile((app.saveDir + "/progress.bin").c_str(), preserved) && preserved == std::string(unrelated, sizeof unrelated),
              "Records delete preserves unrelated progress save");
        trigger.caxis.value = 0;
        trigger.caxis.axis = SDL_CONTROLLER_AXIS_TRIGGERLEFT;
        options.event(app, trigger);
        trigger.caxis.axis = SDL_CONTROLLER_AXIS_TRIGGERRIGHT;
        options.event(app, trigger);
        options.page = 2;
        app.settings.characterStyle = 2;
        button.cbutton.button = SDL_CONTROLLER_BUTTON_START;
        options.event(app, button);
        check(options.page == -1 && app.settings.characterStyle == 2, "Start alone returns from Records and keeps the Pian costume");
        options.page = 2;
        button.type = SDL_CONTROLLERBUTTONDOWN;
        button.cbutton.button = SDL_CONTROLLER_BUTTON_B;
        options.event(app, button);
        check(options.page == -1, "B returns from Dreamcast Records page");
        app.saveDir = oldSaveDir;
        fs::remove_all(saveDir, ec);
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
        puzzle.event(app, start);
        const int afterControllerResume = puzzle.sim.now;
        check(!puzzle.paused && !puzzle.pauseState.freeze && !puzzle.pauseState.overlay,
              "controller Start resumes the tap-triggered Puzzle overlay");
        puzzle.tick(app);
        check(puzzle.sim.now > afterControllerResume,
              "Puzzle simulation advances after controller resume");
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
        auto findFreeArrowCell = [&](int avoidX, int avoidY, int& x, int& y) {
            for (int row = 0; row < kRows; ++row) for (int col = 0; col < kCols; ++col) {
                if ((col != avoidX || row != avoidY) &&
                    !(battle.game.sim.coll[row][col] & (kRocket | kHole | kArrow | kGenerator))) {
                    x = col; y = row; return true;
                }
            }
            return false;
        };
        int ownX = -1, ownY = -1, otherX = -1, otherY = -1;
        check(findFreeArrowCell(-1, -1, ownX, ownY), "Arrow reset test finds a free cell");
        check(battle.game.placeArrow(0, ownX, ownY, 0), "Arrow reset test places the player's panel");
        battle.game.tick(); // Original arrow tasks register collision on the following tick.
        battle.game.rotateOwn = false;
        check(!battle.game.placeArrow(0, ownX, ownY, 1),
              "Arrow reset Off refuses to rewrite the player's existing panel");
        battle.game.rotateOwn = true;
        check(battle.game.placeArrow(0, ownX, ownY, 1),
              "Arrow reset On rewrites the player's existing panel direction");
        check(std::count_if(battle.game.sim.arrows.begin(), battle.game.sim.arrows.end(),
                            [&](const auto& arrow) { return arrow.live && arrow.owner == 0; }) == 1 &&
              battle.game.sim.arrows.back().dir == 1,
              "Arrow reset reuses the panel rather than adding another slot");
        check(findFreeArrowCell(ownX, ownY, otherX, otherY), "Arrow reset test finds another free cell");
        check(battle.game.placeArrow(1, otherX, otherY, 2), "Arrow reset test places another player's panel");
        battle.game.tick();
        check(!battle.game.placeArrow(0, otherX, otherY, 3),
              "Arrow reset cannot rewrite another player's panel");
    }
    app.models3d.clear();
    app.rouletteDraw.reset();
    SDL_JoystickDetachVirtual(device);
    SDL_DestroyRenderer(app.ren); app.ren = nullptr;
    SDL_DestroyWindow(app.win); app.win = nullptr;
    gApp = nullptr;
    SDL_Quit();
}
