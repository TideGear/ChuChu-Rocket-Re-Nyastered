$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
Import-Module Microsoft.PowerShell.Utility, Microsoft.PowerShell.Archive
. (Join-Path $PSScriptRoot 'windows-download.ps1')
$root = Split-Path -Parent $PSScriptRoot
$tools = Join-Path $root 'local/tools/windows'
if ($env:CCR_TOOL_ARCHIVES) {
    $env:CCR_TOOL_ARCHIVES = (Resolve-Path -LiteralPath $env:CCR_TOOL_ARCHIVES).ProviderPath.Replace('\', '/')
}
New-Item -ItemType Directory -Force -Path $tools | Out-Null

function Get-BuildTool($Name, $Version, $Url, $Hash, $Executable) {
    $destination = Join-Path $tools "$Name-$Version"
    $program = Join-Path $destination $Executable
    if (Test-Path -LiteralPath $program -PathType Leaf) { return $program }

    $staging = Join-Path $tools ([guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $staging | Out-Null
    try {
        $archive = Join-Path $staging "$Name.zip"
        Get-VerifiedArchive "$Name $Version" "$Name.zip" $Url $Hash $archive
        $unpacked = Join-Path $staging 'unpacked'
        Expand-Archive -LiteralPath $archive -DestinationPath $unpacked
        if (-not (Test-Path -LiteralPath (Join-Path $unpacked $Executable) -PathType Leaf)) {
            throw "$Name $Version archive is missing $Executable."
        }
        try { [IO.Directory]::Move($unpacked, $destination) }
        catch { if (-not (Test-Path -LiteralPath $program -PathType Leaf)) { throw } }
    } finally {
        $resolved = (Resolve-Path -LiteralPath $staging).ProviderPath
        $toolRoot = (Resolve-Path -LiteralPath $tools).ProviderPath
        if ((Split-Path -Parent $resolved) -eq $toolRoot) {
            Remove-Item -LiteralPath $resolved -Recurse -Force
        }
    }
    return $program
}

# Use the same pinned portable releases as the F-117A Recomp setup.
$zig = Get-BuildTool 'zig' '0.14.1' `
    'https://ziglang.org/download/0.14.1/zig-x86_64-windows-0.14.1.zip' `
    '554f5378228923ffd558eac35e21af020c73789d87afeabf4bfd16f2e6feed2c' 'zig-x86_64-windows-0.14.1/zig.exe'
$cmake = Get-BuildTool 'cmake' '4.0.3' `
    'https://github.com/Kitware/CMake/releases/download/v4.0.3/cmake-4.0.3-windows-x86_64.zip' `
    'b59a31dfbfa376a4aaea9ff560ff2b29f78ee5f9fb15447fc71ae7bf9fea9379' 'cmake-4.0.3-windows-x86_64/bin/cmake.exe'
$ninja = Get-BuildTool 'ninja' '1.12.1' `
    'https://github.com/ninja-build/ninja/releases/download/v1.12.1/ninja-win.zip' `
    'f550fec705b6d6ff58f2db3c374c2277a37691678d6aba463adcbb129108467a' 'ninja.exe'

# CMake caches the compiler, so use a separate build tree from existing MSVC builds.
$build = Join-Path $root 'build/game-zig'
$env:ZIG_GLOBAL_CACHE_DIR = Join-Path $tools 'zig-cache'
$env:ZIG_LOCAL_CACHE_DIR = Join-Path $build 'zig-cache'
$toolchain = Join-Path $PSScriptRoot 'cmake/zig-windows.cmake'
$output = Join-Path $root 'build/game'
& $cmake -S (Join-Path $root 'game') -B $build -G Ninja "-DCMAKE_MAKE_PROGRAM=$ninja" `
    "-DCMAKE_TOOLCHAIN_FILE=$toolchain" "-DCCR_ZIG_EXECUTABLE=$zig" "-DCMAKE_RUNTIME_OUTPUT_DIRECTORY=$output" `
    '-DCMAKE_BUILD_TYPE=Release'
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $cmake --build $build @args
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# Keep the development asset cache in step with the game it was just built for, so a build never runs on stale art
# (the game shows "Game art out of date" otherwise). The version the game needs is kDcAssetsVersion in game/app/main.cpp;
# extract_all.py writes the cache's version to assets/ret_all/dc_assets_version.txt. Set CCR_SKIP_ASSET_REFRESH=1 to skip.
$cache = Join-Path $root 'local/cache'
$have = Join-Path $cache 'assets/ret_all/dc_assets_version.txt'
if (-not $env:CCR_SKIP_ASSET_REFRESH -and (Test-Path -LiteralPath $have)) {
    $need = [int]([regex]::Match((Get-Content -Raw (Join-Path $root 'game/app/main.cpp')), 'kDcAssetsVersion = (\d+)').Groups[1].Value)
    $current = [int]((Get-Content -Raw -LiteralPath $have).Trim())
    if ($current -lt $need) {
        $gameFiles = Join-Path $root 'Original Game Files'
        $manifestPath = Join-Path $cache 'manifest.json'
        if (Test-Path -LiteralPath $manifestPath) { $m = Get-Content -Raw -LiteralPath $manifestPath | ConvertFrom-Json; if ($m.game_files -and (Test-Path -LiteralPath $m.game_files)) { $gameFiles = $m.game_files } }
        Write-Output "Dev asset cache is version $current, the game needs ${need}: re-extracting from $gameFiles (a few minutes; saves and settings are kept)"
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'prepare.ps1') -GameFiles $gameFiles -Cache $cache
        if ($LASTEXITCODE -ne 0) { Write-Output 'Asset refresh failed: see local/cache/setup.log'; exit $LASTEXITCODE }
    }
}
exit 0
