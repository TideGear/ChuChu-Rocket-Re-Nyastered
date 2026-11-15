#pragma once

#include "roulette_mesh.hpp"
#include <SDL.h>
#include <cstdio>
#include <memory>
#include <string>
#include <vector>

class RouletteDraw {
    int width_ = 0, height_ = 0;
    RouletteMesh mesh_{};
    std::vector<Uint8> art_, pixels_;
    bool tried_ = false;
    std::unique_ptr<SDL_Texture, decltype(&SDL_DestroyTexture)> overlay_{nullptr, SDL_DestroyTexture};

    bool load(const std::string& base) {
        using File = std::unique_ptr<FILE, decltype(&fclose)>;
        File texture(fopen((base + ".tex.bin").c_str(), "rb"), fclose);
        File frames(fopen((base + ".frames.bin").c_str(), "rb"), fclose);
        uint32_t size[2], frameCount;
        int16_t frame[10];
        if (!texture || !frames || fread(size, sizeof(*size), 2, texture.get()) != 2 ||
            size[0] == 0 || size[0] > 4096 || size[1] == 0 || size[1] > 4096 ||
            fread(&frameCount, sizeof(frameCount), 1, frames.get()) != 1 || !frameCount ||
            fseek(frames.get(), 4 * sizeof(float), SEEK_CUR) != 0 ||
            fread(frame, sizeof(*frame), 10, frames.get()) != 10) return false;
        width_ = static_cast<int>(size[0]);
        height_ = static_cast<int>(size[1]);
        if (frame[6] < 0 || frame[7] > width_ || frame[7] - frame[6] <= 2 ||
            frame[8] < 0 || frame[9] > height_ || frame[9] - frame[8] <= 2) return false;
        art_.resize(width_ * height_ * 4);
        if (fread(art_.data(), 1, art_.size(), texture.get()) != art_.size()) {
            art_.clear();
            return false;
        }
        // SetTextureAnchor insets the frame by one texel in the 1024-square atlas.
        // With the inset, every sample lies within the extracted tile, regardless of its atlas position.
        mesh_ = makeRouletteMesh((frame[6] + 1) / 1024.0f, (frame[8] + 1) / 1024.0f,
                                 (frame[7] - 1) / 1024.0f, (frame[9] - 1) / 1024.0f);
        return true;
    }

    static float edge(const RouletteScreenVertex& a, const RouletteScreenVertex& b, float x, float y) {
        return (b.x - a.x) * (y - a.y) - (b.y - a.y) * (x - a.x);
    }

    static bool inside(float e, const RouletteScreenVertex& a, const RouletteScreenVertex& b) {
        return e > 0 || (e == 0 && (a.y > b.y || (a.y == b.y && a.x < b.x)));
    }

    void sample(float u, float v, float light, Uint8* out) const {
        const float x = u * 1024.0f - 0.5f, y = v * 1024.0f - 0.5f;
        const int ix = static_cast<int>(std::floor(x)), iy = static_cast<int>(std::floor(y));
        const float fx = x - ix, fy = y - iy;
        const Uint8* a = &art_[4 * (iy * width_ + ix)];
        const Uint8* b = a + 4;
        const Uint8* c = a + 4 * width_;
        const Uint8* d = c + 4;
        for (int k = 0; k < 4; ++k) {
            const float top = a[k] + (b[k] - a[k]) * fx;
            const float bottom = c[k] + (d[k] - c[k]) * fx;
            out[k] = static_cast<Uint8>(std::lround((top + (bottom - top) * fy) * (k == 3 ? 1.0f : light)));
        }
    }

public:
    void reset() { overlay_.reset(); }

    void draw(SDL_Renderer* renderer, const std::string& base, const RoulettePose& pose, int width, int height) {
        if (!tried_) { tried_ = true; load(base); }
        if (art_.empty()) return;
        if (!overlay_) {
            overlay_.reset(SDL_CreateTexture(renderer, SDL_PIXELFORMAT_RGBA32, SDL_TEXTUREACCESS_STREAMING,
                                              width, height));
            if (!overlay_) return;
            SDL_SetTextureBlendMode(overlay_.get(), SDL_BLENDMODE_BLEND);
        }

        std::array<RouletteScreenVertex, 18> projected;
        std::array<float, 18> lights;
        const float angle = (pose.degrees + 135.0f) * 0.017453292519943295f;
        const float c = std::cos(angle), s = std::sin(angle);
        const float normalScale = 2.0f / pose.scale;
        const float lightLength = std::hypot(23.5f, 25.5f);
        float left = static_cast<float>(width), top = static_cast<float>(height), right = 0, bottom = 0;
        for (size_t i = 0; i < mesh_.vertices.size(); ++i) {
            const auto& vertex = mesh_.vertices[i];
            const auto p = projected[i] = projectRouletteVertex(vertex, pose);
            left = std::min(left, p.x); right = std::max(right, p.x);
            top = std::min(top, p.y); bottom = std::max(bottom, p.y);
            const float ny = vertex.ny * c - vertex.nz * s;
            const float nz = vertex.ny * s + vertex.nz * c;
            const float incidence = (23.5f * ny - 25.5f * nz) * normalScale / lightLength;
            // GLES default material and global ambient with the recorded LIGHT0 diffuse.
            lights[i] = std::min(1.0f, 0.04f + 25.6f * std::max(0.0f, incidence));
        }
        const int x0 = std::max(0, static_cast<int>(std::floor(left)));
        const int y0 = std::max(0, static_cast<int>(std::floor(top)));
        const int x1 = std::min(width, static_cast<int>(std::ceil(right)));
        const int y1 = std::min(height, static_cast<int>(std::ceil(bottom)));
        if (x0 >= x1 || y0 >= y1) return;
        const SDL_Rect bounds{x0, y0, x1 - x0, y1 - y0};
        pixels_.assign(bounds.w * bounds.h * 4, 0);

        for (size_t i = 0; i < mesh_.indices.size(); i += 3) {
            const auto ia = mesh_.indices[i], ib = mesh_.indices[i + 1], ic = mesh_.indices[i + 2];
            const auto& a = projected[ia];
            const auto& b = projected[ib];
            const auto& p = projected[ic];
            const float area = edge(a, b, p.x, p.y);
            // Swapping portrait GL axes reverses winding. Front faces are culled.
            if (area <= 0) continue;
            const int minX = std::max(x0, static_cast<int>(std::floor(std::min({a.x, b.x, p.x}))));
            const int maxX = std::min(x1, static_cast<int>(std::ceil(std::max({a.x, b.x, p.x}))));
            const int minY = std::max(y0, static_cast<int>(std::floor(std::min({a.y, b.y, p.y}))));
            const int maxY = std::min(y1, static_cast<int>(std::ceil(std::max({a.y, b.y, p.y}))));
            for (int y = minY; y < maxY; ++y) {
                for (int x = minX; x < maxX; ++x) {
                    const float ea = edge(b, p, x + 0.5f, y + 0.5f);
                    const float eb = edge(p, a, x + 0.5f, y + 0.5f);
                    const float ec = edge(a, b, x + 0.5f, y + 0.5f);
                    if (!inside(ea, b, p) || !inside(eb, p, a) || !inside(ec, a, b)) continue;
                    const float wa = ea * a.inverseDepth, wb = eb * b.inverseDepth, wc = ec * p.inverseDepth;
                    const float w = wa + wb + wc;
                    const auto& va = mesh_.vertices[ia];
                    const auto& vb = mesh_.vertices[ib];
                    const auto& vc = mesh_.vertices[ic];
                    sample((wa * va.u + wb * vb.u + wc * vc.u) / w,
                           (wa * va.v + wb * vb.v + wc * vc.v) / w,
                           (wa * lights[ia] + wb * lights[ib] + wc * lights[ic]) / w,
                           &pixels_[4 * ((y - y0) * bounds.w + x - x0)]);
                }
            }
        }
        if (SDL_UpdateTexture(overlay_.get(), &bounds, pixels_.data(), bounds.w * 4) == 0)
            SDL_RenderCopy(renderer, overlay_.get(), &bounds, &bounds);
    }
};
