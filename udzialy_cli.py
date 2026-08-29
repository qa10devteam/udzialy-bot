"""
Udziały Bot CLI — single entry point.

Usage:
    udzialy setup      — interactive config wizard (token, portals, LLM)
    udzialy run        — start Tor + bot (foreground)
    udzialy gui        — launch GUI dashboard
    udzialy tor-check  — verify Tor is working
    udzialy scan       — one-shot scan (no Telegram); same pipeline as the bot
    udzialy autostart  — toggle Windows autostart
"""

import argparse
import os
import sys
import subprocess
import asyncio
from pathlib import Path


APP_DIR = Path.home() / ".udzialy-bot"
CONFIG_PATH = APP_DIR / "config.yaml"
DATA_DIR = APP_DIR / "data"
TOR_DATA_DIR = APP_DIR / "tor_data"


def ensure_dirs():
    """Create app directories."""
    APP_DIR.mkdir(exist_ok=True)
    DATA_DIR.mkdir(exist_ok=True)
    TOR_DATA_DIR.mkdir(exist_ok=True)


def cmd_setup(args):
    """Interactive setup wizard (terminal-based)."""
    ensure_dirs()
    import yaml

    print()
    print("=" * 50)
    print("  Udziały Bot — Konfiguracja")
    print("=" * 50)
    print()

    # Load existing config if any
    config = {}
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            config = yaml.safe_load(f) or {}
        print(f"  [i] Znaleziono istniejącą konfigurację: {CONFIG_PATH}")
        print()

    # Telegram token
    current_token = config.get("telegram", {}).get("token", "")
    if current_token and current_token != "YOUR_BOT_TOKEN_HERE":
        print(f"  Token: ...{current_token[-8:]}")
        change = input("  Zmienić token? [n/Y]: ").strip().lower()
        if change != "y":
            token = current_token
        else:
            token = input("  Nowy token z @BotFather: ").strip()
    else:
        token = input("  Token z @BotFather: ").strip()

    if not token:
        print("  [!] Token jest wymagany.")
        return 1

    # Owner ID
    current_id = config.get("telegram", {}).get("owner_id", 0)
    if current_id:
        print(f"  Owner ID: {current_id}")
        change = input("  Zmienić? [n/Y]: ").strip().lower()
        if change != "y":
            owner_id = current_id
        else:
            owner_id = int(input("  Nowy ID (z @userinfobot): ").strip() or "0")
    else:
        owner_id = int(input("  Twoje ID Telegram (z @userinfobot): ").strip() or "0")

    # LLM (optional)
    sys.path.insert(0, str(Path(__file__).parent))
    from bot.config import default_model_for, normalize_llm_model

    existing_llm = config.get("llm", {}) or {}
    existing_key = existing_llm.get("api_key", "") or ""
    print()
    print("  [Opcjonalnie] Klucz API do analizy AI:")
    if existing_key:
        print(f"  Obecny klucz: ...{existing_key[-6:]}  (Enter = zostaw)")
        llm_key = input("  API key: ").strip() or existing_key
    else:
        print("  (Enter = pomiń, bot działa bez AI)")
        llm_key = input("  API key: ").strip()
    llm_provider = "openai"
    llm_model = ""
    if llm_key:
        print("  Provider:")
        print("    1 = Claude (Anthropic)")
        print("    2 = ChatGPT (OpenAI)")
        print("    3 = Gemini (Google)")
        print("    4 = DeepSeek")
        choice = input("  Wybór [1]: ").strip() or "1"
        providers = {"1": "claude", "2": "openai", "3": "gemini", "4": "deepseek"}
        llm_provider = providers.get(choice, "claude")

        # Default model per provider (Claude → claude-sonnet-4-6)
        llm_model = default_model_for(llm_provider)
        print(f"  Model: {llm_model}")
        custom = input("  Inny model? (Enter = domyślny): ").strip()
        if custom:
            llm_model = custom
        llm_model = normalize_llm_model(llm_provider, llm_model)

    # Save config
    config = {
        "telegram": {"token": token, "owner_id": owner_id},
        "llm": {
            "enabled": bool(llm_key),
            "provider": llm_provider,
            "api_key": llm_key or "",
            "model": llm_model,
        },
        "portals": {
            "otodom": {"enabled": True},
            "olx": {"enabled": True},
            "morizon": {"enabled": True},
            "domiporta": {"enabled": True},
        },
        "tor": {
            "enabled": True,
            "socks_port": 9050,
            "control_port": 9051,
            "control_password": "udzialy2026",
        },
        "scraping": {"timeout": 25, "delay_between": 2, "max_pages": 2},
        "database": {"path": str(DATA_DIR / "udzialy.db")},
        "logging": {"level": "INFO", "file": str(DATA_DIR / "bot.log")},
    }

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)

    print()
    print(f"  ✓ Konfiguracja zapisana: {CONFIG_PATH}")
    print()
    print("  Następne kroki:")
    print("    udzialy run    — uruchom bota")
    print("    udzialy gui    — uruchom GUI")
    print()
    return 0


def cmd_run(args):
    """Start bot (with optional Tor)."""
    ensure_dirs()

    if not CONFIG_PATH.exists():
        print("  [!] Brak konfiguracji. Uruchom: udzialy setup")
        return 1

    # Set config path env for bot
    os.environ["UDZIALY_CONFIG"] = str(CONFIG_PATH)
    os.environ["PYTHONUNBUFFERED"] = "1"
    os.environ["PYTHONIOENCODING"] = "utf-8"

    print()
    print("  Udziały Bot — uruchamianie...")
    print("  Ctrl+C aby zatrzymać")
    print()

    # Import and run bot
    sys.path.insert(0, str(Path(__file__).parent))
    # Fix Windows asyncio issues (ProactorEventLoop bugs with subprocess+SSL)
    import platform
    if platform.system() == "Windows":
        import asyncio
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    from bot.main import main as bot_main
    bot_main()


def cmd_gui(args):
    """Launch GUI dashboard."""
    ensure_dirs()
    gui_path = Path(__file__).parent / "launcher.pyw"
    if not gui_path.exists():
        gui_path = Path(__file__).parent / "launcher.py"  # pip install ships .py only
    if not gui_path.exists():
        print("  [!] Nie znaleziono launcher.py")
        return 1

    python = sys.executable
    if sys.platform == "win32":
        # Use pythonw for no console
        pythonw = Path(python).parent / "pythonw.exe"
        if pythonw.exists():
            python = str(pythonw)

    subprocess.Popen([python, str(gui_path)])
    print("  GUI uruchomione.")
    return 0


def cmd_tor_check(args):
    """Check if Tor is reachable."""
    import socket
    print("  Sprawdzanie Tor (127.0.0.1:9050)...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(3)
    result = sock.connect_ex(("127.0.0.1", 9050))
    sock.close()
    if result == 0:
        print("  ✓ Tor jest aktywny na porcie 9050")
        return 0
    else:
        print("  ✗ Tor nie działa")
        print("    Zainstaluj Tor: https://www.torproject.org/download/")
        print("    Lub na Windows: pobierz Tor Expert Bundle")
        return 1


def cmd_autostart(args):
    """Enable/disable Windows autostart."""
    import platform
    if platform.system() != "Windows":
        print("  Autostart dostępny tylko na Windows.")
        print("  Na Linux użyj: systemctl --user enable udzialy-bot")
        return 0

    import winreg
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    app_name = "UdzialyBot"
    exe_path = f'"{sys.executable}" -m udzialy_cli run'

    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)
        try:
            winreg.QueryValueEx(key, app_name)
            # Already exists — remove it
            winreg.DeleteValue(key, app_name)
            print("  ✗ Autostart wyłączony.")
        except FileNotFoundError:
            # Doesn't exist — add it
            winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, exe_path)
            print("  ✓ Autostart włączony!")
            print(f"    Bot uruchomi się automatycznie po starcie Windows.")
        winreg.CloseKey(key)
    except Exception as e:
        print(f"  Błąd: {e}")
    return 0


def cmd_scan(args):
    """Run single scan without Telegram (print results)."""
    ensure_dirs()
    if not CONFIG_PATH.exists():
        print("  [!] Brak konfiguracji. Uruchom: udzialy setup")
        return 1

    os.environ["UDZIALY_CONFIG"] = str(CONFIG_PATH)
    os.environ["PYTHONIOENCODING"] = "utf-8"
    return _run_scan(args)


def _run_scan(args) -> int:
    """One-shot scan: same 3-stage pipeline as the Telegram /search, printed to stdout.

    Also the quickest way to verify an installation: if this prints shares, the bot will.
    """
    import logging
    import platform
    import time

    if platform.system() == "Windows":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    logging.basicConfig(
        level=logging.DEBUG if getattr(args, "verbose", False) else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    sys.path.insert(0, str(Path(__file__).parent))
    from bot.config import get_settings
    from scraper.pipeline import format_text_report, run_search_pipeline, select_portals

    settings = get_settings()
    portals = select_portals(settings.portals.enabled_portals())
    if getattr(args, "portals", None):
        wanted = {p.strip().lower() for p in args.portals.split(",")}
        portals = [p for p in portals if p in wanted] or portals

    filters = {}
    if getattr(args, "city", None):
        filters["city"] = args.city
    if getattr(args, "price_max", None):
        filters["price_max"] = args.price_max
    if getattr(args, "price_min", None):
        filters["price_min"] = args.price_min

    print(f"  Skanowanie portali: {', '.join(portals)}")
    if filters:
        print(f"  Filtry: {filters}")
    print("  (to potrwa 1-2 minuty)")
    print()

    def _progress(stage, d):
        if stage == "portal":
            icon = "OK " if d["status"] == "done" else "!! "
            print(f"  {icon}{d['portal']}: {d['status']} ({d['count']} ogłoszeń) [{d['done']}/{d['total']}]")
        elif stage == "deep":
            print(f"  -> pobieram pełne opisy {d['candidates']} kandydatów (odrzucono {d['noise']} szumu)")

    t0 = time.time()
    result = asyncio.run(run_search_pipeline(
        filters=filters,
        portals=portals,
        timeout_per_portal=float(settings.scraping.portal_timeout),
        deep_fetch=not getattr(args, "no_deep", False),
        progress=_progress,
    ))
    print()
    print(format_text_report(result, limit=getattr(args, "limit", 20) or 20))
    print()
    print(f"  Czas: {time.time() - t0:.0f}s")
    if getattr(args, "json", None):
        import json
        Path(args.json).write_text(
            json.dumps(result.display, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        print(f"  Zapisano JSON: {args.json}")
    return 0 if result.raw_count > 0 else 2


def main():
    parser = argparse.ArgumentParser(
        prog="udzialy",
        description="Bot do wyszukiwania udziałów w nieruchomościach",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("setup", help="Konfiguracja (token, portale, AI)")
    sub.add_parser("run", help="Uruchom bota (Tor + Telegram)")
    sub.add_parser("gui", help="Uruchom GUI dashboard")
    sub.add_parser("tor-check", help="Sprawdź połączenie Tor")
    scan_p = sub.add_parser("scan", help="Jednorazowy skan (bez Telegram)")
    scan_p.add_argument("--city", help="Miasto (np. Gdynia)")
    scan_p.add_argument("--price-max", dest="price_max", type=int, help="Cena maksymalna PLN")
    scan_p.add_argument("--price-min", dest="price_min", type=int, help="Cena minimalna PLN")
    scan_p.add_argument("--portals", help="Lista portali po przecinku (np. olx,morizon)")
    scan_p.add_argument("--limit", type=int, default=20, help="Ile wyników wypisać (domyślnie 20)")
    scan_p.add_argument("--no-deep", dest="no_deep", action="store_true", help="Pomiń pobieranie pełnych opisów")
    scan_p.add_argument("--json", help="Zapisz wyniki do pliku JSON")
    scan_p.add_argument("-v", "--verbose", action="store_true", help="Pełne logi")
    sub.add_parser("autostart", help="Włącz/wyłącz autostart z Windows")

    args = parser.parse_args()

    commands = {
        "setup": cmd_setup,
        "run": cmd_run,
        "gui": cmd_gui,
        "tor-check": cmd_tor_check,
        "scan": cmd_scan,
        "autostart": cmd_autostart,
    }

    if args.command is None:
        parser.print_help()
        print()
        print("  Szybki start:")
        print("    pip install udzialy-bot")
        print("    udzialy setup")
        print("    udzialy run")
        return 0

    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main() or 0)
