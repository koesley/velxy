@echo off
setlocal
cd /d "%~dp0"
py -3 -m venv .build-venv
if errorlevel 1 goto failed
call .build-venv\Scripts\activate.bat
python -m pip install "pyinstaller>=6,<7" "pywebview>=5,<7"
if errorlevel 1 goto failed
python -m unittest test_desktop_maintenance test_desktop_entry -q
if errorlevel 1 goto failed
python build_windows.py
if errorlevel 1 goto failed
dist\VELXTRIA-Desktop\VELXTRIA-Desktop.exe --smoke-test
if errorlevel 1 goto failed
where iscc >nul 2>nul
if not errorlevel 1 (
  iscc installer\VELXTRIA.iss
) else (
  echo Inno Setup 6 not found. Desktop folder built; install Inno Setup to build Setup.exe.
)
echo Build finished. See dist\VELXTRIA-Desktop
pause
exit /b 0
:failed
echo Build failed.
pause
exit /b 1
