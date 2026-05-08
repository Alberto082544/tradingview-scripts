@echo off
cd /d C:\Users\alber\tradingview-scripts\python\bot
start "BVortex Flask" /min cmd /c start_flask_watchdog.bat
timeout /t 3 /nobreak >nul
start "BVortex Ngrok" /min ngrok http --domain=shorter-urgent-moonstone.ngrok-free.dev 5000
timeout /t 2 /nobreak >nul
start "" "C:\Program Files\Capital Point Trading MT5 Terminal\terminal64.exe"
