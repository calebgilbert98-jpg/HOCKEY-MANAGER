"""Records screen: league/team records browser.

DECISION (Team H, Oct 8 2026): this screen stays a redirect by design.
On main, open_records_window opens the Stats window focused on the
Records tab rather than being a separate window. The native port does
the same: navigating to "records" immediately routes to the "stats"
screen with the Records tab selected. The actual records content lives
in native_ui/screens/stats.py (_build_records / _build_nhl_records),
so there is no duplicate records UI.

Implementation note: MainWindow.show_screen returns None, so the
redirect unwraps the cached stats screen from main_window._screens
(the same unwrap MainWindow.show_player performs) to focus the
Records tab. All failures are swallowed so a broken stats screen can
never leave the user on a dead screen.
"""
from PySide6.QtCore import QTimer

from .base import BaseScreen


class RecordsScreen(BaseScreen):
    title = "Records"

    def _build_body(self):
        # Redirect to stats with records tab focused.
        # Use a single-shot timer so the screen exists before navigating.
        QTimer.singleShot(0, self._redirect)

    def _redirect(self):
        try:
            mw = self.main_window
            mw.show_screen("stats")
            # show_screen returns None; unwrap the cached instance.
            scroll = getattr(mw, "_screens", {}).get("stats")
            stats = scroll.widget() if scroll is not None \
                and hasattr(scroll, "widget") else None
            # Focus the records tab if the stats screen exposes it
            tabs = getattr(stats, "tabs", None)
            if tabs is not None:
                for i in range(tabs.count()):
                    if "record" in tabs.tabText(i).lower():
                        tabs.setCurrentIndex(i)
                        break
        except Exception:
            pass

    def refresh(self):
        # Re-redirect on revisit
        self._redirect()
