<#
.SYNOPSIS
    Starts the shop locally: the API and the website, in two separate windows.

.DESCRIPTION
    Run this from the project root:

        .\start.ps1

    It opens two PowerShell windows you can see:
      * Backend  - the API on http://localhost:8000
      * Frontend - the website on http://localhost:5173

    Close a window (or press Ctrl+C in it) to stop that part.

    Why a script? The two halves have to run at the same time, and each needs
    its own terminal to show errors. If a window closes itself, just run this
    again.

.NOTES
    First run only:  cd backend; python -m venv .venv
                     .\.venv\Scripts\pip install -r requirements.txt
                     cd ..\frontend; npm install; cd ..
#>

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

# --- check the Python virtual environment exists -----------------------------
$venv = Join-Path $root 'backend\.venv\Scripts\python.exe'
if (-not (Test-Path $venv)) {
    Write-Host ''
    Write-Host 'Setting up for the first time (one-off, takes a minute)...' -ForegroundColor Yellow
    Push-Location (Join-Path $root 'backend')
    python -m venv .venv
    & $venv -m pip install --quiet --upgrade pip
    & $venv -m pip install --quiet -r requirements.txt
    Pop-Location
    Push-Location (Join-Path $root 'frontend')
    npm install --silent
    Pop-Location
    Write-Host 'First-time setup finished.' -ForegroundColor Green
}

# --- is anything already running? -------------------------------------------
function Test-Port($number) {
    return [bool](Get-NetTCPConnection -LocalPort $number -State Listen -ErrorAction SilentlyContinue)
}

if (Test-Port 8000) { Write-Host 'Backend is already running on 8000.' -ForegroundColor DarkGray }
else { Start-Process powershell -ArgumentList '-NoExit', '-Command', "cd '$root\backend'; .\.venv\Scripts\python.exe -m uvicorn main:app --port 8000 --reload" }

if (Test-Port 5173) { Write-Host 'Frontend is already running on 5173.' -ForegroundColor DarkGray }
else { Start-Process powershell -ArgumentList '-NoExit', '-Command', "cd '$root\frontend'; npm run dev" }

Write-Host ''
Write-Host 'Starting up...' -ForegroundColor Cyan

# Wait for each service instead of guessing. The backend has to reach Supabase
# on boot, which can take several seconds on a cold connection, so a fixed
# sleep here would report a false failure.
function Wait-For($label, $url, $seconds = 45) {
    $deadline = (Get-Date).AddSeconds($seconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $null = Invoke-WebRequest $url -UseBasicParsing -TimeoutSec 3
            Write-Host "  $label ready" -ForegroundColor Green
            return $true
        } catch {
            Start-Sleep -Milliseconds 800
        }
    }
    Write-Host "  $label did not start within $seconds s - read the window for the error" -ForegroundColor Yellow
    return $false
}

$backendOk = Wait-For 'Backend  http://localhost:8000' 'http://localhost:8000/api/health'
$frontendOk = Wait-For 'Frontend http://localhost:5173' 'http://localhost:5173'

Write-Host ''
Write-Host 'Open  http://localhost:5173  in your browser.' -ForegroundColor Cyan
Write-Host 'To stop everything, close both PowerShell windows.' -ForegroundColor DarkGray
