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
    else { $GameFiles = Read-Host "Folder containing any of your original game files (loose or ZIP)" }
}
if (-not (Test-Path $GameFiles)) { throw "Game files folder not found: $GameFiles" }
if (-not $Cache) {
    $Cache = Join-Path $env:APPDATA "ChuChuRocketReNyastered"
    $old = Join-Path $env:APPDATA "ReNyastered"   # the folder name used before the rename: move it once if the new one does not exist
    if (-not (Test-Path -LiteralPath $Cache) -and (Test-Path -LiteralPath $old)) { Move-Item -LiteralPath $old -Destination $Cache }
}
New-Item -ItemType Directory -Force $Cache | Out-Null

. (Join-Path $PSScriptRoot 'setup-python.ps1')
$python = Get-SetupPython (Join-Path $root 'local/tools/windows')
$prefix = $python.Prefix
Write-Host "Using $($python.Exe)"

$log = Join-Path $Cache "setup.log"
Write-Host "Extracting assets from your files (this can take several minutes). Log: $log"
& {
    $ErrorActionPreference = 'Continue'
    & $python.Exe @prefix (Join-Path $PSScriptRoot 'extract_all.py') --game-files $GameFiles --cache $Cache *> $log
}
if ($LASTEXITCODE -ne 0) { Get-Content $log -Tail 20; throw "Extraction failed" }
Write-Host "Extraction finished. Manifest: $Cache\manifest.json"
$manifest = Get-Content (Join-Path $Cache 'manifest.json') -Raw | ConvertFrom-Json
foreach ($gameInput in $manifest.inputs) {
    if ($gameInput.error) { Write-Host ("Input could not be used: " + $gameInput.file + " - " + $gameInput.error) }
}
if ($manifest.playable_modes) {
    Write-Host "Playable modes in this cache: $($manifest.playable_modes -join ', ')"
} elseif (!$manifest.base_graphics_available) {
    Write-Host "No playable graphics were found. Check for a supported Dreamcast GDI/numbered BIN-CUE image or add a supported iOS/Android release."
    throw "Setup cannot finish without playable modes."
} else {
    Write-Host "No playable stage data was found. Add a supported Dreamcast GDI/numbered BIN-CUE image or compatible mobile graphics and stage data. See the extraction log for input errors."
    throw "Setup cannot finish without playable modes."
}

Write-Host "Preparing the portable Zig toolchain and building the game..."
& (Join-Path $root 'build.cmd')
if ($LASTEXITCODE -ne 0) { throw "Build failed" }
Write-Host "Done. Game: $root\build\game\ccr.exe"
