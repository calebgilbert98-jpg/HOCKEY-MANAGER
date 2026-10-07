"""Records screen: league/team records browser.

On main (open_records_window), this opens the Stats window focused on
the Records tab rather than being a separate window. The native port
follows the same behavior: this screen immediately redirects to the
Stats screen with the records tab selected.

The actual records content lives in native_ui/screens/stats.py
(_build_records / _build_nhl_records).
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
            stats = self.main_window.show_screen("stats")
            # Focus the records tab if the stats screen exposes it
            if stats is not None:
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
