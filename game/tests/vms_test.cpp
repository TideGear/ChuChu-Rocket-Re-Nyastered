// Reads the user's real DEPuzzle and PuzzleP packs (local/cache/assets/dlc, skipped when absent), re-encodes every slot and compares, and round-trips a synthetic pack.
#include "../core/vms.hpp"
#include <cstdio>
using namespace ccr;
static int fails = 0;
#define CHECK(c) do { if (!(c)) { printf("FAIL line %d: %s\n", __LINE__, #c); fails++; } } while (0)
static bool load(const char* p, std::vector<uint8_t>& d) { FILE* f = fopen(p, "rb"); if (!f) return false; uint8_t b[4096]; size_t n; d.clear(); while ((n = fread(b, 1, sizeof b, f)) > 0) d.insert(d.end(), b, b + n); fclose(f); return true; }
int main(int argc, char** argv) {
    const char* dir = argc > 1 ? argv[1] : "../local/cache/assets/dlc";
    for (const char* name : {"DEPuzzle", "PuzzleP"}) {
        std::vector<uint8_t> d; char path[512]; snprintf(path, sizeof path, "%s/%s.VMS", dir, name);
        if (!load(path, d)) { printf("%s: not found, skipped\n", path); continue; }
        std::vector<VmsPuzzle> ps; const int n = vms::readPack(d, ps); CHECK(n >= 24);
        int bad = 0;
        for (int k = 0; k < n; k++) {
            uint8_t e[vms::kSlot]; CHECK(vms::encodeSlot(ps[k], e));
            const uint8_t* s = d.data() + vms::kHeader + k * vms::kSlot; const int an = s[475] > 12 ? 12 : s[475];
            if (memcmp(e, s, 476) || memcmp(e + 476, s + 476, an) || ((e[488] | e[489] << 8 | e[490] << 16) & ((1 << (2 * an)) - 1)) != ((s[488] | s[489] << 8 | s[490] << 16) & ((1 << (2 * an)) - 1)) || strncmp((const char*)e + 491, (const char*)s + 491, 21)) bad++;
        }
        printf("%s: %d puzzles, %d differ after re-encoding\n", name, n, bad); CHECK(bad == 0);
    }
    VmsPuzzle p; for (int i = 0; i < 108; i++) p.tiles[i] = (i % 7 == 0) ? 1 : (i % 11 == 0 ? 0x11 : 0); for (int i = 0; i < 237; i++) p.walls[i] = (i % 5 == 0);
    p.arrows = {{1, 2, 0}, {3, 4, 1}, {5, 6, 2}, {11, 8, 3}}; p.title = "Test Puzzle";
    std::vector<VmsPuzzle> in{p, p}; auto v = vms::writePack(in); CHECK(v.size() % 512 == 0);
    std::vector<VmsPuzzle> out; vms::readPack(v, out); CHECK(out.size() == 2);
    CHECK(out[0].title == "Test Puzzle" && out[0].arrows.size() == 4 && out[0].arrows[3].dir == 3 && out[0].arrows[3].x == 11 && !memcmp(out[0].tiles, p.tiles, 108));
    CHECK(vms::readPack(std::vector<uint8_t>(40000, 0), out) == -1);
    printf("vms test: %s\n", fails ? "FAILED" : "ok"); return fails;
}
