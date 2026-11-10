@echo off
chcp 65001 >nul
title Coletor de Estatisticas
cd /d "%~dp0"
set PYTHONUTF8=1

rem Procura o Python (o lançador "py" vem com o instalador oficial)
set "PY="
py -3 -c "import sys" >nul 2>&1 && set "PY=py -3"
if not defined PY python -c "import sys; sys.exit(0 if sys.version_info >= (3,8) else 1)" >nul 2>&1 && set "PY=python"

if not defined PY (
  echo.
  echo  O Python nao esta instalado neste computador.
  echo.
  echo  1. Vou abrir a pagina de download do Python.
  echo  2. Baixe e instale. Na primeira tela do instalador, MARQUE a opcao
  echo     "Add python.exe to PATH".
  echo  3. Depois, de duplo clique neste arquivo de novo.
  echo.
  start "" "https://www.python.org/downloads/"
  pause
  exit /b 1
)

%PY% coletor.py
echo.
pause
