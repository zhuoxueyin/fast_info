# fastInfo - status check
# Usage:
#     .\status.ps1                  # show all services status + health
#     .\status.ps1 -Logs            # also show last 5 lines of each log
[CmdletBinding()]
param(
    [switch]$Logs = $false
)

$root = $PSScriptRoot
Set-Location $root
$pidFile = Join-Path $root 'data\running.pids'
$dataDir = Join-Path $root 'data'

$env:HTTP_PROXY = ''
$env:HTTPS_PROXY = ''
$env:ALL_PROXY = ''

function Write-Status($name, $ok, $detail) {
    if ($ok) {
        Write-Host '    [UP]   ' -NoNewline -ForegroundColor Green
    } else {
        Write-Host '    [DOWN] ' -NoNewline -ForegroundColor Red
    }
    Write-Host ('{0,-15} ' -f $name) -NoNewline
    Write-Host $detail -ForegroundColor $(if ($ok) { 'Gray' } else { 'DarkGray' })
}

Write-Host ''
Write-Host '=== fastInfo Service Status ===' -ForegroundColor Cyan
Write-Host ''

$serviceDefs = @(
    @{ name = 'backend';   port = 8000; url = 'http://127.0.0.1:8000/healthz' },
    @{ name = 'frontend';  port = 5173; url = 'http://127.0.0.1:5173/' },
    @{ name = 'docs';      port = 5174; url = 'http://127.0.0.1:5174/' },
    @{ name = 'ingest';    port = 0;    url = $null },
    @{ name = 'scheduler'; port = 0;    url = $null }
)

$saved = @()
if (Test-Path $pidFile) {
    try {
        $saved = Get-Content $pidFile -Raw | ConvertFrom-Json -ErrorAction Stop
        if ($saved -isnot [array]) { $saved = @($saved) }
    } catch { }
}

$servicePatterns = @(
    @{ name = 'backend';   patterns = @('*api_server.py*') },
    @{ name = 'ingest';    patterns = @('*ingest_daemon.py*') },
    @{ name = 'scheduler'; patterns = @('*subs_scheduler.py*') },
    @{ name = 'frontend';  patterns = @('*fast_info*frontend*', '*frontend*vite*', '*frontend*node_modules*') },
    @{ name = 'docs';      patterns = @('*fast_info*docs-site*', '*docs-site*vite*', '*docs-site*node_modules*') }
)

$running = @{}

# Method 1: Get-Process with CommandLine
foreach ($p in (Get-Process python, node, powershell -ErrorAction SilentlyContinue)) {
    $cmd = $p.CommandLine
    if (-not $cmd) { continue }
    foreach ($svc in $servicePatterns) {
        foreach ($pat in $svc.patterns) {
            if ($cmd -like $pat) {
                if (-not $running[$svc.name]) { $running[$svc.name] = @() }
                if ($running[$svc.name] -notcontains $p.Id) {
                    $running[$svc.name] += $p.Id
                }
                break
            }
        }
    }
}

# Method 2: CIM fallback (in case CommandLine is not accessible via Get-Process)
try {
    $cimProcs = Get-CimInstance Win32_Process -ErrorAction Stop | Where-Object {
        $_.Name -in @('python.exe', 'node.exe', 'powershell.exe')
    }
    foreach ($cp in $cimProcs) {
        $cmd = $cp.CommandLine
        if (-not $cmd) { continue }
        foreach ($svc in $servicePatterns) {
            foreach ($pat in $svc.patterns) {
                if ($cmd -like $pat) {
                    if (-not $running[$svc.name]) { $running[$svc.name] = @() }
                    if ($running[$svc.name] -notcontains $cp.ProcessId) {
                        $running[$svc.name] += $cp.ProcessId
                    }
                    break
                }
            }
        }
    }
} catch { }

foreach ($svc in $serviceDefs) {
    $pids = $running[$svc.name]
    $inPidFile = $saved | Where-Object { $_.name -eq $svc.name }

    if ($pids -and $pids.Count -gt 0) {
        $pidStr = 'PID=' + ($pids -join ',')
        if ($svc.port -gt 0) {
            try {
                $r = Invoke-WebRequest -Uri $svc.url -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
                Write-Status $svc.name $true ($pidStr + ' :' + $svc.port + ' HTTP ' + $r.StatusCode)
            } catch {
                $portOpen = $false
                try {
                    $tnc = Test-NetConnection -ComputerName 127.0.0.1 -Port $svc.port -InformationLevel Quiet -WarningAction SilentlyContinue -ErrorAction SilentlyContinue
                    $portOpen = $tnc
                } catch { }
                if ($portOpen) {
                    Write-Status $svc.name $true ($pidStr + ' :' + $svc.port + ' port open (HTTP check failed)')
                } else {
                    Write-Status $svc.name $false ($pidStr + ' :' + $svc.port + ' not responding')
                }
            }
        } else {
            Write-Status $svc.name $true ($pidStr + ' (daemon, no HTTP)')
        }
    } else {
        if ($inPidFile) {
            Write-Status $svc.name $false ('stale PID entry (' + $inPidFile.pid + ') - process gone')
        } else {
            Write-Status $svc.name $false 'not running'
        }
    }
}

Write-Host ''
Write-Host '  Quick links:' -ForegroundColor Cyan
Write-Host '    Web      http://127.0.0.1:5173/' -ForegroundColor Green
Write-Host '    Mobile   http://127.0.0.1:5173/m' -ForegroundColor Green
Write-Host '    Docs     http://127.0.0.1:5174/' -ForegroundColor Green
Write-Host '    Swagger  http://127.0.0.1:8000/docs' -ForegroundColor Green

if ($Logs) {
    Write-Host ''
    Write-Host '=== Recent Logs ===' -ForegroundColor Cyan
    foreach ($svc in $serviceDefs) {
        $logFile = Join-Path $dataDir ($svc.name + '.log')
        if (Test-Path $logFile) {
            Write-Host ''
            Write-Host ('--- ' + $svc.name + '.log (last 5 lines) ---') -ForegroundColor Yellow
            Get-Content $logFile -Tail 5 -ErrorAction SilentlyContinue | ForEach-Object {
                Write-Host ('  ' + $_) -ForegroundColor Gray
            }
        }
    }
}

Write-Host ''
