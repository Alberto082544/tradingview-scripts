@echo off
cd /d C:\Users\alber\tradingview-scripts\python\bot
echo [%date% %time%] Watchdog iniciado >> flask.log

:restart
echo [%date% %time%] Arrancando Flask... >> flask.log
python server.py >> flask.log 2>&1
echo [%date% %time%] Flask se ha caido. Reiniciando en 5 segundos... >> flask.log
timeout /t 5 /nobreak >nul
goto restart
