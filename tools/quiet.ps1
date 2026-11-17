# Machine-load guard for timing tests (other projects run on this PC). Run it directly:
#   .\tools\quiet.ps1 -Check                     one sample: prints CPU %, GPU %, and the busiest other process; exit 0 = quiet, 1 = busy
#   .\tools\quiet.ps1 -Wait 300                  wait up to 300 s for a quiet moment (several quiet samples in a row); exit 0 = quiet, 1 = gave up
#   .\tools\quiet.ps1 -Run 'cmd args' [-Wait s] [-Label x]
#                                                wait for quiet (default 300 s, otherwise exit 3 = NOT RUN), run the command while sampling load every
#                                                second, then print CLEAN or TAINTED; the command's output and exit code are passed through
# Thresholds (parameters): CPU above 25 %, GPU above 15 % (during a run only the GPU use of OTHER processes counts, per-process engine counters).
# Our own process names are ignored: ccr, cl, clang, ninja, zig, py, python, powershell, pwsh, bash, conhost, node, claude.
param([switch]$Check, [int]$Wait = 0, [string]$Run = '', [string]$Label = '', [int]$CpuMax = 25, [int]$GpuMax = 15, [int]$QuietSamples = 5)
$ErrorActionPreference = 'SilentlyContinue'
$own = @('ccr', 'cl', 'clang', 'clang++', 'ninja', 'zig', 'py', 'python', 'powershell', 'pwsh', 'bash', 'conhost', 'node', 'claude')

function Get-ForeignGpu {
    $mine = @(Get-Process | Where-Object { $own -contains $_.ProcessName } | ForEach-Object { $_.Id })
    $foreign = 0.0; $who = ''
    foreach ($x in (Get-Counter '\GPU Engine(*)\Utilization Percentage').CounterSamples) {
        if ($x.InstanceName -match 'pid_(\d+)_') {
            $p = [int]$Matches[1]
            if ($mine -notcontains $p -and $x.CookedValue -gt $foreign) { $foreign = [math]::Round($x.CookedValue, 1); $who = (Get-Process -Id $p).ProcessName }
        }
    }
    [pscustomobject]@{ Gpu = $foreign; Who = $who }
}

function Get-Load {
    $cpu = [math]::Round((Get-Counter '\Processor(_Total)\% Processor Time' -SampleInterval 1).CounterSamples[0].CookedValue, 1)
    $g = Get-ForeignGpu
    $busy = $null
    if ($cpu -gt $CpuMax) {
        $a = @{}; Get-Process | ForEach-Object { $a[$_.Id] = $_.CPU }
        Start-Sleep -Milliseconds 700
        $bd = 0
        Get-Process | Where-Object { $own -notcontains $_.ProcessName } | ForEach-Object { if ($a.ContainsKey($_.Id)) { $d = $_.CPU - $a[$_.Id]; if ($d -gt $bd) { $bd = $d; $busy = $_.ProcessName } } }
    }
    if ($g.Gpu -gt $GpuMax -and -not $busy) { $busy = $g.Who }
    [pscustomobject]@{ Cpu = $cpu; Gpu = $g.Gpu; Busy = $busy; Quiet = ($cpu -le $CpuMax -and $g.Gpu -le $GpuMax) }
}

function Wait-Quiet([int]$seconds) {
    $deadline = (Get-Date).AddSeconds($seconds); $streak = 0
    while ($true) {
        $l = Get-Load
        if ($l.Quiet) { $streak++ } else { $streak = 0; Write-Output ("waiting: cpu {0} %  other-process gpu {1} %  busiest {2}" -f $l.Cpu, $l.Gpu, $l.Busy) }
        if ($streak -ge $QuietSamples) { return $true }
        if ((Get-Date) -gt $deadline) { return $false }
    }
}

if ($Check) {
    $l = Get-Load
    Write-Output ("cpu {0} %  other-process gpu {1} %  {2}{3}" -f $l.Cpu, $l.Gpu, $(if ($l.Quiet) { 'QUIET' } else { 'BUSY' }), $(if ($l.Busy) { "  (busiest: $($l.Busy))" } else { '' }))
    exit $(if ($l.Quiet) { 0 } else { 1 })
}

if ($Wait -gt 0 -and -not $Run) { if (Wait-Quiet $Wait) { Write-Output 'quiet'; exit 0 } else { Write-Output 'gave up: machine stayed busy'; exit 1 } }

if ($Run) {
    $timeout = if ($Wait -gt 0) { $Wait } else { 300 }
    if (-not (Wait-Quiet $timeout)) { Write-Output "NOT RUN: machine stayed busy for $timeout s ($Label)"; exit 3 }
    $job = Start-Job -ScriptBlock {
        param($own)
        while ($true) {
            $c = [math]::Round((Get-Counter '\Processor(_Total)\% Processor Time' -SampleInterval 1).CounterSamples[0].CookedValue, 1)
            $mine = @(Get-Process | Where-Object { $own -contains $_.ProcessName } | ForEach-Object { $_.Id })
            $foreign = 0.0; $who = '-'
            foreach ($x in (Get-Counter '\GPU Engine(*)\Utilization Percentage').CounterSamples) {
                if ($x.InstanceName -match 'pid_(\d+)_') { $p = [int]$Matches[1]; if ($mine -notcontains $p -and $x.CookedValue -gt $foreign) { $foreign = [math]::Round($x.CookedValue, 1); $who = (Get-Process -Id $p).ProcessName } }
            }
            "$c $foreign $who"
        }
    } -ArgumentList (, $own)
    $t0 = Get-Date
    $out = Invoke-Expression $Run
    $code = $LASTEXITCODE
    $elapsed = ((Get-Date) - $t0).TotalSeconds
    $rows = Receive-Job $job; Stop-Job $job; Remove-Job $job
    $out
    $peakCpu = 0; $peakForeign = 0; $who = '-'
    foreach ($r in $rows) { $p = $r -split ' '; if ([double]$p[0] -gt $peakCpu) { $peakCpu = [double]$p[0] }; if ([double]$p[1] -gt $peakForeign) { $peakForeign = [double]$p[1]; $who = $p[2] } }
    $after = Get-Load
    Write-Output ("load during run {0:N0} s: peak total cpu {1} %, peak GPU use by other processes {2} % ({3}); after the run: cpu {4} %  other gpu {5} %" -f $elapsed, $peakCpu, $peakForeign, $who, $after.Cpu, $after.Gpu)
    if (@($rows).Count -eq 0) { Write-Output 'TAINTED (no load samples); repeat this measurement' }
    elseif ($peakForeign -gt $GpuMax) { Write-Output "TAINTED (another process used the GPU during the run: $who $peakForeign %); repeat this measurement" }
    elseif ($after.Busy) { Write-Output "TAINTED (another process was busy right after the run: $($after.Busy)); repeat this measurement" }
    else { Write-Output 'CLEAN (quiet before, no other GPU use during, quiet after)' }
    exit $code
}
Write-Output 'usage: quiet.ps1 -Check | -Wait <s> | -Run "<command>" [-Wait <s>] [-Label <name>]'
