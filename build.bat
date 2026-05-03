@echo off
rem ============================================================
rem  MacPlayer — Windows Build Script
rem  Produces: dist\MacPlayer\MacPlayer.exe
rem            dist\MacPlayer-windows.zip
rem ============================================================
setlocal EnableDelayedExpansion

echo.
echo  ╔══════════════════════════════════╗
echo  ║   MacPlayer Build  (Windows)     ║
echo  ╚══════════════════════════════════╝
echo.

rem ── 1. Sanity checks ─────────────────────────────────────
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Install from https://python.org
    exit /b 1
)

set PYTHON=python
if exist ".venv\Scripts\python.exe" (
    set PYTHON=.venv\Scripts\python.exe
    echo -- Using virtualenv: .venv
)

rem ── 2. Install build dependencies ────────────────────────
echo -- Installing build dependencies...
%PYTHON% -m pip install --quiet --upgrade pyinstaller pyinstaller-hooks-contrib Pillow
if %errorlevel% neq 0 ( echo [ERROR] pip install failed & exit /b 1 )

rem ── 3. Generate icons ────────────────────────────────────
echo -- Generating icons...
%PYTHON% create_icon.py
if %errorlevel% neq 0 ( echo [ERROR] Icon generation failed & exit /b 1 )

rem ── 4. Clean previous build ──────────────────────────────
echo -- Cleaning previous build...
if exist build  rmdir /s /q build
if exist dist   rmdir /s /q dist

rem ── 5. PyInstaller ───────────────────────────────────────
echo -- Building MacPlayer.exe...
%PYTHON% -m PyInstaller MacPlayer.spec --noconfirm
if %errorlevel% neq 0 ( echo [ERROR] PyInstaller failed & exit /b 1 )

echo.
echo [OK] Build complete: dist\MacPlayer\MacPlayer.exe
echo.

rem ── 6. ZIP archive ───────────────────────────────────────
echo -- Creating ZIP archive...
powershell -NoProfile -Command ^
    "Compress-Archive -Path 'dist\MacPlayer\*' -DestinationPath 'dist\MacPlayer-windows.zip' -Force"

if %errorlevel% equ 0 (
    echo [OK] Archive ready: dist\MacPlayer-windows.zip
) else (
    echo [WARN] ZIP creation failed - distribute the dist\MacPlayer folder manually
)

echo.
echo  NOTE: VLC must be installed on the target machine.
echo        Download: https://www.videolan.org/vlc/
echo.
