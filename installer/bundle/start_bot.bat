@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>nul

echo  ============================================
echo   Bot Udzialy - Uruchamianie
echo  ============================================
echo.

set "BASE=%~dp0"
if "%BASE:~-1%"=="\" set "BASE=%BASE:~0,-1%"

:: Check Python
if not exist "%BASE%\python\python.exe" (
    echo  BLAD: Python nie zainstalowany.
    echo  Uruchom najpierw setup_env.bat
    pause
    exit /b 1
)

:: Check config
if not exist "%BASE%\config.yaml" (
    echo  BLAD: Brak pliku konfiguracji.
    echo  Uruchom setup_env.bat lub launcher.
    pause
    exit /b 1
)

echo [1/3] Uruchamianie Tor...
start "" /B "%BASE%\tor\tor\tor.exe" -f "%BASE%\tor\torrc"

echo       Czekam na polaczenie Tor (port 9050)...
set /a ATTEMPTS=0
:wait_tor
timeout /t 2 /nobreak >nul
set /a ATTEMPTS+=1
netstat -an 2>nul | find "9050" | find "LISTENING" >nul
if errorlevel 1 (
    if !ATTEMPTS! GEQ 30 (
        echo  BLAD: Tor nie uruchomil sie w 60 sekund.
        echo  Sprawdz czy firewall nie blokuje tor.exe
        pause
        exit /b 1
    )
    goto wait_tor
)
echo       Tor gotowy!

echo.
echo [2/3] Uruchamianie bota...
"%BASE%\python\python.exe" -m bot.main

echo.
echo [3/3] Bot zakonczyl prace.
pause
