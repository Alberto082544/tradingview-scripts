@echo off
REM Revisa comunidades trading 3 veces/semana
REM Programar con Task Scheduler de Windows: lunes/miercoles/viernes a las 8:00

cd /d C:\Users\alber\tradingview-scripts\python
set PYTHONIOENCODING=utf-8
python monitor\check_communities.py --save --hours 72

REM Mantener ventana abierta 5s para ver output (opcional, quitar si molesta)
timeout /t 5 /nobreak >nul
