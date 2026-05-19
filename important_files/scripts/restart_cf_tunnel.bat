@echo off
REM Restart Cloudflare Tunnel for ai.appsscale.com/automationtest
REM This script restarts the tunnel to pick up new configuration

echo ============================================================
echo   Restarting Cloudflare Tunnel
echo ============================================================
echo.

REM Kill existing cloudflared processes
echo [1/3] Stopping existing tunnel...
taskkill /F /IM cloudflared.exe 2>nul
timeout /t 2 /nobreak >nul

REM Start tunnel with updated config
echo [2/3] Starting tunnel with new configuration...
start "" "C:\Users\appsf\AppData\Local\cloudflared\cloudflared-windows-amd64.exe" tunnel run --config C:\Users\appsf\.cloudflared\config.yml

REM Wait for tunnel to start
echo [3/3] Waiting for tunnel to initialize...
timeout /t 5 /nobreak >nul

echo.
echo ============================================================
echo   Tunnel Restarted!
echo ============================================================
echo.
echo Access the automation chat at:
echo   https://ai.appsscale.com/automationtest/
echo.
echo To view tunnel status, visit:
echo   https://dash.cloudflare.com/
echo.
pause
