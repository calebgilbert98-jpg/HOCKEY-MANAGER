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
import webbrowser

SETUP_URL = "http://localhost:5050/setup"
GAME_URL = "http://localhost:5050/"
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


def launch(url=SETUP_URL):
    """Open the game in its own chromeless window. Never raises."""
    exe = _find_browser()
    if exe:
        try:
            # --app: chromeless window (no tabs/address bar). Looks native.
            # (No --user-data-dir: a relative one broke Edge on some
            # machines; the default profile is the reliable choice.)
            subprocess.Popen(
                [exe, f"--app={url}"],
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
