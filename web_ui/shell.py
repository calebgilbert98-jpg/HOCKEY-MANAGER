# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Game shell (2026-10-04): the game is ONE browser tab.

Opens the system browser to the local web UI. Everything runs on
localhost, fully offline. The Tk root is withdrawn (invisible) but its
mainloop keeps pumping the web command queue.

Why not an embedded webview: on Windows, embedded browser engines
require the main thread, which Tkinter already owns -- running one off
the main thread hard-crashes the process (seen in v0.21.0). The system
browser is a separate process, so there is no threading conflict, and
"the game is the only tab" is exactly the UX requested.

Lifecycle: the tab heartbeats every 30s; if it goes silent for 150s
(closed/crashed) the game shuts itself down so no ghost process
lingers. An Exit button in the hub also shuts down cleanly.
"""
import webbrowser

WEB_URL = "http://localhost:5050/"
SETUP_URL = "http://localhost:5050/setup"


def launch_shell(url=WEB_URL):
    """Open the game in the system browser. Never raises."""
    try:
        webbrowser.open(url)
        print(f"🖥️  Game opened in browser: {url}")
        return True
    except Exception as e:
        print(f"⚠️ Could not open browser: {e}")
        print(f"   Open this URL manually: {url}")
        return False
