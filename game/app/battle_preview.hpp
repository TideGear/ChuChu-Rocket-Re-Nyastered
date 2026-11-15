#pragma once

#include "../core/sim.hpp"

#include <algorithm>
#include <array>
#include <filesystem>
#include <fstream>
#include <vector>

class BattlePreviewAtlas {
    struct Frame { int x, y, w, h; };
    static constexpr int atlasWidth = 594, atlasHeight = 282;
    std::array<Frame, 35> frames_{};
    std::vector<uint16_t> pixels_;

    static int u16(const uint8_t* bytes) { return bytes[0] | (bytes[1] << 8); }

    static uint16_t blend(uint16_t src, uint16_t dst) {
        int alpha = src & 15;
        if (alpha == 0) return dst;
        unsigned result = 15;
        for (int shift : {4, 8, 12}) {
            int channel = (((src >> shift) & 15) * (alpha + 1) +
                           ((dst >> shift) & 15) * (15 - alpha)) >> 4;
            result |= static_cast<unsigned>(channel) << shift;
        }
        return static_cast<uint16_t>(result);
    }

public:
    static constexpr int width = 832, height = 640;

    // HD 1.0 iPad resources 0x11e and 0x11f in the locally extracted ccrpad pack.
    bool load(const std::filesystem::path& pack) {
        std::ifstream metadata(pack / "0873.bin", std::ios::binary);
        std::array<uint8_t, 4 + 36 * 35> records{};
        if (!metadata.read(reinterpret_cast<char*>(records.data()), records.size()) ||
            u16(records.data()) != frames_.size()) return false;
        std::array<Frame, 35> frames{};
        for (size_t i = 0; i < frames.size(); ++i) {
            const auto* record = records.data() + 4 + i * 36;
            Frame frame{u16(record + 28), u16(record + 32), u16(record + 20), u16(record + 22)};
            if (frame.w < 2 || frame.h < 3 || frame.x + frame.w > atlasWidth ||
                frame.y + frame.h > atlasHeight || frame.w > 84 || frame.h > 84) return false;
            frames[i] = frame;
        }

        std::ifstream texture(pack / "0872.bin", std::ios::binary);
        std::vector<uint8_t> rgba(8 + atlasWidth * atlasHeight * 4);
        if (!texture.read(reinterpret_cast<char*>(rgba.data()), rgba.size()) ||
            u16(rgba.data()) != atlasWidth || u16(rgba.data() + 4) != atlasHeight) return false;
        std::vector<uint16_t> pixels(atlasWidth * atlasHeight);
        for (size_t i = 0; i < pixels.size(); ++i) {
            const auto* src = rgba.data() + 8 + 4 * i;
            pixels[i] = static_cast<uint16_t>(((src[0] & 0xf0) << 8) | ((src[1] & 0xf0) << 4) |
                                              (src[2] & 0xf0) | (src[3] >> 4));
        }
        frames_ = frames;
        pixels_ = std::move(pixels);
        return true;
    }

    // Render::createPlayfield uses an RGBA4444 buffer. Floors copy the
    // inner rows directly. Objects and walls blend after the checkerboard.
    std::vector<uint16_t> compose(const ccr::Stage& board, int stage, bool team) const {
        if (pixels_.empty() || stage < 0 || stage >= 25) return {};
        std::vector<uint16_t> result(width * height, 0x8080);
        auto draw = [&](int id, int x, int y, bool floor = false) {
            const Frame& f = frames_[id];
            const int firstRow = floor ? 1 : 0;
            const int lastRow = f.h - (floor ? 1 : 0);
            for (int row = firstRow; row < lastRow; ++row) {
                const auto* src = pixels_.data() + (f.y + row) * atlasWidth + f.x + 1;
                auto* dst = result.data() + (y + row) * width + x + 1;
                if (floor) std::copy_n(src, f.w - 1, dst);
                else for (int col = 0; col < f.w - 1; ++col) dst[col] = blend(src[col], dst[col]);
            }
        };

        constexpr int pitch = 64, origin = 32;
        constexpr int floorColors[] = {1, 3, 4, 5};
        constexpr int rocketFrames[2][4] = {{20, 23, 22, 21}, {24, 25, 24, 25}};
        constexpr int generators[] = {27, 28, 29, 34, 26, 30, 33, 32, 31};
        for (int y = 0; y < ccr::kRows; ++y)
            for (int x = 0; x < ccr::kCols; ++x)
                draw(8 + 2 * floorColors[stage & 3] + ((x ^ y) & 1), origin + x * pitch, origin + y * pitch, true);

        for (int y = 0; y < ccr::kRows; ++y) {
            for (int x = 0; x < ccr::kCols; ++x) {
                int tile = board.tiles[y * ccr::kCols + x];
                int left = origin + x * pitch, top = origin + y * pitch;
                if (tile >= 1 && tile <= 4) {
                    draw(6, left, top);
                    draw(rocketFrames[team][tile - 1], left, top);
                } else if (tile >= 5 && tile <= 8) draw(generators[(y / 3) * 3 + x / 4], left, top);
                else if (tile == ccr::T_Hole) draw(7, left, top);
            }
        }

        for (int y = 0; y <= ccr::kRows; ++y) {
            for (int x = 0; x < ccr::kCols; ++x)
                if (board.hw[y * ccr::kCols + x]) draw(0, origin + x * pitch - 9, origin + y * pitch - 11);
            if (y == ccr::kRows) break;
            for (int x = 0; x <= ccr::kCols; ++x)
                if (board.vw[y * (ccr::kCols + 1) + x]) draw(3, origin + x * pitch - 10, origin + y * pitch - 10);
        }
        return result;
    }
};
