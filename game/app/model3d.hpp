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
#include <string>
#include <vector>
struct Model3D {
    struct V { float x, y, z, u, v, nx, ny, nz; };
    struct Tri { uint8_t mat; V v[3]; };
    std::string name; std::vector<Tri> tris; std::vector<uint32_t> matTex; std::vector<std::vector<float>> frames;   // animation poses: 18 floats per triangle (3 x position xyz + normal xyz)
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
    ModelPack() = default;
    ModelPack(const ModelPack&) = delete;
    ModelPack& operator=(const ModelPack&) = delete;
    ~ModelPack() { clear(); }
    void clear() {
        for (auto* texture : textures) SDL_DestroyTexture(texture);
        textures.clear();
        models.clear();
    }
    const Model3D* find(const std::string& n) const { for (const auto& m : models) if (m.name == n) return &m; return nullptr; }
    bool load(SDL_Renderer* ren, const std::string& path) {
        ModelPack loaded;
        if (!loaded.read(ren, path)) return false;
        textures.swap(loaded.textures);
        models.swap(loaded.models);
        return true;
    }
private:
    bool read(SDL_Renderer* ren, const std::string& path) {
        FILE* f = fopen(path.c_str(), "rb"); if (!f) return false;
        std::vector<uint8_t> d; uint8_t buf[65536]; size_t n; while ((n = fread(buf, 1, sizeof buf, f)) > 0) d.insert(d.end(), buf, buf + n); fclose(f);
        size_t p = 0;
        auto remaining = [&] { return d.size() - p; };
        auto rd = [&](void* o, size_t k) { if (k > remaining()) return false; memcpy(o, d.data() + p, k); p += k; return true; };
        char magic[4]; uint32_t nt; if (!rd(magic, 4) || memcmp(magic, "CCM3", 4) || !rd(&nt, 4)) return false;
        for (uint32_t i = 0; i < nt; i++) {
            uint16_t w, h;
            if (!rd(&w, 2) || !rd(&h, 2) || !w || !h || h > remaining() / (size_t(w) * 4)) return false;
            SDL_Texture* t = SDL_CreateTexture(ren, SDL_PIXELFORMAT_ABGR8888, SDL_TEXTUREACCESS_STATIC, w, h);
            if (!t) return false;
            textures.push_back(t);
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
            for (auto& t : m.tris) { if (!rd(&t.mat, 1)) return false; for (auto& v : t.v) if (!rd(&v, 32)) return false; }
            const size_t frameBytes = size_t(ntri) * 18 * 4;
            uint32_t nf;
            if (!rd(&nf, 4) || (nf && (!frameBytes || nf > remaining() / frameBytes))) return false;
            m.frames.resize(nf);
            for (auto& fr : m.frames) { fr.resize((size_t)ntri * 18); if (!rd(fr.data(), fr.size() * 4)) return false; }
            models.push_back(std::move(m));
        }
        return true;
    }
public:
    // The Battle draw task builds a dome from two copies of the lid,
    // at yaw 90 and 270 degrees, under its top-down perspective camera.
    void drawDcRocketDome(SDL_Renderer* ren, const Model3D& lid, SDL_FPoint floorPosition,
                          SDL_FPoint cameraCenter, float pixelsPerUnit, float pulse) const {
        struct Triangle {
            float height = 0;
            SDL_Vertex vertices[3];
        };
        if (lid.tris.empty()) return;
        const size_t material = lid.tris.front().mat;
        if (material >= lid.matTex.size() || lid.matTex[material] >= textures.size()) return;
        const float scale = pixelsPerUnit * pulse;
        std::vector<Triangle> projected;
        projected.reserve(2 * lid.tris.size());
        for (float side : {1.0f, -1.0f}) {
            for (const auto& tri : lid.tris) {
                Triangle out;
                for (int i = 0; i < 3; ++i) {
                    const auto& v = tri.v[i];
                    const float depth = 218.0f - v.y * pulse;
                    const float perspective = 218.0f / depth;
                    const float dx = floorPosition.x - cameraCenter.x + side * v.z * scale;
                    const float dy = floorPosition.y - cameraCenter.y - side * v.x * scale;
                    const float light = 0.3f + std::max(0.0f, 0.5f * v.ny + 0.25f * side * v.nx);
                    const Uint8 shade = static_cast<Uint8>(std::lround(255.0f * light));
                    // The decoded PVR's axes are transposed relative to the Ninja UVs.
                    out.vertices[i] = {{cameraCenter.x + dx * perspective, cameraCenter.y + dy * perspective},
                                       {shade, shade, shade, 255}, {1.0f - v.v, v.u}};
                    out.height += v.y;
                }
                projected.push_back(out);
            }
        }
        std::stable_sort(projected.begin(), projected.end(), [](const Triangle& a, const Triangle& b) {
            return a.height < b.height;
        });
        std::vector<SDL_Vertex> vertices;
        vertices.reserve(projected.size() * 3);
        for (const auto& tri : projected)
            vertices.insert(vertices.end(), tri.vertices, tri.vertices + 3);
        SDL_RenderGeometry(ren, textures[lid.matTex[material]], vertices.data(),
                           static_cast<int>(vertices.size()), nullptr, 0);
    }

    // Wall pieces exactly as the Dreamcast board task submits them (Flycast Puzzle 01, PowerVR stream at state offset 0x253eb0): the bar mesh lies flat in the model's xz plane at
    // height 3, is turned about the vertical axis (0 for horizontal edges, -90 degrees for vertical ones; with that the lighting below matches all ten real vertices of both)
    // and drawn at pixelsPerUnit = wall-plane cell / 15. Each vertex carries its own intensity 0.3 + max(0, 0.5 * ny - 0.25 * nz) of the turned normal (checked to four decimals
    // against the real base intensities 0.3846 .. 0.8394), multiplied with the texture; no extra brightness factor.
    void drawDcWall(SDL_Renderer* ren, const Model3D& wall, int material, SDL_FPoint center, float pixelsPerUnit, float yawDeg) const {
        if (wall.tris.empty() || material < 0 || material >= (int)wall.matTex.size() || wall.matTex[material] >= textures.size()) return;
        const float a = yawDeg * 0.017453292f, c = cosf(a), s = sinf(a);
        std::vector<SDL_Vertex> vertices; vertices.reserve(wall.tris.size() * 3);
        for (const auto& tri : wall.tris) {
            for (int i = 0; i < 3; ++i) {
                const auto& v = tri.v[i];
                const float x = v.x * c + v.z * s, z = -v.x * s + v.z * c;
                const float nx = v.nx * c + v.nz * s, nz = -v.nx * s + v.nz * c; (void)nx;
                const float light = std::min(1.0f, 0.3f + std::max(0.0f, 0.5f * v.ny - 0.25f * nz));
                const Uint8 shade = static_cast<Uint8>(std::lround(255.0f * light));
                vertices.push_back({{center.x + x * pixelsPerUnit, center.y + z * pixelsPerUnit}, {shade, shade, shade, 255}, {1.0f - v.v, v.u}});   // the pack's textures are stored transposed (as for the lids), so the stream's (u, v) is sampled as (v, u)
            }
        }
        SDL_RenderGeometry(ren, textures[wall.matTex[material]], vertices.data(), static_cast<int>(vertices.size()), nullptr, 0);
    }

    // A character (mouse or cat) exactly as the Dreamcast field callbacks draw it (0x8c0193e0 for mice, 0x8c011060 for cats; verified by fitting the real PowerVR vertices of 40 mice and
    // the cats in Flycast frames with zero residual, docs/dreamcast_models.md): matrix = position * translate(0, 0, translateZ) * RotateX(-45 degrees) * RotateY(yaw) * scale 1, in world
    // units (15 per cell; X right, Y up, Z down the screen) seen from 218 units above the floor with the screen centre at `camera`: sx = camera.x + k * 218 * X / (218 - Y), likewise
    // sy with Z. Lighting per vertex: 0.3 + max(0, light . R n). `blend` > 0 mixes pose frame `frame` with pose frame `frame + 1` (the cat's head morph and walk pose are interpolated by
    // the fractional part of its phase); mice pass blend 0 and use one of their eight keyframe models.
    void drawDcCharacter(SDL_Renderer* ren, const Model3D& m, SDL_FPoint planePos, SDL_FPoint camera, float pixelsPerUnit, float yawDeg, float translateZ,
                         const float (&light)[3], int frame, float blend, int uvMode, uint32_t translucentMaterials = 0) const {
        if (m.tris.empty()) return;
        const float ya = yawDeg * 0.017453292f, cy = cosf(ya), sy = sinf(ya);
        constexpr float kTilt = -45.0f * 0.017453292f; const float ct = cosf(kTilt), st = sinf(kTilt);
        const float ox = (planePos.x - camera.x) / pixelsPerUnit, oz = (planePos.y - camera.y) / pixelsPerUnit + translateZ;
        const std::vector<float>* a = (frame >= 0 && !m.frames.empty()) ? &m.frames[frame % (int)m.frames.size()] : nullptr;
        const std::vector<float>* b = (frame >= 0 && !m.frames.empty() && blend > 0.0f) ? &m.frames[(frame + 1) % (int)m.frames.size()] : nullptr;
        struct Tri { float depth; int tex; bool translucent; bool over; SDL_Vertex v[3]; SDL_Color extra[3]; };
        std::vector<Tri> out; out.reserve(m.tris.size());
        for (size_t ti = 0; ti < m.tris.size(); ++ti) {
            const auto& tri = m.tris[ti]; Tri o; o.over = false; float depthSum = 0;
            for (int k = 0; k < 3; ++k) {
                float vx = tri.v[k].x, vy = tri.v[k].y, vz = tri.v[k].z, nx = tri.v[k].nx, ny = tri.v[k].ny, nz = tri.v[k].nz;
                if (a) {
                    const float* pa = &(*a)[ti * 18 + k * 6];
                    vx = pa[0]; vy = pa[1]; vz = pa[2]; nx = pa[3]; ny = pa[4]; nz = pa[5];
                    if (b) { const float* pb = &(*b)[ti * 18 + k * 6]; const float f = blend; vx += (pb[0] - vx) * f; vy += (pb[1] - vy) * f; vz += (pb[2] - vz) * f; nx += (pb[3] - nx) * f; ny += (pb[4] - ny) * f; nz += (pb[5] - nz) * f; }
                }
                const float x1 = vx * cy + vz * sy, z1 = -vx * sy + vz * cy;                 // RotateY(yaw)
                const float y2 = vy * ct - z1 * st, z2 = vy * st + z1 * ct;                  // RotateX(-45)
                const float n1x = nx * cy + nz * sy, n1z = -nx * sy + nz * cy;
                const float n2x = n1x, n2y = ny * ct - n1z * st, n2z = ny * st + n1z * ct;
                const float depth = 218.0f - y2, scale = pixelsPerUnit * 218.0f / depth;
                const float rawLum = 0.3f + std::max(0.0f, light[0] * n2x + light[1] * n2y + light[2] * n2z);   // can exceed 1.0 (mice reach 1.08); the PowerVR multiplies the texture and saturates
                const float lum = std::min(1.0f, rawLum);
                const Uint8 shade = static_cast<Uint8>(std::lround(255.0f * lum));
                const Uint8 extra = static_cast<Uint8>(std::lround(255.0f * std::min(1.0f, std::max(0.0f, rawLum - 1.0f)))); o.extra[k] = {extra, extra, extra, 255}; if (extra) o.over = true;
                const SDL_FPoint uv = uvMode == 1 ? SDL_FPoint{1.0f - tri.v[k].v, tri.v[k].u} : SDL_FPoint{tri.v[k].u, tri.v[k].v};
                o.v[k].position = {camera.x + (ox + x1) * scale, camera.y + (oz + z2) * scale};
                o.v[k].color = {shade, shade, shade, 255}; o.v[k].tex_coord = uv; depthSum += depth;
            }
            const int mi = tri.mat; o.translucent = (translucentMaterials >> (mi & 31)) & 1u; o.depth = depthSum / 3; o.tex = mi < (int)m.matTex.size() ? (int)m.matTex[mi] : -1; out.push_back(o);
        }
        std::stable_sort(out.begin(), out.end(), [](const Tri& p, const Tri& q) { if (p.translucent != q.translucent) return !p.translucent; return p.depth > q.depth; });   // opaque first, then the translucent list (the PowerVR draws its lists in that order), each far to near
        std::vector<SDL_Vertex> batch;
        for (size_t i = 0; i < out.size();) {
            size_t j = i; batch.clear();
            while (j < out.size() && out[j].tex == out[i].tex && out[j].translucent == out[i].translucent) { batch.insert(batch.end(), out[j].v, out[j].v + 3); j++; }
            if (out[i].tex >= 0 && out[i].tex < (int)textures.size()) SDL_RenderGeometry(ren, textures[out[i].tex], batch.data(), (int)batch.size(), nullptr, 0);
            i = j;
        }
        // Intensities above 1.0: add texture * (intensity - 1) on top (additive blend), as the PowerVR's saturating multiply brightens the texture.
        for (size_t i = 0; i < out.size();) {
            size_t j = i; batch.clear();
            static const bool noOver = getenv("CCR_NO_OVERBRIGHT") != nullptr;   // comparison switch
            while (j < out.size() && out[j].tex == out[i].tex) { if (out[j].over && !noOver) for (int k = 0; k < 3; ++k) { SDL_Vertex v = out[j].v[k]; v.color = out[j].extra[k]; batch.push_back(v); } j++; }
            if (!batch.empty() && out[i].tex >= 0 && out[i].tex < (int)textures.size()) {
                SDL_SetTextureBlendMode(textures[out[i].tex], SDL_BLENDMODE_ADD);
                SDL_RenderGeometry(ren, textures[out[i].tex], batch.data(), (int)batch.size(), nullptr, 0);
                SDL_SetTextureBlendMode(textures[out[i].tex], SDL_BLENDMODE_BLEND);
            }
            i = j;
        }
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
