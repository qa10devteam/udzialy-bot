# Discovery: Windows Subprocess Management for Tkinter GUI

**Date:** 2026-08-22  
**Context:** Building a tkinter desktop app that manages Tor + Python bot processes on Windows 10/11, Python 3.11, all stdlib.

---

## 1. Current Batch Files Analysis

### start_bot.bat
```batch
@echo off
start "" /B "%~dp0tor\tor\tor.exe" -f "%~dp0tor\torrc"   # Start Tor in background
:wait_tor                                                   # Poll loop
timeout /t 2 /nobreak >nul
netstat -an | find "9050" | find "LISTENING" >nul           # Check port
if errorlevel 1 goto wait_tor
"%~dp0python\python.exe" -m bot.main                       # Start bot (blocking)
```

### stop_bot.bat
```batch
wmic process where "CommandLine like '%%bot.main%%'" call terminate  # Kill bot by cmdline
taskkill /f /im tor.exe                                              # Kill tor by image name
```

**Key insight:** The batch approach uses `start /B` (background), polling with `netstat`, and `wmic`/`taskkill` for termination. The GUI must replicate all of this programmatically.

---

## 2. CREATE_NO_WINDOW Flag (0x08000000)

### What it does
- Prevents a subprocess from spawning a visible console window
- Essential for GUI apps that launch CLI tools (Tor, Python scripts)
- Windows-only; `creationflags` parameter on `subprocess.Popen`

### Python 3.11 compatibility
- ✅ Fully supported since Python 3.0+
- ✅ Works on Windows 10/11
- ✅ Compatible with `subprocess.Popen`, `subprocess.run`, `subprocess.call`
- ✅ Can be combined with `PIPE` for stdout/stderr capture
- ✅ Works with `subprocess.CREATE_NO_WINDOW` constant (added Python 3.7)

### Usage pattern
```python
import subprocess
import sys

CREATE_NO_WINDOW = 0x08000000

# Also available as:
# subprocess.CREATE_NO_WINDOW  (Python 3.7+)

proc = subprocess.Popen(
    [exe_path, *args],
    creationflags=CREATE_NO_WINDOW,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    stdin=subprocess.DEVNULL,
    bufsize=1,
)
```

### Pitfalls
- ⚠️ Do NOT combine with `shell=True` — shell already has its own window handling
- ⚠️ On non-Windows platforms, `creationflags` is ignored — use `os.name == 'nt'` guard
- ⚠️ If the subprocess itself spawns a console (e.g., cmd.exe), the flag may not suppress child windows
- ⚠️ `subprocess.STARTUPINFO` with `dwFlags=STARTF_USESHOWWINDOW, wShowWindow=SW_HIDE` is an alternative but more verbose

### Cross-platform guard (for development on Linux)
```python
import sys
_CREATION_FLAGS = 0x08000000 if sys.platform == 'win32' else 0
```

---

## 3. Real-time stdout Capture on Windows

### Problem
Windows does NOT support `select.select()` or `poll()` on pipes. The only reliable approach for real-time line-by-line reading is a dedicated reader thread.

### ✅ Recommended: threading.Thread + readline() loop

```python
import threading
import queue

def _reader_thread(proc, log_queue, stop_event):
    """Read subprocess stdout line-by-line, push to queue."""
    try:
        for line in iter(proc.stdout.readline, b''):
            if stop_event.is_set():
                break
            text = line.decode('utf-8', errors='replace').rstrip('\r\n')
            if text:
                log_queue.put(text)
    except (OSError, ValueError):
        pass  # Pipe closed or process dead
    finally:
        log_queue.put(None)  # Sentinel: stream ended
```

### Why this works
- `readline()` blocks until a full line is available — natural for log output
- Thread terminates when process ends (readline returns `b''`)
- `stop_event` provides graceful shutdown signal
- Queue provides thread-safe delivery to the main (tkinter) thread

### Why NOT asyncio
- asyncio's `create_subprocess_exec` works but:
  - Requires running asyncio event loop alongside tkinter mainloop
  - Complex integration (asyncio.get_event_loop().run_in_executor or async generators)
  - No real advantage for this use case
  - More moving parts → more bugs

### Why NOT os.read() with timeout
- `os.read(fd, n)` also blocks on Windows
- No non-blocking pipe reading on Windows without overlapped I/O (ctypes/win32api)
- Far too complex for this use case

### Buffering gotcha
- Python subprocess buffers stdout by default
- Solutions:
  1. Use `bufsize=1` (line-buffered) in Popen — only works if child uses line buffering
  2. For Python child processes: `PYTHONUNBUFFERED=1` env var or `-u` flag
  3. For Tor: it already writes line-by-line to stdout

```python
env = os.environ.copy()
env['PYTHONUNBUFFERED'] = '1'

proc = subprocess.Popen(
    [python_exe, '-u', '-m', 'bot.main'],
    env=env,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    creationflags=CREATE_NO_WINDOW,
)
```

---

## 4. Reliable Process Tree Killing on Windows

### The problem
- `Popen.terminate()` sends `TerminateProcess()` on Windows — only kills the direct process
- `Popen.kill()` is identical to `terminate()` on Windows (both call TerminateProcess)
- Tor spawns child processes; Python bot may spawn threads/subprocesses
- Orphaned child processes persist after parent is killed

### Solution 1: taskkill /T /F /PID (Recommended)
```python
import subprocess

def kill_process_tree(pid):
    """Kill a process and all its children on Windows."""
    try:
        subprocess.run(
            ['taskkill', '/T', '/F', '/PID', str(pid)],
            creationflags=0x08000000,
            capture_output=True,
            timeout=10,
        )
    except Exception:
        pass
```

- `/T` = kill child processes (tree kill)
- `/F` = force (no graceful shutdown)
- `/PID` = target specific PID
- Returns exit code 128 if process already dead — that's fine

### Solution 2: WMI via subprocess (fallback)
```python
def kill_by_cmdline(pattern):
    """Kill processes whose command line matches pattern."""
    subprocess.run(
        ['wmic', 'process', 'where',
         f"CommandLine like '%{pattern}%'",
         'call', 'terminate'],
        creationflags=0x08000000,
        capture_output=True,
    )
```

### Solution 3: os.kill with signal (Limited)
```python
import os, signal
os.kill(pid, signal.SIGTERM)  # On Windows, only SIGTERM works (maps to TerminateProcess)
```
- Does NOT kill children — not recommended alone

### Recommended approach (belt + suspenders)
```python
def kill_process_tree_safe(proc):
    """Terminate process + children. Fallback to direct kill."""
    if proc is None or proc.poll() is not None:
        return  # Already dead
    
    pid = proc.pid
    
    # 1. Try taskkill /T (tree kill)
    try:
        subprocess.run(
            ['taskkill', '/T', '/F', '/PID', str(pid)],
            creationflags=0x08000000,
            capture_output=True,
            timeout=10,
        )
    except Exception:
        pass
    
    # 2. Ensure Popen object reflects death
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()  # Last resort
```

### Linux equivalent (for dev/testing)
```python
import os, signal

def kill_process_tree(pid):
    """Kill process group on Linux."""
    try:
        os.killpg(os.getpgid(pid), signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        pass
```

### Cross-platform wrapper
```python
import sys

def kill_tree(proc):
    if proc is None or proc.poll() is not None:
        return
    if sys.platform == 'win32':
        subprocess.run(['taskkill', '/T', '/F', '/PID', str(proc.pid)],
                       creationflags=0x08000000, capture_output=True, timeout=10)
    else:
        import os, signal
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
```

---

## 5. Port Readiness Check

### Pattern: socket.connect_ex() in a polling loop

```python
import socket
import time

def wait_for_port(host, port, timeout=60, interval=2):
    """Block until a TCP port is accepting connections."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex((host, port))
        sock.close()
        if result == 0:
            return True
        time.sleep(interval)
    return False
```

### Key points
- ✅ `connect_ex()` returns 0 on success — no exception thrown
- ✅ Works identically on Windows and Linux
- ✅ Safe to call from a background thread
- ✅ `settimeout(1)` prevents indefinite blocking per attempt
- ⚠️ Must close the socket after each attempt (resource leak otherwise)
- ⚠️ Don't use in the tkinter main thread (blocks the GUI)

### For Tor specifically
- Tor SOCKS5 port = 9050 (default)
- Tor usually takes 5-15 seconds to bootstrap
- 60-second timeout is generous but safe for slow connections
- Once port accepts connections, Tor may still be bootstrapping circuits
- For full readiness: send a SOCKS5 handshake or check Tor control port

---

## 6. Process Manager Class Design

```python
class ProcessManager:
    """Manages Tor + Bot subprocess lifecycle."""
    
    def __init__(self, tor_path, python_path, script_dir):
        self.tor_path = tor_path
        self.python_path = python_path
        self.script_dir = script_dir
        
        self._tor_proc = None
        self._bot_proc = None
        self._log_queue = queue.Queue()
        self._reader_thread = None
        self._stop_event = threading.Event()
    
    def start_tor(self) -> bool:
        """Start Tor subprocess. Returns True if port becomes ready."""
        ...
    
    def start_bot(self) -> bool:
        """Start bot subprocess. Returns True if process started."""
        ...
    
    def stop_all(self):
        """Kill bot + Tor process trees."""
        ...
    
    def is_running(self) -> dict:
        """Return status of each process."""
        return {
            'tor': self._tor_proc is not None and self._tor_proc.poll() is None,
            'bot': self._bot_proc is not None and self._bot_proc.poll() is None,
        }
    
    def get_log_lines(self) -> list[str]:
        """Drain the log queue (non-blocking). Returns list of new lines."""
        lines = []
        while True:
            try:
                line = self._log_queue.get_nowait()
                if line is None:
                    break  # Sentinel
                lines.append(line)
            except queue.Empty:
                break
        return lines
```

### Thread safety guarantees
- `queue.Queue` is thread-safe (GIL + internal locks)
- `threading.Event` is thread-safe
- `Popen.poll()` is safe to call from any thread
- `Popen.pid` is set immediately after Popen() returns — safe to read

---

## 7. Tkinter Integration Pattern

### The `root.after()` polling pattern

```python
class App:
    def __init__(self):
        self.root = tk.Tk()
        self.pm = ProcessManager(...)
        self._poll_logs()
    
    def _poll_logs(self):
        """Called every 100ms to drain log queue into GUI."""
        lines = self.pm.get_log_lines()
        for line in lines:
            self._append_to_log_widget(line)
        
        # Also check if processes died unexpectedly
        status = self.pm.is_running()
        if not status['bot'] and self.state == 'running':
            self._handle_bot_crash()
        
        # Reschedule
        self.root.after(100, self._poll_logs)
```

### Why 100ms?
- Fast enough for responsive UI (human can't perceive <100ms lag)
- Slow enough to not waste CPU (10 polls/sec)
- Lines accumulate in the queue between polls → batch update → efficient

### Key rules
1. **NEVER block the tkinter main thread** — no `time.sleep()`, no `proc.wait()`
2. **Use `root.after(0, callback)` for thread→GUI communication** or queue+poll
3. **Start all I/O-bound work in daemon threads** (`daemon=True` → auto-kill on exit)
4. **Use `threading.Event` for stop signals** — threads check `event.is_set()`

### Architecture diagram
```
┌─────────────────────────────────────────────────┐
│                 MAIN THREAD (tkinter)            │
│                                                   │
│  root.after(100) → poll_logs() → update widget  │
│  Button click → pm.start_tor() in new thread    │
│  WM_DELETE_WINDOW → pm.stop_all()               │
└───────────────────────────┬─────────────────────┘
                            │ queue.Queue
┌───────────────────────────┴─────────────────────┐
│              READER THREAD (daemon)              │
│                                                   │
│  while proc.stdout.readline():                  │
│      queue.put(decoded_line)                    │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│              STARTER THREAD (daemon)             │
│                                                   │
│  start_tor() → wait_for_port() → start_bot()   │
│  queue.put("[STATUS] tor_ready")                │
│  queue.put("[STATUS] bot_started")              │
└─────────────────────────────────────────────────┘
```

### Status signaling via queue
Use special prefixed messages for status updates:
```python
log_queue.put("[TOR_READY]")       # Tor port is open
log_queue.put("[BOT_STARTED]")     # Bot process launched
log_queue.put("[BOT_EXITED:0]")    # Bot exited with code 0
log_queue.put("[ERROR] msg")       # Error occurred
```

The GUI poll loop can parse these and update state:
```python
def _poll_logs(self):
    for line in self.pm.get_log_lines():
        if line.startswith("[TOR_READY]"):
            self._set_state("tor_ready")
        elif line.startswith("[BOT_STARTED]"):
            self._set_state("running")
        elif line.startswith("[BOT_EXITED"):
            self._set_state("stopped")
        elif line.startswith("[ERROR]"):
            self._show_error(line[7:])
        else:
            self._append_log(line)
```

---

## 8. Race Conditions & Edge Cases

### Known issues
1. **Double-start**: User clicks Start twice before Tor is ready
   - Fix: Disable button immediately, check state before starting
   
2. **Zombie process on crash**: If the GUI crashes, Tor/Bot keep running
   - Fix: Use `atexit.register(pm.stop_all)` as safety net
   - Fix: On startup, check if port 9050 is already bound (stale Tor)

3. **Pipe deadlock**: If stdout buffer fills and nobody reads it
   - Fix: Always have reader thread running OR use `stderr=STDOUT` to merge

4. **Process exits between poll() and kill()**: Race between checking and killing
   - Fix: Wrap kill in try/except (ProcessLookupError, PermissionError)

5. **Tkinter destroyed during after() callback**: If root.destroy() is called
   - Fix: Guard with `try: self.root.after(...)  except tk.TclError: pass`

6. **Bot imports fail**: Python process exits immediately with ImportError
   - Fix: Read exit code + last stderr lines → show meaningful error

### Startup sequence safety
```python
def _safe_start(self):
    """Idempotent start — safe to call multiple times."""
    if self._starting or self.is_running()['bot']:
        return
    self._starting = True
    threading.Thread(target=self._start_sequence, daemon=True).start()
```

---

## 9. Summary: The Production Pattern

For the final `launcher.pyw`, the process management should use:

| Concern | Solution |
|---------|----------|
| No window | `creationflags=CREATE_NO_WINDOW` |
| Stdout capture | Thread + `readline()` loop → `queue.Queue` |
| GUI update | `root.after(100, poll_queue)` polling |
| Kill tree | `taskkill /T /F /PID` (Windows) |
| Port check | `socket.connect_ex()` in starter thread |
| Stop signal | `threading.Event` |
| Cross-platform | Guards on `sys.platform == 'win32'` |
| Unbuffered | `PYTHONUNBUFFERED=1` env + `-u` flag |
| Safety | `atexit`, try/except on every kill, state guards |

---

## 10. Existing launcher.pyw Analysis

The current `launcher.pyw` already implements most of this correctly:
- ✅ Uses `CREATE_NO_WINDOW = 0x08000000`
- ✅ Uses `threading.Thread(daemon=True)` for start sequence
- ✅ Uses `socket.connect_ex()` for port polling
- ✅ Uses `root.after(0, callback)` for thread→GUI communication
- ✅ Uses `threading.Event` for stop signaling
- ⚠️ Does NOT use `queue.Queue` — uses `root.after(0, _log)` directly from reader thread
- ⚠️ Does NOT kill process tree — only calls `terminate()`/`kill()` on direct process
- ⚠️ Does NOT set `PYTHONUNBUFFERED=1`
- ⚠️ Does NOT use `taskkill /T` — orphan risk with Tor children

### Improvements needed in production:
1. Add `taskkill /T /F /PID` for tree kill
2. Add `PYTHONUNBUFFERED=1` env for bot subprocess
3. Consider switching from direct `root.after(0,...)` to queue polling (more structured)
4. Add `atexit.register()` as safety net
5. Add stale-process detection on startup
