<#
.SYNOPSIS
    Sovereign On-Premise Agentic AI Workbench — Air-Gapped Bootstrap Wrapper (PowerShell).
.DESCRIPTION
    Runs scripts\bootstrap.py to prepare offline database, vectors, and audit ledger.
#>

$ErrorActionPreference = "Stop"

$scriptPath = Join-Path $PSScriptRoot "bootstrap.py"
python $scriptPath
if ($LASTEXITCODE -ne 0) {
    Write-Error "Air-gapped bootstrap failed with exit code $LASTEXITCODE"
}
