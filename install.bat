@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

echo ============================================================
echo    INSTALATOR BOTA UDZIALY - Wersja 1.0.0
echo ============================================================
echo.

:: ============================================================
:: KROK 1: Sprawdzenie Pythona
:: ============================================================
echo [1/6] Sprawdzanie wersji Pythona...

python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo [BLAD] Python nie jest zainstalowany!
    echo.
    echo Pobierz Python 3.11 lub nowszy ze strony:
    echo   https://www.python.org/downloads/
    echo.
    echo WAZNE: Podczas instalacji zaznacz opcje:
    echo   [x] Add Python to PATH
    echo   [x] Install pip
    echo.
    echo Po zainstalowaniu Pythona uruchom ten skrypt ponownie.
    echo.
    pause
    exit /b 1
)

:: Check Python version >= 3.11
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PYVER=%%v
for /f "tokens=1,2 delims=." %%a in ("%PYVER%") do (
    set PYMAJOR=%%a
    set PYMINOR=%%b
)

if %PYMAJOR% LSS 3 (
    echo [BLAD] Wymagany Python 3.11+, znaleziono: %PYVER%
    echo Pobierz nowsza wersje: https://www.python.org/downloads/
    pause
    exit /b 1
)
if %PYMAJOR%==3 if %PYMINOR% LSS 11 (
    echo [BLAD] Wymagany Python 3.11+, znaleziono: %PYVER%
    echo Pobierz nowsza wersje: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo    OK - Python %PYVER%
echo.

:: ============================================================
:: KROK 2: Tworzenie srodowiska wirtualnego
:: ============================================================
echo [2/6] Tworzenie srodowiska wirtualnego (.venv)...

if exist .venv (
    echo    Srodowisko juz istnieje, pomijam...
) else (
    python -m venv .venv
    if errorlevel 1 (
        echo [BLAD] Nie udalo sie utworzyc srodowiska wirtualnego!
        pause
        exit /b 1
    )
    echo    OK - Srodowisko utworzone
)
echo.

:: ============================================================
:: KROK 3: Instalacja zaleznosci Python
:: ============================================================
echo [3/6] Instalacja bibliotek Pythona (moze potrwac kilka minut)...

call .venv\Scripts\activate.bat
pip install --upgrade pip >nul 2>&1
pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [BLAD] Instalacja bibliotek nie powiodla sie!
    echo Sprawdz polaczenie z internetem i sprobuj ponownie.
    pause
    exit /b 1
)
echo    OK - Biblioteki zainstalowane
echo.

:: ============================================================
:: KROK 4: Pobieranie Tor Expert Bundle
:: ============================================================
echo [4/6] Pobieranie Tor Expert Bundle...

if exist tor\tor.exe (
    echo    Tor juz pobrany, pomijam...
) else (
    if not exist tor mkdir tor

    echo    Pobieranie z torproject.org (ok. 10 MB)...
    echo    To moze potrwac kilka minut...

    :: Download Tor Expert Bundle for Windows x86_64
    powershell -Command "& { $ProgressPreference = 'SilentlyContinue'; try { Invoke-WebRequest -Uri 'https://archive.torproject.org/tor-package-archive/torbrowser/13.5.6/tor-expert-bundle-windows-x86_64-13.5.6.tar.gz' -OutFile 'tor\tor-bundle.tar.gz' -UseBasicParsing } catch { Invoke-WebRequest -Uri 'https://dist.torproject.org/torbrowser/13.5.6/tor-expert-bundle-windows-x86_64-13.5.6.tar.gz' -OutFile 'tor\tor-bundle.tar.gz' -UseBasicParsing } }"

    if not exist tor\tor-bundle.tar.gz (
        echo.
        echo [BLAD] Nie udalo sie pobrac Tora!
        echo.
        echo Pobierz recznie Tor Expert Bundle ze strony:
        echo   https://www.torproject.org/download/tor/
        echo.
        echo Rozpakuj zawartosc do folderu 'tor' w katalogu bota.
        echo Plik tor.exe powinien byc w: tor\tor.exe
        pause
        exit /b 1
    )

    echo    Rozpakowywanie...
    powershell -Command "& { $ProgressPreference = 'SilentlyContinue'; tar -xzf 'tor\tor-bundle.tar.gz' -C 'tor' }"

    :: Move files from nested directory if needed
    if exist tor\tor\tor.exe (
        xcopy /E /Y tor\tor\* tor\ >nul 2>&1
        rmdir /S /Q tor\tor >nul 2>&1
    )

    :: Clean up archive
    del tor\tor-bundle.tar.gz >nul 2>&1

    if not exist tor\tor.exe (
        echo [BLAD] Rozpakowywanie nie powiodlo sie!
        echo Pobierz Tor recznie i umiesc tor.exe w folderze 'tor'.
        pause
        exit /b 1
    )

    echo    OK - Tor zainstalowany
)

:: Create data directory for Tor
if not exist tor\data mkdir tor\data
echo.

:: ============================================================
:: KROK 5: Instalacja przegladarki Chromium
:: ============================================================
echo [5/6] Instalacja przegladarki Chromium (ok. 280 MB)...
echo    To moze potrwac kilka minut przy wolnym laczu...

python -m patchright install chromium
if errorlevel 1 (
    echo.
    echo [UWAGA] Instalacja Chromium nie powiodla sie.
    echo Bot bedzie dzialac, ale scraping Otodom moze nie funkcjonowac.
    echo Mozesz sprobowac pozniej: .venv\Scripts\python -m patchright install chromium
    echo.
)
echo    OK - Chromium zainstalowany
echo.

:: ============================================================
:: KROK 6: Konfiguracja bota
:: ============================================================
echo [6/6] Konfiguracja...

if exist config.yaml (
    echo    Plik config.yaml juz istnieje, pomijam konfiguracje.
    echo    Edytuj config.yaml reczne jesli chcesz zmienic ustawienia.
) else (
    echo.
    echo ============================================================
    echo    KONFIGURACJA BOTA TELEGRAM
    echo ============================================================
    echo.
    echo Aby bot dzialal, potrzebujesz tokenu z Telegrama.
    echo.
    echo Jak uzyskac token:
    echo   1. Otworz Telegram i znajdz @BotFather
    echo   2. Wyslij: /newbot
    echo   3. Podaj nazwe bota (np. "Moje Udzialy Bot")
    echo   4. Podaj login bota (np. "moje_udzialy_bot")
    echo   5. BotFather wysle Ci token - skopiuj go
    echo.

    set /p TELEGRAM_TOKEN="Wklej token bota Telegram: "

    if "!TELEGRAM_TOKEN!"=="" (
        echo [UWAGA] Nie podano tokenu. Edytuj config.yaml recznie przed uruchomieniem bota.
        copy config.yaml.template config.yaml >nul 2>&1
    ) else (
        echo.
        set /p OWNER_ID="Podaj swoje ID uzytkownika Telegram (liczba, np. 123456789): "

        if "!OWNER_ID!"=="" set OWNER_ID=0

        :: Create config from template with user values
        (
            echo # Konfiguracja bota udzialy
            echo # Wygenerowano automatycznie przez install.bat
            echo.
            echo telegram:
            echo   token: "!TELEGRAM_TOKEN!"
            echo   owner_id: !OWNER_ID!
            echo.
            echo tor:
            echo   socks_port: 9050
            echo   control_port: 9051
            echo   control_password: "udzialy2026"
            echo.
            echo scraping:
            echo   olx_enabled: true
            echo   otodom_enabled: true
            echo   check_interval_minutes: 30
            echo.
            echo logging:
            echo   level: INFO
            echo   file: bot.log
        ) > config.yaml

        echo    OK - Konfiguracja zapisana
    )
)

echo.
echo ============================================================
echo    INSTALACJA ZAKONCZONA POMYSLNIE!
echo ============================================================
echo.
echo Co dalej:
echo   1. Upewnij sie, ze config.yaml zawiera poprawny token bota
echo   2. Uruchom bota: start_bot.bat
echo   3. Aby zatrzymac bota: stop_bot.bat (lub Ctrl+C)
echo.
echo W razie problemow sprawdz plik README_INSTALACJA.md
echo ============================================================
echo.
pause
