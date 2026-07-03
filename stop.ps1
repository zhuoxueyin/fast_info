# fastInfo - one-click stop
# Usage:
#     .\stop.ps1                    # stop all (asks for confirmation)
#     .\stop.ps1 -Force             # stop all without confirmation
#     .\stop.ps1 -Only backend      # stop only backend
#     .\stop.ps1 -Only backend,frontend
[CmdletBinding()]
param(
    [switch]$Force = $false,
    [string[]]$Only = @()
)

$root = $PSScriptRoot
$pidFile = Join-Path $root 'data\running.pids'

function Step($n, $msg)  { Write-Host ('[{0}] ' -f $n) -NoNewline -ForegroundColor Cyan; Write-Host $msg }
function Ok($msg)        { Write-Host ('    [OK]  ' + $msg) -ForegroundColor Green }
function Info($msg)      { Write-Host ('    [..]  ' + $msg) -ForegroundColor Gray }
function Warn($msg)      { Write-Host ('    [!!]  ' + $msg) -ForegroundColor Yellow }

function ShouldStop([string]$svc) {
    if ($script:Only.Count -eq 0) { return $true }
    return $script:Only -contains $svc
}

function Kill-Tree {
    param([int]$ProcId)
    try {
        Start-Process -FilePath 'taskkill.exe' -ArgumentList @('/PID', $ProcId, '/T', '/F') -NoNewWindow -Wait -ErrorAction SilentlyContinue | Out-Null
    } catch { }
}

Step '1' 'Scanning fastInfo processes...'

$servicePatterns = @(
    @{ name = 'backend';   patterns = @('*api_server.py*') },
    @{ name = 'ingest';    patterns = @('*ingest_daemon.py*') },
    @{ name = 'scheduler'; patterns = @('*subs_scheduler.py*') },
    @{ name = 'frontend';  patterns = @('*frontend*vite*', '*frontend*node_modules*', '*fast_info*frontend*') },
    @{ name = 'docs';      patterns = @('*docs-site*vite*', '*docs-site*node_modules*', '*fast_info*docs-site*') }
)

$found = @()

foreach ($p in (Get-Process python, node, powershell -ErrorAction SilentlyContinue)) {
    $cmd = $p.CommandLine
    if (-not $cmd) { continue }
    foreach ($svc in $servicePatterns) {
        if (-not (ShouldStop $svc.name)) { continue }
        foreach ($pat in $svc.patterns) {
            if ($cmd -like $pat) {
                $found += [PSCustomObject]@{
                    name = $svc.name
                    pid  = $p.Id
                    exe  = $p.ProcessName
                    cmd  = if ($cmd.Length -gt 80) { $cmd.Substring(0, 80) + '...' } else { $cmd }
                }
                break
            }
        }
    }
}

if (Test-Path $pidFile) {
    try {
        $saved = Get-Content $pidFile -Raw | ConvertFrom-Json -ErrorAction Stop
        if ($saved -isnot [array]) { $saved = @($saved) }
        foreach ($s in $saved) {
            if (-not (ShouldStop $s.name)) { continue }
            $proc = Get-Process -Id $s.pid -ErrorAction SilentlyContinue
            if ($proc -and -not ($found | Where-Object { $_.pid -eq $s.pid })) {
                $found += [PSCustomObject]@{
                    name = $s.name
                    pid  = $s.pid
                    exe  = $proc.ProcessName
                    cmd  = '(from running.pids)'
                }
            }
        }
    } catch { }
}

$found = $found | Sort-Object pid -Unique

if (-not $found) {
    Warn 'No fastInfo process found.'
    if ((Test-Path $pidFile) -and $Only.Count -eq 0) {
        Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
        Info 'cleaned stale running.pids'
    }
    exit 0
}

Write-Host ''
$found | Format-Table -AutoSize -Property `
    @{N='PID'; E={$_.pid}; Align='right'}, `
    @{N='Service'; E={$_.name}}, `
    @{N='Exe'; E={$_.exe}}, `
    @{N='Command'; E={$_.cmd}} | Out-Host
Write-Host ''

if (-not $Force) {
    $ans = Read-Host 'Confirm kill? (y/N)'
    if ($ans -ne 'y' -and $ans -ne 'Y') {
        Info 'Cancelled'
        exit 0
    }
}

Step '2' 'Killing process trees...'

$killOrder = @('ingest', 'scheduler', 'backend', 'frontend', 'docs')
foreach ($svcName in $killOrder) {
    if (-not (ShouldStop $svcName)) { continue }
    $items = $found | Where-Object { $_.name -eq $svcName }
    foreach ($it in $items) {
        try {
            $proc = Get-Process -Id $it.pid -ErrorAction SilentlyContinue
            if ($proc) {
                Kill-Tree $it.pid
                Start-Sleep -Milliseconds 300
                $check = Get-Process -Id $it.pid -ErrorAction SilentlyContinue
                if ($check) { Stop-Process -Id $it.pid -Force -ErrorAction SilentlyContinue }
                Ok ('killed ' + $svcName + ' tree (PID ' + $it.pid + ', ' + $it.exe + ')')
            } else {
                Info ($svcName + ' (PID ' + $it.pid + ') already gone')
            }
        } catch {
            Warn ($svcName + ' (PID ' + $it.pid + '): ' + $_.Exception.Message)
        }
    }
}

Start-Sleep -Seconds 1

$remaining = @()
foreach ($p in (Get-Process python, node, powershell -ErrorAction SilentlyContinue)) {
    $cmd = $p.CommandLine
    if (-not $cmd) { continue }
    foreach ($svc in $servicePatterns) {
        if (-not (ShouldStop $svc.name)) { continue }
        foreach ($pat in $svc.patterns) {
            if ($cmd -like $pat) {
                $remaining += [PSCustomObject]@{ name = $svc.name; pid = $p.Id }
                break
            }
        }
    }
}
if ($remaining) {
    Warn ('Still ' + $remaining.Count + ' process(es) alive, force-killing...')
    foreach ($r in $remaining) {
        try { Stop-Process -Id $r.pid -Force -ErrorAction SilentlyContinue } catch { }
    }
}

if ($Only.Count -eq 0) {
    if (Test-Path $pidFile) { Remove-Item $pidFile -Force -ErrorAction SilentlyContinue }
    Ok 'cleaned running.pids'
} else {
    if (Test-Path $pidFile) {
        try {
            $saved = Get-Content $pidFile -Raw | ConvertFrom-Json -ErrorAction Stop
            if ($saved -isnot [array]) { $saved = @($saved) }
            $saved = $saved | Where-Object { $Only -notcontains $_.name }
            $saved | ConvertTo-Json -Depth 3 | Out-File $pidFile -Encoding utf8
            Ok ('updated running.pids, kept ' + $saved.Count + ' service(s)')
        } catch { }
    }
}

Write-Host ''
Ok 'All done.'
