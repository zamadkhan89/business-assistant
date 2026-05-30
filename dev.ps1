<#
.SYNOPSIS
    Dev environment control for the Business Assistant.

.DESCRIPTION
    Starts/stops the FastAPI backend (port 8000) and Next.js frontend (port 3000)
    in separate PowerShell windows. Stopping is port-based — only processes
    listening on 8000 or 3000 are killed.

.EXAMPLE
    .\dev.ps1          # start both (default)
    .\dev.ps1 start    # start both
    .\dev.ps1 stop     # stop both
    .\dev.ps1 restart  # stop then start
    .\dev.ps1 status   # show what is running
#>

param(
    [Parameter(Position = 0)]
    [ValidateSet("start", "stop", "restart", "status")]
    [string]$Command = "start"
)

$ROOT = $PSScriptRoot

# ── helpers ──────────────────────────────────────────────────────────────────

function Get-PidsOnPort([int]$Port) {
    # Get-NetTCPConnection -State Listen is reliable but can return Windows/Hyper-V
    # system sockets with OwningProcess = 0 or 4 that have no real process behind them.
    # We filter those out and confirm the PID is a live user process.
    Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess |
        Where-Object { $_ -gt 4 -and (Get-Process -Id $_ -ErrorAction SilentlyContinue) } |
        Sort-Object -Unique
}

function Stop-Port([int]$Port, [string]$Label) {  # approved verb: Stop
    $pids = Get-PidsOnPort $Port
    if ($pids) {
        Write-Host "  Stopping $Label (port $Port, PIDs: $($pids -join ', '))..." -ForegroundColor Yellow
        foreach ($p in $pids) {
            # /T kills the entire process tree (parent + all spawned children).
            # Needed because uvicorn --reload and Next.js both spawn child workers,
            # and Next.js binds on both IPv4 and IPv6, producing multiple PIDs.
            taskkill /F /T /PID $p 2>$null | Out-Null
        }
        Write-Host "  $Label stopped." -ForegroundColor Gray
    } else {
        Write-Host "  $Label not running on port $Port." -ForegroundColor Gray
    }
}

# ── commands ─────────────────────────────────────────────────────────────────

function Start-Services {
    Write-Host ""
    Write-Host "  Starting Business Assistant..." -ForegroundColor Cyan
    Write-Host ""

    # Backend
    $backendCmd = "Set-Location '$ROOT\backend'; .venv\Scripts\Activate.ps1; uvicorn app.main:app --reload --port 8000"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCmd

    # Give backend a moment before opening the frontend window
    Start-Sleep -Seconds 1

    # Frontend
    $frontendCmd = "Set-Location '$ROOT\frontend'; npm run dev"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendCmd

    Write-Host "  Two new terminal windows have opened." -ForegroundColor Green
    Write-Host ""
    Write-Host "  Backend  → http://localhost:8000  (wait for 'Application startup complete')" -ForegroundColor White
    Write-Host "  Frontend → http://localhost:3001  (wait for 'Local: http://localhost:3001')" -ForegroundColor White
    Write-Host ""
    Write-Host "  Once both windows are ready, open http://localhost:3001 in your browser." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  To stop:  .\dev.ps1 stop" -ForegroundColor DarkGray
    Write-Host ""
}

function Stop-Services {
    Write-Host ""
    Write-Host "  Stopping Business Assistant..." -ForegroundColor Cyan
    Stop-Port 8000 "Backend (uvicorn)"
    Stop-Port 3001 "Frontend (Next.js)"
    Write-Host ""
    Write-Host "  All services stopped." -ForegroundColor Green
    Write-Host ""
}

function Show-Status {
    Write-Host ""
    Write-Host "  Service status:" -ForegroundColor Cyan
    Write-Host ""

    foreach ($entry in @(@{Port=8000; Label="Backend  (uvicorn) "}, @{Port=3001; Label="Frontend (Next.js) "})) {
        $pids = Get-PidsOnPort $entry.Port
        if ($pids) {
            Write-Host "  $($entry.Label)  port $($entry.Port)  RUNNING  [PID $($pids -join ', ')]" -ForegroundColor Green
        } else {
            Write-Host "  $($entry.Label)  port $($entry.Port)  STOPPED" -ForegroundColor Red
        }
    }

    Write-Host ""

    # Quick health check if backend is up
    if (Get-PidsOnPort 8000) {
        try {
            $health = Invoke-RestMethod "http://localhost:8000/health" -TimeoutSec 3
            Write-Host "  Health check: $($health.status)" -ForegroundColor Green
        } catch {
            Write-Host "  Health check: unreachable (still starting?)" -ForegroundColor Yellow
        }
    }

    Write-Host ""
}

# ── dispatch ─────────────────────────────────────────────────────────────────

switch ($Command) {
    "start"   { Start-Services }
    "stop"    { Stop-Services }
    "restart" { Stop-Services; Start-Sleep -Seconds 2; Start-Services }
    "status"  { Show-Status }
}
