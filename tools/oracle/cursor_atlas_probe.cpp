// Hidden accelerated SDL check: an atlas frame must render like its original
// separate texture throughout the original 16-tick cursor pulse.
#define SDL_MAIN_HANDLED
#include <SDL.h>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <vector>

struct Sheet { SDL_Texture* texture; SDL_Rect frame; };
Sheet load(SDL_Renderer* renderer, const char* base) {
    char path[1024]; snprintf(path, sizeof path, "%s.tex.bin", base);
    FILE* file = fopen(path, "rb"); if (!file) return {};
    unsigned size[2]; fread(size, 4, 2, file);
    std::vector<unsigned char> pixels(size[0] * size[1] * 4);
    fread(pixels.data(), 1, pixels.size(), file); fclose(file);
    SDL_Texture* texture = SDL_CreateTexture(renderer, SDL_PIXELFORMAT_ABGR8888, SDL_TEXTUREACCESS_STATIC, size[0], size[1]);
    SDL_UpdateTexture(texture, nullptr, pixels.data(), size[0] * 4);
    SDL_SetTextureBlendMode(texture, SDL_BLENDMODE_BLEND);
    SDL_SetTextureScaleMode(texture, SDL_ScaleModeLinear);
    snprintf(path, sizeof path, "%s.frames.bin", base); file = fopen(path, "rb");
    unsigned count; float uv[9]; fread(&count, 4, 1, file); fread(uv, 4, 9, file); fclose(file);
    return {texture, {(int)std::lround(uv[0] * size[0]), (int)std::lround(uv[1] * size[1]),
                      (int)std::lround((uv[2] - uv[0]) * size[0]), (int)std::lround((uv[3] - uv[1]) * size[1])}};
}
int main(int argc, char** argv) {
    if (argc != 4 && argc != 5) return 2; SDL_SetMainReady();
    if (SDL_Init(SDL_INIT_VIDEO)) return 2;
    SDL_Window* window = SDL_CreateWindow("Cursor atlas probe", 0, 0, 640, 480, SDL_WINDOW_HIDDEN);
    SDL_Renderer* renderer = SDL_CreateRenderer(window, -1, SDL_RENDERER_ACCELERATED);
    if (!renderer) { printf("accelerated renderer unavailable: %s\n", SDL_GetError()); return 2; }
    SDL_RendererInfo info{}; SDL_GetRendererInfo(renderer, &info); printf("renderer %s\n", info.name);
    Sheet sheets[] = {load(renderer, argv[1]), load(renderer, argv[2]), load(renderer, argv[3])};
    for (const auto& sheet : sheets) if (!sheet.texture) return 2;
    std::vector<unsigned> image[3]; for (auto& pixels : image) pixels.resize(640 * 480);
    unsigned total[2]{}, residue[2]{};
    for (int phase = 0; phase < 16; ++phase) {
        const float size = (457.67653f / 12) * (1 + 0.1f * std::sin(phase * 6.283185307f / 16));
        SDL_FRect dst{380, 190, size, size};
        for (int i = 0; i < 3; ++i) {
            SDL_SetRenderDrawColor(renderer, 203, 177, 117, 255); SDL_RenderClear(renderer);
            SDL_RenderCopyF(renderer, sheets[i].texture, &sheets[i].frame, &dst);
            SDL_RenderReadPixels(renderer, nullptr, SDL_PIXELFORMAT_ABGR8888, image[i].data(), 640 * 4);
            if (argc == 5 && phase == 1) {
                char path[1024]; snprintf(path, sizeof path, "%s-%d.bmp", argv[4], i);
                SDL_Surface* surface = SDL_CreateRGBSurfaceWithFormatFrom(image[i].data(), 640, 480, 32, 640 * 4, SDL_PIXELFORMAT_ABGR8888);
                SDL_SaveBMP(surface, path); SDL_FreeSurface(surface);
            }
        }
        unsigned bad[2]{}, large[2]{}, maximum[2]{};
        for (int i = 0; i < 2; ++i) for (size_t p = 0; p < image[i].size(); ++p) {
            unsigned error = 0;
            for (int c = 0; c < 3; ++c) {
                const int a = (image[i][p] >> (8 * c)) & 255, b = (image[2][p] >> (8 * c)) & 255;
                error = std::max(error, (unsigned)std::abs(a - b));
            }
            bad[i] += error != 0; large[i] += error > 1; maximum[i] = std::max(maximum[i], error);
        }
        total[0] += bad[0]; total[1] += bad[1];
        residue[0] += large[0]; residue[1] += large[1];
        printf("phase %d: old %u/max%u padded %u/max%u; >1-level pixels %u/%u\n", phase, bad[0], maximum[0], bad[1], maximum[1], large[0], large[1]);
    }
    for (auto& sheet : sheets) SDL_DestroyTexture(sheet.texture);
    SDL_DestroyRenderer(renderer); SDL_DestroyWindow(window); SDL_Quit();
    printf("totals old %u padded %u\n", total[0], total[1]);
    return total[1] ? 1 : 0;
}
