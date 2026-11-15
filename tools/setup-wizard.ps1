# ChuChu Rocket! Re-Nyastered setup wizard.
# Finds your own copies of the game, extracts assets into a local cache (never committed, never shipped) and builds the game.
param([string]$GameFiles = "", [string]$Cache = "")
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Write-Host "ChuChu Rocket! Re-Nyastered setup"
Write-Host "You must own the original game. This project is unofficial and not affiliated with SEGA."
Write-Host ""
if (-not $GameFiles) {
    $guess = Join-Path $root "Original Game Files"
    if (Test-Path $guess) { $GameFiles = $guess }
    else { $GameFiles = Read-Host "Folder containing your iOS (.ipa), Android (.apk), GBA (.gba/.zip) and Dreamcast (.zip) files" }
}
if (-not (Test-Path $GameFiles)) { throw "Game files folder not found: $GameFiles" }
if (-not $Cache) { $Cache = Join-Path $env:APPDATA "ReNyastered" }
New-Item -ItemType Directory -Force $Cache | Out-Null

# Python 3.12 (needed only for extraction)
$py = $null
foreach ($cand in @("py -3.12", "py -3", "python")) {
    try { $v = & cmd /c "$cand --version 2>&1"; if ($v -match "Python 3\.(1[0-9])") { $py = $cand; break } } catch {}
}
if (-not $py) { throw "Python 3.10+ not found. Install it from python.org, then run setup again." }
Write-Host "Using $py"
$pillow = & cmd /c "$py -c ""import PIL"" 2>&1"
if ($LASTEXITCODE -ne 0) { Write-Host "Installing Pillow (image library)..."; & cmd /c "$py -m pip install --user pillow" | Out-Null }

$log = Join-Path $Cache "setup.log"
Write-Host "Extracting assets from your files (this can take several minutes). Log: $log"
& cmd /c "$py ""$root\tools\extract_all.py"" --game-files ""$GameFiles"" --cache ""$Cache"" > ""$log"" 2>&1"
if ($LASTEXITCODE -ne 0) { Get-Content $log -Tail 20; throw "Extraction failed" }
Write-Host "Extraction finished. Manifest: $Cache\manifest.json"

Write-Host "Preparing the portable Zig toolchain and building the game..."
& (Join-Path $root 'build.cmd')
if ($LASTEXITCODE -ne 0) { throw "Build failed" }
Write-Host "Done. Game: $root\build\game\ccr.exe"
