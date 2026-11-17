// Controller button assignments (controls.ini beside the settings), pad prompt names and the controller-only quit combo. Button numbers are SDL_GameControllerButton values
// (A 0, B 1, X 2, Y 3, Back 4, Guide 5, Start 6, stick clicks 7/8, shoulders 9/10, d-pad 11..14) so this header needs no SDL.
#pragma once
#include "userdata.hpp"
#include <cstring>
namespace ccr {
struct PadMap {
    int arrow[4] = {0, 2, 3, 1};      // button that places the arrow pointing dir 0 (down), 1 (left), 2 (up), 3 (right): A, X, Y, B as before
    int pause = 6;                    // Start
    int quitA = 4, quitB = 6;         // hold both (Back + Start) ...
    int quitHoldTicks = 120;          // ... for this many 60 Hz ticks to leave the game (back to the launcher)
};
inline const char* const* padButtonNames() { static const char* const n[] = {"a", "b", "x", "y", "back", "guide", "start", "left_stick", "right_stick", "left_shoulder", "right_shoulder", "dpad_up", "dpad_down", "dpad_left", "dpad_right", nullptr}; return n; }
inline int padButtonFromName(const std::string& s) { std::string t; for (char c : s) t += (char)tolower((unsigned char)c); const char* const* n = padButtonNames(); for (int i = 0; n[i]; i++) if (t == n[i]) return i; return -1; }
inline std::string padButtonLabel(int b) { static const char* const lab[] = {"A", "B", "X", "Y", "Back", "Guide", "Start", "L3", "R3", "LB", "RB", "D-pad up", "D-pad down", "D-pad left", "D-pad right"}; return b >= 0 && b < 15 ? lab[b] : "?"; }
inline PadMap parsePadMap(const std::string& text) {
    PadMap m; size_t pos = 0;
    while (pos <= text.size()) {
        size_t nl = text.find('\n', pos); if (nl == std::string::npos) nl = text.size();
        std::string line = text.substr(pos, nl - pos); pos = nl + 1; const size_t h = line.find('#'); if (h != std::string::npos) line.erase(h);
        const size_t eq = line.find('='); if (eq == std::string::npos) continue;
        const std::string k = trim(line.substr(0, eq)), v = trim(line.substr(eq + 1)); if (v.empty()) continue; const int b = padButtonFromName(v);
        if (k == "arrow_down" && b >= 0) m.arrow[0] = b; else if (k == "arrow_left" && b >= 0) m.arrow[1] = b; else if (k == "arrow_up" && b >= 0) m.arrow[2] = b; else if (k == "arrow_right" && b >= 0) m.arrow[3] = b;
        else if (k == "pause" && b >= 0) m.pause = b; else if (k == "quit_button_1" && b >= 0) m.quitA = b; else if (k == "quit_button_2" && b >= 0) m.quitB = b;
        else if (k == "quit_hold_ticks") m.quitHoldTicks = std::max(30, std::min(600, atoi(v.c_str())));
    }
    return m;
}
inline std::string padMapText(const PadMap& m) {
    const char* const* n = padButtonNames(); char b[1500];
    snprintf(b, sizeof b,
        "# Controller buttons. Names: a b x y back guide start left_stick right_stick left_shoulder right_shoulder dpad_up dpad_down dpad_left dpad_right.\n"
        "# Button names follow the Xbox layout; on other pads SDL maps its buttons to these positions. The d-pad moves the cursor and cannot be changed.\n\n"
        "# Buttons that place an arrow pointing down, left, up and right.\narrow_down = %s\narrow_left = %s\narrow_up = %s\narrow_right = %s\n\n"
        "# Pause / start the run.\npause = %s\n\n"
        "# Leave the game from the controller alone: hold both of these buttons for quit_hold_ticks (60 ticks = 1 second).\nquit_button_1 = %s\nquit_button_2 = %s\nquit_hold_ticks = %d\n",
        n[m.arrow[0]], n[m.arrow[1]], n[m.arrow[2]], n[m.arrow[3]], n[m.pause], n[m.quitA], n[m.quitB], m.quitHoldTicks);
    return b;
}
inline PadMap loadOrCreatePadMap(const std::string& dir) { std::string t; if (readFile(dir + "/controls.ini", t)) return parsePadMap(t); PadMap d; writeFile(dir + "/controls.ini", padMapText(d)); return d; }
// Counts ticks while both quit buttons are held; returns true once the hold time is reached.
struct QuitHold { int held = 0; bool tick(bool a, bool b, int need) { held = (a && b) ? held + 1 : 0; return held >= need; } };
} // namespace ccr
