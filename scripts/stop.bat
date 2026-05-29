@echo off
echo Stopping all Python services...
taskkill /F /IM python3.13.exe >nul 2>&1
echo Python services stopped.
echo.
echo Mosquitto still running. Stop with: net stop mosquitto
pause
