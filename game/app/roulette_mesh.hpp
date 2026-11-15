#pragma once

#include "roulette_pose.hpp"
#include <array>
#include <cstdint>

struct RouletteVertex {
    float nx, ny, nz;
    float x, y, z;
    float u, v;
};

struct RouletteMesh {
    std::array<RouletteVertex, 18> vertices;
    std::array<uint16_t, 48> indices;
};

// HD 1.0 Render::createRouletteModel (0x1b420). Each end uses nine
// vertices so the two sides of the texture seam have distinct coordinates.
inline RouletteMesh makeRouletteMesh(float u0, float v0, float u1, float v1) {
    RouletteMesh mesh{};
    constexpr float eighthTurn = 0x1.921fb6p-1f;
    const float dv = (v1 - v0) * 0.125f;
    float angle = 0.0f;
    float v = v0;
    for (int column = 0; column < 8; ++column) {
        const float y = std::cos(angle), z = std::sin(angle);
        const float length = std::sqrt(y * y + z * z);
        mesh.vertices[column] = {0.0f, y / length, z / length, -2.0f, y, z, u0, v};
        mesh.vertices[column + 9] = {0.0f, y / length, z / length, 2.0f, y, z, u1, v};
        const auto i = static_cast<uint16_t>(column);
        const auto j = static_cast<uint16_t>(column + 9);
        const std::array<uint16_t, 6> side = {
            i, j, static_cast<uint16_t>(j + 1),
            i, static_cast<uint16_t>(j + 1), static_cast<uint16_t>(i + 1)};
        std::copy(side.begin(), side.end(), mesh.indices.begin() + column * side.size());
        angle += eighthTurn;
        v += dv;
    }
    mesh.vertices[8] = mesh.vertices[0];
    mesh.vertices[17] = mesh.vertices[9];
    mesh.vertices[8].v = mesh.vertices[17].v = v1;
    return mesh;
}

struct RouletteScreenVertex {
    float x, y, inverseDepth;
};

// HD 1.0 DrawRoulette uses the portrait GL viewport rotated 270 degrees.
// The 0.1 model-view scale cancels when calculating the screen coordinates.
// Retain reciprocal eye-space depth for perspective-correct texture sampling.
inline RouletteScreenVertex projectRouletteVertex(const RouletteVertex& vertex,
                                                   const RoulettePose& pose) {
    constexpr float cameraCos = 0.39273399114608765f;
    constexpr float cameraSin = 0.9196521043777466f;
    constexpr float frustumRight = 0.1636245846748352f;
    constexpr float frustumTop = 0.21816611289978027f;
    constexpr float radians = 0.017453292519943295f;
    const float angle = (pose.degrees + 135.0f) * radians;
    const float c = std::cos(angle), s = std::sin(angle);
    const float scale = pose.scale * 5.0f;
    const float x = vertex.x * scale + (pose.x + 65.0f) - 1080.0f - 512.0f;
    const float y = (vertex.y * c - vertex.z * s) * scale + pose.y - 476.0f - 950.0f;
    const float z = (vertex.y * s + vertex.z * c) * scale - 56.0f + 480.0f;
    const float depth = cameraCos * z - cameraSin * y;
    return {
        512.0f + 256.0f * (1024.0f + x) / (frustumTop * depth),
        384.0f + 192.0f * (cameraCos * y + cameraSin * z) / (frustumRight * depth),
        10.0f / depth
    };
}
