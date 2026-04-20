@echo off
chcp 65001 > nul
title 経費管理システム
cd /d "%~dp0"

for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /C:"IPv4"') do (
    set LOCAL_IP=%%a
    goto :found
)
:found
set LOCAL_IP=%LOCAL_IP: =%

echo.
echo  ======================================
echo   経費管理システム 起動中...
echo  ======================================
echo.
echo  このPC:     http://localhost:5000
echo  他のPCから: http://%LOCAL_IP%:5000
echo.
echo  停止するには Ctrl+C を押してください
echo.

py -3 app.py

echo.
echo サーバーが停止しました。
pause
