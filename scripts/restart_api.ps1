# fastInfo · API 启动 / 停止 / 重启脚本
# ==========================================
#
# 严格只动 fast_info 自己的 api_server 进程,不误伤其他项目。
# 用法:
#   powershell -File scripts/restart_api.ps1          # 默认:stop + start
#   powershell -File scripts/restart_api.ps1 start    # 启动
#   powershell -File scripts/restart_api.ps1 stop     # 停止
#   powershell -File scripts/restart_api.ps1 restart  # 停止 + 启动(默认)
#   powershell -File scripts/restart_api.ps1 status   # 看进程
#   powershell -File scripts/restart_api.ps1 log      # 看日志(最近 20 行)

param(
    [ValidateSet("start","stop","restart","status","log")]
    [string]$Action = "restart"
)

$ErrorActionPreference = "Stop"
$ScriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$LogFile     = Join-Path $ProjectRoot "data\api-server.log"
$MatchCmd    = "*fast_info*api_server*"
$VenvPy      = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

function Get-ApiProcess {
    Get-Process python -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like $MatchCmd } |
        Select-Object Id, StartTime, CommandLine
}

switch ($Action) {
    "status" {
        $p = Get-ApiProcess
        if ($p) {
            $p | Format-Table -AutoSize
        } else {
            Write-Host "  (无 fastInfo API 进程在跑)" -ForegroundColor Yellow
        }
    }

    "stop" {
        $p = Get-ApiProcess
        if ($p) {
            Write-Host "  停止 fastInfo API 进程 (PID=$($p.Id -join ','))" -ForegroundColor Yellow
            $p | Stop-Process -Force
            Start-Sleep -Seconds 1
        } else {
            Write-Host "  (无进程可停)" -ForegroundColor Yellow
        }
    }

    "start" {
        if (-not (Test-Path $VenvPy)) {
            Write-Host "  ✗ 找不到 venv: $VenvPy" -ForegroundColor Red
            Write-Host "    请先建 venv: python -m venv .venv"
            exit 1
        }
        $p = Get-ApiProcess
        if ($p) {
            Write-Host "  fastInfo API 已在跑 (PID=$($p.Id -join ','))" -ForegroundColor Green
            exit 0
        }
        Write-Host "  启动 fastInfo API (后台,日志→$LogFile)" -ForegroundColor Green
        New-Item -ItemType Directory -Force -Path (Split-Path $LogFile) | Out-Null

        # 用 cmd /c start 把 venv python 真正"分离"出去,
        # 这样 ps1 不会持有 uvicorn 的 stdout 句柄,可以立即退出。
        $argsStr = "scripts\api_server.py > `"$LogFile`" 2>&1"
        $proc = Start-Process -FilePath $VenvPy `
                              -ArgumentList $argsStr `
                              -WorkingDirectory $ProjectRoot `
                              -WindowStyle Hidden `
                              -PassThru
        Write-Host "  PID=$($proc.Id)  等待 4s 让 uvicorn 起来..." -ForegroundColor Green
        Start-Sleep -Seconds 4
        # 双指标判断:进程存在 OR 端口在监听 (用 Test-NetConnection 替代,免 Get-NetTCPConnection 卡)
        $check = Get-ApiProcess
        $portUp = $false
        try {
            $tnc = Test-NetConnection -ComputerName 127.0.0.1 -Port 8000 -InformationLevel Quiet -WarningAction SilentlyContinue -ErrorAction SilentlyContinue
            $portUp = $tnc
        } catch { $portUp = $false }
        if ($check -or $portUp) {
            Write-Host "  ✓ 启动成功 (PID=$($proc.Id), port8000=$portUp)" -ForegroundColor Green
        } else {
            Write-Host "  ✗ 启动失败,看日志: $LogFile" -ForegroundColor Red
            Get-Content $LogFile -Tail 20 -ErrorAction SilentlyContinue
            exit 1
        }
    }

    "restart" {
        & $MyInvocation.MyCommand.Path stop
        & $MyInvocation.MyCommand.Path start
    }

    "log" {
        if (Test-Path $LogFile) {
            Get-Content $LogFile -Tail 20 -Wait
        } else {
            Write-Host "  (无日志)" -ForegroundColor Yellow
        }
    }
}
