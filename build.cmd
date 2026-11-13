@echo off
rem Configure and build the game with MSVC + Ninja. Usage: build.cmd [target]
setlocal
set "VCVARS=C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
if defined CCR_VCVARS set "VCVARS=%CCR_VCVARS%"
if not exist "%VCVARS%" (
  set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
  for /f "usebackq delims=" %%I in (`"%VSWHERE%" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set "VCVARS=%%I\VC\Auxiliary\Build\vcvars64.bat"
)
if not exist "%VCVARS%" ( echo ERROR: vcvars64.bat not found; install the Visual Studio C++ Build Tools or set CCR_VCVARS & exit /b 1 )
call "%VCVARS%" >nul
cd /d "%~dp0"
cmake -S game -B build\game -G Ninja -DCMAKE_BUILD_TYPE=Release || exit /b 1
cmake --build build\game %* || exit /b 1
