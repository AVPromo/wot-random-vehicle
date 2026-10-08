@echo off
rem ============================================================
rem  WOT Random Vehicle MOD - GUI installer
rem  Double-click this file to open the graphical installer.
rem ============================================================
setlocal
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
where pythonw >nul 2>&1
if not errorlevel 1 (
  start "" pythonw "%~dp0install_gui.py"
  exit /b 0
)
where python >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Python not found. Install Python and add it to PATH.
  pause
  exit /b 1
)
start "" python "%~dp0install_gui.py"
