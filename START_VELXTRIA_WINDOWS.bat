@echo off
setlocal
cd /d "%~dp0velxy-main"
where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  py -3 launch_velxtria.py
  goto done
)
where python >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  python launch_velxtria.py
  goto done
)
echo Python 3 is required for this edition. Install Python from https://www.python.org/downloads/
echo Check "Add python.exe to PATH" during installation, then double-click this file again.
:done
if errorlevel 1 pause
