@echo off
chcp 65001 > nul

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ws = New-Object -ComObject WScript.Shell; ^
   $sc = $ws.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\経費管理システム.lnk'); ^
   $sc.TargetPath = '%~dp0start_server.bat'; ^
   $sc.WorkingDirectory = '%~dp0'; ^
   $sc.IconLocation = 'C:\Windows\System32\shell32.dll,13'; ^
   $sc.Description = '経費管理システムを起動する'; ^
   $sc.Save()"

echo.
echo デスクトップにショートカットを作成しました。
echo 「経費管理システム」をダブルクリックして起動してください。
echo.
pause
