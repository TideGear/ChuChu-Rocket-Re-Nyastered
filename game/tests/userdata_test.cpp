// Settings parsing/round trip, portable data folder choice and log rotation (core/userdata.hpp).
#include "../core/userdata.hpp"
#include <cassert>
#include <cstdio>
using namespace ccr;
namespace fs = std::filesystem;
static int fails = 0;
#define CHECK(c) do { if (!(c)) { printf("FAIL line %d: %s\n", __LINE__, #c); fails++; } } while (0)
int main() {
    std::error_code ec; const fs::path tmp = fs::temp_directory_path() / "ccr_userdata_test"; fs::remove_all(tmp, ec); fs::create_directories(tmp / "prog", ec); fs::create_directories(tmp / "assets", ec);
    // defaults are written, commented, and read back unchanged
    Settings d = loadOrCreateSettings((tmp / "assets").string()); std::string text; CHECK(readFile((tmp / "assets/settings.ini").string(), text));
    CHECK(text.find("# Start in fullscreen") != std::string::npos); Settings r = parseSettings(text);
    CHECK(r.fullscreen == d.fullscreen && r.vsync == d.vsync && r.filter == d.filter && r.logLevel == d.logLevel && r.logMaxKb == d.logMaxKb && r.logKeepFiles == d.logKeepFiles);
    CHECK(d.models3d && r.models3d && !parseSettings("models_3d = false").models3d);
    // edited values, comments, bad values
    Settings e = parseSettings("fullscreen = yes # comment\nvsync=off\nfilter = nearest\nwindow_width = 1280\nwindow_height=720\nlog_level = 9\nlog_keep_files = 0\nunknown = 1\nfilter2\n");
    CHECK(e.fullscreen && !e.vsync && e.filter == "nearest" && e.width == 1280 && e.height == 720 && e.logLevel == 2 && e.logKeepFiles == 1);
    CHECK(parseSettings("filter = blurry\n").filter == "linear");
    CHECK(parseSettings("cpu_style = gba").cpuStyle == "gba" && parseSettings("cpu_style = x").cpuStyle == "dreamcast" && r.cpuStyle == "dreamcast");
    CHECK(!r.unlockAll && parseSettings("unlock_all = yes").unlockAll && parseSettings(settingsText(parseSettings("unlock_all = true"))).unlockAll);
    Settings battle = parseSettings("battle_time=2\nbattle_speed=5\nbattle_mice=1\nbattle_arrow=1\n");
    CHECK(battle.battleTime == 2 && battle.battleSpeed == 5 && battle.battleMice == 1 && battle.battleArrow == 1);
    CHECK(parseSettings(settingsText(battle)).battleTime == 2 && parseSettings(settingsText(battle)).battleArrow == 1);
    // data folder
    CHECK(resolveDataDir((tmp / "prog").string(), (tmp / "assets").string(), false) == (tmp / "assets").string());
    CHECK(resolveDataDir((tmp / "prog").string(), (tmp / "assets").string(), true) == (tmp / "prog" / "data").generic_string() && fs::is_directory(tmp / "prog" / "data"));
    writeFile((tmp / "prog/portable.txt").string(), "x"); CHECK(resolveDataDir((tmp / "prog").string(), (tmp / "assets").string(), false) == (tmp / "prog" / "data").generic_string());
    // rotation: 1 KB limit, keep 3
    RotatingLog log; log.open((tmp / "assets").string(), 1, 1, 3); std::string line(100, 'x');
    for (int i = 0; i < 100; i++) log.write(1, line.c_str());
    log.write(2, "not written at level 1");
    CHECK(fs::exists(tmp / "assets/logs/ccr.log") && fs::exists(tmp / "assets/logs/ccr.1.log") && fs::exists(tmp / "assets/logs/ccr.2.log") && fs::exists(tmp / "assets/logs/ccr.3.log") && !fs::exists(tmp / "assets/logs/ccr.4.log"));
    CHECK(fs::file_size(tmp / "assets/logs/ccr.log", ec) < 2048);
    std::string cur; readFile((tmp / "assets/logs/ccr.log").string(), cur); CHECK(cur.find("not written") == std::string::npos);
    RotatingLog off; off.open((tmp / "assets2").string(), 0, 1, 3); off.write(1, "x"); CHECK(!fs::exists(tmp / "assets2"));
    fs::remove_all(tmp, ec);
    printf("userdata test: %s\n", fails ? "FAILED" : "ok"); return fails ? 1 : 0;
}
