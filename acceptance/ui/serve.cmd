@echo off
rem UI acceptance server: temp instance + demo seed on port 8899. Arg1 = instance dir; optional LIMS_DATABASE_URL.
setlocal
cd /d "%~dp0..\.."
set "LIMS_INSTANCE=%~1"
".venv\Scripts\python.exe" manage.py upgrade || exit /b 1
".venv\Scripts\python.exe" manage.py seed-demo || exit /b 1
".venv\Scripts\python.exe" manage.py serve --port 8899
