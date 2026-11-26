# J.A.R.V.I.S. Desktop Background Launcher (PowerShell)
# Silently launches FastAPI backend and PySide6 Desktop AI Bubble with zero console windows.

param(
    [int]$Port = 8000,
    [string]$BackendHost = "127.0.0.1"
)

$RootDir = $PSScriptRoot
Set-Location $RootDir

# 1. Locate pythonw.exe and python.exe in .venv or system PATH
$Pythonw = Join-Path $RootDir ".venv\Scripts\pythonw.exe"
if (-not (Test-Path $Pythonw)) {
    $Pythonw = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source
}
if (-not $Pythonw) {
    $Pythonw = Join-Path $RootDir ".venv\Scripts\python.exe"
    if (-not (Test-Path $Pythonw)) {
        $Pythonw = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
    }
}

# 2. Check if backend port is already open
function Test-PortOpen([string]$HostName, [int]$CheckPort) {
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $asyncResult = $client.BeginConnect($HostName, $CheckPort, $null, $null)
        $wait = $asyncResult.AsyncWaitHandle.WaitOne(400, $false)
        if ($wait -and $client.Connected) {
            $client.EndConnect($asyncResult)
            $client.Close()
            return $true
        }
        $client.Close()
        return $false
    } catch {
        return $false
    }
}

$port8000Active = Test-PortOpen $BackendHost 8000
$port8765Active = Test-PortOpen $BackendHost 8765

$targetUrl = "http://localhost:$Port"

if (-not $port8000Active -and -not $port8765Active) {
    # 3. Start FastAPI server silently in background with pythonw
    $serverArgs = "server.py --port $Port --host $BackendHost"
    Start-Process -FilePath $Pythonw -ArgumentList $serverArgs -WorkingDirectory $RootDir -WindowStyle Hidden

    # 4. Wait for /health endpoint to return 200 OK (up to 15 seconds)
    $deadline = (Get-Date).AddSeconds(15)
    $serverReady = $false
    while ((Get-Date) -lt $deadline) {
        try {
            $res = Invoke-RestMethod -Uri "http://$BackendHost`:$Port/health" -TimeoutSec 1 -ErrorAction Stop
            if ($res.status -eq "ok" -or $res.online -eq $true) {
                $serverReady = $true
                break
            }
        } catch {
            Start-Sleep -Milliseconds 400
        }
    }
    $targetUrl = "http://localhost:$Port"
} elseif ($port8000Active) {
    $targetUrl = "http://localhost:8000"
} elseif ($port8765Active) {
    $targetUrl = "http://localhost:8765"
}

# 5. Launch PySide6 Desktop AI Bubble with zero console windows
$bubbleArgs = "desktop_bubble\main.py --url $targetUrl"
Start-Process -FilePath $Pythonw -ArgumentList $bubbleArgs -WorkingDirectory $RootDir -WindowStyle Hidden
