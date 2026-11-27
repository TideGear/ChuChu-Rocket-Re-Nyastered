# Windowless asset extraction for launchers (RecompLauncher "prepare" step): extracts assets from YOUR original game files into the cache.
# Same extraction as setup.cmd (tools\extract_all.py), without the questions and without building the game. Never changes your original files.
# usage: prepare.ps1 -GameFiles <folder, ZIP archive, disc descriptor, or one file inside a folder> [-Cache <folder>] [-DownloadPython]
# Prints "progress <0..1> <text>" lines; exits 0 when the cache holds playable stage data, 1 otherwise.
param([string]$GameFiles = $env:CCR_SETUP_GAME_FILES, [string]$Cache = "", [switch]$DownloadPython)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$staging = $null
$lock = $null
$published = $false
try {
    if (-not $GameFiles -or -not (Test-Path -LiteralPath $GameFiles)) { Write-Output "Your game folder, disc image or ZIP archive was not found: $GameFiles"; exit 1 }
    $resolvedGameFiles = (Resolve-Path -LiteralPath $GameFiles).ProviderPath
    if (Test-Path -LiteralPath $resolvedGameFiles -PathType Leaf) {
        if ([IO.Path]::GetExtension($resolvedGameFiles).ToLowerInvariant() -notin @('.gdi', '.cue', '.chd', '.zip')) { $GameFiles = Split-Path -Parent $resolvedGameFiles }
        else { $GameFiles = $resolvedGameFiles }
    } else { $GameFiles = $resolvedGameFiles }
    if (-not $Cache) {
        $Cache = Join-Path $env:APPDATA "ChuChuRocketReNyastered"
    $old = Join-Path $env:APPDATA "ReNyastered"   # the folder name used before the rename: move it once if the new one does not exist
    if (-not (Test-Path -LiteralPath $Cache) -and (Test-Path -LiteralPath $old)) { Move-Item -LiteralPath $old -Destination $Cache }
    }
    [IO.Directory]::CreateDirectory($Cache) | Out-Null
    $Cache = (Resolve-Path -LiteralPath $Cache).ProviderPath
    $lock = [IO.File]::Open((Join-Path $Cache 'prepare.lock'), 'OpenOrCreate', 'Write', 'None')
    Write-Output "progress 0.02 Looking for Python"
    . (Join-Path $PSScriptRoot 'setup-python.ps1')
    $python = Get-SetupPython (Join-Path $root 'local/tools/windows') -NoDownload:(-not $DownloadPython)
    $prefix = $python.Prefix
    Write-Output "progress 0.15 Extracting from your game files (this can take several minutes)"
    $staging = Join-Path $Cache ("prepare-" + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $staging | Out-Null
    $log = Join-Path $Cache "setup.log"
    & {
        $ErrorActionPreference = 'Continue'
        & $python.Exe @prefix (Join-Path $PSScriptRoot 'extract_all.py') --game-files $GameFiles --cache $staging --exclude-cache $Cache *> $log
    }
    if ($LASTEXITCODE -ne 0) { Write-Output "Extraction failed. See $log"; Get-Content $log -Tail 10; exit 1 }
    Write-Output "progress 0.95 Checking what can be played"
    $newManifest = Join-Path $staging 'manifest.json'
    $manifest = Get-Content -LiteralPath $newManifest -Raw | ConvertFrom-Json
    foreach ($gameInput in $manifest.inputs) {
        if ($gameInput.error) { Write-Output ("Input could not be used: " + $gameInput.file + " - " + $gameInput.error) }
    }
    if (-not $manifest.playable_modes) {
        if (-not $manifest.base_graphics_available) { Write-Output "No playable graphics were found. Check for a supported Dreamcast GDI/numbered BIN-CUE image or add a supported iOS/Android release." }
        else { Write-Output "No playable stage data was found. See $log" }
        exit 1
    }
    $assets = Join-Path $Cache 'assets'
    $newAssets = Join-Path $staging 'assets'
    $oldAssets = Join-Path $staging 'previous-assets'
    $oldExists = [IO.Directory]::Exists($assets)
    if ($oldExists) {
        foreach ($name in 'progress.bin', 'challenge.bin', 'options.bin', 'settings.ini', 'controls.ini') {
            $save = Join-Path $assets $name
            if (Test-Path -LiteralPath $save -PathType Leaf) { Copy-Item -LiteralPath $save -Destination $newAssets }
        }
        foreach ($dir in 'imports', 'logs') { $keep = Join-Path $assets $dir; if (Test-Path -LiteralPath $keep -PathType Container) { Copy-Item -LiteralPath $keep -Destination $newAssets -Recurse } }   # player data kept across re-runs
        [IO.Directory]::Move($assets, $oldAssets)
    }
    try {
        [IO.Directory]::Move($newAssets, $assets)
        $destination = Join-Path $Cache 'manifest.json'
        if ([IO.File]::Exists($destination)) { [IO.File]::Replace($newManifest, $destination, [NullString]::Value) }
        else { [IO.File]::Move($newManifest, $destination) }
        $published = $true
    } catch {
        if ([IO.Directory]::Exists($assets)) { [IO.Directory]::Move($assets, $newAssets) }
        if ($oldExists) { [IO.Directory]::Move($oldAssets, $assets) }
        throw
    }
    Write-Output "Playable modes: $($manifest.playable_modes -join ', ')"
    Write-Output "progress 1 Done"
    exit 0
} catch {
    Write-Output "Setup failed: $($_.Exception.Message)"
    exit 1
} finally {
    if ($staging -and (Test-Path -LiteralPath $staging)) {
        $resolved = (Resolve-Path -LiteralPath $staging).ProviderPath
        $recoverable = -not $published -and (Test-Path -LiteralPath (Join-Path $staging 'previous-assets'))
        if (-not $recoverable -and (Split-Path -Parent $resolved) -eq $Cache) {
            Remove-Item -LiteralPath $resolved -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
    if ($lock) { $lock.Dispose() }
}
