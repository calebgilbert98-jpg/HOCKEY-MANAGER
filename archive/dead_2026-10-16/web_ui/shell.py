# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Game shell (2026-10-04): Puck Dynasty in its OWN window.

v0.23.0 tried pywebview (native embed) and it doesn't launch on
Windows -- WebView2 hard-requires the main thread, Tkinter wants it
too, and the background-thread workarounds are unreliable blind.

This version goes back to the v0.22.0 architecture that provably
works (Tk on main thread, Flask in background) but launches the
browser in CHROMELESS APP MODE:

    msedge.exe --app=http://localhost:5050/setup

That opens a standalone window with NO tabs, NO address bar, NO
favorites bar -- just the game. It looks and feels like a native app
window (this is how many "desktop apps" ship their UI). Fully offline.

Fallbacks: regular browser tab if no Edge/Chrome found.
"""
import os
import subprocess
import time
import urllib.request
import webbrowser

SETUP_URL = "http://localhost:5050/setup"
GAME_URL = "http://localhost:5050/"
HEALTH_URL = "http://127.0.0.1:5050/api/health"
APP_TITLE = "Puck Dynasty"


def _find_browser():
    """Return path to an Edge/Chrome executable, or None."""
    candidates = [
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ]
    for p in candidates:
        if p and os.path.isfile(p):
            return p
    return None


def _wait_for_server(timeout=10.0):
    """Poll /api/health until Flask is accepting connections.

    Prevents the race where the browser opens localhost:5050 before
    Flask has bound the port (user would see "can't reach this page").
    Returns True if the server responded, False on timeout.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(HEALTH_URL, timeout=1) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(0.15)
    return False


def launch(url=SETUP_URL):
    """Open the game in its own chromeless window. Never raises."""
    if not _wait_for_server():
        print("⚠️ Web server did not respond on :5050 — opening URL anyway")
    exe = _find_browser()
    if exe:
        try:
            # --app: chromeless window (no tabs/address bar). Looks native.
            # --start-maximized: fill the screen on launch.
            # --user-data-dir: ISOLATED profile for the game. This is what
            # makes it feel like a Steam game instead of a browser tab:
            # no extensions (Grammarly, ad blockers, etc.), no browsing
            # history, no saved passwords, no dev tools access to the
            # user's real profile. The game gets its own clean sandbox.
            # Uses an absolute path (relative paths broke Edge on some
            # machines).
            try:
                _base = os.path.dirname(os.path.abspath(__file__))
                # Go up from web_ui/ to the game root, then into a profile dir
                _root = os.path.dirname(_base)
                _profile_dir = os.path.join(_root, ".edge-profile")
                os.makedirs(_profile_dir, exist_ok=True)
            except Exception:
                _profile_dir = None
            _args = [exe, "--start-maximized", f"--app={url}"]
            if _profile_dir:
                _args.insert(1, f"--user-data-dir={_profile_dir}")
            subprocess.Popen(
                _args,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "DETACHED_PROCESS", 0),
            )
            print(f"🖥️  Game window opened ({os.path.basename(exe)} app mode)")
            return True
        except Exception as e:
            print(f"⚠️ App-mode launch failed ({e}); falling back to tab")
    try:
        webbrowser.open(url)
        print(f"🖥️  Game opened in browser tab: {url}")
        return True
    except Exception as e:
        print(f"⚠️ Could not open browser: {e}")
        print(f"   Open this URL manually: {url}")
        return False
