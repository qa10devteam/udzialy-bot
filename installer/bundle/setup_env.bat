@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>nul

:: ============================================
:: Bot Udzialy - Instalacja (v2.1)
:: Bullet-proof: offline wheels, full paths,
:: error recovery, preflight checks
:: ============================================
echo.
echo  ============================================
echo   Bot Udzialy - Wyszukiwarka Udzialow
echo   Instalacja i konfiguracja
echo  ============================================
echo.

:: BASE = folder where this .bat lives (no trailing backslash)
set "BASE=%~dp0"
if "!BASE:~-1!"=="\" set "BASE=!BASE:~0,-1!"

:: ============================================
:: LOCKFILE (prevent double-run)
:: ============================================
if exist "!BASE!\setup.lock" (
    echo  [!] Instalacja juz trwa w innym oknie.
    echo  Zamknij inne okno i sprobuj ponownie.
    pause
    exit /b 1
)
echo %date% %time% > "!BASE!\setup.lock"

:: ============================================
:: PREFLIGHT CHECKS
:: ============================================

:: Check we can write to this folder
echo [Test] Sprawdzanie uprawnien...
echo test > "!BASE!\_write_test.tmp" 2>nul
if not exist "!BASE!\_write_test.tmp" (
    echo.
    echo  BLAD: Brak uprawnien do zapisu w tym folderze.
    echo  Wypakuj ZIP w inne miejsce, np. C:\UdzialyBot
    del /f "!BASE!\setup.lock" 2>nul
    pause
    exit /b 1
)
del /f "!BASE!\_write_test.tmp" 2>nul
echo       OK
echo.

:: ============================================
:: STEP 1: PYTHON INSTALLATION
:: ============================================

if exist "!BASE!\python\python.exe" (
    echo [1/3] Python juz zainstalowany - OK
    goto :step_packages
)

echo [1/3] Instalowanie Python 3.11...
echo       To potrwa 1-2 minuty, prosze czekac...
echo.

if not exist "!BASE!\python-3.11.9-amd64.exe" (
    echo  BLAD: Nie znaleziono pliku python-3.11.9-amd64.exe
    echo  Upewnij sie ze wypakowano CALY ZIP.
    del /f "!BASE!\setup.lock" 2>nul
    pause
    exit /b 1
)

:: Run Python installer silently to local folder
"!BASE!\python-3.11.9-amd64.exe" /quiet InstallAllUsers=0 TargetDir="!BASE!\python" Include_pip=1 Include_tcltk=1 Include_test=0 Include_doc=0 Include_launcher=0 AssociateFiles=0 Shortcuts=0 PrependPath=0 CompileAll=0

:: Wait for installer to finish writing
timeout /t 5 /nobreak >nul

:: Verify installation
if not exist "!BASE!\python\python.exe" (
    echo.
    echo  BLAD: Python nie zainstalowal sie.
    echo.
    echo  Rozwiazanie:
    echo   1. Kliknij prawym na python-3.11.9-amd64.exe
    echo   2. Wybierz "Wlasciwosci"
    echo   3. Zaznacz "Odblokuj" na dole
    echo   4. Kliknij OK
    echo   5. Uruchom setup_env.bat ponownie
    echo.
    echo  Lub: dodaj folder do wyjatkow antywirusa.
    del /f "!BASE!\setup.lock" 2>nul
    pause
    exit /b 1
)

if not exist "!BASE!\python\pythonw.exe" (
    echo  BLAD: pythonw.exe nie znalezione.
    echo  Instalacja Python jest niekompletna.
    del /f "!BASE!\setup.lock" 2>nul
    pause
    exit /b 1
)

echo       Python zainstalowany!
echo.

:: ============================================
:: STEP 2: INSTALL PACKAGES (OFFLINE from wheels/)
:: ============================================
:step_packages

echo [2/3] Instalowanie pakietow...

:: Try offline first (from bundled wheels - no internet needed)
if exist "!BASE!\wheels" (
    echo       (z lokalnych plikow)
    "!BASE!\python\python.exe" -m pip install --no-index --find-links="!BASE!\wheels" -r "!BASE!\requirements.txt" --no-warn-script-location -q 2>"!BASE!\pip_errors.log"
    if not errorlevel 1 (
        echo       Pakiety zainstalowane offline!
        del /f "!BASE!\pip_errors.log" 2>nul
        goto :step_launch
    )
    echo       Offline nie powiodlo sie, proba online...
)

:: Fallback: online install
echo       (wymaga internetu)
"!BASE!\python\python.exe" -m pip install --upgrade pip --no-warn-script-location -q 2>nul
"!BASE!\python\python.exe" -m pip install -r "!BASE!\requirements.txt" --no-warn-script-location -q 2>"!BASE!\pip_errors.log"
if errorlevel 1 (
    echo.
    echo  BLAD: Nie udalo sie zainstalowac pakietow.
    echo.
    echo  Sprawdz:
    echo   - Polaczenie z internetem
    echo   - Czy firewall nie blokuje python.exe
    echo.
    echo  Log: !BASE!\pip_errors.log
    del /f "!BASE!\setup.lock" 2>nul
    pause
    exit /b 1
)
del /f "!BASE!\pip_errors.log" 2>nul
echo       Pakiety zainstalowane!
echo.

:: ============================================
:: STEP 3: LAUNCH GUI
:: ============================================
:step_launch

echo [3/3] Uruchamianie aplikacji...
echo.

:: Create data directory (needed for bot logs/db)
if not exist "!BASE!\data" mkdir "!BASE!\data"

:: Remove lockfile before launch
del /f "!BASE!\setup.lock" 2>nul

:: Launch GUI (pythonw = no console window)
start "" "!BASE!\python\pythonw.exe" "!BASE!\launcher.pyw"

:: Verify it started (give 3 seconds)
timeout /t 3 /nobreak >nul

echo  ============================================
echo   Gotowe! Okno aplikacji powinno sie otworzyc.
echo  ============================================
echo.
echo  Jesli okno sie nie pojawilo:
echo   - Uruchom: python\python.exe launcher.pyw
echo     (pokaze bledy w konsoli)
echo.

exit /b 0
