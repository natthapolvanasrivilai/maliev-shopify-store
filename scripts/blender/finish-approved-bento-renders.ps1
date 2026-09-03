param(
    [Parameter(Mandatory = $true)][int]$ToolingProcessId
)
$ErrorActionPreference = 'Stop'
$renderRepo = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$renderRoot = 'M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\renders\final'
$renderBlender = 'D:\Blender 5.2\blender.exe'
$renderLogs = Join-Path $renderRepo '.codex-tmp'
Set-Location -LiteralPath $renderRepo

function Assert-CompleteSequence([string]$Manifest, [string]$Shot, [int]$Count) {
    if (-not (Test-Path -LiteralPath $Manifest -PathType Leaf)) {
        throw "Render did not produce a complete manifest: $Manifest"
    }
    $result = Get-Content -Raw -LiteralPath $Manifest | ConvertFrom-Json
    if ($result.shot -ne $Shot -or $result.frames.Count -ne $Count) {
        throw "Incomplete $Shot sequence; later stages will not run."
    }
}

$toolingProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $ToolingProcessId"
if ($toolingProcess) {
    if ($toolingProcess.Name -ne 'blender.exe' -or
        $toolingProcess.CommandLine -notmatch 'blender_bento_r22_native.py.*--shot tooling') {
        throw 'Supplied process is not the approved tooling render worker.'
    }
    Write-Output "Waiting for tooling render PID $ToolingProcessId"
    Wait-Process -Id $ToolingProcessId -ErrorAction SilentlyContinue
}
Assert-CompleteSequence "$renderRoot/bento-20260903-r23-native-motion/tooling/final.json" 'tooling' 192

Write-Output 'Rendering the approved web-sized capacity sequence.'
& $renderBlender --background --python-exit-code 1 --python scripts/blender/pimm_production/blender_bento_capacity_web_final.py *> "$renderLogs/bento-r27-capacity-final.log"
if ($LASTEXITCODE -ne 0) { throw 'Capacity render failed; see bento-r27-capacity-final.log' }
Assert-CompleteSequence "$renderRoot/bento-20260903-r27-capacity-web-final/capacity/final.json" 'capacity' 192

Write-Output 'Rendering all 840 approved yaw/pitch views.'
& $renderBlender --background --python-exit-code 1 --python scripts/blender/pimm_production/blender_bento_r22_native.py -- --shot configuration *> "$renderLogs/bento-r23-configuration-final.log"
if ($LASTEXITCODE -ne 0) { throw 'Configuration render failed; see bento-r23-configuration-final.log' }
Assert-CompleteSequence "$renderRoot/bento-20260903-r23-native-motion/configuration/final.json" 'configuration' 840
Write-Output 'ALL_APPROVED_NATIVE_RENDER_SEQUENCES_COMPLETE'
