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

    bool load(const char* executable, long offset = 0xbde18, uint8_t terminalType = 4) {
        *this = DcStaffMouse{};
        FILE* f = fopen(executable, "rb");
        if (!f) return false;
        bool ok = fseek(f, offset, SEEK_SET) == 0;
        for (int i = 0; ok && i < 256; ++i) {
            uint8_t b[32];
            if (fread(b, 1, sizeof b, f) != sizeof b) { ok = false; break; }
            Row r{}; r.type = b[0];
            memcpy(&r.delta, b + 4, 4); memcpy(&r.target, b + 8, 4); memcpy(&r.reset, b + 12, 4);
            memcpy(&r.angleDelta, b + 16, 2); memcpy(&r.angleTarget, b + 18, 2); memcpy(&r.angleReset, b + 20, 2);
            memcpy(&r.walk, b + 24, 4); memcpy(&r.scale, b + 28, 4);
            if (r.type > terminalType || !std::isfinite(r.delta) || !std::isfinite(r.target) || !std::isfinite(r.reset) ||
                !std::isfinite(r.walk) || r.walk < 0 || r.walk > 255 || !std::isfinite(r.scale) || r.scale < 0) { ok = false; break; }
            script.push_back(r);
            if (r.type == terminalType) break;
        }
        fclose(f);
        alive = ok && !script.empty() && script.back().type == terminalType;
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

// Creator 0x8c051984, update 0x8c051580, draw 0x8c051920.
struct DcStaffCat : DcStaffMouse {
    int16_t roll = 0, wait = 0; // task +48/+50; the latter is not used by draw
    bool load(const char* executable) {
        const bool ok = DcStaffMouse::load(executable, 0xbe718, 6);
        alive = false; // preloaded script; A creates this task later
        return ok;
    }
    void start() {
        age = row = walk = 0; angle = 180; roll = wait = 0;
        pos[0] = 160.0f; pos[1] = 100.0f; pos[2] = 130.0f; scale = 0.6f;
        alive = !script.empty();
    }
    bool tick() {
        if (!alive) return false;
        ++age;
        const bool spawnFlock = age >= 1950 && age < 2048 && (age - 1950) % 7 == 0;
        const Row& r = script[row];
        walk = static_cast<uint8_t>(static_cast<int>(r.walk)); scale = r.scale;
        if (r.type <= 2) {
            float& p = pos[r.type]; p += r.delta;
            if (p == r.target) { p = r.reset; ++row; }
        } else if (r.type <= 5) {
            int16_t& a = r.type == 3 ? angle : r.type == 4 ? roll : wait;
            a = static_cast<int16_t>(static_cast<uint16_t>(a + r.angleDelta));
            if (a == r.angleTarget) { a = r.angleReset; ++row; }
        } else alive = false;
        return spawnFlock;
    }
    float phase() const { return ((walk * age) % 192) * 0.125f; } // 0x8c05193a / 0x8c051a0c
    int rollUnits() const { return static_cast<int>(roll * 182.0444488525390625f) & 0xffff; }
};

// 0x8c051ab6 creates six tasks at each cat event, slots 0..5.
// Update 0x8c051a60 retires on old age >=500; draw 0x8c051a76
// assigns Z = 30 + age % 100 and selects (age / 4) & 7.
struct DcStaffFlockMouse {
    int slot = 0, age = 0, born = 0;
    bool alive = true;
    void tick() { if (alive && age++ >= 500) alive = false; }
    float x() const { return 135.0f + 8.0f * slot; }
    float z() const { return 30.0f + age % 100; }
    int pose() const { return (age / 4) & 7; }
};
}
