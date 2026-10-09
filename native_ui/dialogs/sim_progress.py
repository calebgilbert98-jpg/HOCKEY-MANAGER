"""Sim progress dialog + fallback-save helper for long sim operations.

Native Qt port of the mainline ``sim_progress.py`` and ``day_sim_loading.py``.

Two progress surfaces:
  * ``SimProgressDialog`` -- modal dialog with a determinate progress bar
    and Cancel button. Two modes:
      - synchronous: caller pumps ``dlg.update(fraction, status)`` between
        sim steps so the app shows live progress instead of freezing;
      - threaded (``run_threaded``): the sim runs in a worker thread while
        the dialog stays responsive, with Cancel support.
  * ``DaySimLoadingOverlay`` -- non-modal toast pinned to the bottom-right
    corner for day simulation. Indeterminate spinner + status text. Never
    modal, never grabs focus (matches the mainline design note: it must not
    block the Game Day Watch/Quick choice).

Also ported:
  * ``create_fallback_save`` -- snapshot before a heavy sim; never raises.
  * ``confirm_heavy_sim`` / ``ask_heavy_sim`` -- heavy-sim confirmation gates.

All helpers are try/except guarded and never raise -- a broken progress UI
must never block the sim itself.
"""
import os
import queue
import threading
from datetime import datetime

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout,
    QWidget,
)

from . import modal


# ---------------------------------------------------------------------------
# SimProgressDialog
# ---------------------------------------------------------------------------

class SimProgressDialog(QDialog):
    """Modal progress dialog for a long sim operation.

    Usage:
        dlg = SimProgressDialog(parent, title="Simulating Playoffs",
                                warning="...")
        try:
            for i, step in enumerate(steps):
                ... do work ...
                dlg.update((i + 1) / len(steps), f"Working on {step}...")
        finally:
            dlg.close()

    For a cancelable background sim, use ``run_threaded`` instead.
    """

    def __init__(self, parent=None, title="Simulating...",
                 status="Starting...",
                 warning=("This can take a minute or two. The app may appear "
                          "frozen while it works -- this is normal."),
                 cancelable=False):
        super().__init__(parent)
        self._closed = False
        self._cancel_event = threading.Event()
        self._cancelable = bool(cancelable)

        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(460)
        self.setMaximumWidth(460)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(24, 20, 24, 20)

        title_lbl = QLabel(title)
        title_lbl.setObjectName("dialog-title")
        title_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_lbl)

        self._status_lbl = QLabel(status)
        self._status_lbl.setWordWrap(True)
        self._status_lbl.setAlignment(Qt.AlignCenter)
        self._status_lbl.setStyleSheet("color: #E8ECF1; font-size: 13px;")
        layout.addWidget(self._status_lbl)

        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setTextVisible(True)
        self._bar.setStyleSheet(
            "QProgressBar { border: 1px solid #2a2f3a; border-radius: 4px;"
            " background: #1a1d24; height: 22px; text-align: center;"
            " color: #E8ECF1; font-size: 12px; }"
            "QProgressBar::chunk { background: #3B82F6; border-radius: 3px; }"
        )
        layout.addWidget(self._bar)

        warn_lbl = QLabel(warning)
        warn_lbl.setWordWrap(True)
        warn_lbl.setAlignment(Qt.AlignCenter)
        warn_lbl.setStyleSheet("color: #8B93A5; font-size: 11px;")
        layout.addWidget(warn_lbl)

        if self._cancelable:
            btn_row = QHBoxLayout()
            btn_row.addStretch()
            cancel_btn = QPushButton("Cancel")
            cancel_btn.setCursor(Qt.PointingHandCursor)
            cancel_btn.clicked.connect(self._on_cancel)
            btn_row.addWidget(cancel_btn)
            btn_row.addStretch()
            layout.addLayout(btn_row)

    def _on_cancel(self):
        """User hit Cancel: the worker finishes the current step, then stops."""
        self._cancel_event.set()
        try:
            self._status_lbl.setText("Cancelling... finishing the current step.")
        except Exception:
            pass

    @property
    def cancel_event(self):
        """threading.Event the worker checks between sim steps."""
        return self._cancel_event

    def was_cancelled(self):
        return self._cancel_event.is_set()

    def update(self, fraction, status=None):
        """Advance the bar (0.0-1.0) and pump the UI. Safe to call often."""
        if self._closed:
            return
        try:
            pct = max(0.0, min(1.0, float(fraction))) * 100.0
            self._bar.setValue(int(pct))
            if status is not None:
                self._status_lbl.setText(str(status))
            # Pump the event loop so the dialog repaints during a
            # synchronous (same-thread) sim.
            from PySide6.QtWidgets import QApplication
            QApplication.processEvents()
        except Exception:
            pass

    def close(self):
        if self._closed:
            return
        self._closed = True
        try:
            super().close()
        except Exception:
            pass

    # QDialog.closeEvent -> mark closed so update() becomes a no-op.
    def closeEvent(self, event):
        self._closed = True
        super().closeEvent(event)


def run_threaded(parent, title, worker, on_done=None,
                 status="Starting..."):
    """Run a heavy sim in a worker thread with a cancelable progress dialog.

    worker(cancel_event, progress) runs OFF the UI thread and must not touch
    widgets -- only sim objects. progress(fraction, status) is thread-safe
    (it queues to the UI thread). The worker should check
    cancel_event.is_set() between steps and return early when set.

    on_done(cancelled, error) runs ON the UI thread after the worker
    finishes, so it can safely refresh widgets. Returns the dialog.
    """
    dlg = SimProgressDialog(
        parent, title=title, status=status, cancelable=True,
        warning=("Running in the background -- the app stays responsive. "
                 "You can cancel anytime; the current step finishes first."))

    # Under automation, skip the dialog entirely and run synchronously.
    if modal.automation_bypass():
        print(f"[sim-progress:auto-skip] '{title}' running synchronously")
        try:
            worker(dlg.cancel_event,
                   lambda f, s=None: None)
            if on_done is not None:
                on_done(False, None)
        except Exception as e:
            if on_done is not None:
                on_done(False, e)
        dlg._closed = True
        return dlg

    q = queue.Queue()

    def progress(fraction, status_text=None):
        try:
            q.put(("progress", float(fraction), status_text))
        except Exception:
            pass

    def _worker():
        try:
            worker(dlg.cancel_event, progress)
            q.put(("done", None, None))
        except Exception as e:  # noqa: BLE001 -- reported on UI thread
            q.put(("error", e, None))

    def _poll():
        if dlg._closed:
            return
        try:
            while True:
                kind, a, b = q.get_nowait()
                if kind == "progress":
                    dlg.update(a, b)
                elif kind in ("done", "error"):
                    err = a if kind == "error" else None
                    cancelled = dlg.was_cancelled()
                    dlg.close()
                    if on_done is not None:
                        try:
                            on_done(cancelled, err)
                        except Exception:
                            pass
                    return
        except queue.Empty:
            pass
        QTimer.singleShot(100, _poll)

    threading.Thread(target=_worker, daemon=True).start()
    # The dialog must be visible or the user never sees progress and can
    # never press Cancel -- a QDialog is hidden until show()/open()/exec().
    dlg.show()
    QTimer.singleShot(100, _poll)
    return dlg


# ---------------------------------------------------------------------------
# Fallback save
# ---------------------------------------------------------------------------

def create_fallback_save(game, context: str):
    """Save a fallback snapshot before a heavy sim. Returns the filename
    or None. Never raises -- a failed fallback save must not block the sim.
    """
    try:
        mgr = getattr(game, "save_manager", None)
        if mgr is None:
            # game may BE the GameManager; look for save via app attribute
            app = getattr(game, "app", None)
            mgr = getattr(app, "save_manager", None) if app else None
        if mgr is None:
            return None
        save_dir = getattr(mgr, "save_directory", "saves")
        fallback_dir = os.path.join(save_dir, "fallback")
        os.makedirs(fallback_dir, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join("fallback", f"fallback_{context}_{stamp}.hm")
        ok = mgr.save_game(filename, compress=True)
        if ok:
            print(f"[sim-progress] Fallback save created: {filename}")
            return filename
    except Exception as e:
        print(f"[sim-progress] Fallback save failed (non-fatal): {e}")
    return None


# ---------------------------------------------------------------------------
# Heavy-sim confirmation gates
# ---------------------------------------------------------------------------

def confirm_heavy_sim(parent, title, detail):
    """Yes/No gate with the unresponsiveness warning. Returns True to proceed.

    Uses the centralized modal helper so automation bypass is honored
    (returns False under automation -- safe default).
    """
    return modal.confirm(
        parent, title,
        f"{detail}\n\n"
        "This can take a minute or two, during which the app may appear "
        "frozen -- this is normal. A fallback save will be created first "
        "so you can restore if anything goes wrong.\n\n"
        "Proceed?")


def ask_heavy_sim(parent, title, detail, on_yes=None, on_answer=None):
    """Heavy-sim gate: confirm, then run the continuation.

    Yes runs on_yes (the caller should create the fallback save first,
    then start the sim); No/dismiss does nothing. Returns the answer bool.
    """
    answer = confirm_heavy_sim(parent, title, detail)
    if on_answer is not None:
        try:
            on_answer(answer)
        except Exception:
            pass
    if answer and on_yes is not None:
        try:
            on_yes()
        except Exception as e:
            print(f"[sim-progress] heavy-sim continuation failed: {e}")
    return answer


# ---------------------------------------------------------------------------
# DaySimLoadingOverlay -- non-modal toast for day simulation
# ---------------------------------------------------------------------------

class DaySimLoadingOverlay(QWidget):
    """Non-modal loading toast for day simulation.

    A small status toast pinned to the bottom-right corner -- deliberately
    NOT modal and NOT centered, so it never covers crucial info and can
    never block other UI. No grab, ever.

    Usage:
        overlay = DaySimLoadingOverlay(parent)
        overlay.set_status("Simulating games...")
        ...
        overlay.destroy()

    All methods are try/except guarded and never raise.
    """

    _W = 300
    _H = 108
    _H_AUTO = 134  # with the auto-advance hint label
    _MARGIN = 24   # px from the parent's bottom-right corner

    def __init__(self, parent=None):
        super().__init__(parent)
        self._status_lbl = None
        self._bar = None
        self._hint_lbl = None
        self._auto_mode = False
        try:
            self._build(parent)
        except Exception:
            pass

    def _build(self, parent):
        self.setWindowTitle("Simulating...")
        self.setFixedSize(self._W, self._H)
        self.setWindowFlags(
            Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setStyleSheet(
            "background: #1e1e24; border: 1px solid #2a2f3a;"
            " border-radius: 8px;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        self._status_lbl = QLabel("Starting...")
        self._status_lbl.setWordWrap(True)
        self._status_lbl.setAlignment(Qt.AlignCenter)
        self._status_lbl.setStyleSheet(
            "color: #E8ECF1; font-size: 13px; border: none;")
        layout.addWidget(self._status_lbl)

        self._bar = QProgressBar()
        self._bar.setRange(0, 0)  # indeterminate
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(10)
        self._bar.setStyleSheet(
            "QProgressBar { border: none; background: #2a2f3a;"
            " border-radius: 5px; }"
            "QProgressBar::chunk { background: #3B82F6; border-radius: 5px; }"
        )
        layout.addWidget(self._bar)

        # Bottom-right corner of the parent: out of the way.
        try:
            if parent is not None:
                geo = parent.geometry()
                x = geo.x() + geo.width() - self._W - self._MARGIN
                y = geo.y() + geo.height() - self._H - self._MARGIN
                self.move(max(x, 0), max(y, 0))
        except Exception:
            pass

        # Paint BEFORE the blocking sim starts.
        try:
            self.show()
            from PySide6.QtWidgets import QApplication
            QApplication.processEvents()
        except Exception:
            pass

    def set_status(self, text):
        """Update the status text and force a repaint."""
        try:
            if self._status_lbl is not None:
                self._status_lbl.setText(text or "Working...")
            from PySide6.QtWidgets import QApplication
            QApplication.processEvents()
        except Exception:
            pass

    def set_auto_mode(self, on):
        """Show/hide the auto-advance hint ("press ESC to stop")."""
        try:
            on = bool(on)
            if on == self._auto_mode:
                return
            self._auto_mode = on
            if on and self._hint_lbl is None:
                self._hint_lbl = QLabel("Auto-advancing \u2014 press ESC to stop")
                self._hint_lbl.setAlignment(Qt.AlignCenter)
                self._hint_lbl.setStyleSheet(
                    "color: #8B93A5; font-size: 11px; border: none;")
                self.layout().addWidget(self._hint_lbl)
                self.setFixedSize(self._W, self._H_AUTO)
            elif not on and self._hint_lbl is not None:
                self.layout().removeWidget(self._hint_lbl)
                self._hint_lbl.deleteLater()
                self._hint_lbl = None
                self.setFixedSize(self._W, self._H)
            from PySide6.QtWidgets import QApplication
            QApplication.processEvents()
        except Exception:
            pass

    def destroy(self):
        """Close the toast. Never raises."""
        try:
            self.close()
            self.deleteLater()
        except Exception:
            pass
        finally:
            self._status_lbl = None
            self._bar = None
            self._hint_lbl = None

    @property
    def is_showing(self):
        """True if the overlay is currently visible."""
        try:
            return bool(self.isVisible())
        except Exception:
            return False
