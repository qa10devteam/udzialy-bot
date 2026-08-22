@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo ============================================================
echo   Udzialy Bot - Konfiguracja srodowiska
echo   (c) QA10 sp. z o.o.
echo ============================================================
echo.

REM ============================================================
REM Step 1: Create virtual environment from embedded Python
REM ============================================================
echo [1/5] Tworzenie srodowiska wirtualnego...

if exist ".venv" (
    echo   Srodowisko juz istnieje - pomijam.
    goto :install_pip
)

python\python.exe -m venv .venv
if errorlevel 1 (
    echo [BLAD] Nie udalo sie utworzyc srodowiska wirtualnego!
    echo   Sprobuj usunac folder .venv i uruchom ponownie.
    pause
    exit /b 1
)
echo   [OK] Srodowisko utworzone.

REM ============================================================
REM Step 2: Bootstrap pip in venv
REM ============================================================
:install_pip
echo.
echo [2/5] Instalowanie pip...

.venv\Scripts\python.exe python\get-pip.py --no-warn-script-location -q 2>nul
if errorlevel 1 (
    echo   [UWAGA] get-pip.py nie powiodl sie, probuje alternatywna metode...
    .venv\Scripts\python.exe -m ensurepip --upgrade -q 2>nul
)
echo   [OK] pip zainstalowany.

REM ============================================================
REM Step 3: Install wheels from local directory
REM ============================================================
echo.
echo [3/5] Instalowanie bibliotek Python (offline)...

if exist "wheels\*.whl" (
    .venv\Scripts\pip.exe install --no-index --find-links=wheels\ wheels\*.whl -q 2>nul
    if errorlevel 1 (
        echo   [UWAGA] Niektore pakiety nie zainstalowaly sie offline.
        echo   Probuje instalacje online dla brakujacych...
        .venv\Scripts\pip.exe install --find-links=wheels\ -r app\requirements.txt -q 2>nul
    )
) else (
    echo   Brak plikow .whl - instalacja online...
    .venv\Scripts\pip.exe install -r app\requirements.txt -q
)

REM Install binary packages that may not be bundled (too platform-specific)
echo   Instalowanie pakietow binarnych (online)...
.venv\Scripts\pip.exe install curl_cffi>=0.7 selectolax>=0.3 patchright>=1.0 -q 2>nul
if errorlevel 1 (
    echo   [UWAGA] Niektorych pakietow binarnych nie udalo sie zainstalowac.
    echo   Bot moze dzialac z ograniczona funkcjonalnoscia.
)

echo   [OK] Biblioteki zainstalowane.

REM ============================================================
REM Step 4: Download Patchright Chromium browser
REM ============================================================
echo.
echo [4/5] Pobieranie przegladarki Chromium (ok. 280 MB)...
echo   To moze potrwac kilka minut...

.venv\Scripts\python.exe -m patchright install chromium
if errorlevel 1 (
    echo   [UWAGA] Nie udalo sie pobrac Chromium.
    echo   Sprawdz polaczenie z internetem i uruchom ponownie setup_env.bat
) else (
    echo   [OK] Chromium zainstalowany.
)

REM ============================================================
REM Step 5: Launch configuration wizard
REM ============================================================
echo.
echo [5/5] Uruchamianie kreatora konfiguracji...

if exist "config.yaml" (
    echo   Konfiguracja juz istnieje. Pomijam kreator.
    echo.
    echo ============================================================
    echo   INSTALACJA ZAKONCZONA POMYSLNIE!
    echo   Uruchom bota za pomoca: start_bot.bat
    echo ============================================================
    pause
    exit /b 0
)

REM Launch config wizard (GUI - .pyw runs with pythonw.exe)
if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" "config_wizard.pyw"
) else (
    start "" "python\pythonw.exe" "config_wizard.pyw"
)

echo.
echo ============================================================
echo   INSTALACJA ZAKONCZONA!
echo   1. Skonfiguruj bota w oknie kreatora
echo   2. Uruchom: start_bot.bat
echo ============================================================
echo.
pause
exit /b 0
