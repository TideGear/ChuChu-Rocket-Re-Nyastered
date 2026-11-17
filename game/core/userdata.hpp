// Where the player's data lives, the readable settings file and the rotating log. No SDL here so it can be tested headlessly (tests/userdata_test.cpp).
//  Portable mode: a file named "portable.txt" beside the program, the command line flag --portable, or CCR_PORTABLE=1 keeps saves, settings and logs in "<program folder>/data".
//  Otherwise saves stay in the extracted asset folder (as before), settings and logs go beside them.
#pragma once
#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <ctime>
#include <filesystem>
#include <string>
namespace ccr {
struct Settings {
    bool fullscreen = false;     // start in fullscreen
    bool vsync = true;           // wait for the display refresh
    std::string filter = "linear";   // "linear" or "nearest" scaling
    int width = 0, height = 0;   // window size, 0 = default
    int logLevel = 1;            // 0 = no log, 1 = sessions and results, 2 = also every screen change
    int logKeepFiles = 5;        // rotated log files kept
    int logMaxKb = 256;          // size at which the log rotates
};
inline std::string trim(std::string s) { const char* w = " \t\r\n"; s.erase(0, s.find_first_not_of(w)); const size_t e = s.find_last_not_of(w); s.erase(e == std::string::npos ? 0 : e + 1); return s; }
inline bool parseBool(const std::string& v, bool def) { std::string t; for (char c : v) t += (char)tolower((unsigned char)c); if (t == "1" || t == "true" || t == "yes" || t == "on") return true; if (t == "0" || t == "false" || t == "no" || t == "off") return false; return def; }
inline Settings parseSettings(const std::string& text) {
    Settings s; size_t pos = 0;
    while (pos <= text.size()) {
        size_t nl = text.find('\n', pos); if (nl == std::string::npos) nl = text.size();
        std::string line = text.substr(pos, nl - pos); pos = nl + 1;
        const size_t hash = line.find('#'); if (hash != std::string::npos) line.erase(hash);
        const size_t eq = line.find('='); if (eq == std::string::npos) continue;
        const std::string k = trim(line.substr(0, eq)), v = trim(line.substr(eq + 1)); if (v.empty()) continue;
        if (k == "fullscreen") s.fullscreen = parseBool(v, s.fullscreen);
        else if (k == "vsync") s.vsync = parseBool(v, s.vsync);
        else if (k == "filter") { if (v == "linear" || v == "nearest") s.filter = v; }
        else if (k == "window_width") s.width = std::max(0, atoi(v.c_str()));
        else if (k == "window_height") s.height = std::max(0, atoi(v.c_str()));
        else if (k == "log_level") s.logLevel = std::max(0, std::min(2, atoi(v.c_str())));
        else if (k == "log_keep_files") s.logKeepFiles = std::max(1, std::min(50, atoi(v.c_str())));
        else if (k == "log_max_kb") s.logMaxKb = std::max(16, std::min(65536, atoi(v.c_str())));
    }
    return s;
}
inline std::string settingsText(const Settings& s) {
    char b[1800];
    snprintf(b, sizeof b,
        "# ChuChu Rocket! Re-Nyastered settings (an unofficial fan project, not affiliated with SEGA).\n"
        "# Edit with any text editor; the game reads this file at start. Lines starting with # are comments.\n"
        "# Environment variables (CCR_FULLSCREEN, CCR_VSYNC, CCR_FILTER, CCR_SIZE) and launcher options override these values.\n\n"
        "# Start in fullscreen: true or false.\nfullscreen = %s\n\n"
        "# Wait for the display refresh (stops tearing): true or false.\nvsync = %s\n\n"
        "# How the picture is scaled: linear (smooth) or nearest (sharp pixels).\nfilter = %s\n\n"
        "# Window size in pixels; 0 uses the default size.\nwindow_width = %d\nwindow_height = %d\n\n"
        "# Log detail: 0 = off, 1 = sessions and match results, 2 = also every screen change.\nlog_level = %d\n\n"
        "# The log file (logs/ccr.log) rotates when it reaches this many kilobytes; this many old files are kept.\nlog_max_kb = %d\nlog_keep_files = %d\n",
        s.fullscreen ? "true" : "false", s.vsync ? "true" : "false", s.filter.c_str(), s.width, s.height, s.logLevel, s.logMaxKb, s.logKeepFiles);
    return b;
}
inline bool readFile(const std::string& path, std::string& out) { FILE* f = fopen(path.c_str(), "rb"); if (!f) return false; char buf[4096]; size_t n; out.clear(); while ((n = fread(buf, 1, sizeof buf, f)) > 0) out.append(buf, n); fclose(f); return true; }
inline bool writeFile(const std::string& path, const std::string& data) { FILE* f = fopen(path.c_str(), "wb"); if (!f) return false; const bool ok = fwrite(data.data(), 1, data.size(), f) == data.size(); fclose(f); return ok; }
// Reads settings.ini from dir; creates it with the commented defaults when it does not exist (or cannot be read).
inline Settings loadOrCreateSettings(const std::string& dir) {
    const std::string path = dir + "/settings.ini"; std::string text;
    if (readFile(path, text)) return parseSettings(text);
    Settings d; writeFile(path, settingsText(d)); return d;
}
// The folder for saves, settings and logs. Creates it.
inline std::string resolveDataDir(const std::string& programDir, const std::string& assetRoot, bool portableFlag) {
    namespace fs = std::filesystem; std::error_code ec;
    const bool env = getenv("CCR_PORTABLE") && atoi(getenv("CCR_PORTABLE")) != 0;
    const bool portable = portableFlag || env || fs::exists(fs::path(programDir) / "portable.txt", ec);
    const std::string dir = portable ? (fs::path(programDir) / "data").generic_string() : assetRoot;
    fs::create_directories(dir, ec); return dir;
}
// logs/ccr.log, rotated by size: ccr.log -> ccr.1.log -> ... (the oldest beyond keepFiles is deleted).
class RotatingLog {
public:
    void open(const std::string& dir, int level, int maxKb, int keepFiles) {
        namespace fs = std::filesystem; std::error_code ec;
        level_ = level; maxBytes_ = (size_t)std::max(1, maxKb) * 1024; keep_ = std::max(1, keepFiles); base_ = dir + "/logs"; if (level_ <= 0) return;
        fs::create_directories(base_, ec); rotate();
    }
    void write(int level, const char* text) {
        if (level > level_ || level_ <= 0 || base_.empty()) return;
        const std::string path = base_ + "/ccr.log"; FILE* f = fopen(path.c_str(), "ab"); if (!f) return;
        time_t t = time(nullptr); char ts[32]; struct tm tmv;
#ifdef _WIN32
        localtime_s(&tmv, &t);
#else
        localtime_r(&t, &tmv);
#endif
        strftime(ts, sizeof ts, "%Y-%m-%d %H:%M:%S", &tmv); fprintf(f, "%s %s\n", ts, text); long sz = ftell(f); fclose(f);
        if (sz > 0 && (size_t)sz >= maxBytes_) rotate();
    }
    // Moves ccr.log aside when it is already over the limit (also called at open, so a long session never grows past it).
    void rotate() {
        namespace fs = std::filesystem; std::error_code ec; const fs::path cur = fs::path(base_) / "ccr.log";
        if (!fs::exists(cur, ec) || fs::file_size(cur, ec) < maxBytes_) return;
        fs::remove(numbered(keep_), ec);
        for (int i = keep_ - 1; i >= 1; --i) if (fs::exists(numbered(i), ec)) fs::rename(numbered(i), numbered(i + 1), ec);
        fs::rename(cur, numbered(1), ec);
    }
private:
    int level_ = 0, keep_ = 5; size_t maxBytes_ = 256 * 1024; std::string base_;
    std::filesystem::path numbered(int i) const { return std::filesystem::path(base_) / ("ccr." + std::to_string(i) + ".log"); }
};
} // namespace ccr
