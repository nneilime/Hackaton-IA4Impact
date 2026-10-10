@echo off
chcp 65001 >nul
title iMSA Sentinel - installation
cd /d "%~dp0"
echo.
echo  === iMSA Sentinel : installation (a faire une seule fois) ===
echo.
set PY=
where py >nul 2>nul && (py -3.12 --version >nul 2>nul && set PY=py -3.12)
if "%PY%"=="" (where py >nul 2>nul && set PY=py -3)
if "%PY%"=="" (where python >nul 2>nul && set PY=python)
if "%PY%"=="" (
  echo  Python est introuvable.
  echo  Installez Python 3.12 depuis https://www.python.org/downloads/
  echo  en cochant "Add python.exe to PATH", puis relancez INSTALLER.bat
  pause
  exit /b 1
)
echo  Python utilise : %PY%
%PY% --version
if not exist .venv (
  echo  Creation de l'environnement isole .venv ...
  %PY% -m venv .venv || (echo Echec de creation de l'environnement & pause & exit /b 1)
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt || (echo. & echo  L'installation des bibliotheques a echoue. Verifiez la connexion Internet. & pause & exit /b 1)
echo.
echo  === Second moteur OCR (Tesseract) : recommande pour une double lecture fiable ===
if exist "C:\Program Files\Tesseract-OCR\tesseract.exe" (
  echo  Tesseract est deja installe.
) else (
  where winget >nul 2>nul && (
    echo  Installation de Tesseract-OCR via winget ...
    winget install -e --id UB-Mannheim.TesseractOCR --accept-source-agreements --accept-package-agreements --silent
  ) || (
    echo  winget indisponible : installez Tesseract manuellement depuis
    echo  https://github.com/UB-Mannheim/tesseract/wiki  ^(installateur Windows^)
  )
)
echo.
echo  Installation terminee. Lancez maintenant LANCER.bat
echo.
pause
