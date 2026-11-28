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
        const auto preserved = vms::writePack(ps, d.data()); CHECK(preserved.size() == vms::kPackSize && !memcmp(preserved.data(), d.data(), 0x46) && !memcmp(preserved.data() + 0x4c, d.data() + 0x4c, vms::kHeader - 0x4c));
        CHECK((uint32_t)preserved[0x48] + ((uint32_t)preserved[0x49] << 8) + ((uint32_t)preserved[0x4a] << 16) + ((uint32_t)preserved[0x4b] << 24) == vms::kFinalSlot - 4);
        int bad = 0;
        for (int k = 0; k < n; k++) {
            uint8_t e[vms::kSlot]; CHECK(vms::encodeSlot(ps[k], e));
            const uint8_t* s = d.data() + vms::kHeader + k * vms::kSlot; const int an = s[475] > 12 ? 12 : s[475];
            if (memcmp(e, s, 476) || memcmp(e + 476, s + 476, an) || ((e[488] | e[489] << 8 | e[490] << 16) & ((1 << (2 * an)) - 1)) != ((s[488] | s[489] << 8 | s[490] << 16) & ((1 << (2 * an)) - 1)) || strncmp((const char*)e + 491, (const char*)s + 491, 21)) bad++;
        }
        printf("%s: %d puzzles, %d differ after re-encoding\n", name, n, bad); CHECK(bad == 0);
        if (!strcmp(name, "PuzzleP")) for (int k = 0; k < n; ++k) {
            const auto& puzzle = ps[k];
            const uint8_t* slot = d.data() + vms::kHeader + k * vms::kSlot;
            const uint32_t dirs = slot[488] | slot[489] << 8 | slot[490] << 16;
            CHECK(slot[475] >= 1 && slot[475] <= 12 && puzzle.arrows.size() == slot[475]);
            for (size_t i = 0; i < puzzle.arrows.size(); ++i) {
                CHECK(puzzle.arrows[i].x == 0 && puzzle.arrows[i].y == 0);
                CHECK(puzzle.arrows[i].dir == ((dirs >> (2 * i)) & 3));
            }
        }
    }
    VmsPuzzle p; for (int i = 0; i < 108; i++) p.tiles[i] = (i % 7 == 0) ? 1 : (i % 11 == 0 ? 0x11 : 0); for (int i = 0; i < 237; i++) p.walls[i] = (i % 5 == 0);
    p.arrows = {{1, 2, 0}, {3, 4, 1}, {5, 6, 2}, {11, 8, 3}}; p.title = "Test Puzzle";
    std::vector<VmsPuzzle> in{p, p}; auto v = vms::writePack(in); CHECK(v.size() == 38400 && v.size() == vms::kPackSize);
    std::vector<VmsPuzzle> out; vms::readPack(v, out); CHECK(out.size() == 2);
    CHECK((uint32_t)v[0x48] + ((uint32_t)v[0x49] << 8) + ((uint32_t)v[0x4a] << 16) + ((uint32_t)v[0x4b] << 24) == vms::kFinalSlot - 4);
    CHECK((uint16_t)(v[0x46] | (uint16_t)v[0x47] << 8) == vms::fileCrc(v));
    std::array<uint8_t, vms::kHeader> originalHeader{}; for (size_t i = 0; i < originalHeader.size(); ++i) originalHeader[i] = (uint8_t)(i * 37 + 11);
    const auto preservedHeaderPack = vms::writePack(in, originalHeader.data()); CHECK(preservedHeaderPack.size() == vms::kPackSize && !memcmp(preservedHeaderPack.data(), originalHeader.data(), 0x46) && !memcmp(preservedHeaderPack.data() + 0x4c, originalHeader.data() + 0x4c, originalHeader.size() - 0x4c));
    CHECK((uint16_t)(preservedHeaderPack[0x46] | (uint16_t)preservedHeaderPack[0x47] << 8) == vms::fileCrc(preservedHeaderPack));
    auto vmi = vms::writeVmi(v.size(), "CCRPUZ", "CHU_CHU__D00"); CHECK(vmi.size() == vms::kVmiSize);
    const uint8_t checksum[4] = {0x43, 0x41, 0x42, 0x40}; CHECK(!memcmp(vmi.data(), checksum, sizeof checksum));
    CHECK(!memcmp(vmi.data() + 80, "CCRPUZ", 6) && !memcmp(vmi.data() + 88, "CHU_CHU__D00", 12));
    CHECK((uint32_t)vmi[104] + ((uint32_t)vmi[105] << 8) + ((uint32_t)vmi[106] << 16) + ((uint32_t)vmi[107] << 24) == v.size());
    CHECK(out[0].title == "Test Puzzle" && out[0].arrows.size() == 4 && out[0].arrows[3].dir == 3 && out[0].arrows[3].x == 11 && !memcmp(out[0].tiles, p.tiles, 108));
    VmsPuzzle badArrow = p; badArrow.arrows[0].x = 12; uint8_t badSlot[vms::kSlot];
    CHECK(!vms::encodeSlot(badArrow, badSlot));
    badArrow = p; badArrow.arrows[0].dir = 4; CHECK(!vms::encodeSlot(badArrow, badSlot));
    VmsPuzzle longTitle = p; longTitle.title.assign(21, 'x'); CHECK(!vms::encodeSlot(longTitle, badSlot));
    auto malformed = v;
    malformed[640 + 476] = 0xc0; // x=12 is outside the 12-column board
    CHECK(vms::readPack(malformed, out) == -1 && out.empty());
    std::vector<VmsPuzzle> fullPack(25, p); fullPack.back().title = "Puzzle 25";
    const auto retailSizePack = vms::writePack(fullPack); std::vector<VmsPuzzle> fullOut;
    CHECK(retailSizePack.size() == 38400 && vms::readPack(retailSizePack, fullOut) == 25 && fullOut.back().title == "Puzzle 25");
    auto damaged = vms::writePack({p, p, p}); damaged[vms::kHeader + vms::kSlot + 26] = 0xff;
    CHECK(vms::readPack(damaged, out) == -1 && out.empty());
    CHECK(vms::readPack(std::vector<uint8_t>(40000, 0), out) == -1);
    printf("vms test: %s\n", fails ? "FAILED" : "ok"); return fails;
}
