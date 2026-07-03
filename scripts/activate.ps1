#!/usr/bin/env pwsh
# fastInfo · 激活虚拟环境(Linux/WSL/macOS)
# 用法: source scripts/activate.sh

$VENV_DIR = Join-Path $PSScriptRoot ".." ".venv"

if (-not (Test-Path $VENV_DIR)) {
    Write-Host "✗ venv 不存在,请先建: python -m venv .venv --prompt fastinfo" -ForegroundColor Red
    exit 1
}

# 兼容 bash 调用
if ($env:SHELL -match "bash" -or $PSVersionTable.Platform -eq "Unix") {
    & "$VENV_DIR/bin/activate"
} else {
    & "$VENV_DIR/Scripts/Activate.ps1"
}

Write-Host "✓ fastInfo venv activated" -ForegroundColor Green
Write-Host "  Python: $(python --version 2>&1)"
Write-Host "  PWD:    $PWD"
Write-Host "  试试:   python fastinfo.py stats"