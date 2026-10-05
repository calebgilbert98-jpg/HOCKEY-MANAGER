# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Game shell (2026-10-04): the game is ONE window.

Launches the web UI inside an embedded browser window (pywebview, which
uses Edge WebView2 on Windows — preinstalled on Win10/11). The Tkinter
root is withdrawn (invisible) but its mainloop keeps running to drain
the web command queue. No OS popup windows: every dialog is an in-page
web modal.

Falls back to the system browser if pywebview is unavailable.
Fully offline: everything is localhost.
"""
import threading
import webbrowser

WEB_URL = "http://localhost:5050/"
APP_TITLE = "Puck Dynasty"


def launch_shell(tk_root):
    """Show the game window. Call after the web server is up."""
    # Hide the Tk root: it stays alive for the command queue, but the
    # webview is the only visible window.
    try:
        tk_root.withdraw()
    except Exception:
        pass

    try:
        import webview

        def _run():
            try:
                webview.create_window(
                    APP_TITLE, WEB_URL,
                    width=1600, height=950,
                    resizable=True,
                )
                webview.start()
            except Exception:
                pass
            finally:
                # Webview closed: shut the game down cleanly.
                try:
                    tk_root.after(0, tk_root.quit)
                except Exception:
                    pass

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        print("🖥️  Game window: embedded webview")
        return True
    except ImportError:
        print("⚠️ pywebview not installed; opening system browser instead")
        try:
            webbrowser.open(WEB_URL)
        except Exception:
            pass
        return False
