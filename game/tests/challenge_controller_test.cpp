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
        auto button = [&](int id) {
            SDL_Event event{};
            event.type = SDL_CONTROLLERBUTTONDOWN;
            event.cbutton.which = SDL_JoystickInstanceID(stick);
            event.cbutton.button = static_cast<Uint8>(id);
            challenge.event(app, event);
        };
        button(SDL_CONTROLLER_BUTTON_A);
        check(challenge.phase() == ChallengeGame::Countdown, "controller skips intro");
        for (int i = 0; i < 108; ++i) challenge.tick(app);
        check(challenge.phase() == ChallengeGame::Play, "countdown reaches play");
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
        const auto instance = SDL_JoystickInstanceID(stick);
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
    }
    SDL_JoystickDetachVirtual(device);
    SDL_Quit();
}
