@echo off
chcp 65001 >nul
title iMSA Sentinel
cd /d "%~dp0"
if not exist .venv\Scripts\activate.bat (
  echo  Lancez d'abord INSTALLER.bat
  pause
  exit /b 1
)
call .venv\Scripts\activate.bat
cd backend
echo.
echo  iMSA Sentinel demarre : le navigateur va s'ouvrir automatiquement
echo  Laissez cette fenetre ouverte pendant l'utilisation. Fermez-la pour arreter.
echo.
python -m sentinel.cli serve
pause
