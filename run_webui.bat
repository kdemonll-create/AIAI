@echo off
call .venv\Scripts\activate.bat 2>nul
echo Starting Aegis Mind web interface...
echo Open http://127.0.0.1:8770 in your browser once it says "running".
python web_server.py
pause
