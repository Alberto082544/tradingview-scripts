$LogFile = "C:\Users\alber\tradingview-scripts\bot_startup.log"
$Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

function Log($msg) {
    "$Timestamp — $msg" | Add-Content $LogFile
}

Log "=== Iniciando BVortex Bot ==="

# Ngrok
if (-not (Get-Process ngrok -ErrorAction SilentlyContinue)) {
    Start-Process -FilePath "ngrok" `
        -ArgumentList "http --domain=shorter-urgent-moonstone.ngrok-free.dev 5000" `
        -WindowStyle Hidden
    Start-Sleep -Seconds 3
    if (Get-Process ngrok -ErrorAction SilentlyContinue) {
        Log "ngrok arrancado OK"
    } else {
        Log "ERROR: ngrok no arranco"
    }
} else {
    Log "ngrok ya estaba corriendo"
}

# Flask bot
$flaskRunning = $false
try {
    $r = Invoke-WebRequest -Uri "http://localhost:5000" -TimeoutSec 2 -ErrorAction Stop
    $flaskRunning = $true
} catch {
    if ($_.Exception.Response) { $flaskRunning = $true }
}

if (-not $flaskRunning) {
    Start-Process -FilePath "python" `
        -ArgumentList "C:\Users\alber\tradingview-scripts\python\bot\server.py" `
        -WindowStyle Hidden `
        -RedirectStandardOutput "C:\Users\alber\tradingview-scripts\flask_stdout.log" `
        -RedirectStandardError "C:\Users\alber\tradingview-scripts\flask_stderr.log"
    Start-Sleep -Seconds 5
    try {
        Invoke-WebRequest -Uri "http://localhost:5000" -TimeoutSec 3 -ErrorAction Stop | Out-Null
        Log "Flask arrancado OK"
    } catch {
        if ($_.Exception.Response) {
            Log "Flask arrancado OK"
        } else {
            Log "ERROR: Flask no responde — ver flask_stderr.log"
        }
    }
} else {
    Log "Flask ya estaba corriendo"
}

Log "=== Arranque completado ==="
