@echo off
chcp 65001 >nul
echo ============================================
echo   Bot Udzialy - Konfiguracja srodowiska
echo ============================================
echo.

echo [1/3] Instalacja pakietow Python...
"%~dp0python\python.exe" -m pip install --upgrade pip
"%~dp0python\python.exe" -m pip install -r "%~dp0requirements.txt"
if errorlevel 1 (
    echo BLAD: Nie udalo sie zainstalowac pakietow!
    pause
    exit /b 1
)

echo.
echo [2/3] Instalacja przegladarki Chromium (patchright)...
"%~dp0python\python.exe" -m patchright install chromium
if errorlevel 1 (
    echo UWAGA: Nie udalo sie zainstalowac Chromium.
    echo Sprobuj recznie: python\python.exe -m patchright install chromium
)

echo.
echo [3/3] Uruchamianie kreatora konfiguracji...
start "" "%~dp0python\pythonw.exe" "%~dp0config_wizard.pyw"

echo.
echo Konfiguracja zakonczona pomyslnie!
pause
