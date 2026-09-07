@echo off
set STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%STARTUP%\JARVIS.lnk'); $s.TargetPath = 'D:\JARVIS\dist\JARVIS.exe'; $s.WorkingDirectory = 'D:\JARVIS\dist'; $s.Save()"
echo JARVIS startup shortcut installed.
pause
