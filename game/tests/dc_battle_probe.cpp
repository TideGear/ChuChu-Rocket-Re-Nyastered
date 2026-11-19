// Runs the port's whole BattleGame (stage 0, Dreamcast rand() stream) against Flycast.
// usage: dc_battle_probe <battle_stages.bin> <demo_watch.bin> [KEY_STAGE000.BIN]
// Capture with FLYHOST_SYNC=1 and FLY_WATCH=d2184:4:1660; threaded rendering races RAM observations.
// The capture includes seed, countdown, then initialization and the first gameplay tick together.
// Optional demo inputs replay the measured cursor and arrow mapping; RNG agreement does not prove gameplay parity.
#include "../core/battle.hpp"
#include "../core/dc_cursor.hpp"
#include "../core/dc_demo.hpp"
#include "../app/roulette_pose.hpp"
#include <cstdio>
#include <vector>
using namespace ccr;
static bool loadStage(const char* path, int source, int index, Stage& st) {
    FILE* f = fopen(path, "rb"); if (!f) return false;
    uint32_t n = 0; if (fread(&n, 4, 1, f) != 1) { fclose(f); return false; }
    int seen = 0;
    for (uint32_t i = 0; i < n; ++i) {
        uint8_t h[4], w[237]; Stage s{};
        if (fread(h, 1, 4, f) != 4 || fread(s.tiles, 1, 108, f) != 108 || fread(w, 1, 237, f) != 237) break;
        fseek(f, h[1] * 3, SEEK_CUR); uint8_t title[32]; if (fread(title, 1, 32, f) != 32) break;
        for (int r = 0; r < 10; ++r) for (int c = 0; c < 12; ++c) s.hw[r * 12 + c] = w[25 * r + c];
        for (int r = 0; r < 9; ++r) for (int c = 0; c < 13; ++c) s.vw[r * 13 + c] = w[25 * r + 12 + c];
        if (h[0] == source && seen++ == index) { st = s; fclose(f); return true; }
    }
    fclose(f); return false;
}
struct Row { int frame; uint32_t state; };
int main(int argc, char** argv) {
    if (argc < 3 || argc > 4) { puts("usage: dc_battle_probe <battle_stages.bin> <demo_watch.bin> [KEY_STAGE000.BIN]"); return 2; }
    DcDemo demo;
    if (argc == 4 && !demo.load(argv[3])) { puts("cannot parse demo input"); return 2; }
    Stage st{}; if (!loadStage(argv[1], 2, 0, st)) { puts("cannot load stage 0"); return 2; }
    FILE* f = fopen(argv[2], "rb"); if (!f) return 2;
    std::vector<Row> rows;
    Row row;
    while (fread(&row, 1, sizeof row, f) == sizeof row) rows.push_back(row);
    const bool invalid = ferror(f) || ftell(f) % sizeof row != 0;
    fclose(f);
    if (invalid || rows.size() < 2) { puts("invalid watch capture"); return 2; }
    size_t begin = 0;
    while (begin < rows.size() && rows[begin].state != 0xdead0cabu) ++begin;
    if (begin == rows.size()) { puts("demo seed not captured"); return 2; }
    const size_t seeded = begin;
    while (begin + 1 < rows.size() && rows[begin + 1].state == rows[begin].state) ++begin;
    if (begin + 2 >= rows.size()) { puts("gameplay not captured"); return 2; }
    BattleGame g; g.dreamcastRng = true;
    const auto before = g_rngDraws;
    g.start(st, rows[begin].state);
    const auto setupDraws = g_rngDraws - before;
    DcCursor cursors[4];
    for (int p = 0; p < 4; ++p) {
        cursors[p].x = (g.sim.rocketPos[p][0] + 0.5f) * kCell;
        cursors[p].y = (g.sim.rocketPos[p][1] + 0.5f) * kCell;
    }
    if (argc == 4) { g.freezeOnRoll = true; g.rotateOwn = false; g.gtOff = -1; }
    const char* dumpPath = getenv("DC_BATTLE_DUMP");
    FILE* dump = dumpPath ? fopen(dumpPath, "w") : nullptr;
    if (dumpPath && !dump) return 2;
    auto snapshot = [&]() {
        if (!dump) return;
        fprintf(dump, "{\"watch_frame\":%d,\"tick\":%d,\"clock\":%d,\"event\":%d,\"roulette\":%d,\"scores\":[%d,%d,%d,%d],\"entities\":[",
                rows[begin].frame + g.frame, g.frame, g.clock, g.activeEventKind(), g.rollPending(),
                g.score.player[0], g.score.player[1], g.score.player[2], g.score.player[3]);
        bool first = true;
        for (size_t index = 0; index < g.sim.ents.size(); ++index) {
            const auto& e = g.sim.ents[index];
            const bool pending = std::any_of(g.sim.pendingFree.begin(), g.sim.pendingFree.end(),
                [&](const Sim::PendingFree& p) { return p.ent == static_cast<int>(index); });
            if (!(e.alive && !e.done) && !pending) continue;
            fprintf(dump, "%s[%d,%d,%.9g,%.9g,%d]", first ? "" : ",", e.mouse, e.type, e.x, e.z, e.heading);
            first = false;
        }
        fputs("],\"arrows\":[", dump); first = true;
        for (const auto& a : g.sim.arrows) if (a.live) {
            fprintf(dump, "%s[%d,%d,%d,%d,%d,%d]", first ? "" : ",", a.owner, a.x, a.y, a.dir, a.ttl, a.hits);
            first = false;
        }
        fputs("],\"wheel\":", dump);
        int rt, pl, outcome;
        if (g.rouletteDrawState(rt, pl, outcome)) {
            const auto p = dreamcastRoulettePose(rt, g.sim.rocketPos[pl][0], g.sim.rocketPos[pl][1], outcome);
            fprintf(dump, "[%.9g,%.9g,%.9g,%.9g,%d]", p.x,p.height,p.z,p.scale,p.angle & 0xffff);
        } else fputs("null", dump);
        fputs("}\n", dump);
    };
    auto tick = [&]() {
        if (!demo.frames.empty()) {
            const size_t record = static_cast<size_t>(g.frame + 121);
            if (record >= demo.frames.size()) return false;
            static constexpr uint32_t arrowMasks[] = {4, 0x400, 0x200, 2};
            for (int p = 0; p < 4; ++p) {
                const auto& pad = demo.frames[record][p];
                const uint32_t pressed = demo.pressed(record, p);
                if (g.rollPending()) continue;
                cursors[p].tick(pad.held, pad.x, pad.y);
                for (int d = 0; d < 4; ++d) if (pressed & arrowMasks[d])
                    g.placeArrow(p, cursors[p].cellX(), cursors[p].cellY(), d);
            }
        }
        g.tick(); snapshot(); return true;
    };
    printf("seed 0x%08x, countdown %zu frames, setup %llu draws at watch frame %d\n",
           rows[begin].state, begin - seeded, setupDraws, rows[begin].frame);
    int agree = 0;
    if (setupDraws != 128) { puts("initialization draw mismatch"); return 1; }
    if (g.gen->rng().dreamcastState() != rows[begin + 1].state) {
        // Synchronous Flycast executes table initialization and tick 1 in the same video frame.
        if (!tick()) return 2;
        if (g.gen->rng().dreamcastState() != rows[begin + 1].state) {
            puts("initialization plus first tick state mismatch"); return 1;
        }
        ++agree;
        puts("first gameplay tick shares the setup video frame; state agrees");
    }
    for (size_t i = begin + 1; i + 1 < rows.size(); ++i) {
        if (rows[i + 1].frame != rows[i].frame + 1) { puts("nonconsecutive watch frames"); return 2; }
        uint32_t state = rows[i].state; int draws = 0;
        while (state != rows[i + 1].state && draws < 4096) {
            state = state * 1103515245u + 12345u; ++draws;
        }
        if (draws == 4096) { puts("unresolved watch transition"); return 2; }
        const auto tickBefore = g_rngDraws; if (!tick()) return 2;
        const auto mine = g_rngDraws - tickBefore;
        if (mine != (unsigned)draws || g.gen->rng().dreamcastState() != rows[i + 1].state) {
            printf("first divergence at tick %d (watch frame %d): game %d draws, port %llu; state %08x vs %08x\n",
                   agree + 1, rows[i].frame, draws, mine, rows[i + 1].state, g.gen->rng().dreamcastState());
            printf("%d consecutive gameplay ticks agree in draw count AND state\n", agree);
            printf("port clock %d, event %d, roulette %d, scores %d %d %d %d\n", g.clock,
                   g.activeEventKind(), g.rollPending(), g.score.player[0], g.score.player[1], g.score.player[2], g.score.player[3]);
            return 1;
        }
        ++agree;
    }
    printf("%d consecutive gameplay ticks agree in draw count AND state\n", agree);
    if (dump && fclose(dump) != 0) return 2;
    return 0;
}
