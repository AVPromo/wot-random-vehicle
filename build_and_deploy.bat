@echo off
rem ============================================================
rem  WOT Random Vehicle MOD - build and install
rem  Double-click to compile (.pyc) + package (.wotmod) + install.
rem  Args (optional): --version x.y.z.w --game-root "path"
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
python "%~dp0build_wotmod.py" --deploy %*
if errorlevel 1 (
  echo.
  echo [FAILED] See messages above.
) else (
  echo.
  echo [OK] Build + install done. Restart the game and press F11 in the garage.
)
echo.
pause
