// Replays local/testdata/editor_golden.bin (tools/oracle/make_editor_golden.py: the emulated Android Editor::convertField) through core/editor.hpp.
#include "../core/editor.hpp"
#include <cstdio>
#include <vector>
using namespace ccr;
int main(int argc, char** argv) {
    FILE* f = fopen(argc > 1 ? argv[1] : "../local/testdata/editor_golden.bin", "rb"); if (!f) { printf("cannot open golden\n"); return 2; }
    uint32_t n; if (fread(&n, 4, 1, f) != 1) return 2; int ok = 0;
    for (uint32_t i = 0; i < n; i++) {
        uint32_t cells[9][12]; uint8_t title[22], want[0x175]; uint32_t count;
        if (fread(cells, 4, 108, f) != 108 || fread(title, 1, 22, f) != 22 || fread(&count, 4, 1, f) != 1 || fread(want, 1, 0x175, f) != 0x175) return 2;
        std::vector<EditorArrow> arrows(count); for (auto& a : arrows) if (fread(&a, 8, 1, f) != 1) return 2;
        title[21] = 0;
        EditorStage got = convertEditorField(cells, title);
        bool same = got.arrows.size() == count && !memcmp(got.arrows.data(), arrows.data(), count * 8);
        for (int k = 0; k < 0x175; k++) if (k < 0x159 || k >= 0x15c) if (got.bytes[k] != want[k]) same = false;
        if (same) ok++; else printf("MISMATCH case %u\n", i);
    }
    printf("editor golden cases: %u, identical: %d\n", n, ok);
    return ok == (int)n ? 0 : 1;
}
