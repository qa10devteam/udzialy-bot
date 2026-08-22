@echo off
chcp 65001 >nul
echo ============================================
echo   Bot Udzialy - Instalacja zaleznosci
echo ============================================
echo.

cd /d "%~dp0"

echo [1/3] Instalowanie pakietow Python...
python\python.exe -m pip install --upgrade pip -q 2>nul
python\python.exe -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo BLAD: Nie udalo sie zainstalowac pakietow.
    echo Sprawdz polaczenie z internetem.
    pause
    exit /b 1
)
echo    Pakiety zainstalowane!
echo.

echo [2/3] Pobieranie przegladarki Chromium...
python\python.exe -m patchright install chromium
if errorlevel 1 (
    echo    UWAGA: Chromium nie pobrany. Otodom moze nie dzialac.
    echo    Mozesz sprobowac pozniej: python\python.exe -m patchright install chromium
)
echo.

echo [3/3] Uruchamianie kreatora konfiguracji...
echo.
echo ============================================
echo   WAZNE: Otworzy sie okno konfiguracji.
echo   Wklej token z @BotFather i swoje ID.
echo ============================================
echo.

python\pythonw.exe config_wizard.pyw
if errorlevel 1 (
    echo Proba uruchomienia z konsola...
    python\python.exe config_wizard.pyw
)

echo.
echo Instalacja zakonczona!
echo Uzyj start_bot.bat aby uruchomic bota.
pause
