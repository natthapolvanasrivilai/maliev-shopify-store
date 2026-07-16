param(
    [Parameter(Mandatory = $true)]
    [string]$ConfirmThemeId
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$expectedThemeId = '190305730839'
$store = '10b918-e4.myshopify.com'
$repositoryRoot = Split-Path -Parent $PSScriptRoot

if ($ConfirmThemeId -ne $expectedThemeId) {
    throw "Production deployment requires -ConfirmThemeId $expectedThemeId."
}

Push-Location $repositoryRoot
try {
    $branch = (git branch --show-current).Trim()
    if ($branch -ne 'main') {
        throw "Production deployment is allowed only from main. Current branch: $branch"
    }

    $workingTree = git status --porcelain
    if ($workingTree) {
        throw 'Production deployment requires a clean working tree.'
    }

    npm run verify
    if ($LASTEXITCODE -ne 0) {
        throw 'Theme verification failed. Production was not changed.'
    }

    npx shopify theme push `
        --store $store `
        --theme $expectedThemeId `
        --allow-live `
        --strict `
        --ignore config/settings_data.json

    if ($LASTEXITCODE -ne 0) {
        throw 'Shopify rejected the production deployment.'
    }
}
finally {
    Pop-Location
}
