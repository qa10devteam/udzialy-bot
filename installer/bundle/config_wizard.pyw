#!/usr/bin/env python3
"""
Konfiguracja Bota - Udziały
GUI wizard do konfiguracji bota Telegram wyszukującego udziały w nieruchomościach.
Rozszerzenie .pyw powoduje uruchomienie bez okna konsoli na Windows.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import urllib.request
import urllib.error
import json
import re
import os
import subprocess
import threading


class ConfigWizard:
    """Główne okno kreatora konfiguracji."""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Konfiguracja Bota - Udziały")
        self.root.geometry("600x700")
        self.root.resizable(False, False)
        self._center_window()

        # Try 'vista' theme (Windows), fall back to 'clam'
        style = ttk.Style()
        available_themes = style.theme_names()
        if "vista" in available_themes:
            style.theme_use("vista")
        elif "clam" in available_themes:
            style.theme_use("clam")

        # Variables
        self.token_var = tk.StringVar()
        self.owner_id_var = tk.StringVar()
        self.portal_vars = {}

        # Build UI
        self._build_ui()

    def _center_window(self):
        """Wyśrodkuj okno na ekranie."""
        self.root.update_idletasks()
        w = 600
        h = 700
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = (screen_w - w) // 2
        y = (screen_h - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _build_ui(self):
        """Zbuduj interfejs użytkownika."""
        # Main scrollable frame
        main_frame = ttk.Frame(self.root, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # === Step 1: Create Telegram Bot ===
        self._build_step1(main_frame)

        # === Step 2: User ID ===
        self._build_step2(main_frame)

        # === Step 3: Portals ===
        self._build_step3(main_frame)

        # === Bottom buttons ===
        self._build_buttons(main_frame)

    def _build_step1(self, parent):
        """Krok 1: Tworzenie bota Telegram."""
        frame = ttk.LabelFrame(parent, text="Krok 1: Utwórz bota w Telegramie", padding=10)
        frame.pack(fill=tk.X, pady=(0, 10))

        # Instructions text
        instructions = tk.Text(frame, height=6, width=60, wrap=tk.WORD,
                               font=("Segoe UI", 9), relief=tk.FLAT,
                               bg="#f0f0f0")
        instructions.insert(tk.END,
                            "1. Otwórz Telegram i wyszukaj @BotFather\n"
                            "2. Wyślij komendę /newbot\n"
                            '3. Podaj nazwę bota (np. "Moje Udziały")\n'
                            '4. Podaj username bota (np. "moje_udzialy_bot")\n'
                            "5. Skopiuj token który otrzymasz\n")
        instructions.configure(state=tk.DISABLED)
        instructions.pack(fill=tk.X, pady=(0, 8))

        # Token entry
        token_frame = ttk.Frame(frame)
        token_frame.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(token_frame, text="Wklej token bota:").pack(anchor=tk.W)
        self.token_entry = ttk.Entry(token_frame, textvariable=self.token_var,
                                     font=("Consolas", 10), width=55)
        self.token_entry.pack(fill=tk.X, pady=(2, 5))

        # Check button
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X)

        self.check_btn = ttk.Button(btn_frame, text="Sprawdź token",
                                    command=self._check_token)
        self.check_btn.pack(side=tk.LEFT)

        # Status label
        self.token_status = ttk.Label(btn_frame, text="", font=("Segoe UI", 9))
        self.token_status.pack(side=tk.LEFT, padx=(10, 0))

    def _build_step2(self, parent):
        """Krok 2: ID użytkownika Telegram."""
        frame = ttk.LabelFrame(parent, text="Krok 2: Pobierz swój ID użytkownika", padding=10)
        frame.pack(fill=tk.X, pady=(0, 10))

        # Instructions
        instructions = tk.Text(frame, height=4, width=60, wrap=tk.WORD,
                               font=("Segoe UI", 9), relief=tk.FLAT,
                               bg="#f0f0f0")
        instructions.insert(tk.END,
                            "1. Otwórz Telegram i wyszukaj @userinfobot\n"
                            "2. Wyślij /start\n"
                            "3. Skopiuj swoje ID (liczba)\n")
        instructions.configure(state=tk.DISABLED)
        instructions.pack(fill=tk.X, pady=(0, 8))

        # Owner ID entry
        id_frame = ttk.Frame(frame)
        id_frame.pack(fill=tk.X)

        ttk.Label(id_frame, text="Wklej swoje ID:").pack(anchor=tk.W)

        # Register validation for numeric input
        vcmd = (self.root.register(self._validate_numeric), "%P")
        self.id_entry = ttk.Entry(id_frame, textvariable=self.owner_id_var,
                                  font=("Consolas", 10), width=30,
                                  validate="key", validatecommand=vcmd)
        self.id_entry.pack(anchor=tk.W, pady=(2, 0))

    def _build_step3(self, parent):
        """Krok 3: Wybór portali."""
        frame = ttk.LabelFrame(parent, text="Krok 3: Wybierz portale do przeszukiwania", padding=10)
        frame.pack(fill=tk.X, pady=(0, 10))

        portals = ["OLX", "Otodom", "Morizon", "Gratka", "Domiporta"]

        for portal in portals:
            var = tk.BooleanVar(value=True)
            self.portal_vars[portal.lower()] = var
            cb = ttk.Checkbutton(frame, text=portal, variable=var)
            cb.pack(anchor=tk.W, pady=2)

    def _build_buttons(self, parent):
        """Przyciski na dole okna."""
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(btn_frame, text="Anuluj",
                   command=self.root.destroy).pack(side=tk.RIGHT, padx=(5, 0))

        ttk.Button(btn_frame, text="Uruchom bota",
                   command=self._save_and_run).pack(side=tk.RIGHT, padx=(5, 0))

        ttk.Button(btn_frame, text="Zapisz konfigurację",
                   command=self._save_config).pack(side=tk.RIGHT)

    def _validate_numeric(self, value):
        """Walidacja - dozwolone tylko cyfry lub pusty string."""
        if value == "":
            return True
        return value.isdigit()

    def _check_token(self):
        """Sprawdź token bota przez API Telegram."""
        token = self.token_var.get().strip()

        # Validate format first
        if not re.match(r"^\d+:[A-Za-z0-9_-]+$", token):
            self.token_status.configure(text="Błąd: Nieprawidłowy format tokena",
                                        foreground="red")
            return

        # Disable button during check
        self.check_btn.configure(state=tk.DISABLED)
        self.token_status.configure(text="Sprawdzanie...", foreground="gray")

        # Run API call in a thread to avoid freezing UI
        thread = threading.Thread(target=self._verify_token_api, args=(token,),
                                  daemon=True)
        thread.start()

    def _verify_token_api(self, token):
        """Wywołaj API Telegram w osobnym wątku."""
        try:
            url = f"https://api.telegram.org/bot{token}/getMe"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode("utf-8"))

            if data.get("ok"):
                username = data["result"].get("username", "unknown")
                self.root.after(0, self._set_token_status,
                                f"Token poprawny! Bot: @{username}", "green")
            else:
                desc = data.get("description", "Nieznany błąd")
                self.root.after(0, self._set_token_status,
                                f"Błąd: {desc}", "red")

        except urllib.error.URLError:
            self.root.after(0, self._set_token_status,
                            "Nie można połączyć się z Telegramem. Sprawdź internet.", "red")
        except urllib.error.HTTPError as e:
            if e.code == 401:
                self.root.after(0, self._set_token_status,
                                "Błąd: Token jest nieprawidłowy (401 Unauthorized)", "red")
            else:
                self.root.after(0, self._set_token_status,
                                f"Błąd HTTP: {e.code}", "red")
        except Exception as e:
            self.root.after(0, self._set_token_status,
                            f"Błąd: {str(e)}", "red")
        finally:
            self.root.after(0, lambda: self.check_btn.configure(state=tk.NORMAL))

    def _set_token_status(self, text, color):
        """Ustaw status tokena (wywoływane z głównego wątku)."""
        self.token_status.configure(text=text, foreground=color)

    def _build_config_yaml(self):
        """Zbuduj zawartość pliku config.yaml."""
        token = self.token_var.get().strip()
        owner_id = self.owner_id_var.get().strip()

        # Build YAML manually (no external deps)
        lines = [
            "telegram:",
            f'  token: "{token}"',
            f"  owner_id: {owner_id if owner_id else 0}",
            "",
            "portals:",
        ]

        for portal_name, var in self.portal_vars.items():
            enabled = "true" if var.get() else "false"
            lines.append(f"  {portal_name}: {{enabled: {enabled}}}")

        lines.extend([
            "",
            "tor:",
            "  enabled: true",
            "  socks_port: 9050",
            "  control_port: 9051",
            '  control_password: "udzialy2026"',
            "",
            "database:",
            '  path: "data/udzialy.db"',
            "",
        ])

        return "\n".join(lines)

    def _save_config(self):
        """Zapisz konfigurację do pliku config.yaml."""
        token = self.token_var.get().strip()
        owner_id = self.owner_id_var.get().strip()

        # Validate token
        if not token:
            messagebox.showwarning("Brak tokena",
                                   "Wprowadź token bota Telegram (Krok 1).")
            return False

        if not re.match(r"^\d+:[A-Za-z0-9_-]+$", token):
            messagebox.showerror("Nieprawidłowy token",
                                 "Token ma nieprawidłowy format.\n"
                                 "Powinien wyglądać jak: 123456789:ABCdefGHI-jklMNO_pqr")
            return False

        # Warn about empty owner_id but allow save
        if not owner_id:
            result = messagebox.askokcancel(
                "Brak ID użytkownika",
                "Nie podano ID użytkownika (Krok 2).\n"
                "Bot nie będzie wiedział do kogo wysyłać powiadomienia.\n\n"
                "Czy mimo to zapisać konfigurację?")
            if not result:
                return False

        # Write config file
        config_content = self._build_config_yaml()
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml")

        try:
            with open(config_path, "w", encoding="utf-8") as f:
                f.write(config_content)

            messagebox.showinfo("Sukces",
                                f"Konfiguracja została zapisana!\n\n"
                                f"Plik: {config_path}")
            return True

        except OSError as e:
            messagebox.showerror("Błąd zapisu",
                                 f"Nie można zapisać pliku konfiguracji:\n{e}")
            return False

    def _save_and_run(self):
        """Zapisz konfigurację i uruchom bota."""
        if self._save_config():
            bat_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "start_bot.bat")
            if os.path.exists(bat_path):
                try:
                    subprocess.Popen(bat_path, shell=True,
                                     cwd=os.path.dirname(os.path.abspath(__file__)))
                    self.root.destroy()
                except OSError as e:
                    messagebox.showerror("Błąd uruchomienia",
                                         f"Nie można uruchomić bota:\n{e}")
            else:
                messagebox.showwarning("Brak pliku",
                                       f"Nie znaleziono pliku start_bot.bat\n"
                                       f"Ścieżka: {bat_path}\n\n"
                                       "Konfiguracja została zapisana.\n"
                                       "Uruchom bota ręcznie.")

    def run(self):
        """Uruchom główną pętlę aplikacji."""
        self.root.mainloop()


if __name__ == "__main__":
    app = ConfigWizard()
    app.run()
