param(
    [switch]$RecreateDb
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$backendPath = Join-Path $root "backend"
$simulatorPath = Join-Path $root "Smart-Gym\demo-simulator"
$visionPath = Join-Path $root "Smart-Gym\ai-vision"
$dashboardPath = Join-Path $root "Smart-Gym\web-dashboard"
$pidFile = Join-Path $PSScriptRoot ".smart-gym-pids.json"
$backendDb = Join-Path $backendPath "gym_iot.db"

function Test-CommandExists {
    param([string]$CommandName)
    return [bool](Get-Command $CommandName -ErrorAction SilentlyContinue)
}

function Get-PythonCommand {
    if (Test-CommandExists "py") {
        return "py -3"
    }
    if (Test-CommandExists "python") {
        return "python"
    }
    throw "Python was not found. Install Python 3.10+ and make sure 'py' or 'python' works in PowerShell."
}

function Start-WorkerWindow {
    param(
        [string]$Title,
        [string]$WorkingDirectory,
        [string]$Command
    )

    $escapedWorkdir = $WorkingDirectory.Replace("'", "''")
    $wrapped = @"
$Host.UI.RawUI.WindowTitle = '$Title'
Set-Location '$escapedWorkdir'
$Command
"@

    return Start-Process powershell `
        -ArgumentList @("-NoExit", "-Command", $wrapped) `
        -PassThru
}

if (-not (Test-Path $backendPath)) {
    throw "Could not find backend folder at $backendPath"
}

if (-not (Test-Path $simulatorPath)) {
    throw "Could not find simulator folder at $simulatorPath"
}

if (-not (Test-Path $visionPath)) {
    throw "Could not find AI vision folder at $visionPath"
}

if (-not (Test-Path $dashboardPath)) {
    throw "Could not find dashboard folder at $dashboardPath"
}

$python = Get-PythonCommand

if ($RecreateDb -and (Test-Path $backendDb)) {
    Remove-Item -LiteralPath $backendDb -Force
    Write-Host "Deleted existing database: $backendDb"
}

$workers = @()

$workers += [pscustomobject]@{
    Name = "backend"
    Process = Start-WorkerWindow `
        -Title "Smart Gym Backend" `
        -WorkingDirectory $backendPath `
        -Command "$python -m uvicorn main:app --reload"
}

$workers += [pscustomobject]@{
    Name = "simulator"
    Process = Start-WorkerWindow `
        -Title "Smart Gym Simulator" `
        -WorkingDirectory $simulatorPath `
        -Command "$python simulator.py"
}

$workers += [pscustomobject]@{
    Name = "ai-vision"
    Process = Start-WorkerWindow `
        -Title "Smart Gym AI Vision" `
        -WorkingDirectory $visionPath `
        -Command "$python main.py"
}

$workers += [pscustomobject]@{
    Name = "dashboard"
    Process = Start-WorkerWindow `
        -Title "Smart Gym Dashboard Server" `
        -WorkingDirectory $dashboardPath `
        -Command "$python -m http.server 8080"
}

$workers |
    Select-Object Name, @{Name="Pid"; Expression = { $_.Process.Id }} |
    ConvertTo-Json |
    Set-Content -LiteralPath $pidFile

Write-Host ""
Write-Host "Smart Gym controller started."
Write-Host "Backend:   http://localhost:8000"
Write-Host "Dashboard: http://localhost:8080"
Write-Host ""
Write-Host "Use controller\stop-smart-gym.ps1 to stop all launched windows."

