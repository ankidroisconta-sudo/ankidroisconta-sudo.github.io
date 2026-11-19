@echo off
chcp 65001 >nul
setlocal EnableExtensions
title Estudio Livre
cd /d "%~dp0"
echo ============================================
echo   ESTUDIO LIVRE - preparando tudo sozinho
echo ============================================
echo.

rem ---------- 1. Python ----------
call :temPython
if errorlevel 1 (
  echo [1/4] Python nao encontrado. Instalando pelo winget...
  where winget >nul 2>nul || goto semWinget
  winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
  call :recarregarPath
  call :temPython
  if errorlevel 1 (
    echo.
    echo O Python foi instalado, mas o Windows precisa reabrir esta janela.
    echo Feche esta janela e abra Iniciar.cmd de novo.
    pause & exit /b 1
  )
) else (
  echo [1/4] Python OK
)

rem ---------- 2. FFmpeg ----------
where ffmpeg >nul 2>nul && where ffprobe >nul 2>nul
if errorlevel 1 (
  echo [2/4] FFmpeg nao encontrado. Instalando pelo winget...
  where winget >nul 2>nul || goto semWinget
  winget install -e --id Gyan.FFmpeg --accept-package-agreements --accept-source-agreements
  call :recarregarPath
  where ffmpeg >nul 2>nul
  if errorlevel 1 (
    echo.
    echo O FFmpeg foi instalado, mas o Windows precisa reabrir esta janela.
    echo Feche esta janela e abra Iniciar.cmd de novo.
    pause & exit /b 1
  )
) else (
  echo [2/4] FFmpeg OK
)

rem ---------- 3. Ambiente Python ----------
if exist ".ambiente\Scripts\python.exe" (
  ".ambiente\Scripts\python.exe" -c "import sys" >nul 2>nul || rmdir /s /q ".ambiente"
)
if not exist ".ambiente\Scripts\python.exe" (
  echo [3/4] Criando o ambiente do estudio...
  %PY% -m venv .ambiente || (echo Nao foi possivel criar o ambiente Python. & pause & exit /b 1)
)
set "VPY=.ambiente\Scripts\python.exe"
"%VPY%" -c "import flask,PIL,requests,yt_dlp,numpy" >nul 2>nul
if errorlevel 1 (
  echo [3/4] Instalando componentes. Na primeira vez leva alguns minutos...
  "%VPY%" -m pip install --upgrade pip >nul 2>nul
  "%VPY%" -m pip install -r requirements.txt
  if errorlevel 1 (echo. & echo Falha ao instalar. Confira a internet e abra de novo. & pause & exit /b 1)
) else (
  echo [3/4] Componentes OK
)
rem Voz neural opcional: se falhar, o estudio usa a voz do Windows.
"%VPY%" -c "import piper" >nul 2>nul
if errorlevel 1 (
  echo       Instalando a voz neural em portugues - opcional...
  "%VPY%" -m pip install "piper-tts>=1.3,<2" >nul 2>nul || echo       Voz neural indisponivel neste PC. Sera usada a voz do Windows.
)
rem Mantem o baixador do YouTube atualizado, sem travar a abertura.
"%VPY%" -m pip install -q --upgrade yt-dlp >nul 2>nul

rem ---------- 4. Abrir ----------
echo [4/4] Abrindo o estudio no navegador...
echo.
"%VPY%" iniciar.py
if errorlevel 1 pause
exit /b 0

:temPython
set "PY="
where py >nul 2>nul && py -3 -c "import sys" >nul 2>nul && (set "PY=py -3" & exit /b 0)
where python >nul 2>nul && python -c "import sys; sys.exit(0 if sys.version_info>=(3,10) else 1)" >nul 2>nul && (set "PY=python" & exit /b 0)
exit /b 1

:recarregarPath
for /f "usebackq delims=" %%P in (`powershell -NoProfile -Command "[Environment]::GetEnvironmentVariable('Path','Machine')+';'+[Environment]::GetEnvironmentVariable('Path','User')"`) do set "PATH=%%P;%LOCALAPPDATA%\Microsoft\WinGet\Links;%PATH%"
exit /b 0

:semWinget
echo.
echo O instalador winget nao esta disponivel neste Windows.
echo Instale manualmente:
echo   Python 3.12: https://www.python.org/downloads/  (marque "Add python.exe to PATH")
echo   FFmpeg: https://www.gyan.dev/ffmpeg/builds/
echo Depois abra Iniciar.cmd de novo.
pause
exit /b 1
