# fastInfo · 一键查"我现在在哪个环境"
# =====================================
# 排查异常时第一步先跑这个,确认你连的是 dev / docker / prod 哪套。
#
# 用法:
#   .\scripts\whereami.ps1                  # 列出当前 shell 的环境身份
#   .\scripts\whereami.ps1 -Quick           # 只打一行总结
#   .\scripts\whereami.ps1 -Json            # 输出 JSON(便于脚本串联)
#
# 它会读:
#   1. 当前 PowerShell 进程 env(APP_ENV / MONGO_URL / MONGO_DB / REDIS_URL / FASTINFO_SITE_BASE)
#   2. 项目根 .env(以及 docker/env.docker.local 如果存在)
#   3. 实际尝试连接 MongoDB(只 ping,不动数据)
[CmdletBinding()]
param(
    [switch]$Quick = $false,
    [switch]$Json  = $false,
    [switch]$NoMongo = $false
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

# ---------- 1. 收集 env(优先级:shell > .env > 默认) ----------
$rootEnv  = Read-Dotenv (Join-Path $root '.env')
$dockEnv  = Read-Dotenv (Join-Path $root 'docker\env.docker.local')

function Get-Eff([string]$Name, [hashtable]$Layers, $Default = '<unset>') {
    # shell env 优先级最高
    $shellVal = [Environment]::GetEnvironmentVariable($Name)
    if ($shellVal) { return @{ value = $shellVal; source = 'shell' } }
    foreach ($layerName in @('docker.env', 'root.env')) {
        $h = $Layers[$layerName]
        if ($h -and $h.ContainsKey($Name) -and $h[$Name]) {
            return @{ value = $h[$Name]; source = $layerName }
        }
    }
    return @{ value = $Default; source = 'default' }
}

$layers = @{ 'root.env' = $rootEnv; 'docker.env' = $dockEnv }

$appEnv  = Get-Eff 'APP_ENV'         $layers 'dev'
$mongoUrl= Get-Eff 'MONGO_URL'       $layers 'mongodb://127.0.0.1:27017'
$mongoDb = Get-Eff 'MONGO_DB'        $layers 'fastinfo'
$redisUrl= Get-Eff 'REDIS_URL'       $layers 'redis://127.0.0.1:6379'
$siteBase= Get-Eff 'FASTINFO_SITE_BASE' $layers '<unset>'

# ---------- 2. 启发式判 env(APP_ENV 未声明时) ----------
function Guess-Env([string]$AppEnv, [string]$MongoUrl, [string]$RedisUrl) {
    if ($AppEnv -in @('dev','docker','prod','staging','test')) { return $AppEnv }
    if (Test-Path 'C:\.dockerenv') { return 'docker' }
    $dockerMarker = Join-Path $root '.dockerenv'
    if (Test-Path $dockerMarker) { return 'docker' }
    if ($MongoUrl -match '^mongodb://(mongo|fastinfo-mongo):') { return 'docker' }
    if ($RedisUrl -match '^redis://(redis|fastinfo-redis):')   { return 'docker' }
    return 'dev'
}

$env = Guess-Env $appEnv.value $mongoUrl.value $redisUrl.value
$tag = "[$($env.ToUpper())]"
$color = switch ($env) {
    'docker'  { 'Yellow' }
    'prod'    { 'Red' }
    'staging' { 'Magenta' }
    'test'    { 'Green' }
    default   { 'Cyan' }
}

# ---------- 3. Mongo ping ----------
$mongoStatus = 'skipped'
$mongoError  = ''
if (-not $NoMongo) {
    $root/.venv/Scripts/python.exe -c @"
import os, sys
sys.path.insert(0, r'$root/src')
try:
    from storage.mongo_writer import get_sync_client
    c = get_sync_client()
    info = c.server_info()
    print('OK|' + info.get('version','?'))
except Exception as e:
    print('FAIL|' + repr(e))
"@ 2>$null | ForEach-Object {
        if ($_ -match '^OK\|')    { $mongoStatus = 'OK (' + ($_ -split '\|',2)[1] + ')' }
        elseif ($_ -match '^FAIL\|') {
            $mongoStatus = 'FAIL'
            $mongoError  = ($_ -split '\|',2)[1]
        }
    }
}

# ---------- 4. 输出 ----------
$result = [ordered]@{
    env        = $env
    tag        = $tag
    app_env_declared = ($appEnv.source -ne 'default')
    app_env_source   = $appEnv.source
    mongo_url  = $mongoUrl.value
    mongo_db   = $mongoDb.value
    mongo_source = $mongoUrl.source
    redis_url  = $redisUrl.value
    redis_source = $redisUrl.source
    site_base  = $siteBase.value
    mongo_ping = $mongoStatus
    mongo_error = $mongoError
    hostname   = $env:COMPUTERNAME
    pwd        = (Get-Location).Path
}

if ($Json) {
    $result | ConvertTo-Json -Depth 3
    return
}

if ($Quick) {
    Write-Host "$tag" -NoNewline -ForegroundColor $color
    Write-Host ("  mongo={0} db={1}  ping={2}" -f $mongoUrl.value, $mongoDb.value, $mongoStatus) -ForegroundColor Gray
    return
}

Write-Host ''
Write-Host '=== whereami · 当前 shell 环境身份 ===' -ForegroundColor Cyan
Write-Host ''
Write-Host ('  ENV       ') -NoNewline
Write-Host $tag -NoNewline -ForegroundColor $color
Write-Host (' (declared=' + ($appEnv.source) + ')') -ForegroundColor DarkGray
Write-Host ('  MONGO_URL ') -NoNewline
Write-Host $mongoUrl.value -ForegroundColor White
Write-Host ('  MONGO_DB  ') -NoNewline
Write-Host $mongoDb.value -ForegroundColor White
Write-Host ('  REDIS_URL ') -NoNewline
Write-Host $redisUrl.value -ForegroundColor White
Write-Host ('  SITE_BASE ') -NoNewline
Write-Host $siteBase.value -ForegroundColor White
Write-Host ('  MONGO     ') -NoNewline
if ($mongoStatus -like 'OK*') {
    Write-Host $mongoStatus -ForegroundColor Green
} elseif ($mongoStatus -eq 'FAIL') {
    Write-Host $mongoStatus -ForegroundColor Red
    if ($mongoError) { Write-Host ('             ' + $mongoError) -ForegroundColor DarkRed }
} else {
    Write-Host $mongoStatus -ForegroundColor DarkGray
}
Write-Host ('  HOST      ') -NoNewline
Write-Host $env:COMPUTERNAME -ForegroundColor White
Write-Host ('  PWD       ') -NoNewline
Write-Host (Get-Location).Path -ForegroundColor White
Write-Host ''
Write-Host '  .env 加载源:' -ForegroundColor Cyan
Write-Host ('    APP_ENV         <- ' + $appEnv.source) -ForegroundColor DarkGray
Write-Host ('    MONGO_URL       <- ' + $mongoUrl.source) -ForegroundColor DarkGray
Write-Host ('    REDIS_URL       <- ' + $redisUrl.source) -ForegroundColor DarkGray
Write-Host ''
Write-Host '  提示:排查异常前先确认 ENV tag,不要再蹿环境!' -ForegroundColor Yellow
Write-Host ''