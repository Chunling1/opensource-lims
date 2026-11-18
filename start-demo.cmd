@echo off
setlocal
cd /d "%~dp0"
set "LIMS_DATABASE_URL="
set "LIMS_INSTANCE=%~dp0instance"
if not exist ".venv\Scripts\python.exe" (
  py -3.10 -m venv .venv
  if errorlevel 1 goto failed
)
".venv\Scripts\python.exe" -m pip --disable-pip-version-check install --no-index --find-links wheels -r requirements.txt
if errorlevel 1 goto failed
".venv\Scripts\python.exe" manage.py upgrade
if errorlevel 1 goto failed
".venv\Scripts\python.exe" manage.py seed-demo
if errorlevel 1 goto failed
echo Open http://127.0.0.1:8878/ in your browser. Press Ctrl+C to stop.
".venv\Scripts\python.exe" manage.py serve --port 8878
if errorlevel 1 goto failed
exit /b 0
:failed
echo Startup failed. See the message above. The offline demo requires Windows x64 and Python 3.10.
pause
exit /b 1
