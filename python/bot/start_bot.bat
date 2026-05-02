@echo off
cd /d "%~dp0"
echo [BVortex Bot] Instalando dependencias...
pip install -r requirements_bot.txt -q
echo [BVortex Bot] Arrancando servidor...
python server.py
pause
