@echo off
chcp 65001 > nul
title 経費管理システム
cd /d "%~dp0"

echo.
echo  ======================================
echo   経費管理システム 起動中...
echo  ======================================
echo.
echo  ブラウザで開く: http://localhost:5000
echo  停止するには Ctrl+C を押してください
echo.

"C:\Program Files\Python310\python.exe" app.py

echo.
echo サーバーが停止しました。
pause
