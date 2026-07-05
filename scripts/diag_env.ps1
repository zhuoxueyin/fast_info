# fastInfo · 环境诊断(端口 + Mongo + Redis + LLM 一把扫)
# =====================================================
# 用途:跨环境排查时,一次性把"该环境是否健康"全打出来。
#     配合 .\scripts\whereami.ps1 使用,先 whereami 看清在哪,再 diag 看是否健康。
#
# 用法:
#   .\scripts\diag_env.ps1                      # 诊断当前 shell env
#   .\scripts\diag_env.ps1 -Target docker       # 显式诊断 docker 那一套
#   .\scripts\diag_env.ps1 -Both                # 两套都诊断对比
#   .\scripts\diag_env.ps1 -Json                # JSON 输出
[CmdletBinding()]
param(
    [ValidateSet('auto','dev','docker','both')]
    [string]$Target = 'auto',
    [switch]$Json = $false
)

$root = $PSScriptRoot | Split-Path -Parent
Set-Location $root

function Read-Dotenv([string]$Path) {
    if (-not (Test-Path $Path)) { return @{} }
    $h = @{}
    Get-Content $Path | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith('#') -and $line -match '^([A-Za-z_][A-Za-z0-9_]*)=(.*)$') {
            $name = $Matches[1]
            $val  = $Matches[2].Trim().Trim('"').Trim("'")
            $h[$name] = $val
        }
    }
    return $h
}

function Test-Port([string]$Host, [int]$Port, [int]$TimeoutSec = 2) {
    try {
        $tnc = Test-NetConnection -ComputerName $Host -Port $Port -InformationLevel Quiet -WarningAction SilentlyContinue -ErrorAction SilentlyContinue
        if ($tnc) { return @{ ok = $true;  detail = 'port open' } }
        return @{ ok = $false; detail = 'port closed/timeout' }
    } catch {
        return @{ ok = $false; detail = $_.Exception.Message }
    }
}

function Test-Http([string]$Url, [int]$TimeoutSec = 3) {
    try {
        $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec $TimeoutSec -ErrorAction Stop
        return @{ ok = ($r.StatusCode -ge 200 -and $r.StatusCode -lt 400); detail = "HTTP $($r.StatusCode)" }
    } catch {
        $msg = $_.Exception.Message
        if ($msg.Length -gt 80) { $msg = $msg.Substring(0, 80) + '...' }
        return @{ ok = $false; detail = $msg }
    }
}

function Get-Profile([string]$Name) {
    # 'dev' / 'docker' 两套预设端口 + URL
    switch ($Name) {
        'dev' {
            $rootEnv = Read-Dotenv (Join-Path $root '.env')
            $apiPort = 8000;  $webPort = 5173; $docsPort = 5174
            $mongoPort = 27017; $redisPort = 6379
            $mongoUrl = 'mongodb://127.0.0.1:27017'
            $mongoDb  = if ($rootEnv['MONGO_DB']) { $rootEnv['MONGO_DB'] } else { 'fastinfo' }
            $redisUrl = 'redis://127.0.0.1:6379'
            $apiBase  = "http://127.0.0.1:$apiPort"
            $webBase  = "http://127.0.0.1:$webPort"
            return @{
                name=$Name; apiPort=$apiPort; webPort=$webPort; docsPort=$docsPort
                mongoPort=$mongoPort; redisPort=$redisPort
                mongoUrl=$mongoUrl; mongoDb=$mongoDb; redisUrl=$redisUrl
                apiBase=$apiBase; webBase=$webBase
            }
        }
        'docker' {
            $dockEnv = Read-Dotenv (Join-Path $root 'docker\env.docker.local')
            $apiPort = 18000; $webPort = 18080
            $mongoPort = 27018; $redisPort = 6380
            $mongoUrl = 'mongodb://127.0.0.1:27018'
            $mongoDb  = if ($dockEnv['MONGO_DB']) { $dockEnv['MONGO_DB'] } else { 'fastinfo_docker' }
            $redisUrl = 'redis://127.0.0.1:6380'
            $apiBase  = "http://127.0.0.1:$apiPort"
            $webBase  = "http://127.0.0.1:$webPort"
            return @{
                name=$Name; apiPort=$apiPort; webPort=$webPort; docsPort=0
                mongoPort=$mongoPort; redisPort=$redisPort
                mongoUrl=$mongoUrl; mongoDb=$mongoDb; redisUrl=$redisUrl
                apiBase=$apiBase; webBase=$webBase
            }
        }
    }
}

function Run-Diag([hashtable]$P) {
    $r = [ordered]@{
        profile    = $P.name
        ports      = [ordered]@{}
        httpChecks = [ordered]@{}
        mongo      = $null
        summary    = ''
    }

    # 端口探活
    $r.ports['api']     = Test-Port '127.0.0.1' $P.apiPort
    $r.ports['mongo']   = Test-Port '127.0.0.1' $P.mongoPort
    $r.ports['redis']   = Test-Port '127.0.0.1' $P.redisPort
    if ($P.webPort -gt 0) {
        $r.ports['web']  = Test-Port '127.0.0.1' $P.webPort
    }

    # HTTP 探活(端口通 ≠ 服务正常,再看 healthz)
    $r.httpChecks['api_healthz']  = Test-Http "$($P.apiBase)/healthz"
    $r.httpChecks['api_root']     = Test-Http "$($P.apiBase)/"
    if ($P.webPort -gt 0) {
        $r.httpChecks['web_root'] = Test-Http "$($P.webBase)/"
    }

    # Mongo 详细探活(server_info + db 集合数)
    $mongoPy = $root/.venv/Scripts/python.exe
    if ($mongoPy -and (Test-Path $mongoPy) -and $r.ports.mongo.ok) {
        $out = & $mongoPy -c @"
import os, sys, json
os.environ['MONGO_URL'] = r'$($P.mongoUrl)'
os.environ['MONGO_DB']  = r'$($P.mongoDb)'
sys.path.insert(0, r'$root/src')
try:
    from storage.mongo_writer import get_sync_client
    c = get_sync_client()
    info = c.server_info()
    db = c[r'$($P.mongoDb)']
    cols = db.list_collection_names()
    sample = {}
    for col in ['items','subscriptions','users','source_config','source_runs']:
        try:
            sample[col] = db[col].estimated_document_count()
        except Exception:
            sample[col] = None
    print('OK|' + json.dumps({'version': info.get('version'), 'collections': cols, 'sample_counts': sample}, ensure_ascii=False))
except Exception as e:
    print('FAIL|' + repr(e))
"@ 2>$null
        if ($out -match '^OK\|')    { $r.mongo = @{ ok = $true;  detail = ($out -split '\|',2)[1] } }
        elseif ($out -match '^FAIL\|') {
            $r.mongo = @{ ok = $false; detail = ($out -split '\|',2)[1] }
        } else {
            $r.mongo = @{ ok = $false; detail = 'no output' }
        }
    } else {
        $r.mongo = @{ ok = $false; detail = 'mongo port not open' }
    }

    # 总结
    $okCount = 0; $totalCount = 0
    foreach ($k in $r.ports.Keys)  { $totalCount++; if ($r.ports[$k].ok) { $okCount++ } }
    foreach ($k in $r.httpChecks.Keys) { $totalCount++; if ($r.httpChecks[$k].ok) { $okCount++ } }
    if ($r.mongo.ok) { $okCount++ }; $totalCount++
    $r.summary = "$okCount / $totalCount OK"

    return $r
}

function Print-Result($r) {
    $name = $r.profile
    Write-Host ''
    Write-Host ("┌─ profile: {0} ─────────────────────────" -f $name.ToUpper()) -ForegroundColor Cyan
    Write-Host ("│") -ForegroundColor Cyan

    Write-Host ("│  Ports:") -ForegroundColor Cyan
    foreach ($k in $r.ports.Keys) {
        $ok = $r.ports[$k].ok
        Write-Host ("│    ") -NoNewline -ForegroundColor Cyan
        Write-Host ("{0,-8}" -f $k) -NoNewline
        if ($ok) { Write-Host "[OPEN]  " -NoNewline -ForegroundColor Green }
        else     { Write-Host "[DOWN]  " -NoNewline -ForegroundColor Red }
        Write-Host $r.ports[$k].detail -ForegroundColor Gray
    }

    Write-Host ("│  HTTP:") -ForegroundColor Cyan
    foreach ($k in $r.httpChecks.Keys) {
        $ok = $r.httpChecks[$k].ok
        Write-Host ("│    ") -NoNewline -ForegroundColor Cyan
        Write-Host ("{0,-15}" -f $k) -NoNewline
        if ($ok) { Write-Host "[OK]    " -NoNewline -ForegroundColor Green }
        else     { Write-Host "[FAIL]  " -NoNewline -ForegroundColor Red }
        Write-Host $r.httpChecks[$k].detail -ForegroundColor Gray
    }

    Write-Host ("│  Mongo:") -ForegroundColor Cyan
    if ($r.mongo.ok) {
        Write-Host ("│    [OK]    ") -NoNewline -ForegroundColor Green
        Write-Host $r.mongo.detail -ForegroundColor Gray
    } else {
        Write-Host ("│    [FAIL]  ") -NoNewline -ForegroundColor Red
        Write-Host $r.mongo.detail -ForegroundColor Gray
    }

    Write-Host ("│") -ForegroundColor Cyan
    Write-Host ("└─ summary: ") -NoNewline -ForegroundColor Cyan
    if ($r.summary -like '*/*' -and ($r.summary -split '/')[0] -eq ($r.summary -split '/')[1]) {
        Write-Host $r.summary -ForegroundColor Green
    } else {
        Write-Host $r.summary -ForegroundColor Yellow
    }
}

# ---------- 主流程 ----------
$targets = @()
switch ($Target) {
    'auto' {
        $appEnv = [Environment]::GetEnvironmentVariable('APP_ENV')
        if (-not $appEnv) {
            $rootEnv = Read-Dotenv (Join-Path $root '.env')
            $appEnv = if ($rootEnv['APP_ENV']) { $rootEnv['APP_ENV'] } else { 'dev' }
        }
        $targets = @($appEnv.ToLower())
    }
    'both' { $targets = @('dev','docker') }
    default { $targets = @($Target) }
}

if ($Json) {
    $out = @()
    foreach ($t in $targets) {
        $p = Get-Profile $t
        $out += Run-Diag $p
    }
    $out | ConvertTo-Json -Depth 5
    return
}

Write-Host ''
Write-Host '=== fastInfo · 环境诊断 ===' -ForegroundColor Cyan
foreach ($t in $targets) {
    $p = Get-Profile $t
    $r = Run-Diag $p
    Print-Result $r
}
Write-Host ''
Write-Host '  提示:每个 profile 独立 MongoDB(端口 + db 都不同),数据不会窜' -ForegroundColor DarkGray
Write-Host ''