@echo off
chcp 65001 >nul 2>&1

echo ============================================================
echo    UDZIALY BOT - Zatrzymywanie
echo ============================================================
echo.

:: Kill Python (bot process)
echo Zatrzymywanie bota (python.exe)...
tasklist /FI "IMAGENAME eq python.exe" 2>nul | find /I "python.exe" >nul
if not errorlevel 1 (
    taskkill /IM python.exe /F >nul 2>&1
    echo    OK - Bot zatrzymany
) else (
    echo    Bot nie byl uruchomiony
)

echo.

:: Kill Tor
echo Zatrzymywanie Tora (tor.exe)...
tasklist /FI "IMAGENAME eq tor.exe" 2>nul | find /I "tor.exe" >nul
if not errorlevel 1 (
    taskkill /IM tor.exe /F >nul 2>&1
    echo    OK - Tor zatrzymany
) else (
    echo    Tor nie byl uruchomiony
)

echo.
echo ============================================================
echo    Wszystko zatrzymane.
echo ============================================================
echo.
pause
