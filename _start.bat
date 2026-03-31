@echo off
setlocal

set "NGROK_MODE=%~1"
if "%NGROK_MODE%"=="" set "NGROK_MODE=off"

set "PROJECT_ROOT=%~dp0"
if /I "%PROJECT_ROOT:~0,4%"=="\\?\" set "PROJECT_ROOT=%PROJECT_ROOT:~4%"
pushd "%PROJECT_ROOT%" >nul 2>&1
if errorlevel 1 (
  echo Falha ao acessar a pasta do projeto: "%PROJECT_ROOT%"
  exit /b 1
)

set "PYTHON_EXE=%PROJECT_ROOT%venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=C:\Python313\python.exe"
set "FALLBACK_PYTHON=C:\Python313\python.exe"
set "SHARED_SITE_PACKAGES=%APPDATA%\Python\Python313\site-packages"
set "REQUIRED_IMPORTS=import streamlit, dotenv, boto3, pandas, requests, PyPDF2, jinja2, markdown2, bcrypt, pydantic_settings"
set "REQUIRED_IMPORTS_WITH_SHARED=import site; site.addsitedir(r'%SHARED_SITE_PACKAGES%'); import streamlit, dotenv, boto3, pandas, requests, PyPDF2, jinja2, markdown2, bcrypt, pydantic_settings"
set "SBK_SHARED_SITE_PACKAGES="

if not exist "%PYTHON_EXE%" (
  echo Python nao encontrado em "%PYTHON_EXE%"
  popd >nul 2>&1
  exit /b 1
)

set "DD_TRACE_ENABLED=false"
set "DD_INSTRUMENTATION_TELEMETRY_ENABLED=false"

if /I "%NGROK_MODE%"=="on" set "USE_NGROK=1"
if /I "%NGROK_MODE%"=="off" set "USE_NGROK=0"

if not exist "%PROJECT_ROOT%requirements.txt" (
  echo requirements.txt nao encontrado em "%PROJECT_ROOT%"
  popd >nul 2>&1
  exit /b 1
)

"%PYTHON_EXE%" -c "%REQUIRED_IMPORTS%"
if errorlevel 1 (
  if exist "%SHARED_SITE_PACKAGES%" (
    "%PYTHON_EXE%" -c "%REQUIRED_IMPORTS_WITH_SHARED%"
    if not errorlevel 1 (
      echo Ambiente virtual incompleto. Reutilizando site-packages compartilhado: "%SHARED_SITE_PACKAGES%"
      set "SBK_SHARED_SITE_PACKAGES=%SHARED_SITE_PACKAGES%"
      goto start_app
    )
  )

  set "SBK_SHARED_SITE_PACKAGES="

  if /I not "%PYTHON_EXE%"=="%FALLBACK_PYTHON%" if exist "%FALLBACK_PYTHON%" (
    "%FALLBACK_PYTHON%" -c "%REQUIRED_IMPORTS%"
    if not errorlevel 1 (
      echo Ambiente virtual incompleto. Usando Python alternativo ja funcional: "%FALLBACK_PYTHON%"
      set "PYTHON_EXE=%FALLBACK_PYTHON%"
      goto start_app
    )
  )

  echo Dependencias ausentes no ambiente virtual. Instalando requirements.txt...
  "%PYTHON_EXE%" -m ensurepip --upgrade
  if errorlevel 1 (
    echo Falha ao preparar pip no ambiente Python.
    popd >nul 2>&1
    exit /b 1
  )

  "%PYTHON_EXE%" -m pip install -r "%PROJECT_ROOT%requirements.txt"
  if errorlevel 1 (
    echo Falha ao instalar as dependencias do projeto.
    popd >nul 2>&1
    exit /b 1
  )
)

:start_app
echo Inicializando aplicacao...
echo Python: %PYTHON_EXE%
echo Ngrok: %NGROK_MODE%

"%PYTHON_EXE%" main.py --ngrok %NGROK_MODE%
set "APP_EXIT=%errorlevel%"
popd >nul 2>&1
exit /b %APP_EXIT%
