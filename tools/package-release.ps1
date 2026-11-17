# Builds the game and packs a Windows release zip: ccr.exe, recomplauncher.json at the top (for RecompLauncher), and the extraction tools
# that tools\prepare.ps1 needs. Never includes game files, extracted assets or keys. Output: dist\ChuChuRocketReNyastered-<version>-windows-x64.zip
# usage: tools\package-release.ps1 -Version 0.1.0 [-SkipBuild]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^v?\d+\.\d+\.\d+(?:-[A-Za-z0-9]+(?:[.-][A-Za-z0-9]+)*)?$')]
    [string]$Version,
    [switch]$SkipBuild
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
if (-not $SkipBuild) {
    & (Join-Path $root 'build.cmd') --target ccr
    if ($LASTEXITCODE -ne 0) { throw "Build failed" }
}
$exe = Join-Path $root 'build\game\ccr.exe'
if (-not (Test-Path -LiteralPath $exe)) { throw "ccr.exe not found: build first" }
$name = "ChuChuRocketReNyastered-$Version-windows-x64"
$dist = Join-Path $root 'dist'
$temp = Join-Path $dist ([guid]::NewGuid().ToString('N'))
$stage = Join-Path $temp 'release'
$zip = Join-Path $dist "$name.zip"
$deps = Join-Path $root 'build/game-zig/_deps'

New-Item -ItemType Directory -Force -Path (Join-Path $stage 'tools'), (Join-Path $stage 'licenses') | Out-Null
try {
    Copy-Item -LiteralPath $exe, (Join-Path $root 'recomplauncher.json'), (Join-Path $root 'README.md') -Destination $stage
    Copy-Item -LiteralPath (Join-Path $deps 'sdl2-src/LICENSE.txt') -Destination (Join-Path $stage 'licenses/SDL2.txt')
    $vorbis = Get-Content -LiteralPath (Join-Path $deps 'stbvorbis-src/stb_vorbis.c') -Raw
    $license = [regex]::Match($vorbis, '(?s)ALTERNATIVE A - MIT License.*?(?=\r?\n-+\r?\nALTERNATIVE B)')
    if (-not $license.Success) { throw 'stb_vorbis MIT license text was not found' }
    Set-Content -LiteralPath (Join-Path $stage 'licenses/stb_vorbis.txt') -Value $license.Value -Encoding utf8

    $extractors = @(
        'bhunpack', 'dc_models', 'dc_objects', 'export_android_ui', 'export_battle',
        'export_dc_solutions', 'export_dc_ui', 'export_dlc_stages', 'export_hd_geometry',
        'export_hd_images', 'export_hd_locale', 'export_pad_ui', 'export_sprites',
        'export_strings', 'export_testdata', 'export_tilemaps', 'extract_all',
        'extract_android', 'extract_ios_locale', 'extract_packs', 'gba_stages', 'gdi_extract',
        'macho', 'prs', 'pvr2png', 'stage_registry', 'textures', 'thin'
    )
    $tools = @('prepare.ps1', 'setup-python.ps1', 'windows-download.ps1', 'hd_image_ids.txt')
    $tools += $extractors | ForEach-Object { "$_.py" }
    foreach ($file in $tools) {
        Copy-Item -LiteralPath (Join-Path $PSScriptRoot $file) -Destination (Join-Path $stage 'tools')
    }
    $pendingZip = Join-Path $temp "$name.zip"
    Compress-Archive -Path (Join-Path $stage '*') -DestinationPath $pendingZip
    Move-Item -LiteralPath $pendingZip -Destination $zip -Force
} finally {
    $resolved = (Resolve-Path -LiteralPath $temp).ProviderPath
    if ((Split-Path -Parent $resolved) -eq (Resolve-Path -LiteralPath $dist).ProviderPath) {
        Remove-Item -LiteralPath $resolved -Recurse -Force
    }
}
Write-Output "Wrote $zip"
