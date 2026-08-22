@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

echo ============================================================
echo    UDZIALY BOT - Uruchamianie
echo ============================================================
echo.

:: Check if installed
if not exist .venv\Scripts\python.exe (
    echo [BLAD] Bot nie jest zainstalowany!
    echo Uruchom najpierw: install.bat
    pause
    exit /b 1
)

if not exist config.yaml (
    echo [BLAD] Brak pliku konfiguracyjnego config.yaml!
    echo Uruchom najpierw: install.bat
    pause
    exit /b 1
)

:: ============================================================
:: Uruchamianie Tora
:: ============================================================
echo [1/3] Uruchamianie Tora...

:: Check if Tor is already running
tasklist /FI "IMAGENAME eq tor.exe" 2>nul | find /I "tor.exe" >nul
if not errorlevel 1 (
    echo    Tor juz dziala.
    goto :tor_ready
)

if not exist tor\tor.exe (
    echo [BLAD] Nie znaleziono tor\tor.exe!
    echo Uruchom install.bat aby pobrac Tora.
    pause
    exit /b 1
)

:: Ensure data directory exists
if not exist tor\data mkdir tor\data

:: Start Tor in background
start /B "" tor\tor.exe -f tor\torrc >tor\tor.log 2>&1

:: Wait for Tor to be ready (check SOCKS port 9050)
echo    Czekam na polaczenie Tora z siecia...
set TOR_READY=0
for /L %%i in (1,1,60) do (
    if !TOR_READY!==0 (
        timeout /t 2 /nobreak >nul
        powershell -Command "& { try { $c = New-Object System.Net.Sockets.TcpClient('127.0.0.1', 9050); $c.Close(); exit 0 } catch { exit 1 } }" >nul 2>&1
        if not errorlevel 1 (
            set TOR_READY=1
            echo    OK - Tor gotowy ^(port 9050^)
        ) else (
            <nul set /p "=."
        )
    )
)

if !TOR_READY!==0 (
    echo.
    echo [BLAD] Tor nie uruchomil sie w ciagu 120 sekund!
    echo Sprawdz plik tor\tor.log
    echo.
    echo Mozliwe przyczyny:
    echo   - Firewall blokuje polaczenie
    echo   - Antywirus blokuje tor.exe
    echo   - Port 9050 jest zajety przez inny program
    echo.
    taskkill /IM tor.exe /F >nul 2>&1
    pause
    exit /b 1
)

:tor_ready
echo.

:: ============================================================
:: Uruchamianie bota
:: ============================================================
echo [2/3] Aktywacja srodowiska Python...
call .venv\Scripts\activate.bat
echo    OK
echo.

echo [3/3] Uruchamianie bota...
echo ============================================================
echo    Bot uruchomiony! Uzyj Ctrl+C aby zatrzymac.
echo    Logi: bot.log
echo ============================================================
echo.

:: Run bot (Ctrl+C will break out of this)
python -m bot.main

:: ============================================================
:: Zamykanie (po Ctrl+C lub zakonczeniu)
:: ============================================================
echo.
echo ============================================================
echo    Zamykanie...
echo ============================================================

:: Kill Tor gracefully
echo Zatrzymywanie Tora...
taskkill /IM tor.exe /F >nul 2>&1

echo.
echo Bot zatrzymany. Do zobaczenia!
echo.
pause
