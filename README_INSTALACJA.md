# 🏠 Udziały Bot — Instrukcja Instalacji (Windows)

## Wymagania

- **System:** Windows 10 lub Windows 11 (64-bit)
- **Python:** wersja 3.11 lub nowsza
- **Internet:** wymagane stałe połączenie (bot monitoruje OLX/Otodom)
- **Miejsce na dysku:** ~500 MB (Python + Tor + Chromium)
- **Telegram:** konto + token bota od @BotFather

---

## Krok 1: Pobierz i zainstaluj Python

1. Wejdź na stronę: **https://www.python.org/downloads/**
2. Pobierz najnowszą wersję Python 3.11+ (przycisk "Download Python 3.x.x")
3. Uruchom instalator
4. ⚠️ **WAŻNE:** Na pierwszym ekranie zaznacz:
   - ✅ **Add Python to PATH**
   - ✅ **Install pip**
5. Kliknij "Install Now"
6. Po instalacji zrestartuj komputer

### Sprawdzenie instalacji
Otwórz **Wiersz poleceń** (cmd) i wpisz:
```
python --version
```
Powinno wyświetlić np. `Python 3.11.9` lub nowszą wersję.

---

## Krok 2: Uruchom install.bat

1. Rozpakuj archiwum ZIP z botem do wybranego folderu (np. `C:\UdzialyBot\`)
2. Otwórz folder z botem w Eksploratorze plików
3. **Kliknij dwukrotnie** na `install.bat`
4. Jeśli Windows zapyta o zgodę — kliknij "Uruchom mimo to"
5. Poczekaj na zakończenie instalacji (5-15 minut, zależy od prędkości internetu)

Instalator:
- Utworzy środowisko Python
- Pobierze wszystkie biblioteki
- Pobierze Tor (proxy do anonimowego przeglądania OLX)
- Pobierze przeglądarkę Chromium (do scrapingu Otodom)
- Poprosi o token bota Telegram

---

## Krok 3: Skonfiguruj bota w Telegramie

### Utwórz bota:
1. Otwórz Telegram na telefonie lub komputerze
2. Wyszukaj: **@BotFather**
3. Wyślij: `/newbot`
4. Podaj nazwę bota, np.: `Moje Udziały Gdynia`
5. Podaj login bota, np.: `udzialy_gdynia_bot` (musi kończyć się na `bot`)
6. BotFather wyśle token — **skopiuj go** (wygląda jak: `7123456789:AAHxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`)

### Znajdź swoje ID:
1. Wyszukaj w Telegramie: **@userinfobot**
2. Wyślij mu dowolną wiadomość
3. Odpisze Twoim ID (liczba, np. `987654321`)

### Wpisz dane w konfiguracji:
Jeśli nie podałeś tokenu podczas `install.bat`, edytuj plik `config.yaml`:
```yaml
telegram:
  token: "TUTAJ_WKLEJ_TOKEN"
  owner_id: TUTAJ_WPISZ_SWOJE_ID
```

---

## Krok 4: Uruchom bota

1. **Kliknij dwukrotnie** na `start_bot.bat`
2. Poczekaj aż zobaczy komunikat "Bot uruchomiony!"
3. Otwórz Telegram i napisz do swojego bota: `/start`

### Zatrzymanie bota:
- Naciśnij `Ctrl+C` w oknie konsoli, **lub**
- Uruchom `stop_bot.bat`

### Automatyczne uruchamianie:
Aby bot startował z Windows, utwórz skrót do `start_bot.bat` w folderze:
```
C:\Users\TWOJA_NAZWA\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup
```

---

## Rozwiązywanie problemów

### ❌ "Python nie jest zainstalowany"
- Upewnij się, że podczas instalacji Pythona zaznaczyłeś "Add Python to PATH"
- Zrestartuj komputer po instalacji Pythona
- Jeśli masz kilka wersji Pythona, użyj: `python3 --version`

### ❌ "Tor nie uruchomił się"
- **Antywirus:** Dodaj folder `tor\` do wyjątków antywirusa (Windows Defender / Norton / Kaspersky)
- **Firewall:** Zezwól `tor.exe` na połączenia wychodzące
- **Port zajęty:** Sprawdź czy port 9050 nie jest używany: `netstat -an | find "9050"`

### ❌ "Nie można połączyć z Telegram"
- Sprawdź token w `config.yaml` — musi być w cudzysłowach
- Sprawdź połączenie z internetem
- Upewnij się, że bot jest aktywny w @BotFather (wyślij `/mybots`)

### ❌ "Błąd przy instalacji bibliotek"
- Sprawdź połączenie z internetem
- Spróbuj: `pip install --upgrade pip` i uruchom `install.bat` ponownie
- Jeśli antywirus blokuje pobieranie — tymczasowo wyłącz ochronę w czasie rzeczywistym

### ❌ "Chromium nie działa / Otodom nie scrapuje"
- Uruchom ręcznie: `.venv\Scripts\python -m patchright install chromium`
- Upewnij się, że masz ~300 MB wolnego miejsca na dysku

### ❌ Bot się zawiesza / nie odpowiada
1. Uruchom `stop_bot.bat`
2. Sprawdź logi w pliku `bot.log`
3. Uruchom `start_bot.bat` ponownie

### ❌ Windows Defender blokuje skrypt
- Kliknij "Więcej informacji" → "Uruchom mimo to"
- Lub: kliknij prawym → Właściwości → na dole "Odblokuj" → OK

---

## Struktura plików

```
udzialy-bot/
├── install.bat          ← Instalator (uruchom raz)
├── start_bot.bat        ← Uruchamia bota
├── stop_bot.bat         ← Zatrzymuje bota
├── config.yaml          ← Konfiguracja (token, ustawienia)
├── requirements.txt     ← Lista bibliotek Python
├── bot/                 ← Kod źródłowy bota
├── tor/                 ← Tor (proxy)
│   ├── tor.exe
│   ├── torrc           ← Konfiguracja Tora
│   └── data/           ← Dane Tora (cache)
└── .venv/              ← Środowisko Python (nie ruszać)
```

---

## Kontakt / Pomoc

W razie problemów skontaktuj się z twórcą bota.

---

*Ostatnia aktualizacja: 2026-08*
