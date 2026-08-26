"""
Udziały Bot CLI — single entry point.

Usage:
    udzialy setup      — interactive config wizard (token, portals, LLM)
    udzialy run        — start Tor + bot (foreground)
    udzialy gui        — launch GUI dashboard
    udzialy tor-check  — verify Tor is working
    udzialy scan       — run single scan (no Telegram, print results)
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
    print()
    print("  [Opcjonalnie] Klucz API do analizy AI:")
    print("  (Enter = pomiń, bot działa bez AI)")
    llm_key = input("  API key: ").strip()
    llm_provider = "openai"
    if llm_key:
        print("  Provider [1=OpenAI, 2=DeepSeek, 3=Gemini, 4=Claude, 5=Ollama]")
        choice = input("  Wybór [1]: ").strip() or "1"
        providers = {"1": "openai", "2": "deepseek", "3": "gemini", "4": "claude", "5": "ollama"}
        llm_provider = providers.get(choice, "openai")

    # Save config
    config = {
        "telegram": {"token": token, "owner_id": owner_id},
        "llm": {
            "enabled": bool(llm_key),
            "provider": llm_provider,
            "api_key": llm_key or "",
            "model": "gpt-4o-mini",
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

    print()
    print("  Udziały Bot — uruchamianie...")
    print("  Ctrl+C aby zatrzymać")
    print()

    # Import and run bot
    sys.path.insert(0, str(Path(__file__).parent))
    from bot.main import main as bot_main
    bot_main()


def cmd_gui(args):
    """Launch GUI dashboard."""
    ensure_dirs()
    gui_path = Path(__file__).parent / "launcher.pyw"
    if not gui_path.exists():
        print("  [!] Nie znaleziono launcher.pyw")
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


def cmd_scan(args):
    """Run single scan without Telegram (print results)."""
    ensure_dirs()
    if not CONFIG_PATH.exists():
        print("  [!] Brak konfiguracji. Uruchom: udzialy setup")
        return 1

    os.environ["UDZIALY_CONFIG"] = str(CONFIG_PATH)
    print("  Skanowanie portali...")
    print()

    # TODO: integrate with scraper manager for one-shot scan
    print("  [info] Funkcja w rozwoju — użyj 'udzialy run' dla pełnego bota")
    return 0


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
    sub.add_parser("scan", help="Jednorazowy skan (bez Telegram)")

    args = parser.parse_args()

    commands = {
        "setup": cmd_setup,
        "run": cmd_run,
        "gui": cmd_gui,
        "tor-check": cmd_tor_check,
        "scan": cmd_scan,
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
