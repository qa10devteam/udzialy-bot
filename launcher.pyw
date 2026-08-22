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

class SetupWizard(tk.Toplevel):
    """5-step first-run wizard: Welcome → Token → OwnerID → LLM → Portals."""

    def __init__(self, parent, on_complete):
        super().__init__(parent)
        self.on_complete = on_complete
        self.title("Kreator konfiguracji")
        self.geometry("550x480")
        self.resizable(False, False)
        self.configure(bg=BG)
        self.transient(parent)
        self.grab_set()

        self.current_step = 0
        self.data = {'token': '', 'owner_id': '', 'llm_provider': 'openai',
                     'llm_key': '', 'portals': {k: True for k, _ in ALL_PORTALS}}

        # Container
        self.container = tk.Frame(self, bg=BG, padx=32, pady=24)
        self.container.pack(fill='both', expand=True)

        # Progress bar area
        self.progress_frame = tk.Frame(self.container, bg=BG)
        self.progress_frame.pack(fill='x', pady=(0, 16))

        # Content area
        self.content = tk.Frame(self.container, bg=BG)
        self.content.pack(fill='both', expand=True)

        # Navigation
        self.nav_frame = tk.Frame(self.container, bg=BG)
        self.nav_frame.pack(fill='x', pady=(16, 0))

        self.btn_back = ttk.Button(self.nav_frame, text="← Wstecz",
                                   style='Secondary.TButton', command=self._prev)
        self.btn_back.pack(side='left')
        self.btn_next = ttk.Button(self.nav_frame, text="Dalej →",
                                   style='Accent.TButton', command=self._next)
        self.btn_next.pack(side='right')

        self.steps = [
            self._build_welcome, self._build_token,
            self._build_owner, self._build_llm, self._build_portals,
        ]
        self._show_step(0)

    def _show_step(self, idx):
        self.current_step = idx
        for w in self.content.winfo_children():
            w.destroy()
        self.steps[idx]()
        self.btn_back.configure(state='normal' if idx > 0 else 'disabled')
        self.btn_next.configure(text="Zakończ ✓" if idx == 4 else "Dalej →")
        self._update_progress()

    def _update_progress(self):
        for w in self.progress_frame.winfo_children():
            w.destroy()
        for i in range(5):
            color = ACCENT if i <= self.current_step else BORDER
            c = tk.Canvas(self.progress_frame, width=40, height=6,
                         bg=BG, highlightthickness=0)
            c.create_rectangle(0, 0, 40, 6, fill=color, outline='')
            c.pack(side='left', padx=2)

    def _next(self):
        if not self._validate_step():
            return
        if self.current_step < 4:
            self._show_step(self.current_step + 1)
        else:
            self._finish()

    def _prev(self):
        if self.current_step > 0:
            self._show_step(self.current_step - 1)

    def _validate_step(self):
        step = self.current_step
        if step == 1:
            token = self._token_var.get().strip()
            if not re.match(r'^\d+:[A-Za-z0-9_-]{35,}$', token):
                messagebox.showwarning("Błąd", "Token nieprawidłowy.\nFormat: 123456:ABC...")
                return False
            self.data['token'] = token
        elif step == 2:
            oid = self._owner_var.get().strip()
            if not oid.isdigit():
                messagebox.showwarning("Błąd", "Owner ID musi być liczbą.")
                return False
            self.data['owner_id'] = oid
        elif step == 3:
            provider = self._provider_var.get()
            key = self._llm_key_var.get().strip()
            if provider != 'ollama' and not key:
                messagebox.showwarning("Błąd", "Podaj klucz API.")
                return False
            self.data['llm_provider'] = provider
            self.data['llm_key'] = key
        elif step == 4:
            portals = {}
            for key, var in self._portal_vars.items():
                portals[key] = var.get()
            self.data['portals'] = portals
        return True

    def _finish(self):
        save_config(
            self.data['token'], self.data['owner_id'],
            self.data['llm_provider'], self.data['llm_key'],
            self.data['portals'],
        )
        self.on_complete()
        self.destroy()

    # ── Step builders ──

    def _build_welcome(self):
        ttk.Label(self.content, text="👋 Witaj!", style='Title.TLabel').pack(
            anchor='w', pady=(0, 8))
        ttk.Label(self.content, text=(
            "Ten kreator pomoże Ci skonfigurować Bot Udziały.\n\n"
            "Potrzebujesz:\n"
            "• Token bota z @BotFather\n"
            "• Twoje Telegram ID (owner_id)\n"
            "• Klucz API do wybranego modelu LLM\n\n"
            "Kliknij 'Dalej' aby rozpocząć."
        ), style='Body.TLabel', wraplength=460).pack(anchor='w')

    def _build_token(self):
        ttk.Label(self.content, text="🔑 Token Telegram", style='Title.TLabel').pack(
            anchor='w', pady=(0, 8))
        ttk.Label(self.content, text="Wklej token bota od @BotFather:",
                  style='Subtitle.TLabel').pack(anchor='w', pady=(0, 12))
        self._token_var = tk.StringVar(value=self.data['token'])
        entry = ttk.Entry(self.content, textvariable=self._token_var,
                          font=FONT_MONO, width=50)
        entry.pack(fill='x', pady=(0, 12))
        entry.focus_set()
        ttk.Label(self.content, text="Format: 123456789:ABCDefGhIjKlMnOpQrStUvWxYz...",
                  style='Hint.TLabel').pack(anchor='w')

    def _build_owner(self):
        ttk.Label(self.content, text="👤 Owner ID", style='Title.TLabel').pack(
            anchor='w', pady=(0, 8))
        ttk.Label(self.content, text=(
            "Twoje numeryczne Telegram ID.\n"
            "Możesz je sprawdzić: wyślij /start do @userinfobot"
        ), style='Subtitle.TLabel', wraplength=460).pack(anchor='w', pady=(0, 12))
        self._owner_var = tk.StringVar(value=self.data['owner_id'])
        ttk.Entry(self.content, textvariable=self._owner_var, font=FONT, width=20).pack(
            anchor='w', pady=(0, 12))

    def _build_llm(self):
        """Step 4: Multi-LLM provider selection (Gap #9)."""
        ttk.Label(self.content, text="🧠 Model LLM", style='Title.TLabel').pack(
            anchor='w', pady=(0, 8))
        ttk.Label(self.content, text="Wybierz dostawcę AI i podaj klucz API:",
                  style='Subtitle.TLabel').pack(anchor='w', pady=(0, 12))

        # Provider radio buttons
        self._provider_var = tk.StringVar(value=self.data['llm_provider'])
        radio_frame = tk.Frame(self.content, bg=BG)
        radio_frame.pack(fill='x', pady=(0, 16))
        for value, label in LLM_PROVIDERS:
            rb = ttk.Radiobutton(radio_frame, text=label, variable=self._provider_var,
                                 value=value, style='TRadiobutton',
                                 command=self._on_provider_change)
            rb.pack(anchor='w', pady=2)

        # Key entry
        self._llm_key_frame = tk.Frame(self.content, bg=BG)
        self._llm_key_frame.pack(fill='x')
        self._llm_key_label = ttk.Label(self._llm_key_frame, text="Klucz API:",
                                        style='Body.TLabel')
        self._llm_key_label.pack(anchor='w', pady=(0, 4))
        self._llm_key_var = tk.StringVar(value=self.data['llm_key'])
        self._llm_key_entry = ttk.Entry(self._llm_key_frame,
                                        textvariable=self._llm_key_var,
                                        font=FONT_MONO, width=50, show='•')
        self._llm_key_entry.pack(fill='x')
        self._on_provider_change()

    def _on_provider_change(self):
        provider = self._provider_var.get()
        hints = {
            'openai': 'sk-...', 'deepseek': 'sk-...',
            'gemini': 'AIza...', 'claude': 'sk-ant-...',
            'ollama': '(nie wymagany — lokalne API)',
        }
        if provider == 'ollama':
            self._llm_key_label.configure(text="URL Ollama (domyślnie http://localhost:11434):")
            self._llm_key_entry.configure(show='')
        else:
            self._llm_key_label.configure(text=f"Klucz API ({hints.get(provider, '')}):")
            self._llm_key_entry.configure(show='•')

    def _build_portals(self):
        ttk.Label(self.content, text="🌐 Portale", style='Title.TLabel').pack(
            anchor='w', pady=(0, 8))
        ttk.Label(self.content, text="Wybierz portale do monitorowania:",
                  style='Subtitle.TLabel').pack(anchor='w', pady=(0, 12))
        self._portal_vars = {}
        frame = tk.Frame(self.content, bg=BG)
        frame.pack(fill='x')
        for key, label in ALL_PORTALS:
            var = tk.BooleanVar(value=self.data['portals'].get(key, True))
            self._portal_vars[key] = var
            ttk.Checkbutton(frame, text=label, variable=var,
                           style='TCheckbutton').pack(anchor='w', pady=1)

# ═══════════════════════════════════════════════════════════════════════════════
# SETTINGS DIALOG
# ═══════════════════════════════════════════════════════════════════════════════

class SettingsDialog(tk.Toplevel):
    """Edit configuration after initial setup."""

    def __init__(self, parent, cfg, on_save):
        super().__init__(parent)
        self.on_save = on_save
        self.title("Ustawienia")
        self.geometry("500x520")
        self.resizable(False, False)
        self.configure(bg=BG)
        self.transient(parent)
        self.grab_set()

        frame = tk.Frame(self, bg=BG, padx=24, pady=20)
        frame.pack(fill='both', expand=True)

        ttk.Label(frame, text="⚙️ Ustawienia", style='Title.TLabel').pack(
            anchor='w', pady=(0, 16))

        # Token
        ttk.Label(frame, text="Token Telegram:", style='Body.TLabel').pack(anchor='w')
        self._token_var = tk.StringVar(value=cfg.get('telegram', {}).get('token', ''))
        ttk.Entry(frame, textvariable=self._token_var, font=FONT_MONO, width=50).pack(
            fill='x', pady=(0, 12))

        # Owner
        ttk.Label(frame, text="Owner ID:", style='Body.TLabel').pack(anchor='w')
        self._owner_var = tk.StringVar(
            value=str(cfg.get('telegram', {}).get('owner_id', '')))
        ttk.Entry(frame, textvariable=self._owner_var, font=FONT, width=20).pack(
            anchor='w', pady=(0, 12))

        # LLM Provider
        ttk.Label(frame, text="Dostawca LLM:", style='Body.TLabel').pack(anchor='w')
        self._provider_var = tk.StringVar(
            value=cfg.get('llm', {}).get('provider', 'openai'))
        combo = ttk.Combobox(frame, textvariable=self._provider_var,
                            values=[v for v, _ in LLM_PROVIDERS], state='readonly')
        combo.pack(anchor='w', pady=(0, 8))

        # LLM Key
        ttk.Label(frame, text="Klucz API LLM:", style='Body.TLabel').pack(anchor='w')
        self._llm_key_var = tk.StringVar(value=cfg.get('llm', {}).get('api_key', ''))
        ttk.Entry(frame, textvariable=self._llm_key_var, font=FONT_MONO,
                  width=50, show='•').pack(fill='x', pady=(0, 12))

        # Portals
        ttk.Label(frame, text="Portale:", style='Body.TLabel').pack(anchor='w', pady=(0, 4))
        self._portal_vars = {}
        pf = tk.Frame(frame, bg=BG)
        pf.pack(fill='x', pady=(0, 16))
        portals_cfg = cfg.get('portals', {})
        for key, label in ALL_PORTALS:
            enabled = portals_cfg.get(key, {}).get('enabled', True) if isinstance(
                portals_cfg.get(key), dict) else True
            var = tk.BooleanVar(value=enabled)
            self._portal_vars[key] = var
            ttk.Checkbutton(pf, text=label, variable=var).pack(anchor='w', pady=1)

        # Save button
        ttk.Button(frame, text="Zapisz", style='Accent.TButton',
                   command=self._save).pack(anchor='e')

    def _save(self):
        token = self._token_var.get().strip()
        owner = self._owner_var.get().strip()
        provider = self._provider_var.get()
        key = self._llm_key_var.get().strip()
        portals = {k: v.get() for k, v in self._portal_vars.items()}
        if not token or not owner.isdigit():
            messagebox.showwarning("Błąd", "Token i Owner ID są wymagane.")
            return
        save_config(token, owner, provider, key, portals)
        self.on_save()
        self.destroy()

# ═══════════════════════════════════════════════════════════════════════════════
# DASHBOARD — Main Application Screen
# ═══════════════════════════════════════════════════════════════════════════════

class Dashboard(tk.Frame):
    """Main dashboard with status, log display, and control buttons."""

    def __init__(self, parent, pm):
        super().__init__(parent, bg=BG)
        self.pm = pm
        self.state = 'stopped'  # stopped / starting / running
        self._build_ui()

    def _build_ui(self):
        # Header
        header = tk.Frame(self, bg=BG)
        header.pack(fill='x', padx=32, pady=(24, 0))
        ttk.Label(header, text="🤖 Bot Udziały", style='Title.TLabel').pack(
            side='left')
        ttk.Label(header, text=f"v{VERSION}", style='Hint.TLabel').pack(
            side='left', padx=(8, 0), pady=(6, 0))
        ttk.Button(header, text="⚙️", style='Secondary.TButton', width=3,
                   command=self._open_settings).pack(side='right')

        # Status card
        self.status_card = tk.Frame(self, bg=CARD_BG, padx=20, pady=14)
        self.status_card.pack(fill='x', padx=32, pady=(16, 0))

        status_row = tk.Frame(self.status_card, bg=CARD_BG)
        status_row.pack(fill='x')

        self.status_dot = tk.Canvas(status_row, width=12, height=12,
                                    bg=CARD_BG, highlightthickness=0)
        self.status_dot.pack(side='left', padx=(0, 8))
        self._draw_dot('#9CA3AF')  # gray=unknown

        self.status_label = tk.Label(status_row, text="Zatrzymany", bg=CARD_BG,
                                     font=FONT_BOLD, fg=TEXT)
        self.status_label.pack(side='left')

        self.uptime_label = tk.Label(status_row, text="", bg=CARD_BG,
                                     font=FONT, fg=TEXT_SEC)
        self.uptime_label.pack(side='right')

        # Buttons
        btn_frame = tk.Frame(self, bg=BG)
        btn_frame.pack(fill='x', padx=32, pady=(16, 0))
        self.btn_start = ttk.Button(btn_frame, text="▶  Uruchom",
                                    style='Accent.TButton', command=self._start)
        self.btn_start.pack(side='left', padx=(0, 8))
        self.btn_stop = ttk.Button(btn_frame, text="⏹  Zatrzymaj",
                                   style='Secondary.TButton', command=self._stop)
        self.btn_stop.pack(side='left')
        self.btn_stop.configure(state='disabled')

        # Log display
        log_label = tk.Frame(self, bg=BG)
        log_label.pack(fill='x', padx=32, pady=(16, 4))
        ttk.Label(log_label, text="Logi", style='Body.TLabel').pack(side='left')

        log_frame = tk.Frame(self, bg='#1E1E1E', padx=1, pady=1)
        log_frame.pack(fill='both', expand=True, padx=32, pady=(0, 24))

        self.log_text = tk.Text(
            log_frame, wrap='word', font=FONT_MONO,
            bg='#1E1E1E', fg='#D4D4D4', relief='flat',
            padx=12, pady=8, state='disabled',
            highlightthickness=0, borderwidth=0, height=14,
        )
        scrollbar = ttk.Scrollbar(log_frame, orient='vertical',
                                  command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        self.log_text.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Color tags
        self.log_text.tag_configure('INFO', foreground='#D4D4D4')
        self.log_text.tag_configure('SUCCESS', foreground='#10B981')
        self.log_text.tag_configure('WARNING', foreground='#F59E0B')
        self.log_text.tag_configure('ERROR', foreground='#EF4444')
        self.log_text.tag_configure('TS', foreground='#6B7280')

        self._start_time = None
        self.log("Gotowy do uruchomienia.", "INFO")

    def _draw_dot(self, color):
        self.status_dot.delete('all')
        self.status_dot.create_oval(2, 2, 10, 10, fill=color, outline='')

    def _set_state(self, state):
        self.state = state
        if state == 'running':
            self._draw_dot(SUCCESS)
            self.status_label.configure(text="Bot działa")
            self.btn_start.configure(state='disabled')
            self.btn_stop.configure(state='normal')
            self._start_time = time.time()
        elif state == 'starting':
            self._draw_dot(WARNING)
            self.status_label.configure(text="Uruchamianie...")
            self.btn_start.configure(state='disabled')
            self.btn_stop.configure(state='disabled')
        else:
            self._draw_dot('#9CA3AF')
            self.status_label.configure(text="Zatrzymany")
            self.btn_start.configure(state='normal')
            self.btn_stop.configure(state='disabled')
            self._start_time = None
            self.uptime_label.configure(text="")

    def _start(self):
        self._set_state('starting')
        self.pm.start_all()

    def _stop(self):
        self.pm.stop_all()
        self._set_state('stopped')
        self.log("Bot zatrzymany.", "INFO")

    def _open_settings(self):
        cfg = load_config()
        if cfg:
            SettingsDialog(self.winfo_toplevel(), cfg, self._on_settings_saved)

    def _on_settings_saved(self):
        self.log("Ustawienia zapisane. Restart bota wymagany.", "WARNING")

    def log(self, msg, level='INFO'):
        """Append a log line with timestamp and color."""
        self.log_text.configure(state='normal')
        ts = datetime.datetime.now().strftime('%H:%M:%S')
        self.log_text.insert('end', f'[{ts}] ', 'TS')
        self.log_text.insert('end', f'{msg}\n', level)
        self.log_text.see('end')
        # Prune to 500 lines
        lines = int(self.log_text.index('end-1c').split('.')[0])
        if lines > 500:
            self.log_text.delete('1.0', f'{lines - 500}.0')
        self.log_text.configure(state='disabled')

    def poll(self):
        """Called by Application every 100ms — drains queue, updates state."""
        lines = self.pm.poll_output()
        for level, msg in lines:
            if level == '[STATUS]':
                if msg == 'tor_ready' or msg == 'tor_already':
                    self.log("Tor gotowy (port 9050 aktywny)", "SUCCESS")
                elif msg == 'bot_started':
                    self._set_state('running')
            else:
                self.log(msg, level)

        # Detect unexpected death
        if self.state == 'running':
            status = self.pm.is_running()
            if not status['bot']:
                self._set_state('stopped')
                self.log("Bot zakończył działanie nieoczekiwanie!", "ERROR")

        # Update uptime
        if self._start_time:
            elapsed = int(time.time() - self._start_time)
            h, m = divmod(elapsed, 3600)
            m, s = divmod(m, 60)
            self.uptime_label.configure(text=f"⏱ {h:02d}:{m:02d}:{s:02d}")

# ═══════════════════════════════════════════════════════════════════════════════
# APPLICATION — Root Window (Gap #2: clam + style)
# ═══════════════════════════════════════════════════════════════════════════════

class Application:
    """Main application: sets up root, style, decides wizard vs dashboard."""

    def __init__(self):
        ensure_single_instance()

        self.root = tk.Tk()
        self.root.title(APP_TITLE)
        self.root.geometry("650x520")
        self.root.minsize(580, 450)
        self.root.configure(bg=BG)
        self.root.option_add('*Background', BG)

        self._setup_style()
        self.pm = ProcessManager()
        self.dashboard = None

        # Decide: wizard or dashboard
        cfg = load_config()
        if config_is_valid(cfg):
            self._show_dashboard()
        else:
            self._show_wizard()

        # Window close handler
        self.root.protocol('WM_DELETE_WINDOW', self._on_close)
        # Start polling loop (Gap #4: after(100ms))
        self._poll_loop()

    def _setup_style(self):
        """Apply clam theme + full modern styling (Gap #2)."""
        style = ttk.Style(self.root)
        style.theme_use('clam')

        # Global
        style.configure('.', background=BG, foreground=TEXT, font=FONT,
                       borderwidth=0, focuscolor=ACCENT)
        style.configure('TFrame', background=BG)
        style.configure('TLabel', background=BG, foreground=TEXT, font=FONT)
        style.configure('Title.TLabel', font=FONT_TITLE, background=BG)
        style.configure('Subtitle.TLabel', font=FONT_SUBTITLE, foreground=TEXT_SEC,
                       background=BG)
        style.configure('Body.TLabel', font=FONT, background=BG)
        style.configure('Hint.TLabel', font=('Segoe UI', 9), foreground=TEXT_SEC,
                       background=BG)

        # Accent button (primary)
        style.configure('Accent.TButton', background=ACCENT, foreground='white',
                       font=FONT_BOLD, padding=(20, 10), borderwidth=0, relief='flat')
        style.map('Accent.TButton',
                  background=[('active', ACCENT_HOVER), ('pressed', ACCENT_PRESSED),
                              ('disabled', '#CCE4F7')],
                  foreground=[('disabled', '#88BBDD')])

        # Secondary button
        style.configure('Secondary.TButton', background=CARD_BG, foreground=TEXT,
                       font=FONT, padding=(16, 8), borderwidth=1, relief='flat')
        style.map('Secondary.TButton',
                  background=[('active', '#E8E8E8'), ('pressed', '#D0D0D0')])

        # Entry
        style.configure('TEntry', fieldbackground='white', borderwidth=1,
                       relief='solid', padding=(10, 8), font=FONT)
        style.map('TEntry',
                  bordercolor=[('focus', ACCENT), ('!focus', BORDER)],
                  lightcolor=[('focus', ACCENT)],
                  darkcolor=[('focus', ACCENT)])

        # Checkbutton / Radiobutton
        style.configure('TCheckbutton', background=BG, font=FONT, focuscolor='')
        style.configure('TRadiobutton', background=BG, font=FONT, focuscolor='')
        style.map('TCheckbutton', background=[('active', BG)])
        style.map('TRadiobutton', background=[('active', BG)])

        # Combobox
        style.configure('TCombobox', fieldbackground='white', padding=(8, 6))

        # Scrollbar (thin)
        style.configure('Vertical.TScrollbar', background=CARD_BG,
                       troughcolor='#1E1E1E', borderwidth=0, width=10)

    def _show_wizard(self):
        SetupWizard(self.root, self._on_wizard_complete)

    def _on_wizard_complete(self):
        self._show_dashboard()

    def _show_dashboard(self):
        if self.dashboard:
            self.dashboard.destroy()
        self.dashboard = Dashboard(self.root, self.pm)
        self.dashboard.pack(fill='both', expand=True)

    def _poll_loop(self):
        """100ms polling loop for process output (Gap #4)."""
        if self.dashboard:
            self.dashboard.poll()
        try:
            self.root.after(100, self._poll_loop)
        except tk.TclError:
            pass  # Window destroyed

    def _on_close(self):
        """Handle window close — warn if bot running."""
        status = self.pm.is_running()
        if status.get('bot') or status.get('tor'):
            answer = messagebox.askyesnocancel(
                "Zamknij",
                "Bot nadal działa.\n\n"
                "Tak = Zatrzymaj bota i zamknij\n"
                "Nie = Zamknij panel (bot działa w tle)\n"
                "Anuluj = Wróć do panelu"
            )
            if answer is True:
                self.pm.stop_all()
                self.root.destroy()
            elif answer is False:
                self.root.destroy()
            # else: cancel — do nothing
        else:
            self.root.destroy()

    def run(self):
        self.root.mainloop()

# ═══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    app = Application()
    app.run()
