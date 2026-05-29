@echo off
cd /d D:\5ITlearning\OPCUA
echo ===== OPC UA Demo Environment =====
echo.

:: 1. Mosquitto
sc query mosquitto | find "RUNNING" >nul
if %errorlevel% neq 0 (
    echo [1/6] Starting Mosquitto...
    net start mosquitto 2>nul || (
        echo [WARN] Mosquitto not found
    )
) else (
    echo [1/6] Mosquitto already running
)

:: 2. OPC UA Server
echo [2/6] Starting OPC UA Server...
start "OPCUA-Server" cmd /k "cd /d D:\5ITlearning\OPCUA && python src\opcua_server.py"
timeout /t 3 /nobreak >nul

:: 3. Web Dashboard
echo [3/6] Starting Web Dashboard...
start "Dashboard" cmd /k "cd /d D:\5ITlearning\OPCUA && python src\web_dashboard.py"
timeout /t 2 /nobreak >nul

:: 4. Config Editor
echo [4/6] Starting Config Editor...
start "ConfigEditor" cmd /k "cd /d D:\5ITlearning\OPCUA && python src\config_editor.py"

:: 5. Collector
echo [5/6] Starting Collector...
start "Collector" cmd /k "cd /d D:\5ITlearning\OPCUA && python src\collector.py"

:: 6. MQTT Bridge
echo [6/6] Starting MQTT Bridge...
start "Bridge" cmd /k "cd /d D:\5ITlearning\OPCUA && python src\opcua_mqtt_bridge.py"

echo.
echo ===== All services started =====
echo.
echo   OPC UA Server   - opc.tcp://localhost:4840
echo   Web Dashboard   - http://localhost:8080
echo   Config Editor   - http://localhost:8081
echo   Collector       - data to SQL Server
echo   MQTT Bridge     - OPC UA to MQTT on 1883
echo.
pause
