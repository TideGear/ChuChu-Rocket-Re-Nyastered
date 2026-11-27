#pragma once
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <vector>

namespace ccr {
// Mode 17 mouse task: init 0x8c0514c0, update 0x8c051200,
// draw 0x8c05144c. Read the script from the user's extracted executable,
// rather than embedding disc data. The tested USA table is 0x8c0cde18.
struct DcStaffMouse {
    struct Row {
        uint8_t type;
        float delta, target, reset;
        int16_t angleDelta, angleTarget, angleReset;
        float walk, scale;
    };
    std::vector<Row> script;
    int age = 0, row = 0, walk = 0;
    int16_t angle = 0;
    float pos[3] = {155.0f, 100.0f, 30.0f}, scale = 0.6f;
    bool alive = false;

    bool load(const char* executable) {
        *this = DcStaffMouse{};
        FILE* f = fopen(executable, "rb");
        if (!f) return false;
        bool ok = fseek(f, 0xbde18, SEEK_SET) == 0;
        for (int i = 0; ok && i < 256; ++i) {
            uint8_t b[32];
            if (fread(b, 1, sizeof b, f) != sizeof b) { ok = false; break; }
            Row r{}; r.type = b[0];
            memcpy(&r.delta, b + 4, 4); memcpy(&r.target, b + 8, 4); memcpy(&r.reset, b + 12, 4);
            memcpy(&r.angleDelta, b + 16, 2); memcpy(&r.angleTarget, b + 18, 2); memcpy(&r.angleReset, b + 20, 2);
            memcpy(&r.walk, b + 24, 4); memcpy(&r.scale, b + 28, 4);
            if (r.type > 4 || !std::isfinite(r.delta) || !std::isfinite(r.target) || !std::isfinite(r.reset) ||
                !std::isfinite(r.walk) || r.walk < 0 || r.walk > 255 || !std::isfinite(r.scale) || r.scale < 0) { ok = false; break; }
            script.push_back(r);
            if (r.type == 4) break;
        }
        fclose(f);
        alive = ok && !script.empty() && script.back().type == 4;
        if (!alive) script.clear();
        return alive;
    }
    // Returns the cat-spawn event at old counter 930 (0x8c051208).
    bool tick() {
        if (!alive) return false;
        const bool spawnCat = age++ == 930;
        const Row& r = script[row];
        walk = static_cast<uint8_t>(static_cast<int>(r.walk)); scale = r.scale;
        if (r.type <= 2) {
            float& p = pos[r.type]; p += r.delta;
            if (p == r.target) { p = r.reset; ++row; }
        } else if (r.type == 3) {
            angle = static_cast<int16_t>(static_cast<uint16_t>(angle + r.angleDelta));
            if (angle == r.angleTarget) { angle = r.angleReset; ++row; }
        } else alive = false;
        return spawnCat;
    }
    int pose() const { return ((walk * age) / 8) & 7; }
    int yaw() const { return static_cast<int>(angle * 182.0444488525390625f) & 0xffff; } // literal 0x8c0514a4
};
}
