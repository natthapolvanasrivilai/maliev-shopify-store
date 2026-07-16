$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repositoryRoot = Split-Path -Parent $PSScriptRoot

Push-Location $repositoryRoot
try {
    shopify theme pull `
        --store 10b918-e4.myshopify.com `
        --theme 190305730839 `
        --nodelete

    if ($LASTEXITCODE -ne 0) {
        throw 'Unable to synchronize the live Shopify theme.'
    }
}
finally {
    Pop-Location
}
