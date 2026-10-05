# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Game shell (2026-10-04): Puck Dynasty runs in its OWN native window.

Architecture (the correct one):
- MAIN thread: pywebview window (Edge WebView2 on Windows). This is a
  real game window -- no tabs, no address bar, no browser chrome.
- GAME thread: hidden Tkinter root + Flask server + command queue.
  Tkinter is fine on a background thread as long as ALL Tk calls stay
  on that thread (which they do -- the root is never shown).

Why this works where v0.21.0 crashed: WebView2/COM has a HARD Windows
requirement to run on the main thread. v0.21.0 ran it in a background
thread -> instant crash. Tkinter has no such requirement; it just needs
thread consistency. So the engines swapped threads.

Lifecycle: closing the game window sets the shutdown event; the game
thread exits its loop and tears down cleanly. No ghost processes.

Falls back to a browser tab if pywebview/WebView2 is unavailable.
"""
import threading
import time
import webbrowser

SETUP_URL = "http://localhost:5050/setup"
GAME_URL = "http://localhost:5050/"
APP_TITLE = "Puck Dynasty"

_shutdown_event = threading.Event()
_game_thread = None


def _run_game_thread():
    """Game thread: Tk root (hidden) + Flask + command queue.

    Uses a manual update() loop instead of mainloop() so the main
    thread can signal shutdown cleanly via the event.
    """
    import tkinter as tk
    import web_ui.bridge as _bridge

    root = tk.Tk()
    root.withdraw()  # invisible; the game window is pywebview
    _bridge._setup_root = root
    _bridge.start_web_server(None)  # setup mode: no game yet
    root.after(250, lambda: _bridge.drain_commands(None, root))
    print("🎮 Game thread running (hidden Tk + web server)")

    try:
        while not _shutdown_event.is_set():
            try:
                root.update()  # pump Tk events incl. after() callbacks
            except Exception:
                break
            time.sleep(0.01)
    finally:
        try:
            _bridge._shutting_down = True
        except Exception:
            pass
        for _r in {_bridge._setup_root, _bridge._web_app_ref}:
            try:
                if _r is not None:
                    _r.destroy()
            except Exception:
                pass
        print("🎮 Game thread shut down")


def request_shutdown():
    """Signal the game thread to exit (called after window closes)."""
    _shutdown_event.set()


def launch():
    """Start the game thread, then open the native window on THIS thread.

    Must be called on the main thread (pywebview requirement).
    Returns when the game window closes.
    """
    global _game_thread
    _shutdown_event.clear()
    _game_thread = threading.Thread(target=_run_game_thread, daemon=True,
                                    name="puck-game")
    _game_thread.start()

    # Wait for Flask to be up before opening the window.
    import web_ui.bridge as _bridge
    for _ in range(100):
        if _bridge.server_running():
            break
        time.sleep(0.1)

    opened = False
    try:
        import webview
        print("🖥️  Opening native game window (pywebview)")
        webview.create_window(APP_TITLE, SETUP_URL,
                              width=1600, height=950, resizable=True)
        webview.start()  # blocks until the window closes (main thread)
        opened = True
    except ImportError:
        print("⚠️ pywebview not available; falling back to browser tab")
    except Exception as e:
        print(f"⚠️ Native window failed ({e}); falling back to browser tab")

    if not opened:
        try:
            webbrowser.open(SETUP_URL)
        except Exception:
            pass
        # Browser fallback: wait until the game thread ends on its own
        # (Exit button / heartbeat timeout), then return.
        _game_thread.join()

    # Window closed: shut the game down.
    print("🖥️  Game window closed; shutting down")
    request_shutdown()
    _game_thread.join(timeout=10)
