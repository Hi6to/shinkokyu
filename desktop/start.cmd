@echo off
rem シン呼吸 デスクトップを起動する
rem Electron の本体が OneDrive の外にあれば、そちらを使う（OneDrive が大きなファイルを同期しないように）
set "ELECTRON_OVERRIDE_DIST_PATH=%USERPROFILE%\apps\shinkokyu-electron\node_modules\electron\dist"
if not exist "%ELECTRON_OVERRIDE_DIST_PATH%\electron.exe" set "ELECTRON_OVERRIDE_DIST_PATH="
cd /d "%~dp0"
npx electron .
