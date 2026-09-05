param([Parameter(Mandatory = $true)][int]$RenderQueueProcessId)
$ErrorActionPreference = 'Stop'
$deliveryRepo = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
Set-Location -LiteralPath $deliveryRepo
$queue = Get-CimInstance Win32_Process -Filter "ProcessId = $RenderQueueProcessId"
if ($queue) {
    if ($queue.Name -ne 'pwsh.exe' -or $queue.CommandLine -notmatch 'finish-approved-bento-renders.ps1') {
        throw 'Expected the approved render queue process.'
    }
    Write-Output "Waiting for approved render queue PID $RenderQueueProcessId"
    Wait-Process -Id $RenderQueueProcessId -ErrorAction SilentlyContinue
}
# The packager fails closed unless all 1,224 final PNG/EXR receipts validate.
py -3 scripts/blender/pimm_production/package_bento_final_delivery.py
if ($LASTEXITCODE -ne 0) { throw 'Final delivery validation or encoding failed; existing files preserved.' }
