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
struct ModelLight { float lx = 0.6f, ly = 0.1f, lz = 0.5f, amb = 0.75f, diff = 0.8f; };   // fitted to the mobile turntable (tools/fit_light.py, fine pass): mean luminance error 0.080 (first guess 0.148)
inline ModelLight& modelLight() {
    static ModelLight l; static bool init = false;
    if (!init) { init = true; if (const char* e = getenv("CCR_LIGHT")) sscanf(e, "%f,%f,%f,%f,%f", &l.lx, &l.ly, &l.lz, &l.amb, &l.diff); float n = sqrtf(l.lx * l.lx + l.ly * l.ly + l.lz * l.lz); if (n > 0) { l.lx /= n; l.ly /= n; l.lz /= n; } }
    return l;
}
struct ModelPack {
    std::vector<SDL_Texture*> textures; std::vector<Model3D> models;
    ~ModelPack() { for (auto* t : textures) if (t) SDL_DestroyTexture(t); }
    const Model3D* find(const std::string& n) const { for (const auto& m : models) if (m.name == n) return &m; return nullptr; }
    bool load(SDL_Renderer* ren, const std::string& path) {
        FILE* f = fopen(path.c_str(), "rb"); if (!f) return false;
        std::vector<uint8_t> d; uint8_t buf[65536]; size_t n; while ((n = fread(buf, 1, sizeof buf, f)) > 0) d.insert(d.end(), buf, buf + n); fclose(f);
        size_t p = 0; auto rd = [&](void* o, size_t k) { if (p + k > d.size()) return false; memcpy(o, d.data() + p, k); p += k; return true; };
        char magic[4]; uint32_t nt; if (!rd(magic, 4) || memcmp(magic, "CCM3", 4) || !rd(&nt, 4)) return false;
        for (uint32_t i = 0; i < nt; i++) {
            uint16_t w, h; if (!rd(&w, 2) || !rd(&h, 2) || p + (size_t)w * h * 4 > d.size()) return false;
            SDL_Texture* t = SDL_CreateTexture(ren, SDL_PIXELFORMAT_ABGR8888, SDL_TEXTUREACCESS_STATIC, w, h);
            if (!t) return false; SDL_UpdateTexture(t, nullptr, d.data() + p, w * 4); SDL_SetTextureBlendMode(t, SDL_BLENDMODE_BLEND); p += (size_t)w * h * 4; textures.push_back(t);
        }
        uint32_t nm; if (!rd(&nm, 4)) return false;
        for (uint32_t i = 0; i < nm; i++) {
            Model3D m; char nm24[25] = {}; uint32_t ntri, nmat; if (!rd(nm24, 24) || !rd(&ntri, 4) || !rd(&nmat, 4)) return false; m.name = nm24;
            m.matTex.resize(nmat); if (nmat && !rd(m.matTex.data(), 4 * nmat)) return false;
            m.tris.resize(ntri);
            for (auto& t : m.tris) { if (!rd(&t.mat, 1)) return false; for (auto& v : t.v) if (!rd(&v, 32)) return false; }
            uint32_t nf; if (!rd(&nf, 4)) return false; m.frames.resize(nf);
            for (auto& fr : m.frames) { fr.resize((size_t)ntri * 18); if (!rd(fr.data(), fr.size() * 4)) return false; }
            models.push_back(std::move(m));
        }
        return true;
    }
    // Draws the model centred at (cx, cy) on screen. scale: pixels per model unit; yaw/pitch in degrees; light: simple directional shade 0..1 (1 = none).
    void draw(SDL_Renderer* ren, const Model3D& m, float cx, float cy, float scale, float yawDeg, float pitchDeg, float shade = 1.0f, int frame = -1, int forceMat = -1) const {
        const std::vector<float>* pose = (frame >= 0 && !m.frames.empty()) ? &m.frames[frame % (int)m.frames.size()] : nullptr;
        const float ya = yawDeg * 0.017453292f, pa = pitchDeg * 0.017453292f, cyw = cosf(ya), syw = sinf(ya), cp = cosf(pa), sp = sinf(pa);
        struct T { float z; int tex; SDL_Vertex v[3]; };
        std::vector<T> out; out.reserve(m.tris.size());
        const ModelLight& L = modelLight();
        for (size_t ti = 0; ti < m.tris.size(); ti++) {
            const auto& t = m.tris[ti];
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
                const uint8_t c = (uint8_t)(255.0f * lum);
                o.v[k].position = SDL_FPoint{cx + x * scale, cy - y2 * scale};
                o.v[k].color = SDL_Color{c, c, c, 255}; o.v[k].tex_coord = SDL_FPoint{t.v[k].u, t.v[k].v};
                zsum += z2;
            }
            const int mi = forceMat >= 0 ? forceMat : t.mat; o.z = zsum / 3; o.tex = mi < (int)m.matTex.size() ? (int)m.matTex[mi] : 0; out.push_back(o);
        }
        std::sort(out.begin(), out.end(), [](const T& a, const T& b) { return a.z > b.z; });   // far to near (the camera looks down -z in model space after the rotation)
        std::vector<SDL_Vertex> batch;
        for (size_t i = 0; i < out.size();) {
            size_t j = i; batch.clear();
            while (j < out.size() && out[j].tex == out[i].tex) { batch.insert(batch.end(), out[j].v, out[j].v + 3); j++; }
            if (out[i].tex >= 0 && out[i].tex < (int)textures.size()) SDL_RenderGeometry(ren, textures[out[i].tex], batch.data(), (int)batch.size(), nullptr, 0);
            i = j;
        }
    }
};
