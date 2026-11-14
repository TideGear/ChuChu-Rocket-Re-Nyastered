// 16-bit angle helpers copied from the original (Android libccrjni.so: Core::subAngle 0x2bc40, Core::adjustAngle 0x2bc18, Core::diffAngle 0x2bc50) and the entity turn step
// (entity task +0x20 current angle, +0x24 target angle = heading << 14, +0x28 step = int(speed * 32768 / 12)). Verified against the original code by tools/oracle/make_angle_golden.py.
#pragma once
#include <cstdint>
namespace ccr {
inline int subAngle(int a, int b) { return (int16_t)(uint16_t)(((uint32_t)b & 0xffff) - ((uint32_t)a & 0xffff)); }      // signed 16-bit difference b - a
inline int diffAngle(int a, int b) { int s = subAngle(a, b); return s < 0 ? (int)(((uint32_t)(s * -0x10000)) >> 16) : s; } // absolute value (as the original computes it)
inline uint32_t adjustAngle(int cur, int target, int step) {
    uint32_t t = (uint32_t)target & 0xffff; int d = (int)t - (int)((uint32_t)cur & 0xffff);   // numeric difference, as in the original
    if (step < d || d < -step) {
        if ((int16_t)(uint16_t)d < 0) step = -step;                                          // direction from the sign of the 16-bit wrapped difference: shortest way round
        t = ((uint32_t)step + ((uint32_t)cur & 0xffff)) & 0xffff;
    }
    return t;
}
// one simulation tick of an entity's turn: returns the new current angle
inline int stepAngle(int cur, int heading, float speed) {
    int target = (heading << 14) & 0xffff; int step = (int)(speed * 32768.0f / 12.0f);
    if (diffAngle(cur, target) < 0x7f01) return (int)adjustAngle(cur, target, step);
    return (cur + step) & 0xffff;                                                             // about-face: keep turning the same way
}
} // namespace ccr
