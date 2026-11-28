#define main ccrApplicationMain
#include "../app/main.cpp"
#undef main

static void check(bool passed, const char* name) {
    if (!passed) { fprintf(stderr, "FAILED: %s\n", name); std::exit(1); }
    printf("passed: %s\n", name);
}

int main(int argc, char** argv) {
    if (argc != 2) {
        fprintf(stderr, "usage: challenge_controller_test <assets>\n");
        return 2;
    }
    SDL_SetHint(SDL_HINT_JOYSTICK_ALLOW_BACKGROUND_EVENTS, "1");
    check(SDL_Init(SDL_INIT_GAMECONTROLLER) == 0, "SDL controller initialization");
    int device = SDL_JoystickAttachVirtual(SDL_JOYSTICK_TYPE_GAMECONTROLLER,
        SDL_CONTROLLER_AXIS_MAX, SDL_CONTROLLER_BUTTON_MAX, 0);
    check(device >= 0, "virtual controller attachment");
    SDL_Joystick* stick = SDL_JoystickOpen(device);
    check(stick != nullptr, "virtual joystick open");
    App app;
    app.headless = true;
    app.root = argv[1];
    gApp = &app;
    {
        ChallengeMode challenge;
        check(challenge.load(app.root, 0), "normal Challenge load");
        check(challenge.controller != nullptr, "existing controller opened on entry");
        // Prefer the virtual pad attached by this test when the host also has
        // a physical controller. Challenge intentionally adopts the first pad.
        SDL_GameControllerClose(challenge.controller);
        challenge.controller = SDL_GameControllerOpen(device);
        check(challenge.controller != nullptr, "virtual controller opened for regression");
        std::vector<int> cues;
        challenge.sfx = [&](int id) { cues.push_back(id); };
        auto button = [&](int id) {
            SDL_Event event{};
            event.type = SDL_CONTROLLERBUTTONDOWN;
            event.cbutton.which = SDL_JoystickInstanceID(
                SDL_GameControllerGetJoystick(challenge.controller));
            event.cbutton.button = static_cast<Uint8>(id);
            challenge.event(app, event);
        };
        button(SDL_CONTROLLER_BUTTON_A);
        check(challenge.phase() == ChallengeGame::Countdown && cues.empty(),
              "controller skip enters Challenge countdown before its task pass");
        challenge.tick(app);
        check(cues == std::vector<int>{16}, "Challenge intro transition requests original cue 16");
        for (int i = 0; i < 34; ++i) challenge.tick(app);
        check(cues == std::vector<int>{16}, "Challenge ready cue waits until countdown frame 36");
        challenge.tick(app);
        check(cues == (std::vector<int>{16, 17}), "Challenge countdown frame 36 requests cue 17");
        for (int i = 0; i < 36; ++i) challenge.tick(app);
        check(cues == (std::vector<int>{16, 17, 18}), "Challenge countdown frame 72 requests cue 18");
        for (int i = 0; i < 36; ++i) challenge.tick(app);
        check(challenge.phase() == ChallengeGame::Play && cues == (std::vector<int>{16, 17, 18, 19}),
              "Challenge countdown frame 108 requests cue 19 before gameplay");
        float initialX = challenge.padAim.x;
        SDL_JoystickSetVirtualButton(stick, SDL_CONTROLLER_BUTTON_DPAD_RIGHT, 1);
        SDL_JoystickUpdate();
        for (int i = 0; i < 10; ++i) challenge.tick(app);
        check(challenge.padAim.x > initialX, "held D-pad moves cursor");
        SDL_JoystickSetVirtualButton(stick, SDL_CONTROLLER_BUTTON_DPAD_RIGHT, 0);
        SDL_JoystickUpdate();
        SDL_JoystickSetVirtualAxis(stick, SDL_CONTROLLER_AXIS_LEFTX, -32768);
        SDL_JoystickUpdate();
        float analogBefore = challenge.padAim.x;
        challenge.tick(app);
        check(challenge.padAim.x < analogBefore, "analog stick moves cursor");
        SDL_JoystickSetVirtualAxis(stick, SDL_CONTROLLER_AXIS_LEFTX, 0);
        SDL_JoystickUpdate();
        button(SDL_CONTROLLER_BUTTON_START);
        check(challenge.paused, "Start pauses");
        button(SDL_CONTROLLER_BUTTON_Y);

        int before = challenge.game.playTick;
        challenge.tick(app);
        check(challenge.game.playTick == before, "pause freezes simulation");
        check(challenge.game.sim.arrows.empty(), "pause blocks arrow placement");
        button(SDL_CONTROLLER_BUTTON_START);
        check(!challenge.paused, "Start resumes");
        button(SDL_CONTROLLER_BUTTON_Y);
        challenge.tick(app);
        challenge.tick(app);
        check(!challenge.game.sim.arrows.empty(), "face button places an arrow");
        const auto instance = SDL_JoystickInstanceID(
            SDL_GameControllerGetJoystick(challenge.controller));
        SDL_JoystickClose(stick);
        SDL_JoystickDetachVirtual(device);
        SDL_Event removed{};
        removed.type = SDL_CONTROLLERDEVICEREMOVED;
        removed.cdevice.which = instance;
        challenge.event(app, removed);
        check(challenge.controller == nullptr, "disconnect releases controller");
        device = SDL_JoystickAttachVirtual(SDL_JOYSTICK_TYPE_GAMECONTROLLER,
            SDL_CONTROLLER_AXIS_MAX, SDL_CONTROLLER_BUTTON_MAX, 0);
        check(device >= 0, "replacement controller attachment");
        SDL_Event added{};
        added.type = SDL_CONTROLLERDEVICEADDED;
        added.cdevice.which = device;
        challenge.event(app, added);
        check(challenge.controller != nullptr, "reconnect opens controller");

        cues.clear();
        challenge.begin(24);
        check(challenge.battle && challenge.bgame.type == 5, "final Challenge loads its Dreamcast Battle engine");
        challenge.bgame.phase = ChallengeGame::Play;
        for (int seconds = 5; seconds >= 0; --seconds) {
            challenge.bgame.game.clock = challenge.bgame.game.roundFrames - seconds * 60 - 1;
            challenge.tick(app);
        }
        check(cues == (std::vector<int>{14, 15, 16, 17, 18, 19}) &&
              challenge.phase() == ChallengeGame::Play,
              "final Challenge routes Battle's 5-to-0-second countdown cues through its sound hook");
        challenge.tick(app);
        check(cues == (std::vector<int>{14, 15, 16, 17, 18, 19, 27}) &&
              challenge.phase() == ChallengeGame::Failure,
              "final Challenge dispatches its failure cue after the timed-out battle");
    }
    SDL_JoystickDetachVirtual(device);
    SDL_Quit();
}
