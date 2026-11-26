// Headless regression for Puzzle rocket-entry cue scheduling across normal and Dash simulation passes.
#include "../core/sim.hpp"
#include <cstdio>
#include <cstdlib>
#include <vector>
using namespace ccr;

static void check(bool passed, const char* name) {
    if (!passed) { std::fprintf(stderr, "FAILED: %s\n", name); std::exit(1); }
    std::printf("passed: %s\n", name);
}

static Stage singleRocketStage() {
    Stage stage{};
    stage.tiles[0] = T_MouseS + East;
    stage.tiles[2] = T_Rocket;
    return stage;
}

static std::vector<int> arrive(bool dash) {
    Sim sim; Stage stage = singleRocketStage(); sim.load(stage);
    check(sim.placeArrow(1, 0, East), "place arrow toward rocket");
    PuzzleAudioRequests audio;
    std::vector<int> cues;
    for (int frame = 0; frame < 40 && sim.saved == 0; ++frame) {
        const int passes = dash ? 2 : 1;
        for (int pass = 0; pass < passes; ++pass) {
            sim.events.clear();
            sim.tick();
            audio.afterSimulationPass(sim.events, [&](int cue) { cues.push_back(cue); });
        }
    }
    check(sim.saved == 1, dash ? "Dash mouse reaches rocket" : "mouse reaches rocket");
    return cues;
}

static std::vector<int> catArrives() {
    Sim sim; Stage stage{}; stage.tiles[0] = T_CatS + East; stage.tiles[2] = T_Rocket; sim.load(stage);
    check(sim.placeArrow(1, 0, East), "place arrow toward rocket for the cat");
    PuzzleAudioRequests audio; std::vector<int> cues;
    for (int frame = 0; frame < 80 && sim.catsInRocket == 0; ++frame) { sim.events.clear(); sim.tick(); audio.afterSimulationPass(sim.events, [&](int cue) { cues.push_back(cue); }); }
    check(sim.catsInRocket == 1, "cat reaches rocket");
    return cues;
}

int main() {
    const auto normal = arrive(false);
    check(normal == std::vector<int>{6}, "normal mouse arrival uses Battle cue 6");

    const auto dash = arrive(true);
    check(dash == std::vector<int>{6}, "Dash arrival uses Battle cue 6 once");

    const auto cat = catArrives();
    check(cat == std::vector<int>{7}, "cat entering a rocket uses cue 7 (0x8c011532)");

    return 0;
}
