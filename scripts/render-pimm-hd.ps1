param(
    [string]$OutputRoot = 'M:/30_Products/00_Pneumatic Injection Molding Machine/blender-product-renders/renders/hero/cinema-hd-final',
    [switch]$Proof,
    [switch]$ApprovedMotion
)
$ErrorActionPreference = 'Stop'
if (-not $ApprovedMotion) { throw 'High-resolution rendering is paused. Validate operating motion first, then explicitly pass -ApprovedMotion.' }
$repo = Split-Path -Parent $PSScriptRoot
$blender = 'D:/Blender 5.2/blender.exe'
$master = 'M:/30_Products/00_Pneumatic Injection Molding Machine/blender-product-renders/masters/PIMM-30G-MASTER.blend'
# Render only: never uploads assets or changes the published Shopify theme.
foreach ($profile in @('desktop', 'mobile')) {
    $renderArgs = @('-b', $master, '--python-exit-code', '1', '--python', "$repo/scripts/blender/pimm_production/blender_30g_component_cinema.py", '--', '--output', "$OutputRoot/$profile", '--profile', $profile, '--samples', '32', '--operations')
    if ($Proof) { $renderArgs += '--proof' }
    & $blender @renderArgs
    if ($LASTEXITCODE -ne 0) { throw "$profile render failed with exit code $LASTEXITCODE" }
}
