#pragma once
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <shellapi.h>

static int prepareLauncherAssets() {
    int count = 0;
    std::unique_ptr<wchar_t*, decltype(&LocalFree)> args(
        CommandLineToArgvW(GetCommandLineW(), &count), LocalFree);
    if (!args || (count != 3 && count != 4) ||
        (count == 4 && wcscmp(args.get()[3], L"--download-python") != 0)) {
        puts("Usage: ccr --prepare <game folder> [--download-python]");
        return 1;
    }

    // Forward the user path as data, outside PowerShell's command line.
    if (!SetEnvironmentVariableW(L"CCR_SETUP_GAME_FILES", args.get()[2])) return 1;
    wchar_t system[MAX_PATH];
    UINT length = GetSystemDirectoryW(system, MAX_PATH);
    if (!length || length >= MAX_PATH) return 1;
    std::wstring powershell = std::wstring(system) + L"\\WindowsPowerShell\\v1.0\\powershell.exe";
    std::unique_ptr<char, decltype(&SDL_free)> base(SDL_GetBasePath(), SDL_free);
    if (!base) return 1;
    auto directory = std::filesystem::u8path(base.get());
    auto script = directory / L"tools" / L"prepare.ps1";
    if (!std::filesystem::is_regular_file(script))
        script = (directory / L".." / L".." / L"tools" / L"prepare.ps1").lexically_normal();
    if (!std::filesystem::is_regular_file(script)) {
        printf("Setup script not found beside the game or in the source checkout: %ls\n", script.c_str());
        return 1;
    }
    std::wstring command = L"\"" + powershell + L"\" -NoProfile -NonInteractive "
                           L"-ExecutionPolicy Bypass -File \"" + script.wstring() + L"\"";
    if (count == 4) command += L" -DownloadPython";
    STARTUPINFOW startup{};
    startup.cb = sizeof(startup);
    startup.dwFlags = STARTF_USESTDHANDLES;
    startup.hStdInput = GetStdHandle(STD_INPUT_HANDLE);
    startup.hStdOutput = GetStdHandle(STD_OUTPUT_HANDLE);
    startup.hStdError = GetStdHandle(STD_ERROR_HANDLE);
    PROCESS_INFORMATION child{};
    if (!CreateProcessW(powershell.c_str(), command.data(), nullptr, nullptr, TRUE,
                        CREATE_NO_WINDOW, nullptr, directory.c_str(), &startup, &child)) {
        printf("Could not start Windows PowerShell (error %lu).\n", GetLastError());
        return 1;
    }
    CloseHandle(child.hThread);
    DWORD status = 1;
    if (WaitForSingleObject(child.hProcess, INFINITE) == WAIT_OBJECT_0)
        GetExitCodeProcess(child.hProcess, &status);
    CloseHandle(child.hProcess);
    return static_cast<int>(status);
}
