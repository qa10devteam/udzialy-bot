# Research: Modern tkinter GUI Design for Windows 10/11
## State of the Art — 2025/2026

---

## 1. Available ttk Themes (Built-in)

### Themes on Windows (stdlib, no external deps):
| Theme       | Look                      | Modernity | Notes                          |
|-------------|---------------------------|-----------|--------------------------------|
| `winnative` | Windows XP/7 native       | ★★☆☆☆     | Default on Windows, uses OS native widgets |
| `vista`     | Windows Vista/7            | ★★★☆☆     | Better than winnative, uses visual styles API |
| `clam`      | Cross-platform flat-ish   | ★★★☆☆     | Best built-in for custom styling, no 3D borders |
| `alt`       | Alternative classic        | ★★☆☆☆     | Simple, slightly better than default |
| `default`   | Motif-like                 | ★☆☆☆☆     | Avoid — very 1990s                |
| `xpnative`  | XP look                   | ★★☆☆☆     | Legacy                            |

### External Theme Options:
| Theme         | Look                    | Modernity | Dep Size      | Vendorable? |
|---------------|-------------------------|-----------|---------------|-------------|
| `sv_ttk`      | Windows 11 Fluent-ish   | ★★★★★     | ~200KB .tcl   | YES ✓       |
| Azure-ttk     | Modern flat, blue accent | ★★★★☆     | ~150KB .tcl   | YES ✓       |
| Forest-ttk    | Green/nature modern     | ★★★★☆     | ~120KB .tcl   | YES ✓       |
| CustomTkinter | Full custom rendering   | ★★★★★     | Heavy pip dep | NO ✗        |
| ttkbootstrap  | Bootstrap-like          | ★★★★☆     | Heavy pip dep | NO ✗        |

### VERDICT for our project:
**Use `clam` theme as base + custom ttk.Style overrides.** This gives us:
- Zero external dependencies
- Full control over colors, padding, borders
- Works identically on all Windows 10/11 machines
- `clam` is the ONLY built-in theme that properly supports style customization (colors, relief, etc.)

Why NOT vista/winnative: They delegate to Windows visual styles API, which means you CANNOT override most style options — they're hard-coded by the OS.

---

## 2. sv_ttk (Sun Valley Theme) — Analysis

### What it is:
- Created by rdbende (GitHub: rdbende/Sun-Valley-ttk-theme)
- Pure Tcl theme + PNG image assets (for checkboxes, radio buttons, scrollbars)
- Mimics Windows 11 "Sun Valley" design language
- Light and dark mode
- pip package: `sv-ttk` (~2.5MB installed with images)

### Can it be vendored?
- YES, but it's not a single .tcl file — it needs:
  - `sun-valley.tcl` (main theme file, ~15KB)
  - `theme/` folder with PNG sprites (~200+ files, ~2MB total)
- The PNG sprites are the catch — without them, checkboxes/radio buttons/scrollbars look broken
- You CAN vendor it by copying the entire theme folder into your project

### Usage:
```python
import sv_ttk
sv_ttk.set_theme("light")  # or "dark"
```

Or manual vendoring:
```python
root.tk.call("source", "path/to/sun-valley.tcl")
root.tk.call("set_theme", "light")
```

### VERDICT for our project:
**NOT recommended.** Too many files to vendor (200+ PNGs). If we need just "modern look" without radio buttons and checkboxes being pixel-perfect Win11, custom styling on `clam` achieves 90% of the visual quality with zero deps.

---

## 3. Modern tkinter Without External Libraries

### CustomTkinter:
- By TomSchimansky, 7000+ stars
- Draws widgets on Canvas (not ttk) — fully custom rendering
- Rounded corners, hover effects, dark mode built-in
- **Problem:** Requires `pip install customtkinter` + `packaging` dep
- **Problem:** Uses its own widget classes (CTkButton, CTkEntry) — not ttk-compatible
- **VERDICT: TOO HEAVY** for a vendored single-file approach

### ttkbootstrap:
- Bootstrap-like styling for ttk
- Requires `pip install ttkbootstrap` + Pillow dep
- **VERDICT: TOO HEAVY** (Pillow alone is 10MB+)

### ✅ Can we achieve modern look with JUST stdlib ttk + custom styling?
**YES, absolutely.** Here's how:

```python
import tkinter as tk
from tkinter import ttk

def setup_modern_style(root):
    style = ttk.Style(root)
    style.theme_use('clam')  # CRITICAL: clam allows full customization
    
    # Colors
    BG = '#FFFFFF'
    CARD_BG = '#F5F5F5'
    ACCENT = '#0078D4'  # Windows 11 blue
    ACCENT_HOVER = '#106EBE'
    TEXT = '#1A1A1A'
    TEXT_SECONDARY = '#666666'
    BORDER = '#E0E0E0'
    
    # Global
    style.configure('.', 
        background=BG, 
        foreground=TEXT,
        font=('Segoe UI', 10),
        borderwidth=0,
        focuscolor=ACCENT
    )
    
    # Frames
    style.configure('TFrame', background=BG)
    style.configure('Card.TFrame', background=CARD_BG, relief='flat')
    
    # Labels
    style.configure('TLabel', background=BG, foreground=TEXT, font=('Segoe UI', 10))
    style.configure('Title.TLabel', font=('Segoe UI Semibold', 16), foreground=TEXT)
    style.configure('Subtitle.TLabel', font=('Segoe UI', 11), foreground=TEXT_SECONDARY)
    
    # Buttons — Modern flat style
    style.configure('TButton',
        background=ACCENT,
        foreground='white',
        font=('Segoe UI Semibold', 10),
        padding=(20, 10),
        borderwidth=0,
        relief='flat'
    )
    style.map('TButton',
        background=[('active', ACCENT_HOVER), ('pressed', '#005A9E')],
        foreground=[('active', 'white')]
    )
    
    # Secondary button (outline style)
    style.configure('Secondary.TButton',
        background=BG,
        foreground=ACCENT,
        borderwidth=1,
        relief='solid'
    )
    style.map('Secondary.TButton',
        background=[('active', '#F0F7FF')]
    )
    
    # Entry fields
    style.configure('TEntry',
        fieldbackground='white',
        borderwidth=1,
        relief='solid',
        padding=(10, 8)
    )
    style.map('TEntry',
        bordercolor=[('focus', ACCENT), ('!focus', BORDER)]
    )
    
    # Notebook (tabs)
    style.configure('TNotebook', background=BG, borderwidth=0)
    style.configure('TNotebook.Tab',
        background=CARD_BG,
        foreground=TEXT_SECONDARY,
        padding=(16, 8),
        font=('Segoe UI', 10)
    )
    style.map('TNotebook.Tab',
        background=[('selected', BG)],
        foreground=[('selected', ACCENT)]
    )
    
    # Progressbar
    style.configure('TProgressbar',
        background=ACCENT,
        troughcolor=BORDER,
        borderwidth=0,
        thickness=4
    )
    
    # Separator
    style.configure('TSeparator', background=BORDER)
    
    return style
```

---

## 4. Specific UI Components — Implementation Patterns

### 4.1 Rounded Buttons (ttk limitation workaround)

ttk buttons CANNOT have truly rounded corners (no border-radius in Tcl themes).  
**Workaround options:**
1. **Flat button with generous padding** — looks modern even without radius
2. **Canvas-drawn button** — full control but loses ttk accessibility
3. **Accept rectangular** — Windows 11 itself uses subtle rounding (2-4px) that the eye doesn't notice at small sizes

**Recommended approach (flat button, looks great):**
```python
style.configure('Accent.TButton',
    background='#0078D4',
    foreground='white',
    padding=(24, 12),
    font=('Segoe UI Semibold', 11),
    borderwidth=0,
    relief='flat'
)
# The generous padding + flat relief makes it look modern
```

### 4.2 Cards/Panels with Shadow

True drop shadows are NOT possible in tkinter without hacks.  
**Best alternatives:**

```python
# Option A: Raised frame with subtle border (recommended)
card = ttk.Frame(parent, style='Card.TFrame', padding=20)
# style.configure('Card.TFrame', background='#F8F9FA', relief='solid', borderwidth=1)
# Set bordercolor to a very light gray

# Option B: Canvas with fake shadow (more complex)
def create_card_with_shadow(parent, width, height):
    canvas = tk.Canvas(parent, width=width+4, height=height+4, 
                       bg='white', highlightthickness=0)
    # Draw shadow (offset gray rectangle)
    canvas.create_rectangle(4, 4, width+4, height+4, fill='#E8E8E8', outline='')
    # Draw card
    canvas.create_rectangle(0, 0, width, height, fill='#FFFFFF', outline='#E0E0E0')
    return canvas

# Option C: Multiple nested frames (simplest visual separator)
outer = tk.Frame(parent, bg='#E0E0E0', padx=1, pady=1)  # border color
inner = tk.Frame(outer, bg='#FFFFFF', padx=20, pady=16)
inner.pack(fill='both', expand=True)
```

### 4.3 Color Status Indicators

```python
class StatusIndicator(tk.Canvas):
    """Colored circle indicator (green/red/yellow)"""
    COLORS = {
        'online': '#10B981',   # Green
        'offline': '#EF4444',  # Red  
        'warning': '#F59E0B',  # Yellow/Amber
        'unknown': '#9CA3AF',  # Gray
    }
    
    def __init__(self, parent, status='unknown', size=12, **kwargs):
        super().__init__(parent, width=size, height=size, 
                        highlightthickness=0, bg=parent.cget('bg'), **kwargs)
        self.size = size
        self.set_status(status)
    
    def set_status(self, status):
        self.delete('all')
        color = self.COLORS.get(status, self.COLORS['unknown'])
        pad = 2
        self.create_oval(pad, pad, self.size-pad, self.size-pad, 
                        fill=color, outline='')
```

### 4.4 Scrollable Log Area (with colored tags)

```python
class LogDisplay(tk.Frame):
    """Scrollable log with colored severity levels"""
    
    def __init__(self, parent, height=200):
        super().__init__(parent)
        
        self.text = tk.Text(self, 
            height=10, 
            wrap='word',
            font=('Consolas', 9),
            bg='#1E1E1E',  # Dark background for logs
            fg='#D4D4D4',
            relief='flat',
            padx=12,
            pady=8,
            state='disabled',
            highlightthickness=0,
            borderwidth=0
        )
        
        scrollbar = ttk.Scrollbar(self, orient='vertical', command=self.text.yview)
        self.text.configure(yscrollcommand=scrollbar.set)
        
        self.text.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Color tags
        self.text.tag_configure('INFO', foreground='#D4D4D4')
        self.text.tag_configure('SUCCESS', foreground='#10B981')
        self.text.tag_configure('WARNING', foreground='#F59E0B')
        self.text.tag_configure('ERROR', foreground='#EF4444')
        self.text.tag_configure('TIMESTAMP', foreground='#6B7280')
    
    def log(self, message, level='INFO'):
        import datetime
        self.text.configure(state='normal')
        timestamp = datetime.datetime.now().strftime('%H:%M:%S')
        self.text.insert('end', f'[{timestamp}] ', 'TIMESTAMP')
        self.text.insert('end', f'{message}\n', level)
        self.text.see('end')  # Auto-scroll
        self.text.configure(state='disabled')
```

### 4.5 Tab-Based Wizard (ttk.Notebook)

```python
class SetupWizard(ttk.Notebook):
    """Step-by-step wizard using Notebook tabs"""
    
    def __init__(self, parent):
        super().__init__(parent, style='Wizard.TNotebook')
        self.pages = []
        
    def add_step(self, title, frame):
        self.add(frame, text=f'  {title}  ')
        self.pages.append(frame)
    
    def next_step(self):
        current = self.index('current')
        if current < len(self.pages) - 1:
            self.select(current + 1)
    
    def prev_step(self):
        current = self.index('current')
        if current > 0:
            self.select(current - 1)

# Alternative: Hide tabs, use Next/Back buttons to control
# This is cleaner for a wizard UX:
style.layout('Wizard.TNotebook.Tab', [])  # HIDE TAB BAR
# Then control page switching programmatically
```

**Better wizard pattern (no visible tabs):**
```python
class StepWizard(tk.Frame):
    """Wizard with hidden tabs — controlled by Next/Back buttons"""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.steps = []
        self.current_step = 0
        
        # Progress indicator at top
        self.progress_frame = tk.Frame(self, bg='white')
        self.progress_frame.pack(fill='x', pady=(0, 20))
        
        # Content area (shows one step at a time)
        self.content = tk.Frame(self, bg='white')
        self.content.pack(fill='both', expand=True)
        
        # Navigation buttons at bottom
        self.nav_frame = tk.Frame(self, bg='white')
        self.nav_frame.pack(fill='x', pady=(20, 0))
        
    def show_step(self, index):
        # Hide all, show target
        for step in self.steps:
            step.pack_forget()
        self.steps[index].pack(in_=self.content, fill='both', expand=True)
        self.current_step = index
        self._update_progress()
```

---

## 5. Making tkinter NOT Look Like 1990s

### 5.1 Font Choices

```python
# Windows 10/11 system font
FONT_FAMILY = 'Segoe UI'
FONT_FAMILY_MONO = 'Consolas'  # or 'Cascadia Code' on Win11

# Font scale  
FONTS = {
    'h1': (FONT_FAMILY + ' Semibold', 20),
    'h2': (FONT_FAMILY + ' Semibold', 14),
    'body': (FONT_FAMILY, 10),
    'small': (FONT_FAMILY, 9),
    'button': (FONT_FAMILY + ' Semibold', 10),
    'mono': (FONT_FAMILY_MONO, 9),
}

# Verify font exists (fallback)
import tkinter.font as tkfont
available = tkfont.families()
if 'Segoe UI' not in available:
    FONT_FAMILY = 'Arial'  # fallback (unlikely on Windows)
```

### 5.2 Padding/Spacing (Modern = More Whitespace)

```python
# Key principle: GENEROUS padding everywhere
SPACING = {
    'window_padding': 32,      # Edge of window to content
    'section_gap': 24,         # Between major sections
    'card_padding': 20,        # Inside cards
    'element_gap': 12,         # Between form elements
    'button_padding_x': 24,    # Horizontal button padding
    'button_padding_y': 10,    # Vertical button padding
    'input_padding_x': 12,     # Input field padding
    'input_padding_y': 8,
}

# Apply to root window
root.configure(padx=SPACING['window_padding'], pady=SPACING['window_padding'])

# Between elements — use pack with pady
label.pack(anchor='w', pady=(0, 4))
entry.pack(fill='x', pady=(0, SPACING['element_gap']))
```

### 5.3 Color Palette — Light Theme

```python
# Windows 11-inspired light palette
COLORS = {
    # Backgrounds
    'bg_primary': '#FFFFFF',       # Main window background
    'bg_secondary': '#F5F5F5',     # Cards, panels
    'bg_tertiary': '#FAFAFA',      # Subtle sections
    'bg_hover': '#F0F0F0',         # Hover states
    
    # Accent
    'accent': '#0078D4',           # Windows 11 blue
    'accent_hover': '#106EBE',
    'accent_pressed': '#005A9E',
    'accent_light': '#E8F4FD',     # Light blue tint (selected items)
    
    # Text
    'text_primary': '#1A1A1A',     # Main text (almost black)
    'text_secondary': '#666666',   # Secondary/descriptive text
    'text_disabled': '#AAAAAA',    # Disabled states
    'text_on_accent': '#FFFFFF',   # Text on accent bg
    
    # Borders
    'border': '#E0E0E0',           # Default border
    'border_strong': '#C0C0C0',    # Emphasized borders
    'border_focus': '#0078D4',     # Focus ring = accent
    
    # Semantic
    'success': '#10B981',          # Green
    'warning': '#F59E0B',          # Amber
    'error': '#EF4444',            # Red
    'info': '#3B82F6',             # Blue
}
```

### 5.4 Flat Design Rules

```python
# RULES for modern look:
# 1. relief='flat' EVERYWHERE (no 'raised', 'sunken', 'groove')
# 2. borderwidth=0 or borderwidth=1 with light color
# 3. No default tkinter gray (#d9d9d9) anywhere visible
# 4. Use color/contrast to separate sections, not borders
# 5. Highlight with accent color, not bold/underline

# Kill ALL 3D borders globally:
style.configure('.', relief='flat', borderwidth=0)

# For entries that need a border:
style.configure('TEntry', relief='flat', borderwidth=1)
style.map('TEntry', 
    lightcolor=[('focus', '#0078D4'), ('!focus', '#E0E0E0')],
    darkcolor=[('focus', '#0078D4'), ('!focus', '#E0E0E0')]
)

# Window itself:
root.configure(bg='#FFFFFF')
root.option_add('*Background', '#FFFFFF')
root.option_add('*Foreground', '#1A1A1A')
```

---

## 6. System Tray on Windows

### Option A: tkinter withdraw/deiconify (NO tray icon)
```python
# Can minimize to taskbar but NO system tray icon without external libs
root.protocol('WM_DELETE_WINDOW', lambda: root.withdraw())  # Hide window
root.iconify()  # Minimize to taskbar (still visible there)
root.deiconify()  # Restore

# This is NOT true system tray — just hiding the window
# User has no way to bring it back without Alt+Tab
```

### Option B: pystray (recommended — tiny, vendorable)
- `pystray` is ~50KB of Python code
- Depends on `Pillow` for icon image (PROBLEM — Pillow is huge)
- Can work with a .ico file directly on Windows (via win32 API)
- **VERDICT: Not worth it for this project**

### Option C: ctypes + win32 API (advanced, no deps)
```python
# Technically possible with ctypes Shell_NotifyIconW
# But VERY complex (200+ lines of ctypes struct definitions)
# Not recommended unless critical requirement
```

### ✅ VERDICT for our project:
**Skip system tray entirely.** Instead:
1. App stays in taskbar when running (normal window behavior)
2. Close button → ask "Minimize to taskbar? Bot will keep running."
3. Use `root.iconify()` to minimize (stays in taskbar)
4. Double-click .pyw runs only one instance (check lock file)
5. Bot process lives independently — killing GUI doesn't kill bot

**Better pattern:**
```python
def on_close():
    if bot_is_running():
        if messagebox.askyesno("Zamknij", 
            "Bot nadal działa. Zamknąć okno?\n"
            "Bot będzie działać w tle.\n"
            "Uruchom ponownie aby zobaczyć panel."):
            root.destroy()
    else:
        root.destroy()

root.protocol('WM_DELETE_WINDOW', on_close)
```

---

## 7. subprocess.Popen + CREATE_NO_WINDOW Pattern

### 7.1 Confirmed Working Pattern:

```python
import subprocess
import sys
import os

# Windows flag to prevent console window from appearing
CREATE_NO_WINDOW = 0x08000000

def start_hidden_process(cmd, cwd=None):
    """Start a process with NO visible console window (Windows)"""
    kwargs = {
        'stdout': subprocess.PIPE,
        'stderr': subprocess.PIPE,
        'stdin': subprocess.DEVNULL,
        'cwd': cwd,
        'creationflags': CREATE_NO_WINDOW if sys.platform == 'win32' else 0,
    }
    
    # For .pyw files, use pythonw.exe
    # For .py files or commands, this hides their console
    process = subprocess.Popen(cmd, **kwargs)
    return process
```

### 7.2 Real-time stdout capture:

```python
import threading
import queue

class ProcessManager:
    """Manages a background process with real-time log capture"""
    
    def __init__(self, on_output=None):
        self.process = None
        self.output_queue = queue.Queue()
        self.on_output = on_output  # callback(line, stream)
        self._reader_threads = []
    
    def start(self, cmd, cwd=None):
        CREATE_NO_WINDOW = 0x08000000
        
        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            cwd=cwd,
            creationflags=CREATE_NO_WINDOW if sys.platform == 'win32' else 0,
            bufsize=1,           # Line buffered
            text=True,           # Text mode (decode to str)
            encoding='utf-8',
            errors='replace'     # Handle encoding errors gracefully
        )
        
        # Start reader threads for stdout and stderr
        for stream, name in [(self.process.stdout, 'stdout'), 
                             (self.process.stderr, 'stderr')]:
            t = threading.Thread(target=self._reader, args=(stream, name), daemon=True)
            t.start()
            self._reader_threads.append(t)
    
    def _reader(self, stream, name):
        """Reader thread — reads line by line, puts to queue"""
        try:
            for line in iter(stream.readline, ''):
                if line:
                    self.output_queue.put((name, line.rstrip('\n')))
            stream.close()
        except (ValueError, OSError):
            pass  # Stream closed
    
    def poll_output(self):
        """Non-blocking: get all available output lines"""
        lines = []
        while True:
            try:
                lines.append(self.output_queue.get_nowait())
            except queue.Empty:
                break
        return lines
    
    def is_running(self):
        if self.process is None:
            return False
        return self.process.poll() is None
    
    def stop(self):
        if self.process and self.is_running():
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
```

### 7.3 Threading Pattern: reader thread + queue + after() poll

```python
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.process_mgr = ProcessManager()
        self.log_display = LogDisplay(self)
        # ... setup UI ...
        
        # Start polling loop
        self._poll_output()
    
    def _poll_output(self):
        """Called every 100ms via after() — checks for new output"""
        lines = self.process_mgr.poll_output()
        for stream, line in lines:
            level = 'ERROR' if stream == 'stderr' else 'INFO'
            # Parse log level from line if possible
            if '[ERROR]' in line or 'Error' in line:
                level = 'ERROR'
            elif '[WARN' in line:
                level = 'WARNING'
            elif 'success' in line.lower() or '[OK]' in line:
                level = 'SUCCESS'
            self.log_display.log(line, level)
        
        # Check if process died
        if self.process_mgr.process and not self.process_mgr.is_running():
            returncode = self.process_mgr.process.returncode
            if returncode != 0:
                self.log_display.log(f'Proces zakończony z kodem {returncode}', 'ERROR')
            self._update_status('offline')
        
        # Schedule next poll (100ms = responsive, not CPU-heavy)
        self.after(100, self._poll_output)
    
    def start_bot(self):
        """Start the bot process"""
        cmd = [sys.executable, 'bot.py']
        self.process_mgr.start(cmd, cwd=self.bot_dir)
        self._update_status('online')
        self.log_display.log('Bot uruchomiony', 'SUCCESS')
    
    def stop_bot(self):
        """Stop the bot process"""
        self.process_mgr.stop()
        self._update_status('offline')
        self.log_display.log('Bot zatrzymany', 'INFO')
```

### 7.4 Critical: Python buffering issue

```python
# PROBLEM: Python buffers stdout when not connected to a terminal
# SOLUTION: Run child Python with -u flag (unbuffered) or PYTHONUNBUFFERED=1

cmd = [sys.executable, '-u', 'bot.py']  # -u = unbuffered stdout/stderr

# OR set environment:
env = os.environ.copy()
env['PYTHONUNBUFFERED'] = '1'
process = subprocess.Popen(cmd, env=env, ...)
```

---

## 8. Architecture Decision Summary

### For our Launcher.pyw:

| Decision | Choice | Reason |
|----------|--------|--------|
| Theme | `clam` + custom style | Zero deps, full control |
| Font | Segoe UI / Segoe UI Semibold | Native Windows 10/11 |
| Colors | White + Light gray + Win11 blue accent | Clean, professional |
| Buttons | Flat, generous padding, accent color | No rounded corners needed |
| Cards | Frame with 1px border (#E0E0E0) | Simple, effective |
| Status | Canvas circles (green/red/gray) | Easy to update |
| Logs | tk.Text dark bg + colored tags | VS Code-like feel |
| Wizard | Frame stacking (show/hide) | Simpler than Notebook |
| System tray | Skip — just minimize to taskbar | Too complex for zero benefit |
| Subprocess | CREATE_NO_WINDOW + threading | Proven pattern |
| Output capture | Thread → Queue → after(100ms) poll | Standard tkinter threading |

### Key Principles:
1. **Everything flat** — no 3D borders, no sunken/raised relief
2. **White space is your friend** — 32px window padding, 20px card padding, 12px between elements
3. **Accent color sparingly** — only primary buttons, active tabs, focus rings
4. **Dark log area** — high contrast against light UI, VS Code terminal feel
5. **Big friendly buttons** — minimum 40px height, clear labels in Polish
6. **Single font family** — Segoe UI everywhere (except logs: Consolas)
7. **No scrollbar horror** — auto-hide or style thin/flat
8. **Responsive status** — user should always see if bot is running (indicator + label)

---

## 9. Example: Minimal Modern tkinter Window

```python
"""Minimal example of modern-looking tkinter on Windows"""
import tkinter as tk
from tkinter import ttk

class ModernApp(tk.Tk):
    def __init__(self):
        super().__init__()
        
        self.title("Udziały Bot")
        self.geometry("600x450")
        self.configure(bg='#FFFFFF')
        self.resizable(False, False)
        
        # Windows DPI awareness (important for crisp text!)
        try:
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1)
        except:
            pass
        
        self._setup_style()
        self._build_ui()
    
    def _setup_style(self):
        style = ttk.Style(self)
        style.theme_use('clam')
        
        # Colors
        style.configure('.', background='#FFFFFF', foreground='#1A1A1A',
                       font=('Segoe UI', 10))
        style.configure('TFrame', background='#FFFFFF')
        style.configure('TLabel', background='#FFFFFF')
        style.configure('Title.TLabel', font=('Segoe UI Semibold', 18))
        style.configure('Subtitle.TLabel', font=('Segoe UI', 10), foreground='#666666')
        
        # Primary button
        style.configure('Accent.TButton',
            background='#0078D4', foreground='white',
            font=('Segoe UI Semibold', 11), padding=(24, 12),
            borderwidth=0, relief='flat')
        style.map('Accent.TButton',
            background=[('active', '#106EBE'), ('pressed', '#005A9E')])
        
        # Secondary button  
        style.configure('Secondary.TButton',
            background='#F5F5F5', foreground='#333333',
            font=('Segoe UI', 10), padding=(16, 8),
            borderwidth=1, relief='flat')
        style.map('Secondary.TButton',
            background=[('active', '#E8E8E8')])
    
    def _build_ui(self):
        # Main container with padding
        main = ttk.Frame(self, padding=32)
        main.pack(fill='both', expand=True)
        
        # Title
        ttk.Label(main, text="🤖 Udziały Bot", style='Title.TLabel').pack(anchor='w')
        ttk.Label(main, text="Panel zarządzania botem Telegram", 
                 style='Subtitle.TLabel').pack(anchor='w', pady=(4, 24))
        
        # Status card
        card = tk.Frame(main, bg='#F5F5F5', padx=20, pady=16)
        card.pack(fill='x', pady=(0, 16))
        
        status_row = tk.Frame(card, bg='#F5F5F5')
        status_row.pack(fill='x')
        
        # Green dot
        dot = tk.Canvas(status_row, width=12, height=12, bg='#F5F5F5', 
                       highlightthickness=0)
        dot.create_oval(2, 2, 10, 10, fill='#10B981', outline='')
        dot.pack(side='left', padx=(0, 8))
        
        tk.Label(status_row, text="Bot działa", bg='#F5F5F5',
                font=('Segoe UI Semibold', 11), fg='#1A1A1A').pack(side='left')
        
        # Buttons
        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill='x', pady=(16, 0))
        
        ttk.Button(btn_frame, text="⏹ Zatrzymaj", style='Secondary.TButton',
                  command=self.stop_bot).pack(side='left', padx=(0, 8))
        ttk.Button(btn_frame, text="▶ Uruchom", style='Accent.TButton',
                  command=self.start_bot).pack(side='left')
    
    def start_bot(self):
        pass
    
    def stop_bot(self):
        pass

if __name__ == '__main__':
    app = ModernApp()
    app.mainloop()
```

---

## 10. DPI Awareness on Windows (CRITICAL)

```python
# Without this, text and UI looks blurry on HiDPI displays
# MUST be called BEFORE creating Tk() instance

import sys
if sys.platform == 'win32':
    try:
        from ctypes import windll
        # Per-monitor DPI awareness (Windows 10+)
        windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
    except (AttributeError, OSError):
        try:
            # Fallback: system DPI awareness
            windll.user32.SetProcessDPIAware()
        except:
            pass
```

---

## 11. Single-Instance Lock (prevent multiple launches)

```python
import os
import sys

def ensure_single_instance(lock_name='udzialy_bot_launcher'):
    """Ensure only one instance runs. Returns lock file handle or exits."""
    if sys.platform == 'win32':
        # Windows: named mutex
        import ctypes
        kernel32 = ctypes.windll.kernel32
        mutex = kernel32.CreateMutexW(None, False, f'Global\\{lock_name}')
        if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
            # Another instance running — bring it to front
            return False
        return True
    else:
        # Unix: lock file (for testing)
        lock_path = f'/tmp/{lock_name}.lock'
        try:
            lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(lock_fd, str(os.getpid()).encode())
            return True
        except FileExistsError:
            return False
```

---

## Summary: Implementation Approach

For the Udziały Bot Launcher, we will:

1. **Use `clam` theme** with complete custom style overrides → Windows 11-like flat design
2. **Segoe UI font family** everywhere (native Windows feel)
3. **White + light gray + blue accent** color scheme
4. **Frame-based wizard** (not Notebook) for first-run setup
5. **Canvas status indicators** for bot online/offline state
6. **Dark tk.Text widget** for real-time log display
7. **subprocess + CREATE_NO_WINDOW** for invisible Tor/bot processes
8. **Thread + Queue + after()** for real-time output polling
9. **No system tray** — just standard minimize behavior
10. **DPI awareness via ctypes** before Tk() instantiation
11. **Named mutex** for single-instance enforcement
12. **.pyw extension** = zero console windows ever
