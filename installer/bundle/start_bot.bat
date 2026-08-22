@echo off
chcp 65001 >nul
echo ============================================
echo   Bot Udzialy - Uruchamianie
echo ============================================
echo.

cd /d "%~dp0"

echo [1/3] Uruchamianie Tor...
start "" /B "%~dp0tor\tor\tor.exe" -f "%~dp0tor\torrc"

echo Czekam na polaczenie Tor (port 9050)...
:wait_tor
timeout /t 2 /nobreak >nul
netstat -an | find "9050" | find "LISTENING" >nul
if errorlevel 1 goto wait_tor
echo Tor gotowy!

echo.
echo [2/3] Uruchamianie bota...
"%~dp0python\python.exe" -m bot.main

echo.
echo [3/3] Bot zakonczyl prace.
pause
