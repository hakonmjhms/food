<#
.SYNOPSIS
    Sets up (or tears down) a local development environment for the Cake Voting app.

.PARAMETER Seed
    Populate the database with sample cakes and a voting week after setup.

.PARAMETER Clean
    Remove generated dev artifacts (.venv, .env, *.db, pytest cache) instead of setting up.

.EXAMPLE
    .\scripts\setup-dev.ps1 -Seed
.EXAMPLE
    .\scripts\setup-dev.ps1 -Clean
#>
param(
    [switch]$Seed,
    [switch]$Clean
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root

if ($Clean) {
    Write-Host "Removing dev artifacts..."
    Remove-Item ".venv" -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item ".env" -ErrorAction SilentlyContinue
    Remove-Item "*.db" -ErrorAction SilentlyContinue
    Remove-Item ".pytest_cache" -Recurse -Force -ErrorAction SilentlyContinue
    Get-ChildItem -Recurse -Filter "__pycache__" -Directory | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "Done."
    return
}

if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment..."
    python -m venv .venv
}

Write-Host "Installing dependencies..."
& .\.venv\Scripts\python.exe -m pip install --quiet --disable-pip-version-check -r requirements-dev.txt

if (-not (Test-Path ".env")) {
    Write-Host "Creating .env from .env.example..."
    Copy-Item ".env.example" ".env"
}

if ($Seed) {
    Write-Host "Seeding sample cakes and a voting week..."
    & .\.venv\Scripts\python.exe -m scripts.seed_dev_data
}

Write-Host ""
Write-Host "Setup complete. Run:"
Write-Host "  .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload"
