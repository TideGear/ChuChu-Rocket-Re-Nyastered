// RecompLauncher "prepare" step on Linux and macOS: runs tools/prepare.py (next to the program) with the player's game folder.
// Windows uses launcher_setup.hpp (PowerShell). Needs Python 3.10+ with Pillow on the PATH; prepare.py explains what is missing.
#pragma once
#include <cstdio>
#include <cstring>
#include <string>
#include <unistd.h>
static int prepareLauncherAssets(int argc, char** argv) {
    if (argc != 3 && !(argc == 4 && !strcmp(argv[3], "--download-python"))) { puts("Usage: ccr --prepare <game folder> [--download-python]"); return 1; }
    char* bp = SDL_GetBasePath(); std::string script = std::string(bp ? bp : "./") + "tools/prepare.py"; if (bp) SDL_free(bp);
    if (access(script.c_str(), R_OK) != 0) { printf("Setup script not found: %s\n", script.c_str()); return 1; }
    if (argc == 4) puts("Note: --download-python is only used on Windows; on this system install Python 3 and Pillow with your package manager.");
    for (const char* py : {"python3", "python"}) {
        execlp(py, py, script.c_str(), "--game-files", argv[2], (char*)nullptr);   // only returns when that interpreter is missing
    }
    puts("Python 3 was not found. Install python3 and Pillow (for example: sudo apt install python3 python3-pil, or sudo pacman -S python python-pillow), then run setup again.");
    return 1;
}
