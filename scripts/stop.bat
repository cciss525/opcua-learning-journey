@echo off
echo Stopping all services...
taskkill /F /IM python3.13.exe >nul 2>&1
echo Done.
pause
