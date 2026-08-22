@echo off
chcp 65001 >nul
echo ============================================
echo   Bot Udzialy - Zatrzymywanie
echo ============================================
echo.

echo Zatrzymywanie procesow bota...
wmic process where "CommandLine like '%%bot.main%%'" call terminate >nul 2>&1
echo Zatrzymywanie Tor...
taskkill /f /im tor.exe >nul 2>&1

echo.
echo Wszystkie procesy zatrzymane.
timeout /t 3
