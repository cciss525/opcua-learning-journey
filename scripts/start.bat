@echo off
chcp 65001 >nul
echo ===== OPC UA Demo Environment =====
echo.

:: 1. Mosquitto (check if running)
sc query mosquitto | find "RUNNING" >nul
if %errorlevel% neq 0 (
    echo [1/4] Starting Mosquitto...
    net start mosquitto 2>nul || (
        echo [WARN] Mosquitto service not found. MQTT bridge will not work.
    )
) else (
    echo [1/4] Mosquitto already running
)

:: 2. OPC UA Server
echo [2/4] Starting OPC UA Server...
start "OPCUA-Server" cmd /k "cd /d D:\5ITlearning\OPCUA && python src\opcua_server.py"

:: Wait for server to be ready
timeout /t 4 /nobreak >nul

:: 3. MQTT Bridge
echo [3/4] Starting OPC UA -> MQTT Bridge...
start "Bridge" cmd /k "cd /d D:\5ITlearning\OPCUA && python src\opcua_mqtt_bridge.py"

:: 4. Web Dashboard
echo [4/4] Starting Web Dashboard...
start "Dashboard" cmd /k "cd /d D:\5ITlearning\OPCUA && python src\web_dashboard.py"

echo.
echo ===== All services started =====
echo.
echo   OPC UA Server  - opc.tcp://localhost:4840
echo   MQTT Bridge    - OPC UA -> MQTT on localhost:1883
echo   Web Dashboard  - http://localhost:8080
echo.
echo Test MQTT:   mosquitto_sub -t "factory/#" -v
echo Open browser: http://localhost:8080
echo.
pause
