# fastInfo - one-click start
# Usage:
#     .\start.ps1                          # start all (default 127.0.0.1)
#     .\start.ps1 -BindHost 0.0.0.0        # listen on all interfaces
#     .\start.ps1 -NoDaemons               # skip ingest/scheduler daemons
#     .\start.ps1 -Only backend,frontend   # only start listed services
#     .\start.ps1 -WaitSec 20              # healthcheck wait (default 20s)
[CmdletBinding()]
param(
    [string]$BindHost = '127.0.0.1',
    [switch]$NoDaemons = $false,
    [string[]]$Only = @(),
    [int]$WaitSec = 20
)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
Set-Location $root

function Step($n, $msg)  { Write-Host ('[{0}] ' -f $n) -NoNewline -ForegroundColor Cyan; Write-Host $msg }
function Ok($msg)        { Write-Host ('    [OK]  ' + $msg) -ForegroundColor Green }
function Warn($msg)      { Write-Host ('    [!!]  ' + $msg) -ForegroundColor Yellow }
function Err($msg)       { Write-Host ('    [ERR] ' + $msg) -ForegroundColor Red }
function Info($msg)      { Write-Host ('    [..]  ' + $msg) -ForegroundColor Gray }

function ShouldStart([string]$svc) {
    if ($script:Only.Count -eq 0) { return $true }
    return $script:Only -contains $svc
}

# 0. Load .env file(s)
$envCandidates = @(
    (Join-Path $root '.env'),
    (Join-Path $root 'config\.env')
)
$envLoaded = $false
foreach ($envFile in $envCandidates) {
    if (Test-Path $envFile) {
        Get-Content $envFile | ForEach-Object {
            $line = $_.Trim()
            if ($line -and -not $line.StartsWith('#') -and $line -match '^([A-Za-z_][A-Za-z0-9_]*)=(.*)$') {
                $name = $Matches[1]
                $val = $Matches[2].Trim().Trim('"').Trim("'")
                if ([string]::IsNullOrEmpty([Environment]::GetEnvironmentVariable($name))) {
                    [Environment]::SetEnvironmentVariable($name, $val, 'Process')
                }
            }
        }
        Info ('loaded .env: ' + $envFile)
        $envLoaded = $true
        break
    }
}
if (-not $envLoaded) {
    Info 'no .env file found, using existing environment'
}

# 1. Pre-flight
Step '1' 'Environment check'

$venvPy = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path $venvPy)) {
    Err ('venv not found: ' + $venvPy)
    exit 1
}
Ok ('venv OK -> ' + $venvPy)

if (-not $env:MMX_API_KEY) {
    Warn 'MMX_API_KEY not set (LLM calls will fail)'
} else {
    Ok 'MMX_API_KEY set'
}

if (-not $env:MONGO_URL) {
    $env:MONGO_URL = 'mongodb://127.0.0.1:27017'
    Info ('MONGO_URL default: ' + $env:MONGO_URL)
} else {
    Ok ('MONGO_URL = ' + $env:MONGO_URL)
}

if (-not $env:REDIS_URL) {
    $env:REDIS_URL = 'redis://127.0.0.1:6379'
    Info ('REDIS_URL default: ' + $env:REDIS_URL)
}

$env:HTTP_PROXY = ''
$env:HTTPS_PROXY = ''
$env:ALL_PROXY = ''
Info 'cleared HTTP_PROXY/HTTPS_PROXY/ALL_PROXY'

# Check node_modules
if ((ShouldStart 'frontend') -and -not (Test-Path (Join-Path $root 'frontend\node_modules'))) {
    Err 'frontend/node_modules not found. Run: cd frontend; npm install'
    exit 1
}
if ((ShouldStart 'docs') -and -not (Test-Path (Join-Path $root 'docs-site\node_modules'))) {
    Err 'docs-site/node_modules not found. Run: cd docs-site; npm install'
    exit 1
}

# 2. Kill leftovers (read PID file first, then pattern scan)
Step '2' 'Cleaning up previous instances...'
$pidFile = Join-Path $root 'data\running.pids'
$killed = 0

if (Test-Path $pidFile) {
    try {
        $saved = Get-Content $pidFile -Raw | ConvertFrom-Json -ErrorAction Stop
        if ($saved -isnot [array]) { $saved = @($saved) }
        foreach ($s in $saved) {
            $p = Get-Process -Id $s.pid -ErrorAction SilentlyContinue
            if ($p) {
                Info ('killing saved PID ' + $s.pid + ' (' + $s.name + ')')
                Stop-Process -Id $s.pid -Force -ErrorAction SilentlyContinue
                $killed++
            }
        }
    } catch { }
    Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
}

# Pattern scan for any remaining fastInfo processes
Get-Process python, node -ErrorAction SilentlyContinue | ForEach-Object {
    $c = $_.CommandLine
    if ($c -and ($c -like '*fast_info*api_server*' -or
                 $c -like '*fast_info*ingest_daemon*' -or
                 $c -like '*fast_info*subs_scheduler*' -or
                 $c -like '*fast_info*frontend*' -or
                 $c -like '*fast_info*docs-site*')) {
        Info ('killing leftover PID ' + $_.Id + ' (' + $_.ProcessName + ')')
        Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
        $killed++
    }
}
if ($killed -gt 0) {
    Ok ("cleaned up $killed process(es)")
} else {
    Info 'no leftovers found'
}
Start-Sleep -Seconds 2

# 3. Prepare data dir + runners
Step '3' 'Preparing log directories...'
$dataDir = Join-Path $root 'data'
$runnerDir = Join-Path $dataDir 'runners'
if (-not (Test-Path $dataDir)) { New-Item -ItemType Directory -Path $dataDir | Out-Null }
if (Test-Path $runnerDir) {
    Get-ChildItem $runnerDir -Filter '*.ps1' | Remove-Item -Force -ErrorAction SilentlyContinue
} else {
    New-Item -ItemType Directory -Path $runnerDir | Out-Null
}
Ok ('logs -> ' + $dataDir)

# 4. Spawn services
Step '4' 'Starting services...'
$procs = @()

function Start-Proc {
    param(
        [string]$Name,
        [string]$Cmd,
        [string]$Cwd,
        [int]$Port = 0
    )
    $logPath = Join-Path $dataDir ($Name + '.log')
    $errPath = Join-Path $dataDir ($Name + '.err.log')
    $runnerPath = Join-Path $runnerDir ($Name + '.ps1')

    $runnerContent = @(
        '$ErrorActionPreference = "Continue"',
        '$env:HTTP_PROXY = ""',
        '$env:HTTPS_PROXY = ""',
        '$env:ALL_PROXY = ""',
        ('Set-Location "' + ($Cwd -replace '\\','\\') + '"'),
        $Cmd
    ) -join "`r`n"
    [System.IO.File]::WriteAllText($runnerPath, $runnerContent, [System.Text.UTF8Encoding]::new($false))

    $p = Start-Process -FilePath 'powershell.exe' `
        -ArgumentList @('-NoLogo','-NoProfile','-ExecutionPolicy','Bypass','-File', $runnerPath) `
        -WorkingDirectory $Cwd `
        -RedirectStandardOutput $logPath `
        -RedirectStandardError $errPath `
        -PassThru -WindowStyle Hidden

    Ok ($Name + ' started, PID=' + $p.Id)
    return @{ name = $Name; pid = $p.Id; port = $Port; log = $logPath }
}

if (ShouldStart 'backend') {
    $procs += Start-Proc 'backend' ('& "' + $venvPy + '" scripts\api_server.py --host ' + $BindHost) $root 8000
}
if (ShouldStart 'frontend') {
    $procs += Start-Proc 'frontend' ('npx vite --host ' + $BindHost + ' --port 5173') (Join-Path $root 'frontend') 5173
}
if (ShouldStart 'docs') {
    $procs += Start-Proc 'docs' ('npx vitepress dev . --host ' + $BindHost + ' --port 5174') (Join-Path $root 'docs-site') 5174
}
if ((-not $NoDaemons) -and (ShouldStart 'ingest')) {
    $procs += Start-Proc 'ingest' ('& "' + $venvPy + '" scripts\ingest_daemon.py --interval 1800') $root
}
if ((-not $NoDaemons) -and (ShouldStart 'scheduler')) {
    $procs += Start-Proc 'scheduler' ('& "' + $venvPy + '" scripts\subs_scheduler.py --interval 60') $root
}

# 5. Save PID file
$procs | ConvertTo-Json -Depth 3 | Out-File $pidFile -Encoding utf8
Ok ('PID file saved: ' + $pidFile)

# 6. Health check
Step '5' ('Waiting for services (max ' + $WaitSec + 's)...')

$checks = @()
if (ShouldStart 'backend')  { $checks += @{ name = 'backend :8000';  url = 'http://127.0.0.1:8000/healthz';  log = (Join-Path $dataDir 'backend.log') } }
if (ShouldStart 'frontend') { $checks += @{ name = 'frontend :5173'; url = 'http://127.0.0.1:5173/';         log = (Join-Path $dataDir 'frontend.log') } }
if (ShouldStart 'docs')     { $checks += @{ name = 'docs :5174';     url = 'http://127.0.0.1:5174/';         log = (Join-Path $dataDir 'docs.log') } }

$allOk = $true
foreach ($c in $checks) {
    $ready = $false
    for ($i = 0; $i -lt $WaitSec; $i++) {
        try {
            $r = Invoke-WebRequest -Uri $c.url -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
            if ($r.StatusCode -in 200..299) {
                Ok ($c.name + ' ready (' + $r.StatusCode + ')')
                $ready = $true
                break
            }
        } catch {
            Start-Sleep -Milliseconds 800
        }
    }
    if (-not $ready) {
        Err ($c.name + ' not ready. Log tail:')
        if (Test-Path $c.log) {
            Get-Content $c.log -Tail 8 -ErrorAction SilentlyContinue | ForEach-Object {
                Write-Host ('      ' + $_) -ForegroundColor DarkGray
            }
        }
        $errLog = $c.log -replace '\.log$', '.err.log'
        if (Test-Path $errLog) {
            $errTail = Get-Content $errLog -Tail 8 -ErrorAction SilentlyContinue
            if ($errTail) {
                Write-Host '    stderr:' -ForegroundColor DarkRed
                $errTail | ForEach-Object { Write-Host ('      ' + $_) -ForegroundColor DarkRed }
            }
        }
        $allOk = $false
    }
}

# 7. Summary
Write-Host ''
if ($allOk) {
    Step 'OK' 'All services started successfully.'
} else {
    Step '!!' 'Some services failed to start. Check logs above.'
}
Write-Host ''

$showAccess = ($Only.Count -eq 0) -or ($Only -contains 'frontend') -or ($Only -contains 'docs') -or ($Only -contains 'backend')
if ($showAccess) {
    Write-Host '  Access URLs:' -ForegroundColor Cyan
    if (ShouldStart 'frontend') {
        Write-Host '    Web        ' -NoNewline; Write-Host ('http://' + $BindHost + ':5173/') -ForegroundColor Green
        Write-Host '    Mobile     ' -NoNewline; Write-Host ('http://' + $BindHost + ':5173/m') -ForegroundColor Green
    }
    if (ShouldStart 'docs') {
        Write-Host '    Docs       ' -NoNewline; Write-Host ('http://' + $BindHost + ':5174/') -ForegroundColor Green
    }
    if (ShouldStart 'backend') {
        Write-Host '    Swagger    ' -NoNewline; Write-Host ('http://' + $BindHost + ':8000/docs') -ForegroundColor Green
        Write-Host '    Admin      ' -NoNewline; Write-Host ('http://' + $BindHost + ':5173/admin (admin / admin@2026)') -ForegroundColor Green
        Write-Host '    Healthz    ' -NoNewline; Write-Host ('http://' + $BindHost + ':8000/healthz') -ForegroundColor Green
    }
    Write-Host ''
}

Write-Host '  Processes:' -ForegroundColor Cyan
foreach ($p in $procs) {
    $port = ''
    if ($p.port -gt 0) { $port = ' :' + $p.port }
    Write-Host ('    {0,-15} PID={1,-6}{2}' -f $p.name, $p.pid, $port)
}
Write-Host ''
Write-Host ('  Logs:   ' + $dataDir + '\<service>.log') -ForegroundColor Gray
Write-Host '  Stop:    ' -NoNewline; Write-Host '.\stop.ps1' -ForegroundColor Yellow
Write-Host '  Restart: ' -NoNewline; Write-Host '.\restart.ps1' -ForegroundColor Yellow
Write-Host '  Status:  ' -NoNewline; Write-Host '.\status.ps1' -ForegroundColor Yellow
Write-Host ''

if (-not $allOk) { exit 1 }
