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
    check(puzzleTitleForAsciiUi("ChuChu Challenge", 4) == "ChuChu Challenge" &&
          puzzleTitleForAsciiUi("", 4) == "PUZZLE 5" &&
          puzzleTitleForAsciiUi(std::string("JP\x82\xa0", 4), 4) == "PUZZLE 5" &&
          puzzleTitleForAsciiUi(std::string("bad\x01title", 9), 4) == "PUZZLE 5",
          "Dreamcast puzzle titles use a numbered fallback when unavailable to the ASCII UI");
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
        DcEditMode titleEditor;
        titleEditor.titleEntry = true; SDL_StartTextInput();
        SDL_Event typed{}; typed.type = SDL_TEXTINPUT; SDL_strlcpy(typed.text.text, "A title ", sizeof typed.text.text); titleEditor.event(app, typed);
        typed = SDL_Event{}; typed.type = SDL_TEXTINPUT; SDL_strlcpy(typed.text.text, "with extras beyond twenty", sizeof typed.text.text); titleEditor.event(app, typed);
        check(titleEditor.titleInput == "A title with extras " && titleEditor.titleInput.size() == 20,
              "Puzzle Edit title entry accepts printable ASCII and enforces the VMS 20-character limit");
        SDL_Event titleDone{}; titleDone.type = SDL_KEYDOWN; titleDone.key.keysym.sym = SDLK_RETURN; titleEditor.event(app, titleDone);
        check(titleEditor.titleConfirmed && !titleEditor.titleEntry, "Puzzle Edit title entry confirms on Enter");
        check(titleEditor.currentPuzzle(1).title == titleEditor.titleInput, "Puzzle Edit exports the entered title bytes unchanged");
        DcEditMode padTitle; padTitle.titleEntry = true;
        SDL_Event padButton{}; padButton.type = SDL_CONTROLLERBUTTONDOWN; padButton.cbutton.button = SDL_CONTROLLER_BUTTON_Y; padTitle.event(app, padButton);
        padButton.cbutton.button = SDL_CONTROLLER_BUTTON_DPAD_RIGHT; padTitle.event(app, padButton);
        padButton.cbutton.button = SDL_CONTROLLER_BUTTON_A; padTitle.event(app, padButton);
        padButton.cbutton.button = SDL_CONTROLLER_BUTTON_B; padTitle.event(app, padButton);
        check(padTitle.titleLowercase && padTitle.titleInput.empty(), "Puzzle Edit controller title grid toggles case and deletes characters");
        padButton.cbutton.button = SDL_CONTROLLER_BUTTON_A; padTitle.event(app, padButton);
        padButton.cbutton.button = SDL_CONTROLLER_BUTTON_START; padTitle.event(app, padButton);
        check(padTitle.titleConfirmed && !padTitle.titleEntry && padTitle.currentPuzzle(1).title == "b",
              "Puzzle Edit controller grid enters lowercase and Start confirms the title");
        DcEditMode gridTitle; gridTitle.titleEntry = true;
        padButton.cbutton.button = SDL_CONTROLLER_BUTTON_DPAD_DOWN; gridTitle.event(app, padButton);
        padButton.cbutton.button = SDL_CONTROLLER_BUTTON_DPAD_DOWN; gridTitle.event(app, padButton);
        padButton.cbutton.button = SDL_CONTROLLER_BUTTON_DPAD_RIGHT; gridTitle.event(app, padButton);
        padButton.cbutton.button = SDL_CONTROLLER_BUTTON_A; gridTitle.event(app, padButton);
        check(gridTitle.titleInput == "V", "Puzzle Edit controller grid keeps horizontal navigation on its selected row");
        DcEditMode editor;
        check(editor.music() == 11,
              "Dreamcast Puzzle Edit requests CD track 15 from initializer 0x8c02dcc6");
        editor.startPlay();
        check(editor.fileScreen == 6 && !editor.playing,
              "Dreamcast Puzzle Edit refuses Play when there is no mouse");
        editor.st.tiles[0] = T_MouseS;
        editor.fileScreen = 0;
        editor.startPlay();
        check(editor.playing, "Dreamcast Puzzle Edit starts Play when a mouse exists");
        check(editor.music() == 11, "Puzzle Edit Play retains the editor's original CD track");
    }
    {
        namespace fs = std::filesystem;
        const std::string oldSaveDir = app.saveDir;
        const fs::path dir = fs::temp_directory_path() / "ccr_editor_delete_slots_test";
        std::error_code ec;
        fs::remove_all(dir, ec); fs::create_directories(dir / "puzzle_edit", ec);
        app.saveDir = dir.string();
        const fs::path atomicPath = dir / "atomic.vms", invalidChild = atomicPath / "child.vms";
        { FILE* f = fopen(atomicPath.string().c_str(), "wb"); if (f) { fwrite("old", 1, 3, f); fclose(f); } }
        check(writeFileAtomic(atomicPath.string(), std::vector<uint8_t>{'n', 'e', 'w'}), "atomic file replacement succeeds");
        std::vector<uint8_t> atomicBytes; { FILE* f = fopen(atomicPath.string().c_str(), "rb"); if (f) { uint8_t b[8]; size_t n; while ((n = fread(b, 1, sizeof b, f)) > 0) atomicBytes.insert(atomicBytes.end(), b, b + n); fclose(f); } }
        check(atomicBytes == std::vector<uint8_t>({'n', 'e', 'w'}), "atomic replacement writes the complete new file");
        { FILE* f = fopen(atomicPath.string().c_str(), "wb"); if (f) { fwrite("safe", 1, 4, f); fclose(f); } }
        check(!writeFileAtomic(invalidChild.string(), std::vector<uint8_t>{'b', 'a', 'd'}), "atomic write failure is reported");
        atomicBytes.clear(); { FILE* f = fopen(atomicPath.string().c_str(), "rb"); if (f) { uint8_t b[8]; size_t n; while ((n = fread(b, 1, sizeof b, f)) > 0) atomicBytes.insert(atomicBytes.end(), b, b + n); fclose(f); } }
        check(atomicBytes == std::vector<uint8_t>({'s', 'a', 'f', 'e'}), "atomic write failure preserves the previous file");
        DcEditMode emptyEditor;
        emptyEditor.openFiles(1);
        const bool emptyLoad = emptyEditor.fileScreen == 4 && emptyEditor.savedPuzzles.empty() &&
            std::string(emptyEditor.noDataPrompt()) == "Select a file to load.";
        emptyEditor.openFiles(2);
        check(emptyLoad && emptyEditor.fileScreen == 4 && emptyEditor.savedPuzzles.empty() &&
              std::string(emptyEditor.noDataPrompt()) == "Select a file to delete.",
              "Dreamcast Puzzle Edit shows the matching no-data prompt for empty Load and Delete screens");
        VmsPuzzle first, second, third;
        first.title = "FIRST"; second.title = "SECOND"; third.title = "THIRD";
        auto writePack = [&](const fs::path& path, const std::vector<VmsPuzzle>& puzzles) {
            const auto bytes = vms::writePack(puzzles); FILE* f = fopen(path.string().c_str(), "wb");
            if (f) { fwrite(bytes.data(), 1, bytes.size(), f); fclose(f); }
        };
        const fs::path firstPack = dir / "puzzle_edit" / "a.VMS", secondPack = dir / "puzzle_edit" / "b.VMS";
        writePack(firstPack, {first, second}); writePack(secondPack, {third});
        { FILE* f = fopen((dir / "puzzle_edit" / "b.VMI").string().c_str(), "wb"); if (f) { fputc(1, f); fclose(f); } }
        DcEditMode editor; editor.refreshPuzzleFiles();
        check(editor.savedPuzzles.size() == 3 && editor.puzzleSlots == std::vector<int>({0, 1, 0}),
              "Dreamcast Puzzle Edit tracks each slot within its own VMS pack");
        editor.fileIndex = 2; editor.deleteSelected();
        check(!fs::exists(secondPack) && !fs::exists(dir / "puzzle_edit" / "b.VMI") && editor.savedPuzzles.size() == 2,
              "Dreamcast Puzzle Edit deletes a puzzle in a later VMS pack");
        editor.fileIndex = 1; editor.deleteSelected();
        std::vector<uint8_t> bytes; { FILE* f = fopen(firstPack.string().c_str(), "rb"); if (f) { uint8_t buf[4096]; size_t n; while ((n = fread(buf, 1, sizeof buf, f)) > 0) bytes.insert(bytes.end(), buf, buf + n); fclose(f); } }
        std::vector<VmsPuzzle> remaining;
        check(vms::readPack(bytes, remaining) == 1 && remaining[0].title == "FIRST",
              "Dreamcast Puzzle Edit deletes the selected slot within a multi-puzzle pack");
        std::array<uint8_t, vms::kHeader> existingHeader{}; for (size_t i = 0; i < existingHeader.size(); ++i) existingHeader[i] = (uint8_t)(i * 19 + 7);
        memcpy(existingHeader.data(), "CHU_CHU__D01    ", 16);
        const fs::path userPack = dir / "puzzle_edit" / "user-puzzles.VMS";
        const auto seedPack = vms::writePack({first}, existingHeader.data());
        { FILE* f = fopen(userPack.string().c_str(), "wb"); if (f) { fwrite(seedPack.data(), 1, seedPack.size(), f); fclose(f); } }
        DcEditMode saver; saver.st.tiles[0] = T_MouseS + 3; saver.st.tiles[1] = T_Rocket;
        saver.savePuzzle(); saver.savePuzzle();
        std::vector<uint8_t> userBytes;
        { FILE* f = fopen(userPack.string().c_str(), "rb"); if (f) { uint8_t buf[4096]; size_t n; while ((n = fread(buf, 1, sizeof buf, f)) > 0) userBytes.insert(userBytes.end(), buf, buf + n); fclose(f); } }
        std::vector<VmsPuzzle> userPuzzles;
        check(vms::readPack(userBytes, userPuzzles) == 3 && userPuzzles[0].title == "FIRST" &&
              userPuzzles[1].title == "Puzzle 02" && userPuzzles[2].title == "Puzzle 03" &&
              !memcmp(userBytes.data(), existingHeader.data(), existingHeader.size()),
              "Dreamcast Puzzle Edit appends slots and preserves an existing VMS header");
        fs::remove(dir / "puzzle_edit" / "user-puzzles.VMI", ec);
        fs::create_directory(dir / "puzzle_edit" / "user-puzzles.VMI", ec);
        saver.savePuzzle();
        std::vector<uint8_t> afterFailedSave; { FILE* f = fopen(userPack.string().c_str(), "rb"); if (f) { uint8_t buf[4096]; size_t n; while ((n = fread(buf, 1, sizeof buf, f)) > 0) afterFailedSave.insert(afterFailedSave.end(), buf, buf + n); fclose(f); } }
        check(afterFailedSave == userBytes, "failed VMI update preserves the previous user VMS pack");
        fs::remove_all(dir / "puzzle_edit" / "user-puzzles.VMI", ec);
        DcEditMode namedSaver; namedSaver.st.tiles[0] = T_MouseS + 3; namedSaver.st.tiles[1] = T_Rocket; namedSaver.beginTitleEntry();
        SDL_Event nameText{}; nameText.type = SDL_TEXTINPUT; SDL_strlcpy(nameText.text.text, "Named Puzzle", sizeof nameText.text.text); namedSaver.event(app, nameText);
        SDL_Event nameDone{}; nameDone.type = SDL_KEYDOWN; nameDone.key.keysym.sym = SDLK_RETURN; namedSaver.event(app, nameDone);
        std::vector<uint8_t> namedBytes; { FILE* f = fopen(userPack.string().c_str(), "rb"); if (f) { uint8_t buf[4096]; size_t n; while ((n = fread(buf, 1, sizeof buf, f)) > 0) namedBytes.insert(namedBytes.end(), buf, buf + n); fclose(f); } }
        std::vector<VmsPuzzle> namedPuzzles;
        check(!namedSaver.titleEntry && vms::readPack(namedBytes, namedPuzzles) == 4 && namedPuzzles.back().title == "Named Puzzle",
              "Dreamcast Puzzle Edit title entry saves the entered name into a VMS slot");
        auto corruptPack = vms::writePack({first, second, third}); corruptPack[vms::kHeader + vms::kSlot + 26] = 0xff;
        { FILE* f = fopen(userPack.string().c_str(), "wb"); if (f) { fwrite(corruptPack.data(), 1, corruptPack.size(), f); fclose(f); } }
        saver.savePuzzle(); std::vector<uint8_t> afterCorruptSave;
        { FILE* f = fopen(userPack.string().c_str(), "rb"); if (f) { uint8_t buf[4096]; size_t n; while ((n = fread(buf, 1, sizeof buf, f)) > 0) afterCorruptSave.insert(afterCorruptSave.end(), buf, buf + n); fclose(f); } }
        check(saver.fileScreen == 5 && afterCorruptSave == corruptPack,
              "Dreamcast Puzzle Edit refuses to overwrite a damaged multi-slot VMS pack");
        app.saveDir = oldSaveDir; fs::remove_all(dir, ec);
    }
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
        puzzle.state = 2; puzzle.clearFrames = 211; puzzle.staffRoll = true;
        accept.cbutton.button = SDL_CONTROLLER_BUTTON_Y;
        puzzle.event(app, accept);
        check(puzzle.staffRoll, "Dreamcast Y does not replace the original Puzzle result Start shortcut");
        accept.cbutton.button = SDL_CONTROLLER_BUTTON_START;
        puzzle.event(app, accept);
        check(std::string(puzzle.next()) == "DC_STAFFROLL",
              "Dreamcast Start leaves a queued Puzzle result for the staff roll");
        {
            const bool oldDcLook = app.dcLook;
            SDL_Texture* oldStart = app.dcPuzzleStart.tex;
            SDL_Texture* oldCancel = app.dcPuzzleCancel.tex;
            app.dcLook = true;
            app.dcPuzzleStart.tex = app.dcPuzzleCancel.tex = reinterpret_cast<SDL_Texture*>(1);
            puzzle.staffRoll = false; puzzle.back = false; puzzle.cur = 0;
            puzzle.state = 2; puzzle.clearFrames = 211;
            accept.cbutton.button = SDL_CONTROLLER_BUTTON_Y;
            puzzle.event(app, accept);
            check(puzzle.cur == 0, "Dreamcast Y is ignored on an ordinary Puzzle result");
            accept.cbutton.button = SDL_CONTROLLER_BUTTON_START;
            puzzle.event(app, accept);
            check(puzzle.cur == 1, "Dreamcast Start advances an ordinary Puzzle result");
            puzzle.cur = 0; puzzle.state = 2; puzzle.clearFrames = 211;
            accept.cbutton.button = SDL_CONTROLLER_BUTTON_B;
            puzzle.event(app, accept);
            check(puzzle.back, "Dreamcast B leaves an ordinary Puzzle result");
            app.dcLook = false;
            puzzle.cur = 0; puzzle.back = false; puzzle.state = 2; puzzle.clearFrames = 211;
            accept.cbutton.button = SDL_CONTROLLER_BUTTON_Y;
            puzzle.event(app, accept);
            check(puzzle.cur == 1, "mobile-look Puzzle result retains its Y next-stage control");
            app.dcLook = oldDcLook;
            app.dcPuzzleStart.tex = oldStart;
            app.dcPuzzleCancel.tex = oldCancel;
            puzzle.back = false;
        }
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

        const bool oldDcLook = app.dcLook;
        SDL_Texture* oldStart = app.dcPuzzleStart.tex;
        SDL_Texture* oldCancel = app.dcPuzzleCancel.tex;
        auto failureStartIgnored = [&](bool dreamcast, SDL_Event input, const char* name) {
            app.dcLook = dreamcast;
            app.dcPuzzleStart.tex = dreamcast ? reinterpret_cast<SDL_Texture*>(1) : oldStart;
            app.dcPuzzleCancel.tex = dreamcast ? reinterpret_cast<SDL_Texture*>(1) : oldCancel;
            puzzle.state = 3; puzzle.running = false; puzzle.failureFrames = 1;
            puzzle.paused = false; puzzle.pauseState.resume();
            const int failureFrame = puzzle.sim.now;
            puzzle.event(app, input);
            check(!puzzle.paused && !puzzle.pauseState.freeze, name);
            puzzle.tick(app);
            check(puzzle.sim.now > failureFrame,
                  "failed Puzzle effects continue while pause is disabled");
        };
        failureStartIgnored(true, start, "Dreamcast controller Start is ignored during failure");
        SDL_Event keyboardStart{};
        keyboardStart.type = SDL_KEYDOWN;
        keyboardStart.key.keysym.sym = SDLK_p;
        failureStartIgnored(true, keyboardStart, "Dreamcast keyboard pause is ignored during failure");
        failureStartIgnored(false, start, "Mobile controller Start is ignored during failure");
        failureStartIgnored(false, keyboardStart, "Mobile keyboard pause is ignored during failure");
        app.dcLook = false;
        puzzle.state = 1; puzzle.running = true; puzzle.paused = false;
        puzzle.pauseState.press();
        for (int i = 0; i < 5; ++i) puzzle.pauseState.tick(false);
        puzzle.paused = puzzle.pauseState.overlay;
        puzzle.sim.killed = 1;
        puzzle.tick(app);
        check(puzzle.state == 3 && !puzzle.paused && !puzzle.pauseState.overlay &&
              !puzzle.pauseState.freeze && puzzle.pauseState.ticks < 0,
              "Puzzle failure transition cancels an already-open mobile pause overlay");
        app.dcLook = oldDcLook;
        app.dcPuzzleStart.tex = oldStart;
        app.dcPuzzleCancel.tex = oldCancel;
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
        {
            namespace fs = std::filesystem;
            const bool oldDcLook = app.dcLook, oldTestRun = app.testRun;
            const std::string oldSaveDir = app.saveDir;
            const uint32_t oldChallengeMask = app.challengeMask;
            const bool oldChallengeLoaded = app.challengeMaskLoaded;
            SDL_Texture* oldStaffRoll = app.dcStaffRoll.tex;
            SDL_Texture* oldChallengeResult = app.dcChallengeResult.tex;
            const fs::path saveDir = fs::temp_directory_path() / "ccr_challenge_unlock_roll_test";
            std::error_code ec;
            fs::remove_all(saveDir, ec);
            fs::create_directories(saveDir, ec);
            ChallengeMode::Save seed{}; seed.mask = 0x00ffffff;
            { FILE* f = fopen((saveDir.string() + "/challenge.bin").c_str(), "wb"); check(f != nullptr, "create final Challenge result save"); if (f) { fwrite(&seed, sizeof seed, 1, f); fclose(f); } }
            app.saveDir = saveDir.string(); app.testRun = false; app.dcLook = true;
            app.challengeMask = seed.mask; app.challengeMaskLoaded = true;
            app.dcStaffRoll.tex = reinterpret_cast<SDL_Texture*>(1);
            app.dcChallengeResult.tex = reinterpret_cast<SDL_Texture*>(1);
            challenge.begin(24); challenge.bgame.phase = ChallengeGame::Result;
            challenge.saveResult(app);
            check(challenge.finalChallengeComplete && challenge.chaoRollQueued &&
                  app.challengeMask == 0x1ffffff,
                  "final Challenge clear sets the complete mask and queues pending value 1");
            SDL_Event confirm{}; confirm.type = SDL_CONTROLLERBUTTONDOWN;
            confirm.cbutton.button = SDL_CONTROLLER_BUTTON_START;
            challenge.event(app, confirm);
            check(std::string(challenge.next()) == "DC_STAFFROLL_CHAO",
                  "final Challenge Start result input enters the Chao staff roll");
            DcStaffRollMode roll(app, true);
            check(roll.lines == (std::vector<std::string>{"You can now select Chao", "in the Options Menu!"}),
                  "final Challenge staff roll displays the Chao unlock text");
            challenge.begin(24); challenge.bgame.phase = ChallengeGame::Result;
            challenge.finalChallengeComplete = true; challenge.chaoRollQueued = true;
            SDL_Event confirmA{}; confirmA.type = SDL_CONTROLLERBUTTONDOWN;
            confirmA.cbutton.button = SDL_CONTROLLER_BUTTON_A;
            challenge.event(app, confirmA);
            check(std::string(challenge.next()) == "DC_STAFFROLL_CHAO",
                  "final Challenge A result input enters the pending-value-1 Chao staff roll");
            challenge.begin(24); challenge.bgame.phase = ChallengeGame::Result;
            challenge.finalChallengeComplete = true; challenge.chaoRollQueued = true;
            SDL_Event confirmB{}; confirmB.type = SDL_CONTROLLERBUTTONDOWN;
            confirmB.cbutton.button = SDL_CONTROLLER_BUTTON_B;
            challenge.event(app, confirmB);
            check(std::string(challenge.next()) == "DC_STAFFROLL_CHAO",
                  "final Challenge B result input also enters the pending-value-1 Chao staff roll");
            app.dcLook = oldDcLook; app.testRun = oldTestRun; app.saveDir = oldSaveDir;
            app.challengeMask = oldChallengeMask; app.challengeMaskLoaded = oldChallengeLoaded;
            app.dcStaffRoll.tex = oldStaffRoll; app.dcChallengeResult.tex = oldChallengeResult;
            fs::remove_all(saveDir, ec);
        }
    }
    {
        DcStaffRollMode roll(app);
        check(roll.music() == 12,
              "Dreamcast staff roll requests CD track 16 (song 12) from initializer 0x8c050abc");
        {
            const bool oldDcLook = app.dcLook;
            Sheet oldBiosFont = std::move(app.dcBiosAnsi);
            app.dcLook = false;
            SDL_SetRenderDrawColor(app.ren, 0, 0, 0, 255); SDL_RenderClear(app.ren);
            roll.drawUnlockText(app, "Unlock", 100, 100);
            SDL_Rect sample{100, 105, 1, 1}; Uint8 pixel[4]{};
            const bool read = SDL_RenderReadPixels(app.ren, &sample, SDL_PIXELFORMAT_RGBA32, pixel, 4) == 0;
            check(read && pixel[0] == 255 && pixel[1] == 255 && pixel[2] == 255,
                  "Dreamcast staff-roll unlock text uses the built-in font when no BIOS font is available");
            app.dcBiosAnsi = std::move(oldBiosFont); app.dcLook = oldDcLook;
        }
        if (app.dcStaffRoll.tex) {
            check(roll.mouse.alive, "staff-roll mouse loads its script from the extracted Dreamcast executable");
            int catSpawns = 0;
            // Original frame-loop RAM, local/staff-mouse-20261126/i_watch.bin.
            // Full 4037-age comparison is tools/oracle/staff_mouse_compare.py.
            for (int age = 1; age <= 4037; ++age) {
                catSpawns += roll.mouse.tick() ? 1 : 0;
                if (age == 361) check(roll.mouse.row == 1 && roll.mouse.angle == 0 && roll.mouse.pos[2] == 30.5f,
                                      "staff mouse starts translating on the pass after its 360-degree turn");
                if (age == 1246) check(roll.mouse.row == 8 && roll.mouse.angle == 180 && roll.mouse.pos[2] == 90.0f && roll.mouse.pose() == 7 && roll.mouse.yaw() == 32768,
                                       "staff mouse matches the original walk pose and position at age 1246");
                if (age == 2046) check(roll.mouse.row == 46 && roll.mouse.angle == 90 && roll.mouse.pos[0] == 162.0f,
                                       "staff mouse follows the original repeated square path");
            }
            check(!roll.mouse.alive && roll.mouse.pos[0] == 160.0f && roll.mouse.pos[2] == 130.0f && catSpawns == 1,
                  "staff mouse retires at original age 4037 after emitting one cat spawn");
            DcStaffRollMode actors(app);
            for (int age = 1; age <= 4099; ++age) {
                actors.tick(app);
                if (age == 931) check(actors.cat.alive && actors.cat.age == 0,
                                      "new staff cat waits until the next task-server pass before updating");
                if (age == 1246) check(actors.cat.age == 315 && actors.cat.row == 3 && actors.cat.pos[2] == 115.0f && actors.cat.phase() == 6.75f,
                                       "staff cat matches original task RAM at age 315");
                if (age == 2646) check(actors.cat.row == 65 && actors.cat.roll == 35,
                                       "staff cat executes its original Z rotation script");
                if (age == 2881) check(actors.flock.size() == 6 && actors.flock[0].age == 0 && actors.flock[5].x() == 175.0f,
                                       "first staff flock contains six newly created, unadvanced tasks");
                if (age == 2972) check(actors.flock.size() == 84 && actors.flock.back().born == 2041,
                                       "staff cat creates all fourteen original six-mouse groups");
                if (age == 3846) check(actors.cat.roll == -90 && actors.cat.wait == 101,
                                       "staff cat preserves the signed roll and unused wait channel");
            }
            check(!actors.cat.alive && actors.cat.age == 3168,
                  "staff cat retires at original age 3168");
            check(std::all_of(actors.flock.begin(), actors.flock.end(), [](const DcStaffFlockMouse& m) { return !m.alive && m.age == 501; }),
                  "all 84 flock tasks retire on the pass after old age 500");
        }
        SDL_Event start{}; start.type = SDL_CONTROLLERBUTTONDOWN;
        start.cbutton.button = SDL_CONTROLLER_BUTTON_START;
        roll.event(app, start);
        check(std::string(roll.next()) == "DC_TITLE",
              "Dreamcast Start exits the staff roll to the title as part of input mask 0x60e");
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
        check(battle.load(app.root, 0, 1), "Team Battle result rocket load");
        battle.game.teamMode = true;
        battle.game.score.team[0] = 12;
        battle.game.score.team[1] = 30;
        battle.endRound();
        const float expectedX = app.layF(0x3e8) + app.layF(0x3e4) +
            app.layF(0x30c + battle.winPoint * 0x14 + 0x64);
        check(battle.mode == 4 && battle.roundWinner == 1 && battle.rockets_.size() == 1 &&
              battle.rockets_[0].player == 5 && std::fabs(battle.rockets_[0].x - expectedX) < 0.001f &&
              battle.rockets_[0].y == 620.0f && battle.rockets_[0].tx == 361.0f,
              "Team Battle winner gets a result rocket in its team-colored icon lane");
        battle.intro = 120;
        for (int i = 0; i < 180; ++i) battle.tickBattle(app);
        check(battle.rockets_[0].state == 2,
              "Team Battle result rocket rises, pulses, then settles like the original result effect");
        BattleMode teamZero;
        check(teamZero.load(app.root, 0, 1), "Team Battle team-0 result load");
        teamZero.game.teamMode = true;
        teamZero.game.score.team[0] = 30;
        teamZero.game.score.team[1] = 12;
        teamZero.endRound();
        check(teamZero.rockets_.size() == 1 && teamZero.rockets_[0].player == 4 &&
              std::fabs(teamZero.rockets_[0].x - (app.layF(0x3e4) + app.layF(0x30c + teamZero.winPoint * 0x14))) < 0.001f,
              "Team Battle team-0 rocket uses its corresponding icon lane");
        BattleMode tie;
        check(tie.load(app.root, 0, 1), "Team Battle draw result load");
        tie.game.teamMode = true;
        tie.game.score.team[0] = tie.game.score.team[1] = 30;
        tie.endRound();
        check(tie.drawFlag == 1 && tie.rockets_.empty(),
              "Team Battle draw does not launch a winner rocket");
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
        {
            SDL_AudioSpec want{}; want.freq = 44100; want.format = AUDIO_S16SYS; want.channels = 2; want.samples = 256;
            app.adev = SDL_OpenAudioDevice(nullptr, 0, &want, nullptr, 0);
            check(app.adev != 0, "dummy audio device for Battle trigger taunts");
            SDL_PauseAudioDevice(app.adev, 1);
            const size_t oldSfxSize = app.sfx.size();
            app.sfx.resize(128);
            const auto old125 = app.sfx[125], old126 = app.sfx[126];
            app.sfx[125] = {100, 100}; app.sfx[126] = {200, 200}; app.voices.clear(); battle.banners.clear();
            SDL_Event trigger{}; trigger.type = SDL_CONTROLLERAXISMOTION; trigger.caxis.which = instance;
            trigger.caxis.axis = SDL_CONTROLLER_AXIS_TRIGGERLEFT; trigger.caxis.value = 20000; battle.event(app, trigger);
            check(app.voices.size() == 1 && app.voices.back().d == &app.sfx[125] &&
                  battle.banners.size() == 1 && battle.banners.back().mode == 5 && battle.banners.back().life == 120,
                  "Dreamcast Battle L trigger shows the 2-minute banner and requests cue 125");
            battle.event(app, trigger);
            check(app.voices.size() == 1 && battle.banners.size() == 1,
                  "held Battle L trigger does not retrigger its banner or cue");
            trigger.caxis.value = 0; battle.event(app, trigger);
            trigger.caxis.value = 20000; battle.event(app, trigger);
            check(app.voices.size() == 2 && app.voices.back().d == &app.sfx[125] && battle.banners.size() == 2,
                  "Battle L trigger can show its banner and request cue 125 again after release");
            trigger.caxis.axis = SDL_CONTROLLER_AXIS_TRIGGERRIGHT; battle.event(app, trigger);
            check(app.voices.size() == 3 && app.voices.back().d == &app.sfx[126] &&
                  battle.banners.size() == 3 && battle.banners.back().mode == 4 && battle.banners.back().life == 120,
                  "Dreamcast Battle R trigger shows the 1-minute banner and requests cue 126");
            app.voices.clear(); SDL_CloseAudioDevice(app.adev); app.adev = 0;
            app.sfx[125] = old125; app.sfx[126] = old126; app.sfx.resize(oldSfxSize);
        }
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
