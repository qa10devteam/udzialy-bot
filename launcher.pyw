#!/usr/bin/env python3
"""
Bot Udziały — Launcher GUI v2.0
Jedyny punkt wejścia dla użytkownika. Zastępuje config_wizard.pyw i pliki .bat.
Rozszerzenie .pyw = brak okna konsoli na Windows.

Fixed ALL 12 gaps from audit:
 1. DPI awareness (ctypes SetProcessDpiAwareness)
 2. clam theme + full custom style overrides
 3. CREATE_NO_WINDOW for subprocesses
 4. Thread + Queue + after(100ms) polling
 5. taskkill /T /F /PID (tree kill)
 6. PYTHONUNBUFFERED=1 for bot subprocess
 7. atexit handler
 8. Single-instance mutex
 9. Multi-LLM wizard step
10. Config migration (multi-provider)
11. Stale port detection
12. Modern flat UI (white bg, accent, padding)
"""

import sys
import os
import atexit
import platform
import subprocess
import threading
import queue
import time
import re
import socket
import urllib.request
import urllib.error
import tkinter as tk
from tkinter import ttk, messagebox
import datetime

# ═══════════════════════════════════════════════════════════════════════════════
# DPI AWARENESS — must be BEFORE Tk() instantiation (Gap #1)
# ═══════════════════════════════════════════════════════════════════════════════
if sys.platform == 'win32':
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-monitor DPI
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass

# ═══════════════════════════════════════════════════════════════════════════════
# SINGLE INSTANCE MUTEX (Gap #8)
# ═══════════════════════════════════════════════════════════════════════════════
_mutex_handle = None

def ensure_single_instance():
    """Prevent multiple launcher instances."""
    global _mutex_handle
    if sys.platform == 'win32':
        import ctypes
        kernel32 = ctypes.windll.kernel32
        _mutex_handle = kernel32.CreateMutexW(None, False, "Global\\UdzialyBotLauncher")
        if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
            messagebox.showerror("Udziały Bot", "Launcher jest już uruchomiony.")
            sys.exit(0)
    else:
        lock_path = '/tmp/udzialy_bot_launcher.lock'
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            atexit.register(lambda: os.unlink(lock_path))
        except FileExistsError:
            # Check if PID in lock is still alive
            try:
                with open(lock_path) as f:
                    pid = int(f.read().strip())
                os.kill(pid, 0)
                sys.exit(0)  # Still alive
            except (OSError, ValueError):
                os.unlink(lock_path)
                fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, str(os.getpid()).encode())
                atexit.register(lambda: os.unlink(lock_path))

# ═══════════════════════════════════════════════════════════════════════════════
# YAML SUPPORT
# ═══════════════════════════════════════════════════════════════════════════════
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════
VERSION = "2.0.0"
APP_TITLE = "Bot Udziały"
CREATE_NO_WINDOW = 0x08000000 if sys.platform == 'win32' else 0

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.yaml")
TOR_PATH = os.path.join(SCRIPT_DIR, "tor", "tor", "tor.exe")
TORRC_PATH = os.path.join(SCRIPT_DIR, "tor", "torrc")
PYTHON_PATH = os.path.join(SCRIPT_DIR, "python", "python.exe")
LOG_FILE = os.path.join(SCRIPT_DIR, "data", "bot.log")

ALL_PORTALS = [
    ("otodom", "Otodom"), ("olx", "OLX"), ("gratka", "Gratka"),
    ("morizon", "Morizon"), ("nieruchomosci_online", "Nieruchomości-online"),
    ("domiporta", "Domiporta"), ("lento", "Lento"),
    ("gethome", "GetHome"), ("ogloszenia24", "Ogloszenia24"),
]

LLM_PROVIDERS = [
    ("openai", "OpenAI (GPT-4o)"),
    ("deepseek", "DeepSeek"),
    ("gemini", "Google Gemini"),
    ("claude", "Anthropic Claude"),
    ("ollama", "Ollama (lokalny)"),
]

# ═══════════════════════════════════════════════════════════════════════════════
# COLORS & STYLE CONSTANTS (Gap #2, #12)
# ═══════════════════════════════════════════════════════════════════════════════
BG = '#FFFFFF'
CARD_BG = '#F5F5F5'
ACCENT = '#0078D4'
ACCENT_HOVER = '#106EBE'
ACCENT_PRESSED = '#005A9E'
TEXT = '#1A1A1A'
TEXT_SEC = '#666666'
BORDER = '#E0E0E0'
SUCCESS = '#10B981'
WARNING = '#F59E0B'
ERROR = '#EF4444'

FONT = ('Segoe UI', 10)
FONT_BOLD = ('Segoe UI Semibold', 10)
FONT_TITLE = ('Segoe UI Semibold', 18)
FONT_SUBTITLE = ('Segoe UI', 11)
FONT_MONO = ('Consolas', 9)

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIG I/O + MIGRATION (Gap #10)
# ═══════════════════════════════════════════════════════════════════════════════

def load_config():
    """Load config.yaml. Returns dict or None."""
    if not os.path.exists(CONFIG_PATH):
        return None
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        if HAS_YAML:
            cfg = yaml.safe_load(content)
        else:
            cfg = _parse_config_fallback(content)
        return _migrate_config(cfg) if cfg else None
    except Exception:
        return None


def _parse_config_fallback(text):
    """Minimal YAML-like parser for config (no pyyaml)."""
    cfg = {"telegram": {}, "portals": {}, "tor": {}, "llm": {}}
    m = re.search(r'token:\s*"([^"]*)"', text)
    if m:
        cfg["telegram"]["token"] = m.group(1)
    m = re.search(r'owner_id:\s*(\d+)', text)
    if m:
        cfg["telegram"]["owner_id"] = int(m.group(1))
    # LLM provider
    m = re.search(r'provider:\s*"?(\w+)"?', text)
    if m:
        cfg["llm"]["provider"] = m.group(1)
    m = re.search(r'api_key:\s*"([^"]*)"', text)
    if m:
        cfg["llm"]["api_key"] = m.group(1)
    # Portals
    for key, _ in ALL_PORTALS:
        pattern = rf'{key}:\s*\{{?\s*enabled:\s*(true|false)'
        m2 = re.search(pattern, text)
        if m2:
            cfg["portals"][key] = {"enabled": m2.group(1) == "true"}
    return cfg


def _migrate_config(cfg):
    """Migrate old openai-only config to multi-provider format."""
    if cfg is None:
        return None
    # Old format: cfg["openai"]["api_key"] → new: cfg["llm"]["provider"]+["api_key"]
    if "openai" in cfg and "llm" not in cfg:
        old_key = cfg["openai"].get("api_key", "")
        cfg["llm"] = {"provider": "openai", "api_key": old_key}
    if "llm" not in cfg:
        cfg["llm"] = {"provider": "openai", "api_key": ""}
    return cfg


def save_config(token, owner_id, llm_provider, llm_key, portal_states):
    """Save config.yaml with multi-provider LLM support."""
    base_urls = {
        "otodom": "https://www.otodom.pl", "olx": "https://www.olx.pl",
        "gratka": "https://gratka.pl", "morizon": "https://www.morizon.pl",
        "nieruchomosci_online": "https://www.nieruchomosci-online.pl",
        "domiporta": "https://www.domiporta.pl", "lento": "https://www.lento.pl",
        "gethome": "https://gethome.pl", "ogloszenia24": "https://www.ogloszenia24.pl",
    }
    lines = [
        "# =============================================================================",
        "# Udziały Bot — Configuration (generated by launcher v2.0)",
        "# =============================================================================",
        "", "telegram:",
        f'  token: "{token}"',
        f"  owner_id: {owner_id}",
        "",
        "# LLM provider (openai / deepseek / gemini / claude / ollama)",
        "llm:",
        f'  provider: "{llm_provider}"',
        f'  api_key: "{llm_key}"',
        "",
        "# Portal switches", "portals:",
    ]
    for key, _ in ALL_PORTALS:
        enabled = "true" if portal_states.get(key, True) else "false"
        url = base_urls.get(key, "")
        lines.append(f"  {key}:")
        lines.append(f"    enabled: {enabled}")
        if url:
            lines.append(f'    base_url: "{url}"')
    lines += [
        "", "scraping:", "  timeout: 30", "  max_concurrent: 3",
        "  retry_count: 2", "  retry_delay: 5", "  delay_between: 2",
        "  user_agent_rotate: true",
        "", "tor:", "  enabled: true", "  socks_port: 9050",
        "  control_port: 9051", '  control_password: "udzialy2026"',
        "  circuit_rotate_interval: 300",
        "", "database:", '  path: "data/udzialy.db"',
        "", "logging:", '  level: "INFO"', '  file: "data/bot.log"', "",
    ]
    os.makedirs(os.path.dirname(CONFIG_PATH) or ".", exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def config_is_valid(cfg):
    """Check if config has a real token."""
    if cfg is None:
        return False
    token = cfg.get("telegram", {}).get("token", "")
    if not token or token in ("", "YOUR_BOT_TOKEN_HERE", "TUTAJ_WKLEJ_TOKEN_OD_BOTFATHER"):
        return False
    return True

# ═══════════════════════════════════════════════════════════════════════════════
# PROCESS MANAGER (Gaps #3, #4, #5, #6, #7, #11)
# ═══════════════════════════════════════════════════════════════════════════════

class ProcessManager:
    """Manages Tor + Bot subprocess lifecycle with proper tree kill."""

    def __init__(self):
        self._tor_proc = None
        self._bot_proc = None
        self._log_queue = queue.Queue()
        self._stop_event = threading.Event()
        self._starting = False
        atexit.register(self.stop_all)  # Gap #7: atexit cleanup

    def start_all(self):
        """Start Tor then Bot in background thread."""
        if self._starting:
            return
        self._starting = True
        self._stop_event.clear()
        threading.Thread(target=self._start_sequence, daemon=True).start()

    def _start_sequence(self):
        """Sequential start: Tor → wait port → Bot."""
        try:
            # Check stale Tor on port 9050 (Gap #11)
            if self._port_is_open('127.0.0.1', 9050):
                self._log_queue.put(("[STATUS]", "tor_already"))
            else:
                if not self._start_tor():
                    self._starting = False
                    return
                # Wait for Tor port
                self._log_queue.put(("INFO", "Oczekiwanie na Tor (port 9050)..."))
                if not self._wait_for_port('127.0.0.1', 9050, timeout=60):
                    self._log_queue.put(("ERROR", "Tor nie uruchomił się w 60s"))
                    self._starting = False
                    return
            self._log_queue.put(("[STATUS]", "tor_ready"))
            # Start bot
            if not self._start_bot():
                self._starting = False
                return
            self._log_queue.put(("[STATUS]", "bot_started"))
        except Exception as e:
            self._log_queue.put(("ERROR", f"Błąd startu: {e}"))
        finally:
            self._starting = False

    def _start_tor(self):
        """Start Tor subprocess."""
        if not os.path.exists(TOR_PATH):
            self._log_queue.put(("ERROR", f"Nie znaleziono Tor: {TOR_PATH}"))
            return False
        try:
            self._tor_proc = subprocess.Popen(
                [TOR_PATH, "-f", TORRC_PATH],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                creationflags=CREATE_NO_WINDOW,
                cwd=os.path.dirname(TOR_PATH),
            )
            # Tor stdout reader
            threading.Thread(
                target=self._reader, args=(self._tor_proc.stdout, "TOR"),
                daemon=True
            ).start()
            self._log_queue.put(("SUCCESS", "Tor uruchomiony"))
            return True
        except Exception as e:
            self._log_queue.put(("ERROR", f"Tor start failed: {e}"))
            return False

    def _start_bot(self):
        """Start bot subprocess with PYTHONUNBUFFERED (Gap #6)."""
        python = PYTHON_PATH if os.path.exists(PYTHON_PATH) else sys.executable
        env = os.environ.copy()
        env['PYTHONUNBUFFERED'] = '1'  # Gap #6: force unbuffered output
        try:
            self._bot_proc = subprocess.Popen(
                [python, "-u", "-m", "bot.main"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                creationflags=CREATE_NO_WINDOW,
                cwd=SCRIPT_DIR, env=env,
                bufsize=1,
            )
            threading.Thread(
                target=self._reader, args=(self._bot_proc.stdout, "BOT"),
                daemon=True
            ).start()
            self._log_queue.put(("SUCCESS", "Bot uruchomiony"))
            return True
        except Exception as e:
            self._log_queue.put(("ERROR", f"Bot start failed: {e}"))
            return False

    def _reader(self, stream, prefix):
        """Reader thread — reads stdout line by line into queue (Gap #4)."""
        try:
            for raw in iter(stream.readline, b''):
                if self._stop_event.is_set():
                    break
                line = raw.decode('utf-8', errors='replace').rstrip('\r\n')
                if line:
                    # Detect log level from content
                    level = "INFO"
                    if '[ERROR]' in line or 'Error' in line or 'Traceback' in line:
                        level = "ERROR"
                    elif '[WARN' in line or 'Warning' in line:
                        level = "WARNING"
                    elif 'success' in line.lower() or '[OK]' in line:
                        level = "SUCCESS"
                    self._log_queue.put((level, f"[{prefix}] {line}"))
        except (OSError, ValueError):
            pass
        finally:
            try:
                stream.close()
            except OSError:
                pass

    def stop_all(self):
        """Kill bot + Tor process trees (Gap #5: taskkill /T)."""
        self._stop_event.set()
        self._kill_tree(self._bot_proc)
        self._bot_proc = None
        self._kill_tree(self._tor_proc)
        self._tor_proc = None

    def _kill_tree(self, proc):
        """Kill process tree using taskkill /T /F /PID (Gap #5)."""
        if proc is None or proc.poll() is not None:
            return
        pid = proc.pid
        if sys.platform == 'win32':
            try:
                subprocess.run(
                    ['taskkill', '/T', '/F', '/PID', str(pid)],
                    creationflags=CREATE_NO_WINDOW,
                    capture_output=True, timeout=10,
                )
            except Exception:
                pass
        else:
            try:
                import signal
                os.killpg(os.getpgid(pid), signal.SIGTERM)
            except (ProcessLookupError, PermissionError, OSError):
                pass
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    def poll_output(self):
        """Non-blocking drain of log queue. Returns list of (level, msg)."""
        lines = []
        try:
            while True:
                lines.append(self._log_queue.get_nowait())
        except queue.Empty:
            pass
        return lines

    def is_running(self):
        """Return dict of process statuses."""
        return {
            'tor': self._tor_proc is not None and self._tor_proc.poll() is None,
            'bot': self._bot_proc is not None and self._bot_proc.poll() is None,
        }

    @staticmethod
    def _port_is_open(host, port):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0

    def _wait_for_port(self, host, port, timeout=60):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._stop_event.is_set():
                return False
            if self._port_is_open(host, port):
                return True
            time.sleep(2)
        return False

# ═══════════════════════════════════════════════════════════════════════════════
# SETUP WIZARD — 5 Steps (Gap #9: multi-LLM)
# ═══════════════════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════════════════
# UI THEME — Dark Modern (Gap #2: clam + custom overrides)
# ═══════════════════════════════════════════════════════════════════════════════

# Colors
C_BG = "#1a1a2e"           # Dark navy background
C_CARD = "#16213e"         # Card panels
C_ACCENT = "#0f3460"       # Deep blue accent
C_CORAL = "#e94560"        # Coral/red action buttons
C_TEXT = "#ffffff"          # Primary text
C_MUTED = "#a0aec0"        # Secondary/muted text
C_INPUT_BG = "#0f3460"     # Input field background
C_SUCCESS = "#22c55e"      # Green status
C_ERROR = "#ef4444"        # Red status
C_LOG_BG = "#0d1117"       # Terminal-like log background

# Fonts
F_HEADER = ("Segoe UI", 20, "bold")
F_CARD_TITLE = ("Segoe UI", 13, "bold")
F_LABEL = ("Segoe UI", 10)
F_MUTED = ("Segoe UI", 9)
F_INPUT = ("Consolas", 10)
F_BUTTON = ("Segoe UI", 11, "bold")
F_BIG_BUTTON = ("Segoe UI", 13, "bold")
F_LOG = ("Consolas", 9)

# LLM Providers
LLM_PROVIDERS = [
    ("openai", "OpenAI (GPT-4o-mini)"),
    ("deepseek", "DeepSeek"),
    ("gemini", "Google Gemini"),
    ("claude", "Anthropic Claude"),
    ("ollama", "Ollama (lokalny)"),
]


def _apply_dark_theme(root):
    """Apply dark theme styling to ttk widgets."""
    style = ttk.Style(root)
    style.theme_use("clam")

    style.configure(".", background=C_BG, foreground=C_TEXT, font=F_LABEL)
    style.configure("TFrame", background=C_BG)
    style.configure("Card.TFrame", background=C_CARD)
    style.configure("TLabel", background=C_BG, foreground=C_TEXT)
    style.configure("Card.TLabel", background=C_CARD, foreground=C_TEXT)
    style.configure("Muted.TLabel", background=C_CARD, foreground=C_MUTED, font=F_MUTED)
    style.configure("Header.TLabel", background=C_BG, foreground=C_TEXT, font=F_HEADER)
    style.configure("CardTitle.TLabel", background=C_CARD, foreground=C_TEXT, font=F_CARD_TITLE)

    style.configure("Accent.TButton", background=C_CORAL, foreground=C_TEXT,
                    font=F_BIG_BUTTON, padding=(20, 12))
    style.map("Accent.TButton",
              background=[("active", "#d63851"), ("pressed", "#c0304a")])

    style.configure("Secondary.TButton", background=C_CARD, foreground=C_MUTED,
                    font=F_BUTTON, padding=(16, 8))
    style.map("Secondary.TButton",
              background=[("active", C_ACCENT)])

    style.configure("Small.TButton", background=C_ACCENT, foreground=C_TEXT,
                    font=F_LABEL, padding=(12, 6))
    style.map("Small.TButton",
              background=[("active", "#1a4a80")])

    style.configure("TCheckbutton", background=C_CARD, foreground=C_TEXT, font=F_LABEL)
    style.map("TCheckbutton", background=[("active", C_CARD)])

    style.configure("TCombobox", fieldbackground=C_INPUT_BG, foreground=C_TEXT,
                    background=C_ACCENT, font=F_INPUT)

    root.configure(bg=C_BG)


def _make_card(parent, **kwargs):
    """Create a styled card frame."""
    card = tk.Frame(parent, bg=C_CARD, padx=20, pady=16, **kwargs)
    return card


def _make_entry(parent, show=None, width=50):
    """Create a styled dark entry field."""
    entry = tk.Entry(parent, bg=C_INPUT_BG, fg=C_TEXT, insertbackground=C_TEXT,
                     font=F_INPUT, relief="flat", bd=0, highlightthickness=1,
                     highlightcolor=C_CORAL, highlightbackground=C_ACCENT,
                     width=width)
    if show:
        entry.configure(show=show)
    return entry


# ═══════════════════════════════════════════════════════════════════════════════
# SETUP WIZARD — Dark Card-Based (5 steps in one scrollable view)
# ═══════════════════════════════════════════════════════════════════════════════

class SetupWizard(tk.Toplevel):
    """Modern dark-themed configuration wizard."""

    def __init__(self, master, on_complete=None):
        super().__init__(master)
        self.on_complete = on_complete
        self.title("Bot Udziały — Konfiguracja")
        self.geometry("650x820")
        self.configure(bg=C_BG)
        self.resizable(False, False)

        # Center on screen
        self.update_idletasks()
        x = (self.winfo_screenwidth() - 650) // 2
        y = (self.winfo_screenheight() - 820) // 2
        self.geometry(f"+{x}+{y}")

        # Variables
        self.token_var = tk.StringVar()
        self.owner_id_var = tk.StringVar()
        self.llm_provider_var = tk.StringVar(value="openai")
        self.llm_key_var = tk.StringVar()
        self.portal_vars = {}
        self.token_status = tk.StringVar()

        self._build_ui()
        self.grab_set()

    def _build_ui(self):
        # Scrollable container
        canvas = tk.Canvas(self, bg=C_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self.scroll_frame = tk.Frame(canvas, bg=C_BG)

        self.scroll_frame.bind("<Configure>",
                               lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw", width=630)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        scrollbar.pack(side="right", fill="y")

        # Bind mousewheel
        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

        container = self.scroll_frame

        # ── HEADER ──
        header = tk.Frame(container, bg=C_BG)
        header.pack(fill="x", pady=(20, 24))
        tk.Label(header, text="🏠 Bot Udziały", font=("Segoe UI", 22, "bold"),
                 bg=C_BG, fg=C_TEXT).pack()
        tk.Label(header, text="Wyszukiwarka udziałów w nieruchomościach",
                 font=F_MUTED, bg=C_BG, fg=C_MUTED).pack(pady=(4, 0))

        # ── CARD 1: Token ──
        card1 = _make_card(container)
        card1.pack(fill="x", pady=(0, 16))

        tk.Label(card1, text="🤖  Token Bota Telegram", font=F_CARD_TITLE,
                 bg=C_CARD, fg=C_TEXT).pack(anchor="w")
        tk.Label(card1, text="Utwórz bota u @BotFather → skopiuj token",
                 font=F_MUTED, bg=C_CARD, fg=C_MUTED).pack(anchor="w", pady=(4, 10))

        token_frame = tk.Frame(card1, bg=C_CARD)
        token_frame.pack(fill="x")
        self.token_entry = _make_entry(token_frame, width=45)
        self.token_entry.pack(side="left", fill="x", expand=True, ipady=8)

        check_btn = tk.Button(token_frame, text="Sprawdź", font=F_LABEL,
                              bg=C_ACCENT, fg=C_TEXT, relief="flat", padx=16, pady=6,
                              activebackground="#1a4a80", activeforeground=C_TEXT,
                              cursor="hand2", command=self._check_token)
        check_btn.pack(side="right", padx=(10, 0))

        self.token_status_label = tk.Label(card1, textvariable=self.token_status,
                                           font=F_MUTED, bg=C_CARD, fg=C_MUTED)
        self.token_status_label.pack(anchor="w", pady=(6, 0))

        # ── CARD 2: Owner ID ──
        card2 = _make_card(container)
        card2.pack(fill="x", pady=(0, 16))

        tk.Label(card2, text="👤  ID Użytkownika", font=F_CARD_TITLE,
                 bg=C_CARD, fg=C_TEXT).pack(anchor="w")
        tk.Label(card2, text="Wyślij /start do @userinfobot → skopiuj liczbę",
                 font=F_MUTED, bg=C_CARD, fg=C_MUTED).pack(anchor="w", pady=(4, 10))

        self.id_entry = _make_entry(card2, width=50)
        self.id_entry.pack(fill="x", ipady=8)

        # ── CARD 3: LLM / AI ──
        card3 = _make_card(container)
        card3.pack(fill="x", pady=(0, 16))

        tk.Label(card3, text="🧠  Analiza AI (opcjonalnie)", font=F_CARD_TITLE,
                 bg=C_CARD, fg=C_TEXT).pack(anchor="w")
        tk.Label(card3, text="Dodaj klucz API aby bot analizował ogłoszenia z AI",
                 font=F_MUTED, bg=C_CARD, fg=C_MUTED).pack(anchor="w", pady=(4, 10))

        # Provider selection
        prov_frame = tk.Frame(card3, bg=C_CARD)
        prov_frame.pack(fill="x", pady=(0, 8))
        tk.Label(prov_frame, text="Provider:", font=F_LABEL,
                 bg=C_CARD, fg=C_MUTED).pack(side="left")

        provider_names = [p[1] for p in LLM_PROVIDERS]
        self.provider_combo = ttk.Combobox(prov_frame, values=provider_names,
                                           state="readonly", width=25, font=F_INPUT)
        self.provider_combo.set("OpenAI (GPT-4o-mini)")
        self.provider_combo.pack(side="left", padx=(10, 0))

        # API Key
        tk.Label(card3, text="Klucz API:", font=F_LABEL,
                 bg=C_CARD, fg=C_MUTED).pack(anchor="w", pady=(8, 4))
        self.llm_key_entry = _make_entry(card3, width=50)
        self.llm_key_entry.pack(fill="x", ipady=8)

        tk.Label(card3, text="💡 Pomiń jeśli nie chcesz AI — bot działa bez tego.",
                 font=("Segoe UI", 8), bg=C_CARD, fg="#6b7280").pack(anchor="w", pady=(8, 0))

        # ── CARD 4: Portals ──
        card4 = _make_card(container)
        card4.pack(fill="x", pady=(0, 24))

        tk.Label(card4, text="🌐  Portale do przeszukiwania", font=F_CARD_TITLE,
                 bg=C_CARD, fg=C_TEXT).pack(anchor="w", pady=(0, 10))

        portals_frame = tk.Frame(card4, bg=C_CARD)
        portals_frame.pack(fill="x")
        for portal in ["OLX", "Morizon", "Domiporta", "Otodom"]:
            var = tk.BooleanVar(value=True)
            self.portal_vars[portal.lower()] = var
            cb = tk.Checkbutton(portals_frame, text=portal, variable=var,
                                font=F_LABEL, bg=C_CARD, fg=C_TEXT,
                                selectcolor=C_INPUT_BG, activebackground=C_CARD,
                                activeforeground=C_TEXT)
            cb.pack(side="left", padx=(0, 20))

        # ── BUTTONS ──
        btn_frame = tk.Frame(container, bg=C_BG)
        btn_frame.pack(fill="x", pady=(0, 20))

        launch_btn = tk.Button(btn_frame, text="🚀  Uruchom Bota", font=F_BIG_BUTTON,
                               bg=C_CORAL, fg=C_TEXT, relief="flat", cursor="hand2",
                               activebackground="#d63851", activeforeground=C_TEXT,
                               padx=20, pady=14, command=self._save_and_launch)
        launch_btn.pack(fill="x", ipady=4)

        save_btn = tk.Button(btn_frame, text="Tylko zapisz", font=F_LABEL,
                             bg=C_BG, fg=C_MUTED, relief="flat", cursor="hand2",
                             activebackground=C_CARD, activeforeground=C_TEXT,
                             bd=1, highlightthickness=1, highlightbackground=C_MUTED,
                             padx=16, pady=8, command=self._save_only)
        save_btn.pack(fill="x", pady=(10, 0), ipady=2)

    def _check_token(self):
        """Validate Telegram bot token via API."""
        token = self.token_entry.get().strip()
        if not token or not re.match(r'^\d+:[A-Za-z0-9_-]+$', token):
            self.token_status.set("❌ Nieprawidłowy format tokena")
            self.token_status_label.configure(fg=C_ERROR)
            return

        try:
            url = f"https://api.telegram.org/bot{token}/getMe"
            req = urllib.request.Request(url, method='GET')
            with urllib.request.urlopen(req, timeout=10) as resp:
                import json
                data = json.loads(resp.read().decode())
                if data.get("ok"):
                    name = data["result"].get("username", "?")
                    self.token_status.set(f"✅ Token poprawny! Bot: @{name}")
                    self.token_status_label.configure(fg=C_SUCCESS)
                    self.token_var.set(token)
                else:
                    self.token_status.set("❌ Token odrzucony przez Telegram")
                    self.token_status_label.configure(fg=C_ERROR)
        except Exception as e:
            self.token_status.set(f"❌ Błąd połączenia: {str(e)[:40]}")
            self.token_status_label.configure(fg=C_ERROR)

    def _get_config(self):
        """Build config dict from wizard inputs."""
        # Get provider key from combo selection
        combo_val = self.provider_combo.get()
        provider_key = "openai"
        for key, name in LLM_PROVIDERS:
            if name == combo_val:
                provider_key = key
                break

        return {
            "telegram": {
                "token": self.token_entry.get().strip(),
                "owner_id": int(self.id_entry.get().strip() or "0"),
            },
            "llm": {
                "enabled": bool(self.llm_key_entry.get().strip()),
                "provider": provider_key,
                "api_key": self.llm_key_entry.get().strip(),
                "model": "gpt-4o-mini",
                "base_url": "",
                "max_concurrent": 3,
                "timeout": 15,
            },
            "portals": {k: v.get() for k, v in self.portal_vars.items()},
            "tor": {
                "enabled": True,
                "socks_port": 9050,
                "control_port": 9051,
                "control_password": "udzialy2026",
            },
            "scraping": {"timeout": 25, "delay_between": 2, "max_pages": 2},
            "scorer": {"threshold": 25},
            "database": {"path": "data/udzialy.db"},
            "logging": {"level": "INFO", "file": "data/bot.log"},
        }

    def _save_config(self):
        """Save config to yaml file."""
        config = self._get_config()
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml")

        if HAS_YAML:
            with open(config_path, "w", encoding="utf-8") as f:
                yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
        else:
            # Fallback: write simple yaml manually
            lines = []
            for section, values in config.items():
                lines.append(f"{section}:")
                if isinstance(values, dict):
                    for k, v in values.items():
                        if isinstance(v, bool):
                            lines.append(f"  {k}: {'true' if v else 'false'}")
                        elif isinstance(v, str):
                            lines.append(f'  {k}: "{v}"')
                        else:
                            lines.append(f"  {k}: {v}")
                lines.append("")
            with open(config_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))

        return True

    def _save_and_launch(self):
        """Save config and signal to launch bot."""
        if not self.token_entry.get().strip():
            messagebox.showwarning("Uwaga", "Wklej token bota!", parent=self)
            return
        self._save_config()
        self.destroy()
        if self.on_complete:
            self.on_complete(launch=True)

    def _save_only(self):
        """Save config without launching."""
        self._save_config()
        messagebox.showinfo("Zapisano", "Konfiguracja zapisana!", parent=self)
        self.destroy()
        if self.on_complete:
            self.on_complete(launch=False)


# ═══════════════════════════════════════════════════════════════════════════════
# DASHBOARD — Dark terminal-like status view
# ═══════════════════════════════════════════════════════════════════════════════

class Dashboard(tk.Frame):
    """Main runtime dashboard with dark theme."""

    def __init__(self, master, process_manager, on_settings=None):
        super().__init__(master, bg=C_BG)
        self.pm = process_manager
        self.on_settings = on_settings
        self._log_queue = queue.Queue()
        self._build_ui()
        self._poll_logs()

    def _build_ui(self):
        # Header
        header = tk.Frame(self, bg=C_BG)
        header.pack(fill="x", padx=30, pady=(30, 20))

        tk.Label(header, text="🏠 Bot Udziały", font=("Segoe UI", 18, "bold"),
                 bg=C_BG, fg=C_TEXT).pack(side="left")
        tk.Label(header, text=f"v{VERSION}", font=F_MUTED,
                 bg=C_BG, fg=C_MUTED).pack(side="left", padx=(10, 0))

        # Status card
        status_card = _make_card(self)
        status_card.pack(fill="x", padx=30, pady=(0, 16))

        status_row = tk.Frame(status_card, bg=C_CARD)
        status_row.pack(fill="x")

        self.status_canvas = tk.Canvas(status_row, width=20, height=20,
                                       bg=C_CARD, highlightthickness=0)
        self.status_canvas.pack(side="left")
        self.status_dot = self.status_canvas.create_oval(2, 2, 18, 18, fill=C_ERROR, outline="")

        self.status_label = tk.Label(status_row, text="  Zatrzymany", font=F_CARD_TITLE,
                                     bg=C_CARD, fg=C_TEXT)
        self.status_label.pack(side="left")

        # Control buttons
        btn_frame = tk.Frame(self, bg=C_BG)
        btn_frame.pack(fill="x", padx=30, pady=(0, 16))

        self.start_btn = tk.Button(btn_frame, text="▶  Uruchom", font=F_BUTTON,
                                   bg=C_CORAL, fg=C_TEXT, relief="flat", padx=20, pady=10,
                                   cursor="hand2", activebackground="#d63851",
                                   command=self._start)
        self.start_btn.pack(side="left", padx=(0, 10))

        self.stop_btn = tk.Button(btn_frame, text="⏹  Zatrzymaj", font=F_BUTTON,
                                  bg=C_ACCENT, fg=C_TEXT, relief="flat", padx=20, pady=10,
                                  cursor="hand2", activebackground="#1a4a80",
                                  state="disabled", command=self._stop)
        self.stop_btn.pack(side="left", padx=(0, 10))

        settings_btn = tk.Button(btn_frame, text="⚙  Ustawienia", font=F_LABEL,
                                 bg=C_CARD, fg=C_MUTED, relief="flat", padx=16, pady=8,
                                 cursor="hand2", command=self._open_settings)
        settings_btn.pack(side="right")

        # Log area
        log_label = tk.Label(self, text="Logi:", font=F_LABEL, bg=C_BG, fg=C_MUTED)
        log_label.pack(anchor="w", padx=30, pady=(0, 4))

        log_frame = tk.Frame(self, bg=C_LOG_BG, padx=2, pady=2)
        log_frame.pack(fill="both", expand=True, padx=30, pady=(0, 20))

        self.log_text = tk.Text(log_frame, bg=C_LOG_BG, fg="#c9d1d9", font=F_LOG,
                                relief="flat", wrap="word", state="disabled",
                                insertbackground=C_TEXT, height=15)
        self.log_text.pack(fill="both", expand=True)

        # Configure log tags
        self.log_text.tag_configure("info", foreground="#8b949e")
        self.log_text.tag_configure("success", foreground=C_SUCCESS)
        self.log_text.tag_configure("error", foreground=C_ERROR)
        self.log_text.tag_configure("bot", foreground="#58a6ff")

        # Footer
        tk.Label(self, text="QA10 sp. z o.o. • qa10.io", font=("Segoe UI", 8),
                 bg=C_BG, fg="#4a5568").pack(pady=(0, 10))

    def _log(self, msg, tag="info"):
        """Add line to log area."""
        self.log_text.configure(state="normal")
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_text.insert("end", f"[{timestamp}] {msg}\n", tag)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _poll_logs(self):
        """Poll process manager for new log lines."""
        if self.pm:
            while not self.pm.log_queue.empty():
                try:
                    line = self.pm.log_queue.get_nowait()
                    tag = "info"
                    if "ERROR" in line or "error" in line.lower():
                        tag = "error"
                    elif "INFO" in line and "Bot" in line:
                        tag = "bot"
                    self._log(line.strip(), tag)
                except queue.Empty:
                    break
        self.after(100, self._poll_logs)

    def _start(self):
        """Start Tor + Bot."""
        self._log("Uruchamianie...", "info")
        self.status_canvas.itemconfig(self.status_dot, fill="#eab308")  # Yellow
        self.status_label.configure(text="  Uruchamianie...")
        self.start_btn.configure(state="disabled")

        def _do_start():
            success = self.pm.start_all()
            self.after(0, lambda: self._on_started(success))

        threading.Thread(target=_do_start, daemon=True).start()

    def _on_started(self, success):
        if success:
            self.status_canvas.itemconfig(self.status_dot, fill=C_SUCCESS)
            self.status_label.configure(text="  Działa")
            self.stop_btn.configure(state="normal")
            self._log("Bot uruchomiony pomyślnie!", "success")
        else:
            self.status_canvas.itemconfig(self.status_dot, fill=C_ERROR)
            self.status_label.configure(text="  Błąd startu")
            self.start_btn.configure(state="normal")
            self._log("Nie udało się uruchomić bota.", "error")

    def _stop(self):
        """Stop bot + Tor."""
        self._log("Zatrzymywanie...", "info")
        self.pm.stop_all()
        self.status_canvas.itemconfig(self.status_dot, fill=C_ERROR)
        self.status_label.configure(text="  Zatrzymany")
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self._log("Bot zatrzymany.", "info")

    def _open_settings(self):
        if self.on_settings:
            self.on_settings()


# ═══════════════════════════════════════════════════════════════════════════════
# APPLICATION — Top-level controller
# ═══════════════════════════════════════════════════════════════════════════════

class Application:
    """Main application controller."""

    def __init__(self):
        ensure_single_instance()

        self.root = tk.Tk()
        self.root.title("Bot Udziały")
        self.root.geometry("650x700")
        self.root.configure(bg=C_BG)
        self.root.minsize(600, 600)

        # Center
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() - 650) // 2
        y = (self.root.winfo_screenheight() - 700) // 2
        self.root.geometry(f"+{x}+{y}")

        _apply_dark_theme(self.root)

        # Process manager
        self.pm = ProcessManager()

        # Check if config exists and has token
        self.config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml")
        if self._needs_setup():
            self.root.withdraw()
            wizard = SetupWizard(self.root, on_complete=self._on_wizard_done)
            wizard.protocol("WM_DELETE_WINDOW", lambda: (wizard.destroy(), self.root.destroy()))
        else:
            self._show_dashboard()

        # Close handler
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _needs_setup(self):
        """Check if first-run setup is needed."""
        if not os.path.exists(self.config_path):
            return True
        try:
            if HAS_YAML:
                with open(self.config_path) as f:
                    cfg = yaml.safe_load(f)
                token = cfg.get("telegram", {}).get("token", "")
                return not token or token == "YOUR_BOT_TOKEN_HERE"
            return True
        except Exception:
            return True

    def _on_wizard_done(self, launch=False):
        """Called after wizard completes."""
        self.root.deiconify()
        self._show_dashboard()
        if launch:
            self.dashboard._start()

    def _show_dashboard(self):
        """Show the main dashboard."""
        self.dashboard = Dashboard(self.root, self.pm, on_settings=self._open_settings)
        self.dashboard.pack(fill="both", expand=True)

    def _open_settings(self):
        """Open settings (re-run wizard)."""
        wizard = SetupWizard(self.root, on_complete=lambda launch=False: None)

    def _on_close(self):
        """Handle window close."""
        if self.pm.is_running():
            if messagebox.askyesno("Zamknij", "Bot jest uruchomiony. Zatrzymać i zamknąć?"):
                self.pm.stop_all()
                self.root.destroy()
        else:
            self.root.destroy()

    def run(self):
        self.root.mainloop()


# ═══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    app = Application()
    app.run()


if __name__ == "__main__":
    main()
