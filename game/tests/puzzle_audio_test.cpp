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

int main() {
    const auto normal = arrive(false);
    check(normal == std::vector<int>{6}, "normal mouse arrival uses Battle cue 6");

    const auto dash = arrive(true);
    check(dash == std::vector<int>{6}, "Dash arrival uses Battle cue 6 once");

    return 0;
}
