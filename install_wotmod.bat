@echo off
rem ============================================================
rem  WOT Random Vehicle MOD - one-click install
rem  Double-click this file to install the pre-built mod.
rem  Args (optional): --game-root "path" --version x.y.z.w
rem ============================================================
setlocal
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
where python >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Python not found. Install Python and add it to PATH.
  pause
  exit /b 1
)
python "%~dp0install_wotmod.py" %*
if errorlevel 1 (
  echo.
  echo [FAILED] See messages above.
) else (
  echo.
  echo [OK] Done. Restart the game and press F11 in the garage.
)
echo.
pause
