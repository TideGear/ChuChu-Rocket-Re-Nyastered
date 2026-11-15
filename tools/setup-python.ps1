Import-Module Microsoft.PowerShell.Utility, Microsoft.PowerShell.Archive
. (Join-Path $PSScriptRoot 'windows-download.ps1')

function Get-SetupPython($Tools) {
    $probe = 'import sys; from PIL import Image; assert sys.version_info >= (3, 10); Image.new(chr(76), (1, 1))'
    foreach ($candidate in @(@('py.exe', '-3.12'), @('py.exe', '-3'), @('python.exe'))) {
        $commands = Get-Command $candidate[0] -CommandType Application -All -ErrorAction SilentlyContinue
        $prefix = @($candidate | Select-Object -Skip 1)
        foreach ($command in $commands) {
            try {
                & $command.Source @prefix -c $probe 2>$null
                if ($LASTEXITCODE -eq 0) { return @{ Exe = $command.Source; Prefix = $prefix } }
            } catch { continue }
        }
    }

    $destination = Join-Path $Tools 'python-3.12.10-pillow-12.2.0'
    $python = Join-Path $destination 'python.exe'
    if (Test-Path -LiteralPath $python -PathType Leaf) {
        & $python -c $probe
        if ($LASTEXITCODE -ne 0) { throw "Could not start the cached extraction runtime at $destination." }
        return @{ Exe = $python; Prefix = @() }
    }

    $staging = Join-Path $Tools ([guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Force -Path $staging | Out-Null
    try {
        $pythonZip = Join-Path $staging 'python.zip'
        Get-VerifiedArchive 'Python 3.12.10' 'python-3.12.10-embed-amd64.zip' `
            'https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip' `
            '4acbed6dd1c744b0376e3b1cf57ce906f9dc9e95e68824584c8099a63025a3c3' $pythonZip
        $pillowZip = Join-Path $staging 'pillow.zip'
        Get-VerifiedArchive 'Pillow 12.2.0' 'pillow-12.2.0-cp312-cp312-win_amd64.whl' `
            'https://files.pythonhosted.org/packages/5d/7b/25a221d2c761c6a8ae21bfa3874988ff2583e19cf8a27bf2fee358df7942/pillow-12.2.0-cp312-cp312-win_amd64.whl' `
            '7f84204dee22a783350679a0333981df803dac21a0190d706a50475e361c93f5' $pillowZip
        $runtime = Join-Path $staging 'runtime'
        Expand-Archive -LiteralPath $pythonZip -DestinationPath $runtime
        Expand-Archive -LiteralPath $pillowZip -DestinationPath (Join-Path $runtime 'packages')
        $paths = Join-Path $runtime 'python312._pth'
        Add-Content -LiteralPath $paths -Value 'packages'
        Add-Content -LiteralPath $paths -Value '..\..\..\..\tools'
        & (Join-Path $runtime 'python.exe') -c $probe
        if ($LASTEXITCODE -ne 0) { throw 'The private Python and Pillow runtime could not start.' }
        try { [IO.Directory]::Move($runtime, $destination) }
        catch { if (!(Test-Path -LiteralPath $python -PathType Leaf)) { throw } }
        return @{ Exe = $python; Prefix = @() }
    } finally {
        $resolved = (Resolve-Path -LiteralPath $staging).ProviderPath
        if ((Split-Path -Parent $resolved) -eq (Resolve-Path -LiteralPath $Tools).ProviderPath) {
            Remove-Item -LiteralPath $resolved -Recurse -Force
        }
    }
}
