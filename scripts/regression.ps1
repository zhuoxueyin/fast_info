# fastInfo 回归测试一键运行
# 用法:
#   .\scripts\regression.ps1              # 全量回归
#   .\scripts\regression.ps1 -Smoke       # 快速冒烟
#   .\scripts\regression.ps1 -Report      # 生成 HTML 报告
#   .\scripts\regression.ps1 -Fast        # 跳过慢速测试

param(
    [switch]$Smoke,
    [switch]$Fast,
    [switch]$Report,
    [switch]$NoCleanup,
    [switch]$ExitFirst,
    [string]$Keyword = ""
)

$projectRoot = $PSScriptRoot | Split-Path -Parent
Set-Location $projectRoot

# 激活 venv
if (Test-Path ".venv\Scripts\Activate.ps1") {
    . .venv\Scripts\Activate.ps1
}

# 构建参数
$args = @()
if ($Smoke) { $args += "--smoke" }
if ($Fast) { $args += "--fast" }
if ($Report) { $args += "--report" }
if ($NoCleanup) { $args += "--no-cleanup" }
if ($ExitFirst) { $args += "--exitfirst" }
if ($Keyword) { $args += "-k"; $args += $Keyword }

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  fastInfo 回归测试" -ForegroundColor Cyan
Write-Host "  模式: $(if ($Smoke) {'冒烟'} else {'全量'})" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

python scripts/run_regression.py @args

$exitCode = $LASTEXITCODE
if ($exitCode -eq 0) {
    Write-Host "`n✓ 回归测试全部通过" -ForegroundColor Green
} else {
    Write-Host "`n✗ 回归测试有失败 (exit=$exitCode)" -ForegroundColor Red
}
exit $exitCode
