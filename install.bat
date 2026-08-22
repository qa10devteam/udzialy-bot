@echo off
REM =============================================================================
REM Udzialy Bot — Windows Installer
REM =============================================================================
setlocal enabledelayedexpansion

echo.
echo  ============================================
echo   Udzialy Bot — Instalator
echo  ============================================
echo.

REM --- Check Python ---
echo [1/5] Sprawdzanie Pythona...
python --version >nul 2>&1
if errorlevel 1 (
    echo [BLAD] Python nie znaleziony! Pobierz z https://www.python.org/downloads/
    echo        Upewnij sie, ze zaznaczyles "Add Python to PATH" podczas instalacji.
    pause
    exit /b 1
)

for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo         Znaleziono Python %PYVER%

REM --- Check Python version >= 3.11 ---
for /f "tokens=1,2 delims=." %%a in ("%PYVER%") do (
    if %%a LSS 3 (
        echo [BLAD] Wymagany Python 3.11+. Aktualna wersja: %PYVER%
        pause
        exit /b 1
    )
    if %%a EQU 3 if %%b LSS 11 (
        echo [BLAD] Wymagany Python 3.11+. Aktualna wersja: %PYVER%
        pause
        exit /b 1
    )
)

REM --- Create virtual environment ---
echo.
echo [2/5] Tworzenie srodowiska wirtualnego...
if exist .venv (
    echo         .venv juz istnieje — pomijam
) else (
    python -m venv .venv
    if errorlevel 1 (
        echo [BLAD] Nie udalo sie utworzyc venv!
        pause
        exit /b 1
    )
    echo         Utworzono .venv
)

REM --- Install dependencies ---
echo.
echo [3/5] Instalacja zaleznosci...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo [BLAD] Instalacja zaleznosci nie powiodla sie!
    pause
    exit /b 1
)
echo         Zainstalowano wszystkie pakiety

REM --- Download Tor Expert Bundle ---
echo.
echo [4/5] Pobieranie Tor Expert Bundle...
if exist tor\tor.exe (
    echo         Tor juz pobrany — pomijam
) else (
    mkdir tor 2>nul
    echo         Pobieranie tor-expert-bundle...
    curl -L -o tor\tor-expert-bundle.zip ^
        "https://archive.torproject.org/tor-package-archive/torbrowser/13.0.9/tor-expert-bundle-windows-x86_64-13.0.9.tar.gz"
    if errorlevel 1 (
        echo [UWAGA] Nie udalo sie pobrac Tor. Pobierz recznie:
        echo         https://www.torproject.org/download/tor/
        echo         Wypakuj do folderu tor\ w katalogu projektu
    ) else (
        echo         Rozpakowywanie...
        tar -xf tor\tor-expert-bundle.zip -C tor\ 2>nul
        del tor\tor-expert-bundle.zip 2>nul
        echo         Tor zainstalowany
    )
)

REM --- Install Playwright browsers ---
echo.
echo [5/5] Instalacja przegladarek Playwright...
python -m patchright install chromium
if errorlevel 1 (
    echo [UWAGA] Instalacja Playwright nie powiodla sie.
    echo         Sprobuj recznie: python -m patchright install chromium
)
echo         Przegladarki zainstalowane

REM --- Create data directory ---
mkdir data 2>nul

echo.
echo  ============================================
echo   Instalacja zakonczona!
echo  ============================================
echo.
echo  Nastepne kroki:
echo    1. Edytuj config.yaml — wpisz token bota
echo    2. Uruchom: start_bot.bat
echo.
pause
