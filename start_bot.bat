@echo off
REM =============================================================================
REM Udzialy Bot — Launcher
REM =============================================================================
setlocal

echo.
echo  Udzialy Bot — Start
echo  ===================
echo.

REM --- Activate venv ---
if not exist .venv\Scripts\activate.bat (
    echo [BLAD] Brak srodowiska wirtualnego! Uruchom najpierw install.bat
    pause
    exit /b 1
)
call .venv\Scripts\activate.bat

REM --- Start Tor in background ---
if exist tor\tor.exe (
    echo [*] Uruchamiam Tor...
    start /b "" tor\tor.exe --SocksPort 9050 --ControlPort 9051 --HashedControlPassword 16:00000000000000000000000000000000000000000000000000000000 >nul 2>&1
    timeout /t 3 /nobreak >nul
    echo [+] Tor uruchomiony (SOCKS5 :9050)
) else (
    echo [!] Tor nie znaleziony — dzialanie bez proxy
)

REM --- Start bot ---
echo [*] Uruchamiam bota...
echo.
python -m bot.main

REM --- Cleanup on exit ---
echo.
echo [*] Zatrzymywanie...
taskkill /f /im tor.exe >nul 2>&1
echo [+] Zamknieto.
pause
