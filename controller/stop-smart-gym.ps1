$ErrorActionPreference = "Stop"

$pidFile = Join-Path $PSScriptRoot ".smart-gym-pids.json"

if (-not (Test-Path $pidFile)) {
    Write-Host "No controller PID file found. Nothing to stop."
    exit 0
}

$workers = Get-Content -LiteralPath $pidFile | ConvertFrom-Json

foreach ($worker in $workers) {
    try {
        $process = Get-Process -Id $worker.Pid -ErrorAction Stop
        Stop-Process -Id $process.Id -Force
        Write-Host "Stopped $($worker.Name) (PID $($worker.Pid))"
    } catch {
        Write-Host "Process already stopped for $($worker.Name) (PID $($worker.Pid))"
    }
}

Remove-Item -LiteralPath $pidFile -Force
Write-Host "Smart Gym controller shutdown complete."

