# 🏠 Udziały Bot

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![aiogram 3.x](https://img.shields.io/badge/aiogram-3.x-green.svg)](https://docs.aiogram.dev/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Platform: Windows](https://img.shields.io/badge/platform-Windows-lightgrey.svg)]()

**Telegram bot do wyszukiwania ogłoszeń sprzedaży udziałów w nieruchomościach** na 5 polskich portalach ogłoszeniowych (OLX, Otodom, Morizon, Domiporta, Nieruchomości-online).

Bot automatycznie przeszukuje portale nieruchomości w poszukiwaniu ofert sprzedaży udziałów (ułamkowych części własności) i prezentuje wyniki bezpośrednio w Telegramie.

---

## ✨ Funkcje

- 🔍 Przeszukiwanie 5 portali nieruchomości jednocześnie (3-etapowy pipeline: skan → pełne opisy → ranking)
- 🗺️ Filtrowanie po województwie, mieście, promieniu i cenie
- 📄 Paginacja wyników z klawiaturą inline
- 💾 Zapisywanie interesujących ogłoszeń
- 🛡️ Rotacja proxy przez Tor dla anonimowości
- ⚡ Asynchroniczne scrapowanie (httpx, curl_cffi, nodriver)
- 🧠 FSM do konfiguracji filtrów krok po kroku
- 🚦 Anti-flood middleware

## 📋 Wymagania

- Python 3.11 lub nowszy
- Windows 10/11 (skrypty .bat)
- Konto Telegram + token bota z [@BotFather](https://t.me/BotFather)

## 🚀 Instalacja (Windows)

### Automatyczna (zalecana)

1. Sklonuj repozytorium:
   ```cmd
   git clone https://github.com/your-user/udzialy-bot.git
   cd udzialy-bot
   ```

2. Uruchom instalator:
   ```cmd
   install.bat
   ```
   Skrypt automatycznie:
   - Sprawdzi wersję Pythona
   - Utworzy środowisko wirtualne (venv)
   - Zainstaluje zależności
   - Pobierze Tor Expert Bundle
   - Zainstaluje przeglądarki Playwright

3. Skonfiguruj bota — edytuj `config.yaml`:
   ```yaml
   telegram:
     token: "YOUR_BOT_TOKEN_HERE"
     owner_id: 123456789
   ```

### Ręczna

```cmd
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

## ▶️ Uruchomienie

```cmd
start_bot.bat
```

Lub ręcznie:
```cmd
.venv\Scripts\activate
python -m bot.main
```

## 🎮 Komendy bota

| Komenda | Opis |
|---------|------|
| `/start` | Powitanie i menu główne |
| `/search` | Rozpocznij nowe wyszukiwanie |
| `/filters` | Ustaw filtry (województwo, miasto, cena) |
| `/saved` | Pokaż zapisane ogłoszenia |
| `/settings` | Ustawienia użytkownika |
| `/help` | Pomoc |

## 📁 Struktura projektu

```
udzialy-bot/
├── bot/
│   ├── __init__.py
│   ├── main.py              # Entry point, dispatcher
│   ├── config.py            # Pydantic Settings
│   ├── routers/
│   │   ├── __init__.py      # Router registration
│   │   ├── search.py        # /search command
│   │   ├── results.py       # Pagination
│   │   ├── filters.py       # FSM filters
│   │   ├── saved.py         # Saved listings
│   │   └── settings.py      # User settings
│   ├── keyboards/
│   │   ├── __init__.py
│   │   ├── inline.py        # Inline keyboards
│   │   └── reply.py         # Reply keyboards
│   └── middlewares/
│       ├── __init__.py
│       └── throttle.py      # Anti-flood
├── config.yaml              # Configuration
├── requirements.txt         # Dependencies
├── pyproject.toml           # Project metadata
├── install.bat              # Windows installer
├── start_bot.bat            # Windows launcher
├── .gitignore
└── README.md
```

## ⚙️ Konfiguracja

Plik `config.yaml` zawiera pełną konfigurację bota. Wartości można nadpisać zmiennymi środowiskowymi z prefiksem `UDZIALY_`.

## 🔒 Bezpieczeństwo

- Bot działa w trybie single-user (tylko owner_id)
- Tor zapewnia anonimowość przy scrapowaniu
- Rotacja User-Agent i fingerprint
- Rate limiting na portalach

## 📄 Licencja

MIT License — do użytku osobistego.
