function Get-VerifiedArchive($Name, $File, $Url, $Hash, $Destination) {
    if ($env:CCR_TOOL_ARCHIVES) {
        Write-Host "Using local $Name archive"
        Copy-Item -LiteralPath (Join-Path $env:CCR_TOOL_ARCHIVES $File) -Destination $Destination
    } else {
        Write-Host "Downloading $Name"
        Invoke-WebRequest -UseBasicParsing -Uri $Url -OutFile $Destination
    }
    $stream = [IO.File]::OpenRead($Destination)
    $sha = [Security.Cryptography.SHA256]::Create()
    try { $actual = [BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-', '') }
    finally { $sha.Dispose(); $stream.Dispose() }
    if ($actual -ne $Hash) {
        throw "$Name archive failed its SHA-256 check."
    }
}
