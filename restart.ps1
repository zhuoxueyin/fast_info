# fastInfo - one-click restart
# Usage:
#     .\restart.ps1                            # stop + start everything
#     .\restart.ps1 -Only backend              # restart only backend
#     .\restart.ps1 -Only backend,frontend    # restart listed services
#     .\restart.ps1 -BindHost 0.0.0.0         # restart with new bind host
#     .\restart.ps1 -NoDaemons                 # restart without daemons
#     .\restart.ps1 -WaitSec 25                # healthcheck wait
[CmdletBinding()]
param(
    [string]$BindHost = '127.0.0.1',
    [switch]$NoDaemons = $false,
    [string[]]$Only = @(),
    [int]$WaitSec = 20
)

$root = $PSScriptRoot
Set-Location $root

$ErrorActionPreference = 'Continue'

function Banner($msg) {
    Write-Host ''
    Write-Host ('=== ' + $msg + ' ===') -ForegroundColor Cyan
}

Banner 'Stopping services'
$stopParams = @{ Force = $true }
if ($Only.Count -gt 0) { $stopParams['Only'] = $Only }
& (Join-Path $root 'stop.ps1') @stopParams

Start-Sleep -Seconds 2

Banner 'Starting services'
$startParams = @{
    BindHost = $BindHost
    WaitSec  = $WaitSec
}
if ($NoDaemons) { $startParams['NoDaemons'] = $true }
if ($Only.Count -gt 0) { $startParams['Only'] = $Only }
& (Join-Path $root 'start.ps1') @startParams
