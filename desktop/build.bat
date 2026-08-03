@echo off
rem Build the status_tools Windows executable with PyInstaller.
rem Output is written to D: to avoid filling the (smaller) C: drive.
setlocal
cd /d %~dp0

set DIST=D:\status_tools_dist
set WORK=D:\status_tools_build

echo Installing/updating dependencies...
python -m pip install -r requirements.txt
if errorlevel 1 goto :err

echo Building with PyInstaller (output: %DIST%\status_tools)...
python -m PyInstaller statustools.spec --noconfirm --clean --distpath "%DIST%" --workpath "%WORK%"
if errorlevel 1 goto :err

echo.
echo Done. Run:  %DIST%\status_tools\status_tools.exe
exit /b 0

:err
echo Build failed.
exit /b 1
