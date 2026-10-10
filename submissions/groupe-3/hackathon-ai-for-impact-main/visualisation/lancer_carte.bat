@echo off
cd /d "%~dp0carte"
start "" http://localhost:8765/
python -m http.server 8765
