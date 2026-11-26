// Dreamcast 3D character models (assets/dreamcast/models.bin from tools/export_dc_models.py), drawn with SDL_RenderGeometry: the triangles are transformed
// on the CPU (yaw, pitch, uniform scale, perspective), sorted back to front (the Dreamcast draws chunk models without a depth buffer in the same way) and
// submitted in runs of one texture. Works with the software and the accelerated renderer.
#pragma once
#include <SDL.h>
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <array>
#include <string>
#include <vector>
struct Model3D {
    struct V { float x, y, z, u, v, nx, ny, nz; };
    struct Tri { uint8_t mat; V v[3]; bool alphaStrip = false; bool envMap = false; bool untextured = false; };   // alphaStrip: the Ninja strip chunk's use-alpha flag (0x08), exported in the material byte's top bit
    std::string name; std::vector<Tri> tris; std::vector<uint32_t> matTex; std::vector<std::vector<float>> frames; bool hasStripAlpha = false; std::vector<std::array<uint8_t, 8>> colours;   /* CCM4: per triangle material diffuse then ambient (B, G, R, A) */   // animation poses: 18 floats per triangle (3 x position xyz + normal xyz)
};
// Lighting: the Dreamcast chunk models carry vertex normals (chunk type 41) and a material with diffuse 0xffffffff and ambient 0x7f7f7fff; the colour of a vertex is
// ambient + diffuse * max(0, N.L) with N turned to view space. L, ambient and diffuse are set from the fit against the mobile art (docs/dreamcast_models.md) or CCR_LIGHT=lx,ly,lz,amb,diff.
struct ModelLight { float lx = 0.0f, ly = 0.25f, lz = 0.5f, amb = 0.3f, diff = 0.559f; };   // the game's own Battle light read from the rocket lids (0.3 + max(0, 0.5 up + 0.25 screen-up)); the earlier fit to the mobile turntable was 0.6, 0.1, 0.5, 0.75, 0.8   // fitted to the mobile turntable (tools/fit_light.py, fine pass): mean luminance error 0.080 (first guess 0.148)
inline ModelLight& modelLight() {
    static ModelLight l; static bool init = false;
    if (!init) { init = true; if (const char* e = getenv("CCR_LIGHT")) sscanf(e, "%f,%f,%f,%f,%f", &l.lx, &l.ly, &l.lz, &l.amb, &l.diff); float n = sqrtf(l.lx * l.lx + l.ly * l.ly + l.lz * l.lz); if (n > 0) { l.lx /= n; l.ly /= n; l.lz /= n; } }
    return l;
}
struct ModelPack {
    std::vector<SDL_Texture*> textures; std::vector<Model3D> models;
    std::vector<std::vector<uint8_t>> cpuPixels; std::vector<SDL_Point> cpuSize;   // RGBA bytes of every texture, for the software rasteriser (softRender)
    mutable std::vector<float> sceneDepth;
    mutable int sceneWidth = 0, sceneHeight = 0;
    void beginDepthScene(SDL_Renderer* ren) const {
        SDL_GetRendererOutputSize(ren, &sceneWidth, &sceneHeight);
        sceneDepth.assign((size_t)sceneWidth * sceneHeight, -1.0f);
    }
    void endDepthScene() const { sceneWidth = sceneHeight = 0; }
    ModelPack() = default;
    ModelPack(const ModelPack&) = delete;
    ModelPack& operator=(const ModelPack&) = delete;
    ~ModelPack() { clear(); }
    void clear() {
        for (auto* texture : textures) SDL_DestroyTexture(texture);
        textures.clear();
        models.clear(); cpuPixels.clear(); cpuSize.clear();
    }
    const Model3D* find(const std::string& n) const { for (const auto& m : models) if (m.name == n) return &m; return nullptr; }
    bool load(SDL_Renderer* ren, const std::string& path) {
        ModelPack loaded;
        if (!loaded.read(ren, path)) return false;
        textures.swap(loaded.textures);
        models.swap(loaded.models); cpuPixels.swap(loaded.cpuPixels); cpuSize.swap(loaded.cpuSize);
        return true;
    }
private:
    bool read(SDL_Renderer* ren, const std::string& path) {
        FILE* f = fopen(path.c_str(), "rb"); if (!f) return false;
        std::vector<uint8_t> d; uint8_t buf[65536]; size_t n; while ((n = fread(buf, 1, sizeof buf, f)) > 0) d.insert(d.end(), buf, buf + n); fclose(f);
        size_t p = 0;
        auto remaining = [&] { return d.size() - p; };
        auto rd = [&](void* o, size_t k) { if (k > remaining()) return false; memcpy(o, d.data() + p, k); p += k; return true; };
        char magic[4]; uint32_t nt; if (!rd(magic, 4) || (memcmp(magic, "CCM3", 4) && memcmp(magic, "CCM4", 4)) || !rd(&nt, 4)) return false; const bool ccm4 = !memcmp(magic, "CCM4", 4);
        for (uint32_t i = 0; i < nt; i++) {
            uint16_t w, h;
            if (!rd(&w, 2) || !rd(&h, 2) || !w || !h || h > remaining() / (size_t(w) * 4)) return false;
            SDL_Texture* t = SDL_CreateTexture(ren, SDL_PIXELFORMAT_ABGR8888, SDL_TEXTUREACCESS_STATIC, w, h);
            if (!t) return false;
            textures.push_back(t); cpuPixels.emplace_back(d.data() + p, d.data() + p + (size_t)w * h * 4); cpuSize.push_back({w, h});
            if (SDL_UpdateTexture(t, nullptr, d.data() + p, w * 4) != 0 ||
                SDL_SetTextureBlendMode(t, SDL_BLENDMODE_BLEND) != 0) return false;
            p += (size_t)w * h * 4;
        }
        uint32_t nm; if (!rd(&nm, 4)) return false;
        for (uint32_t i = 0; i < nm; i++) {
            Model3D m; char nm24[25] = {}; uint32_t ntri, nmat; if (!rd(nm24, 24) || !rd(&ntri, 4) || !rd(&nmat, 4)) return false; m.name = nm24;
            if (nmat > remaining() / 4) return false;
            m.matTex.resize(nmat); if (nmat && !rd(m.matTex.data(), size_t(nmat) * 4)) return false;
            constexpr size_t triangleBytes = 1 + 3 * 32;
            if (ntri > remaining() / triangleBytes) return false;
            m.tris.resize(ntri);
            for (auto& t : m.tris) { if (!rd(&t.mat, 1)) return false; t.untextured = (t.mat & 0xc0) == 0xc0; t.alphaStrip = !t.untextured && (t.mat & 0x80) != 0; t.envMap = !t.untextured && (t.mat & 0x40) != 0; t.mat &= 0x3f;   /* 0xc0: a strip without UVs and without environment mapping, drawn untextured (white x light: the Pian's white piece) */ if (t.alphaStrip) m.hasStripAlpha = true; for (auto& v : t.v) if (!rd(&v, 32)) return false; }
            const size_t frameBytes = size_t(ntri) * 18 * 4;
            uint32_t nf;
            if (!rd(&nf, 4) || (nf && (!frameBytes || nf > remaining() / frameBytes))) return false;
            m.frames.resize(nf);
            for (auto& fr : m.frames) { fr.resize((size_t)ntri * 18); if (!rd(fr.data(), fr.size() * 4)) return false; }
            if (ccm4) { uint32_t nc; if (!rd(&nc, 4) || (nc && (nc != ntri || nc > remaining() / 8))) return false; m.colours.resize(nc); for (auto& c : m.colours) if (!rd(c.data(), 8)) return false; }
            models.push_back(std::move(m));
        }
        return true;
    }
public:
    struct SoftTri { SDL_FPoint p[3]; float iw[3], u[3], v[3], light[3]; int tex; bool translucent; bool wrap = false; bool additive = false; bool rgb = false; float lightRGB[3][3] = {}; };   // rgb: per-channel vertex light (material colours)   // wrap: repeat the texture (the floor quad's UVs run past 1)

    // The Battle draw task builds a dome from two copies of the lid,
    // at yaw 90 and 270 degrees (0x8c01b4e0, Flycast frame 3100).
    void drawDcRocketDome(SDL_Renderer* ren, const Model3D& lid, SDL_FPoint floorPosition,
                          SDL_FPoint cameraCenter, float pixelsPerUnit, float pulse,
                          float cameraDistance = 218.0f, const Model3D* oppositeLid = nullptr,
                          float opening = 0.0f, const Model3D* launchedBody = nullptr, int launchAge = -1,
                          const Model3D* launchBase = nullptr, const Model3D* flame = nullptr,
                          const std::vector<int>* smokeBirths = nullptr, float launchScale = 1.0f) const {
        const float scale = pixelsPerUnit * pulse * launchScale;
        // Original 0x8c01b628: TranslateZ(+/-opening), RotateY(+/-90),
        // RotateZ(-int(opening * 12743.111328125)). Keep one shared depth
        // buffer for both lid halves and the body as in the original scene.
        const float angle = -(int)(opening * 12743.111328125f) * (6.283185307f / 65536.0f);
        const float ca = std::cos(angle), sa = std::sin(angle);
        std::vector<SoftTri> projected;
        projected.reserve(2 * lid.tris.size());
        for (float side : {1.0f, -1.0f}) {
            const Model3D& half = side < 0.0f && oppositeLid ? *oppositeLid : lid;
            for (const auto& tri : half.tris) {
                if (tri.mat >= half.matTex.size() || half.matTex[tri.mat] >= cpuPixels.size()) continue;
                SoftTri out{};
                out.tex = half.matTex[tri.mat];
                for (int i = 0; i < 3; ++i) {
                    const auto& v = tri.v[i];
                    const float vx = v.x * ca - v.y * sa, vy = v.x * sa + v.y * ca;
                    const float nx = v.nx * ca - v.ny * sa, ny = v.nx * sa + v.ny * ca;
                    const float depth = cameraDistance - vy * pulse * launchScale;
                    const float perspective = cameraDistance / depth;
                    const float dx = floorPosition.x - cameraCenter.x + side * v.z * scale;
                    const float dy = floorPosition.y - cameraCenter.y - side * vx * scale + side * opening * pixelsPerUnit;
                    // The live age -1 TA vertices confirm that the Dreamcast's uniform rocket scale also scales its diffuse normal term.
                    const float intensity = std::clamp(0.3f + std::max(0.0f, (0.5f * ny + 0.25f * side * nx) * launchScale), 0.0f, 1.0f);
                    const auto intensityByte = (unsigned)(intensity * 255.0f);
                    const float light = (float)(255u * intensityByte / 256u) / 255.0f;
                    out.p[i] = {cameraCenter.x + dx * perspective, cameraCenter.y + dy * perspective};
                    out.iw[i] = 1.0f / depth;
                    out.light[i] = light;
                    // The decoded PVR's axes are transposed relative to the Ninja UVs.
                    out.u[i] = 1.0f - v.v;
                    out.v[i] = v.u;
                }
                projected.push_back(out);
            }
        }
        auto emit = [&](const Model3D* model, float height, int yawUnits, float diffuse, bool shadow, bool additive, int frame, bool translucent = false, bool unlit = false) {
            if (!model) return;
            const float yaw = yawUnits * (6.283185307f / 65536.0f), cy = std::cos(yaw), sy = std::sin(yaw);
            const std::vector<float>* pose = frame >= 0 && !model->frames.empty() ? &model->frames[frame % model->frames.size()] : nullptr;
            for (size_t ti = 0; ti < model->tris.size(); ++ti) {
                const auto& tri = model->tris[ti];
                if (tri.mat >= model->matTex.size()) continue;
                SoftTri out{}; out.tex = model->matTex[tri.mat]; out.translucent = additive || translucent; out.additive = additive; bool clipped = false;
                for (int i = 0; i < 3; ++i) {
                    auto v = tri.v[i];
                    if (pose) { const float* p = &(*pose)[ti * 18 + i * 6]; v.x = p[0]; v.y = p[1]; v.z = p[2]; v.nx = p[3]; v.ny = p[4]; v.nz = p[5]; }
                    const float x = v.x * cy + v.z * sy, z = -v.x * sy + v.z * cy;
                    const float nz = -v.nx * sy + v.nz * cy;
                    const float depth = cameraDistance - height - v.y;
                    if (depth <= 0) { clipped = true; break; }
                    const float perspective = cameraDistance / depth;
                    out.p[i] = {cameraCenter.x + (floorPosition.x - cameraCenter.x + x * pixelsPerUnit) * perspective,
                                cameraCenter.y + (floorPosition.y - cameraCenter.y + z * pixelsPerUnit) * perspective};
                    out.iw[i] = 1.0f / depth;
                    out.light[i] = shadow ? 0.0f : unlit ? 1.0f : diffuse * (0.3f + std::max(0.0f, 0.5f * v.ny - 0.25f * nz));
                    out.u[i] = 1.0f - v.v; out.v[i] = v.u;
                }
                if (!clipped) projected.push_back(out);
            }
        };
        // Base wrapper 0x8c0e9d44 disables directional lights; material ambient is zero.
        if (launchAge >= 0) emit(launchBase, 0, 0, 1, true, false, -1);
        if (launchAge >= 0 && launchAge <= 200) {
            emit(launchedBody, (float)launchAge, launchAge * 0x200, 178.0f / 255.0f, false, false, -1);
            // 0x8c01b7e4: TranslateY(-7), 16-frame vertex morph. Real
            // packet TSP 0x3891a4db uses ONE / DST_ALPHA (additive on the opaque scene).
            emit(flame, launchAge - 7.0f, launchAge * 0x200, 1.0f, false, true, launchAge & 15);
        }
        if (smokeBirths) for (int born : *smokeBirths)
            emit(find("smoke" + std::to_string(launchAge - born)), born - 11.0f, 0, 1, false, false, -1, true, true);
        // Flycast ta_util.cpp sortTriangles: translucent triangles sort by
        // their minimum reciprocal depth, far to near, retaining ties.
        std::stable_sort(projected.begin(), projected.end(), [](const SoftTri& a, const SoftTri& b) {
            if (a.translucent != b.translucent) return !a.translucent;
            return a.translucent && std::min({a.iw[0], a.iw[1], a.iw[2]}) < std::min({b.iw[0], b.iw[1], b.iw[2]});
        });
        softRender(ren, projected);
    }

    // Software rasteriser with the PowerVR's per-pixel behaviour (the SDL geometry renderer has no depth buffer, and a painter's order cannot reproduce the real overlaps, such as a wall's end
    // caps, or a mouse's foot meeting its body): depth test on the interpolated 1/w (greater is nearer, later wins ties), perspective-correct texture coordinates, bilinear filtering with
    // clamping (the real tsp words say bilinear and clamp), per-vertex intensity multiplied with the texture and saturated at 255 (intensities above 1.0 are real), and a second pass for the
    // translucent list (depth-tested against the opaque pixels, no depth write, source-alpha blend). Rendered at the output resolution into a small buffer covering the triangles.
    void softRender(SDL_Renderer* ren, const std::vector<SoftTri>& tris) const {
        if (tris.empty()) return;
        int ow = 0, oh = 0, lw = 0, lh = 0; SDL_GetRendererOutputSize(ren, &ow, &oh); SDL_RenderGetLogicalSize(ren, &lw, &lh);
        if (!lw || !lh) { lw = ow; lh = oh; }
        const float sc = std::max(0.25f, std::min(ow / (float)lw, oh / (float)lh));
        float minx = 1e9f, miny = 1e9f, maxx = -1e9f, maxy = -1e9f;
        for (const auto& t : tris) for (int k = 0; k < 3; ++k) { minx = std::min(minx, t.p[k].x); maxx = std::max(maxx, t.p[k].x); miny = std::min(miny, t.p[k].y); maxy = std::max(maxy, t.p[k].y); }
        minx = std::max(minx, 0.0f); miny = std::max(miny, 0.0f); maxx = std::min(maxx, (float)lw); maxy = std::min(maxy, (float)lh);   // only the screen is rendered: geometry that surrounds the eye (the sky sphere) projects far past it
        if (!(maxx > minx) || !(maxy > miny)) return;
        const int x0 = (int)std::floor(minx * sc) - 1, y0 = (int)std::floor(miny * sc) - 1, W = (int)std::ceil(maxx * sc) + 1 - x0, H = (int)std::ceil(maxy * sc) + 1 - y0;
        if (W <= 0 || H <= 0 || W > 4096 || H > 4096) return;
        static std::vector<uint32_t> color, added; static std::vector<float> depth;
        color.assign((size_t)W * H, 0u); added.assign((size_t)W * H, 0u); bool hasAdditive = false; depth.assign((size_t)W * H, -1.0f);
        auto sample = [&](int tex, float u, float v, bool wrap, float out[4]) {
            if (tex == -2) { out[0] = out[1] = out[2] = 255; out[3] = 255; return; }   // untextured strip: white, lit by the vertex intensity
            if (tex < 0 || tex >= (int)cpuPixels.size()) { out[0] = out[1] = out[2] = 0; out[3] = 255; return; }
            const int tw = cpuSize[tex].x, th = cpuSize[tex].y; const uint8_t* px = cpuPixels[tex].data();
            const float fx = u * tw - 0.5f, fy = v * th - 0.5f; const int ix = (int)std::floor(fx), iy = (int)std::floor(fy); const float ax = fx - ix, ay = fy - iy;
            for (int c = 0; c < 4; ++c) {
                auto at = [&](int x, int y) { if (wrap) { x = ((x % tw) + tw) % tw; y = ((y % th) + th) % th; } else { x = std::max(0, std::min(tw - 1, x)); y = std::max(0, std::min(th - 1, y)); } return (float)px[((size_t)y * tw + x) * 4 + c]; };
                out[c] = (at(ix, iy) * (1 - ax) + at(ix + 1, iy) * ax) * (1 - ay) + (at(ix, iy + 1) * (1 - ax) + at(ix + 1, iy + 1) * ax) * ay;
            }
        };
        for (int pass = 0; pass < 2; ++pass) {
            for (const auto& t : tris) {
                if (t.translucent != (pass == 1)) continue;
                float X[3], Y[3]; for (int k = 0; k < 3; ++k) { X[k] = t.p[k].x * sc - x0; Y[k] = t.p[k].y * sc - y0; }
                const float det = (X[1] - X[0]) * (Y[2] - Y[0]) - (X[2] - X[0]) * (Y[1] - Y[0]);
                if (std::fabs(det) < 1e-6f) continue;
                const int bx0 = std::max(0, (int)std::floor(std::min({X[0], X[1], X[2]}))), bx1 = std::min(W - 1, (int)std::ceil(std::max({X[0], X[1], X[2]})));
                const int by0 = std::max(0, (int)std::floor(std::min({Y[0], Y[1], Y[2]}))), by1 = std::min(H - 1, (int)std::ceil(std::max({Y[0], Y[1], Y[2]})));
                for (int y = by0; y <= by1; ++y) for (int x = bx0; x <= bx1; ++x) {
                    const float px = x + 0.5f, py = y + 0.5f;
                    const float b1 = ((px - X[0]) * (Y[2] - Y[0]) - (X[2] - X[0]) * (py - Y[0])) / det, b2 = ((X[1] - X[0]) * (py - Y[0]) - (px - X[0]) * (Y[1] - Y[0])) / det, b0 = 1.0f - b1 - b2;
                    if (b0 < -1e-4f || b1 < -1e-4f || b2 < -1e-4f) continue;
                    const float iw = b0 * t.iw[0] + b1 * t.iw[1] + b2 * t.iw[2]; if (iw <= 0) continue;
                    const int screenX = x + x0, screenY = y + y0;
                    float& zb = screenX >= 0 && screenX < sceneWidth && screenY >= 0 && screenY < sceneHeight
                        ? sceneDepth[(size_t)screenY * sceneWidth + screenX] : depth[(size_t)y * W + x];
                    if (iw < zb - 2e-7f) continue;                                   // nearer (greater 1/w) wins; equal depth (within float noise): the later polygon wins
                    const float w0 = b0 * t.iw[0], w1 = b1 * t.iw[1], w2 = b2 * t.iw[2], ws = w0 + w1 + w2;
                    const float u = (w0 * t.u[0] + w1 * t.u[1] + w2 * t.u[2]) / ws, v = (w0 * t.v[0] + w1 * t.v[1] + w2 * t.v[2]) / ws;
                    const float lum = b0 * t.light[0] + b1 * t.light[1] + b2 * t.light[2];
                    float c[4]; sample(t.tex, u, v, t.wrap, c);
                    uint32_t& dst = color[(size_t)y * W + x];
                    float lr = lum, lg = lum, lb = lum;
                    if (t.rgb) { lr = b0 * t.lightRGB[0][0] + b1 * t.lightRGB[1][0] + b2 * t.lightRGB[2][0]; lg = b0 * t.lightRGB[0][1] + b1 * t.lightRGB[1][1] + b2 * t.lightRGB[2][1]; lb = b0 * t.lightRGB[0][2] + b1 * t.lightRGB[1][2] + b2 * t.lightRGB[2][2]; }
                    const float r = std::min(255.0f, c[0] * lr), g = std::min(255.0f, c[1] * lg), bl = std::min(255.0f, c[2] * lb);
                    if (t.additive) {
                        uint32_t& d = added[(size_t)y * W + x];
                        const auto rr = (uint32_t)std::min(255.0f, (d & 255) + r + 0.5f);
                        const auto gg = (uint32_t)std::min(255.0f, (d >> 8 & 255) + g + 0.5f);
                        const auto bb = (uint32_t)std::min(255.0f, (d >> 16 & 255) + bl + 0.5f);
                        d = rr | gg << 8 | bb << 16 | 0xff000000u; hasAdditive = true;
                    }
                    else if (!t.translucent) { dst = (uint32_t)(r + 0.5f) | (uint32_t)(g + 0.5f) << 8 | (uint32_t)(bl + 0.5f) << 16 | 0xFF000000u; zb = iw; }
                    else {
                        const float a = c[3] / 255.0f; const float dr = (float)(dst & 255), dg = (float)(dst >> 8 & 255), db = (float)(dst >> 16 & 255), da = (float)(dst >> 24) / 255.0f;
                        const float oa = a + da * (1 - a); const float orr = oa > 0 ? (r * a + dr * da * (1 - a)) / oa : 0, og = oa > 0 ? (g * a + dg * da * (1 - a)) / oa : 0, ob = oa > 0 ? (bl * a + db * da * (1 - a)) / oa : 0;
                        // A later source-alpha sprite also covers previously
                        // accumulated additive light (flame before smoke).
                        uint32_t& ad = added[(size_t)y * W + x];
                        ad = (uint32_t)((ad & 255) * (1 - a) + 0.5f) |
                             (uint32_t)((ad >> 8 & 255) * (1 - a) + 0.5f) << 8 |
                             (uint32_t)((ad >> 16 & 255) * (1 - a) + 0.5f) << 16 | (ad & 0xff000000u);
                        dst = (uint32_t)(orr + 0.5f) | (uint32_t)(og + 0.5f) << 8 | (uint32_t)(ob + 0.5f) << 16 | (uint32_t)(oa * 255.0f + 0.5f) << 24;
                    }
                }
            }
        }
        static SDL_Texture* buffer = nullptr; static int bw = 0, bh = 0;
        if (!buffer || bw < W || bh < H) {
            if (buffer) SDL_DestroyTexture(buffer);
            bw = std::max(bw, std::max(W, 128)); bh = std::max(bh, std::max(H, 128));
            buffer = SDL_CreateTexture(ren, SDL_PIXELFORMAT_ABGR8888, SDL_TEXTUREACCESS_STREAMING, bw, bh);
            if (!buffer) { bw = bh = 0; return; }
            SDL_SetTextureBlendMode(buffer, SDL_BLENDMODE_BLEND);
        }
        SDL_SetTextureScaleMode(buffer, SDL_ScaleModeNearest);
        const SDL_Rect src{0, 0, W, H}; SDL_UpdateTexture(buffer, &src, color.data(), W * 4);
        const SDL_FRect dst{x0 / sc, y0 / sc, W / sc, H / sc}; SDL_RenderCopyF(ren, buffer, &src, &dst);
        if (hasAdditive) {
            SDL_UpdateTexture(buffer, &src, added.data(), W * 4); SDL_SetTextureBlendMode(buffer, SDL_BLENDMODE_ADD);
            SDL_RenderCopyF(ren, buffer, &src, &dst); SDL_SetTextureBlendMode(buffer, SDL_BLENDMODE_BLEND);
        }
    }

    // A board piece (wall bar, generator or hole pad) exactly as the Dreamcast board task submits it (Flycast Puzzle 01 stream, wall piece at state offset 0x253eb0; fitted with zero residual):
    // the piece origin sits on the floor grid (no separate wall plane), the mesh is turned about the vertical axis (0 for horizontal edges, -90 degrees for vertical ones) and every vertex is
    // projected with its own height, sx = camera.x + k * 218 * X / (218 - Y), so a wall's lower side face shows under the bar (the 218 / 215 "wall plane" is this perspective at height 3).
    // Lighting per vertex: 0.3 + max(0, 0.5 * ny - 0.25 * nz) of the turned normal (exact to four decimals on the real vertices), multiplied with the texture. `material` >= 0 forces one
    // material. The pack's textures are stored transposed, so the stream's (u, v) is sampled as (v, u).
    void appendDcPiece(const Model3D& piece, int material, SDL_FPoint planePos, SDL_FPoint camera,
                       float pixelsPerUnit, float yawDeg, std::vector<SoftTri>& out,
                       float cameraDistance) const {
        if (piece.tris.empty()) return;
        const float a = yawDeg * 0.017453292f, c = cosf(a), s = sinf(a);
        const float ox = (planePos.x - camera.x) / pixelsPerUnit, oz = (planePos.y - camera.y) / pixelsPerUnit;
        struct P { float x, y, z, u, v, light; };
        for (const auto& tri : piece.tris) {
            const int mi = material >= 0 ? material : tri.mat;
            const int tex = mi < (int)piece.matTex.size() ? (int)piece.matTex[mi] : -1;
            P poly[4]; int n = 0; P in[3];
            for (int i = 0; i < 3; ++i) {
                const auto& v = tri.v[i];
                const float nz = -v.nx * s + v.nz * c;
                in[i] = {v.x * c + v.z * s, v.y, -v.x * s + v.z * c, 1.0f - v.v, v.u, std::min(1.0f, 0.3f + std::max(0.0f, 0.5f * v.ny - 0.25f * nz))};
            }
            // Clip at the floor plane (height 0): the real floor is drawn first and hides what lies below it; the floor is not in this buffer.
            for (int i = 0; i < 3; ++i) {
                const P& a = in[i]; const P& b = in[(i + 1) % 3];
                const bool ain = a.y >= 0.0f, bin = b.y >= 0.0f;
                if (ain) poly[n++] = a;
                if (ain != bin) { const float t = a.y / (a.y - b.y); poly[n++] = {a.x + (b.x - a.x) * t, 0.0f, a.z + (b.z - a.z) * t, a.u + (b.u - a.u) * t, a.v + (b.v - a.v) * t, a.light + (b.light - a.light) * t}; }
            }
            for (int k = 1; k + 1 < n; ++k) {
                SoftTri o{}; o.tex = tex; o.translucent = false; const P* q[3] = {&poly[0], &poly[k], &poly[k + 1]};
                for (int i = 0; i < 3; ++i) {
                    const float depth = cameraDistance - q[i]->y, scale = pixelsPerUnit * cameraDistance / depth;
                    o.p[i] = {camera.x + (ox + q[i]->x) * scale, camera.y + (oz + q[i]->z) * scale}; o.iw[i] = 1.0f / depth; o.u[i] = q[i]->u; o.v[i] = q[i]->v; o.light[i] = q[i]->light;
                }
                out.push_back(o);
            }
        }
    }

    // A character (mouse or cat) exactly as the Dreamcast field callbacks draw it (0x8c0193e0 for mice, 0x8c011060 for cats; verified by fitting the real PowerVR vertices of 40 mice and
    // the cats in Flycast frames with zero residual, docs/dreamcast_models.md): matrix = position * translate(0, 0, translateZ) * RotateX(-45 degrees) * RotateY(yaw) * scale 1, in world
    // units (15 per cell; X right, Y up, Z down the screen) seen from 218 units above the floor with the screen centre at `camera`: sx = camera.x + k * 218 * X / (218 - Y), likewise
    // sy with Z. Lighting per vertex: 0.3 + max(0, light . R n). `blend` > 0 mixes pose frame `frame` with pose frame `frame + 1` (the cat's head morph and walk pose are interpolated by
    // the fractional part of its phase); basic mice and golden mice select their source-derived frame (the golden mouse's eight poses are sampled from its position/angle motion).
    void drawDcCharacter(SDL_Renderer* ren, const Model3D& m, SDL_FPoint planePos, SDL_FPoint camera, float pixelsPerUnit, float yawDeg, float translateZ,
                         const float (&light)[3], int frame, float blend, int uvMode, uint32_t translucentMaterials = 0, const int* texRemap = nullptr, float run10Diffuse = 1.0f, float height = 0.0f, float modelScale = 1.0f, const float* constRGB = nullptr, float tiltDeg = -45.0f) const {   // constRGB: a constant per-channel vertex colour (the focus ring: face (1, 0.3, 0.3) x intensity 0.8 in the stream)
        if (m.tris.empty()) return;
        const float ya = yawDeg * 0.017453292f, cy = cosf(ya), sy = sinf(ya);
        const float kTilt = tiltDeg * 0.017453292f; const float ct = cosf(kTilt), st = sinf(kTilt);   // characters stand at RotateX(-45); a model drawn flat on the board (the focus ring) passes 0
        const float ox = (planePos.x - camera.x) / pixelsPerUnit, oz = (planePos.y - camera.y) / pixelsPerUnit + translateZ;
        const std::vector<float>* a = (frame >= 0 && !m.frames.empty()) ? &m.frames[frame % (int)m.frames.size()] : nullptr;
        const std::vector<float>* b = (frame >= 0 && !m.frames.empty() && blend > 0.0f) ? &m.frames[(frame + 1) % (int)m.frames.size()] : nullptr;
        std::vector<SoftTri> out; out.reserve(m.tris.size());
        for (size_t ti = 0; ti < m.tris.size(); ++ti) {
            const auto& tri = m.tris[ti]; SoftTri o{}; const size_t mat = (texRemap && tri.mat < 10) ? (size_t)texRemap[tri.mat] : (size_t)tri.mat; o.tex = tri.untextured ? -2 : (mat < m.matTex.size()) ? (int)m.matTex[mat] : -1; o.translucent = (m.hasStripAlpha && (m.name.rfind("chao", 0) == 0 || m.name.rfind("pian", 0) == 0)) ? tri.alphaStrip : ((translucentMaterials >> (tri.mat & 31)) & 1u);   /* costumes: per strip (strips without use-alpha are opaque even on alpha textures: the Pian's white piece); the cat and mice keep their verified material masks (the cat's second-list blend is not the strip flag) */
            for (int k = 0; k < 3; ++k) {
                float vx = tri.v[k].x, vy = tri.v[k].y, vz = tri.v[k].z, nx = tri.v[k].nx, ny = tri.v[k].ny, nz = tri.v[k].nz;
                if (a) {
                    const float* pa = &(*a)[ti * 18 + k * 6];
                    vx = pa[0]; vy = pa[1]; vz = pa[2]; nx = pa[3]; ny = pa[4]; nz = pa[5];
                    if (b) { const float* pb = &(*b)[ti * 18 + k * 6]; const float f = blend; vx += (pb[0] - vx) * f; vy += (pb[1] - vy) * f; vz += (pb[2] - vz) * f; nx += (pb[3] - nx) * f; ny += (pb[4] - ny) * f; nz += (pb[5] - nz) * f; }
                }
                vx *= modelScale; vy *= modelScale; vz *= modelScale;                              // Scale (the ghost task shrinks its model at the end of its life)
                const float x1 = vx * cy + vz * sy, z1 = -vx * sy + vz * cy;                 // RotateY(yaw)
                const float y2 = vy * ct - z1 * st + height, z2 = vy * st + z1 * ct;         // RotateX(-45), then the task position's height

                const float n1x = nx * cy + nz * sy, n1z = -nx * sy + nz * cy;
                const float n2x = n1x, n2y = ny * ct - n1z * st, n2z = ny * st + n1z * ct;
                const float depth = 218.0f - y2, scale = pixelsPerUnit * 218.0f / depth;
                o.light[k] = std::min(1.0f, 0.3f + std::max(0.0f, (light[0] * n2x + light[1] * n2y + light[2] * n2z) * modelScale)) * (tri.mat == 10 ? run10Diffuse : 1.0f);   // a uniform njScale also scales the normals the Dreamcast lights with (as for the rocket dome)   // material slot 10 = the mouse's cream run with chunk diffuse b2b2b2 (0xb2 / 255)   // the stream's intensities reach 1.08 (mice), but the packed vertex intensity saturates at 1.0 before the texture multiply: unsaturated looked too white against the real frame
                if (ti < m.colours.size() && (m.name.rfind("chao", 0) == 0 || m.name.rfind("pian", 0) == 0)) {   // costume material colours: channel = min(1, 0.3 + diffuse term) * material diffuse (face colour)
                    const auto& mc = m.colours[ti]; const float dterm = std::max(0.0f, (light[0] * n2x + light[1] * n2y + light[2] * n2z) * modelScale);
                    for (int ch = 0; ch < 3; ++ch) { const int bi = 2 - ch; o.lightRGB[k][ch] = (mc[7] == 0 ? 0.912f : std::min(1.0f, 0.3f + dterm)) * mc[bi] / 255.0f; }   /* mc[7] == 0: the strip's ignore-light flag (0x01): a constant intensity, 0.912 on every vertex of that Pian strip in Flycast s202390.state (origin of the value not traced) */   // the material diffuse is the PowerVR face colour (Flycast s102390.state: header face (1, 0, 0.498, 1) for the Chao's ff7f00ff chunk) and multiplies the whole vertex intensity; the ambient chunks do not reach the hardware
                    o.rgb = true;
                }
                if (constRGB) { o.light[k] = 1.0f; for (int ch = 0; ch < 3; ++ch) o.lightRGB[k][ch] = constRGB[ch]; o.rgb = true; }
                o.p[k] = {camera.x + (ox + x1) * scale, camera.y + (oz + z2) * scale}; o.iw[k] = 1.0f / depth;
                float mu = tri.v[k].u, mv = tri.v[k].v;
                if (tri.envMap) {   // Ninja strip flag 0x40 (environment map, strips without UVs: the golden mouse's body): UV from the view-space normal
                    mu = 0.5f + 0.5f * n2x; mv = 0.5f - 0.5f * n2y;   // the usual Ninja mapping; the four sign variants all leave the body ~15% brighter than Flycast (open)
                }
                const SDL_FPoint uv = uvMode == 1 ? SDL_FPoint{1.0f - mv, mu} : SDL_FPoint{mu, mv};
                o.u[k] = uv.x; o.v[k] = uv.y;
            }
            out.push_back(o);
        }
        softRender(ren, out);
    }

    // Background sky (draw 0x8c01f2a0): njTranslate(centre), njRotateXYZ(ang) (X, then Y, then Z, the order measured for node angles in
    // tools/export_dc_models.py), njScale(scale), drawn with the character camera (RotateX(-45), eye 218 units out). The sphere surrounds the eye,
    // so triangles are clipped at the eye plane. Unlit: intensity 1. Not called yet: with this camera the streaks land in the wrong places (Puzzle 01 margins 0.72 -> 0.92), so the real Puzzle view matrix is needed first.
    void drawDcSky(SDL_Renderer* ren, const Model3D& m, SDL_FPoint planePos, SDL_FPoint camera, float pixelsPerUnit, const int ang[3], float scale) const {
        const float kTilt = -45.0f * 0.017453292f, ct = cosf(kTilt), st = sinf(kTilt), kNear = 1.0f;
        const float ox = (planePos.x - camera.x) / pixelsPerUnit, oz = (planePos.y - camera.y) / pixelsPerUnit;
        float c[3], s[3]; for (int i = 0; i < 3; ++i) { const float t = ang[i] * 6.283185307f / 65536.0f; c[i] = cosf(t); s[i] = sinf(t); }
        struct V { float x, z2, depth, u, v; };
        std::vector<SoftTri> out; out.reserve(m.tris.size() * 2);
        for (const auto& tri : m.tris) {
            V in[3];
            for (int k = 0; k < 3; ++k) {
                float x = tri.v[k].x * scale, y = tri.v[k].y * scale, z = tri.v[k].z * scale, t;
                t = y * c[0] - z * s[0]; z = y * s[0] + z * c[0]; y = t;      // X
                t = x * c[1] + z * s[1]; z = -x * s[1] + z * c[1]; x = t;     // Y
                t = x * c[2] - y * s[2]; y = x * s[2] + y * c[2]; x = t;      // Z
                in[k] = {ox + x, oz + (y * st + z * ct), 218.0f - (y * ct - z * st), tri.v[k].u, tri.v[k].v};   // RotateX(-45); depth from the eye
            }
            V poly[4]; int n = 0;   // clip against depth >= kNear (Sutherland-Hodgman on one plane)
            for (int k = 0; k < 3; ++k) {
                const V& a = in[k]; const V& b = in[(k + 1) % 3]; const bool ain = a.depth >= kNear, bin = b.depth >= kNear;
                if (ain) poly[n++] = a;
                if (ain != bin) { const float t = (kNear - a.depth) / (b.depth - a.depth); poly[n++] = {a.x + (b.x - a.x) * t, a.z2 + (b.z2 - a.z2) * t, kNear, a.u + (b.u - a.u) * t, a.v + (b.v - a.v) * t}; }
            }
            for (int k = 1; k + 1 < n; ++k) {
                SoftTri o{}; o.tex = (tri.mat < m.matTex.size()) ? (int)m.matTex[tri.mat] : -1;
                const V* q[3] = {&poly[0], &poly[k], &poly[k + 1]};
                for (int e = 0; e < 3; ++e) { const float sc = pixelsPerUnit * 218.0f / q[e]->depth; o.p[e] = {camera.x + q[e]->x * sc, camera.y + q[e]->z2 * sc}; o.iw[e] = 1.0f / q[e]->depth; o.light[e] = 1.0f; o.u[e] = q[e]->u; o.v[e] = q[e]->v; }
                out.push_back(o);
            }
        }
        softRender(ren, out);
    }

    // 0x8c056d00 marker quad: an unlit white-vertex plane of half size h centred on `centre`, drawn as a screen-aligned square of `size` pixels (the field camera looks straight down at it).
    void drawMarkerQuad(SDL_Renderer* ren, const Model3D& m, SDL_FPoint centre, float size, float halfUnits) const {
        std::vector<SoftTri> out; out.reserve(m.tris.size());
        for (const auto& tri : m.tris) {
            SoftTri o{}; o.tex = tri.mat < m.matTex.size() ? (int)m.matTex[tri.mat] : -1; o.translucent = true;
            for (int k = 0; k < 3; ++k) {
                o.light[k] = 1.0f; o.iw[k] = 1.0f;
                o.p[k] = {centre.x + tri.v[k].x / halfUnits * size * 0.5f, centre.y - tri.v[k].y / halfUnits * size * 0.5f};
                o.u[k] = tri.v[k].v; o.v[k] = tri.v[k].u;   // transposed: the asymmetric "50" reads correctly only this way (flyhost golden-mouse capture, 2026-11-24); the "?" is symmetric
            }
            out.push_back(o);
        }
        softRender(ren, out);
    }

    // FUN_8c01d9a0: Translate(position), RotateX(angle), Scale(uniform), native chunk drum.
    void drawDcRoulette(SDL_Renderer* ren, const Model3D& m, SDL_FPoint planePos, SDL_FPoint camera,
                        float pixelsPerUnit, float height, float angle, float size) const {
        const float c = cosf(angle), s = sinf(angle);
        const float ox = (planePos.x - camera.x) / pixelsPerUnit;
        const float oz = (planePos.y - camera.y) / pixelsPerUnit;
        std::vector<SoftTri> out;
        for (const auto& tri : m.tris) {
            SoftTri o{}; o.tex = tri.mat < m.matTex.size() ? static_cast<int>(m.matTex[tri.mat]) : -1;
            for (int k = 0; k < 3; ++k) {
                const auto& v = tri.v[k];
                const float y = height + (v.y * c - v.z * s) * size;
                const float z = (v.y * s + v.z * c) * size;
                const float depth = 218.0f - y;
                const float scale = pixelsPerUnit * 218.0f / depth;
                const float ny = (v.ny * c - v.nz * s) * size;
                const float nz = (v.ny * s + v.nz * c) * size;
                o.p[k] = {camera.x + (ox + v.x * size) * scale, camera.y + (oz + z) * scale};
                o.iw[k] = 1.0f / depth; o.u[k] = 1.0f - v.v; o.v[k] = v.u;
                // The chunk path transforms normals with the scaled model matrix.
                // Keep that length: normalization would darken the bright front faces.
                o.light[k] = std::min(1.0f, 0.3f + std::max(0.0f, 0.5f * ny - 0.25f * nz));
            }
            out.push_back(o);
        }
        softRender(ren, out);
    }

    // Draws the model centred at (cx, cy) on screen. Scale is in pixels per model unit and angles are in degrees.
    void draw(SDL_Renderer* ren, const Model3D& m, float cx, float cy, float scale, float yawDeg, float pitchDeg, float brightness = 1.0f, int frame = -1, int forceMat = -1, uint64_t skipMats = 0) const {
        const std::vector<float>* pose = (frame >= 0 && !m.frames.empty()) ? &m.frames[frame % (int)m.frames.size()] : nullptr;
        const float ya = yawDeg * 0.017453292f, pa = pitchDeg * 0.017453292f, cyw = cosf(ya), syw = sinf(ya), cp = cosf(pa), sp = sinf(pa);
        struct T { float z; int tex; SDL_Vertex v[3]; };
        std::vector<T> out; out.reserve(m.tris.size());
        const ModelLight& L = modelLight();
        static const int uvOverride = getenv("CCR_UV_MODE") ? atoi(getenv("CCR_UV_MODE")) : -1;
        // The Dreamcast textures are stored with U and V transposed (as the lids need): the mouse faces match Flycast with (1 - v, u); other models keep the exported mapping until a real frame checks them.
        const int uvMode = uvOverride >= 0 ? uvOverride : (m.name.rfind("mouse", 0) == 0 ? 1 : 0);
        for (size_t ti = 0; ti < m.tris.size(); ti++) {
            const auto& t = m.tris[ti];
            if (skipMats >> (t.mat & 63) & 1) continue;
            T o; float zsum = 0;
            for (int k = 0; k < 3; k++) {
                const float* pp = pose ? &(*pose)[ti * 18 + k * 6] : nullptr;
                const float vx = pp ? pp[0] : t.v[k].x, vy = pp ? pp[1] : t.v[k].y, vz = pp ? pp[2] : t.v[k].z;
                const float wx = pp ? pp[3] : t.v[k].nx, wy = pp ? pp[4] : t.v[k].ny, wz = pp ? pp[5] : t.v[k].nz;
                float x = vx * cyw + vz * syw, z = -vx * syw + vz * cyw, y = vy;
                float y2 = y * cp - z * sp, z2 = y * sp + z * cp;
                float nx = wx * cyw + wz * syw, nz0 = -wx * syw + wz * cyw, ny0 = wy;   // the normal turns like the position (view space)
                float ny = ny0 * cp - nz0 * sp, nz = ny0 * sp + nz0 * cp;
                const float ndl = std::max(0.0f, nx * L.lx + ny * L.ly + nz * L.lz);
                const float lum = std::min(1.0f, L.amb + L.diff * ndl);
                const uint8_t c = (uint8_t)(255.0f * lum * brightness);
                o.v[k].position = SDL_FPoint{cx + x * scale, cy - y2 * scale};
                o.v[k].color = SDL_Color{c, c, c, 255}; o.v[k].tex_coord = uvMode == 1 ? SDL_FPoint{1.0f - t.v[k].v, t.v[k].u} : uvMode == 2 ? SDL_FPoint{t.v[k].v, t.v[k].u} : uvMode == 3 ? SDL_FPoint{t.v[k].v, 1.0f - t.v[k].u} : SDL_FPoint{t.v[k].u, t.v[k].v};   // comparison switch CCR_UV_MODE
                zsum += z2;
            }
            const int mi = forceMat >= 0 ? forceMat : t.mat; o.z = zsum / 3; o.tex = mi < (int)m.matTex.size() ? (int)m.matTex[mi] : 0; out.push_back(o);
        }
        std::stable_sort(out.begin(), out.end(), [](const T& a, const T& b) { return a.z < b.z; });   // Far to near, with positive view-space z toward the camera.
        std::vector<SDL_Vertex> batch;
        for (size_t i = 0; i < out.size();) {
            size_t j = i; batch.clear();
            while (j < out.size() && out[j].tex == out[i].tex) { batch.insert(batch.end(), out[j].v, out[j].v + 3); j++; }
            if (out[i].tex >= 0 && out[i].tex < (int)textures.size()) SDL_RenderGeometry(ren, textures[out[i].tex], batch.data(), (int)batch.size(), nullptr, 0);
            i = j;
        }
    }
};
