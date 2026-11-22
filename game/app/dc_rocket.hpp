#pragma once
#include <algorithm>
#include <cmath>
#include <vector>

// USA 1ST_READ.BIN update 0x8c01b9a0. Values are task fields +0, +4,
// +0x20 and +0x30. Drawing uses RotateZ, not RotateX (0x8c0e0e38).
struct DcRocketLid {
    int phase = 0, timer = 0, angle = 0;
    float opening = 0;
    int age = 0;
    std::vector<int> smokeBirths;
    static bool visibleAtLaunchAge(int launchAge) { return launchAge != 0; }
    // The original Puzzle snapshots show shared rocket scale 1.20 with the launch flag clear (age 9), then 1.15 after the flag sets and launch tasks replace the parked domes (age 10). The writer that produces the pre-launch value is not yet established.
    static float launchScaleAtAge(int launchAge) { return launchAge == -1 ? 1.2f : 1.0f; }
    void tick(unsigned globalTime, int cellIndex) {
        ++age;
        // 0x8c01b8a0 spawns before the body rises; 0x8c01cbfa retires
        // the stationary smoke task at animation frame 15.
        if (age <= 201 && !(globalTime & 7)) smokeBirths.push_back(age);
        smokeBirths.erase(std::remove_if(smokeBirths.begin(), smokeBirths.end(),
            [&](int born) { return age - born >= 15; }), smokeBirths.end());
        switch (phase) {
        case 0:
            angle += 0x200;
            if (angle >= 0x4000) phase = 1;
            opening = std::sin(angle * (6.283185307f / 65536.0f));
            break;
        case 1:
            if (++timer >= 120) phase = ((globalTime + cellIndex) & 255) ? 2 : 3;
            break;
        case 2: opening = std::max(0.0f, opening - 0.005f); break;
        case 3:
            opening -= 0.005f;
            if (opening < 0.5f) { phase = 4; timer = 0; }
            break;
        case 4:
            opening = 0.5f - (++timer & 15) * 0.006666666828095913f;
            if (timer > 60) { phase = 5; timer = 0; }
            break;
        case 5: if (++timer > 60) phase = 6; break;
        case 6:
            opening += 0.01f;
            if (opening >= 0.8f) phase = 2;
            break;
        }
    }
};
