# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
# day_sim_loading.py
#
# Non-modal loading toast shown during day simulation ("Next Day").
# The day sim blocks the main thread (1.6s average, up to 78s on outlier
# days). Without feedback the app looks crashed. This toast shows a
# spinner + status text that updates as the sim moves through phases.
#
# Design (Muck 2026-10-02): a small status toast pinned to the
# bottom-right corner -- deliberately NOT modal and NOT centered, so it
# never covers crucial info and can never block the Game Day Watch/Quick
# choice (or any other UI). No grab_set, ever.
#
# All methods are try/except guarded and never raise.

import tkinter as tk
from tkinter import ttk


class DaySimLoadingOverlay:
    """Non-modal loading toast for day simulation.

    Shows a spinner (indeterminate progress bar) and a status label that
    updates as the sim progresses through phases ("Simulating games...",
    "Processing AI decisions...", etc.).

    Usage:
        overlay = DaySimLoadingOverlay(parent)
        overlay.set_status("Simulating games...")
        ...
        overlay.destroy()
    """

    # Compact toast dimensions (Muck 2026-10-02: small, out of the way).
    _W = 300
    _H = 108
    _H_AUTO = 134  # with the auto-advance hint label
    _MARGIN = 24   # px from the parent's bottom-right corner

    def __init__(self, parent=None):
        self._parent = parent
        self._window = None
        self._status_var = None
        self._bar = None
        self._hint_label = None
        self._auto_mode = False
        try:
            self._build(parent)
        except Exception:
            pass

    def _build(self, parent):
        # Color scheme matches the app's dark theme
        try:
            from modern_ui import AppColors, AppFonts
            bg = AppColors.BG_ELEVATED
            fg = AppColors.TEXT_PRIMARY
            accent = AppColors.ACCENT
            font_status = AppFonts.BODY
        except Exception:
            bg = '#1e1e1e'
            fg = '#ffffff'
            accent = '#3B82F6'
            font_status = ("Segoe UI", 10)

        win = tk.Toplevel(parent) if parent else tk.Tk()
        self._window = win
        win.title("Simulating...")
        w, h = self._W, self._H
        win.geometry(f"{w}x{h}")
        win.configure(bg=bg)
        win.resizable(False, False)
        # Non-modal by design (Muck 2026-10-02): this is a status toast,
        # not a dialog. It must never block the Game Day Watch/Quick
        # choice or cover crucial info -- so NO grab_set, ever, and it
        # lives in the corner instead of the center.
        try:
            win.transient(parent)
        except Exception:
            pass
        # Stay on top so it's visible during the blocking sim
        try:
            win.attributes('-topmost', True)
        except Exception:
            pass
        # NOTE: no <Escape> binding here. Without a grab the toast never
        # has keyboard focus, so a widget-level binding would never fire.
        # Esc while the toast is up is handled by the app-wide
        # _qol_on_escape in main.py (stops auto-advance; otherwise
        # swallowed so the toast is never torn down mid-sim).

        # Bottom-right corner of the parent: out of the way of the main
        # content (Muck 2026-10-02).
        try:
            if parent:
                parent.update_idletasks()
                x = (parent.winfo_x() + parent.winfo_width()
                     - w - self._MARGIN)
                y = (parent.winfo_y() + parent.winfo_height()
                     - h - self._MARGIN)
                win.geometry(f"{w}x{h}+{max(x, 0)}+{max(y, 0)}")
        except Exception:
            pass

        # Status label (updates per phase)
        try:
            self._status_var = tk.StringVar(value="Starting...")
            status = tk.Label(win, textvariable=self._status_var,
                              font=font_status, bg=bg, fg=fg,
                              wraplength=w - 30)
            status.pack(pady=(14, 8))
        except Exception:
            pass

        # Indeterminate spinner
        try:
            style = ttk.Style()
            # Don't clobber the app's theme; use clam only for our bar
            try:
                style.theme_use('clam')
            except Exception:
                pass
            style.configure("DaySim.Horizontal.TProgressbar",
                            background=accent,
                            troughcolor='#404040',
                            borderwidth=0)
            self._bar = ttk.Progressbar(win, mode='indeterminate',
                                        style="DaySim.Horizontal.TProgressbar",
                                        length=w - 60)
            self._bar.pack(pady=(0, 10))
            self._bar.start(15)  # 15ms per step = smooth spin
        except Exception:
            pass

        # Force paint BEFORE the blocking sim starts
        try:
            win.update()
        except Exception:
            pass

    def set_status(self, text):
        """Update the status text and force a repaint."""
        try:
            if self._status_var is not None:
                self._status_var.set(text or "Working...")
            if self._window is not None:
                # update() processes pending events including the
                # indeterminate bar's animation ticks
                self._window.update()
        except Exception:
            pass

    def set_auto_mode(self, on):
        """Show/hide the auto-advance hint (Muck 2026-10-02).

        While auto-advance owns this overlay, Escape stops the loop
        instead of doing nothing.
        """
        try:
            self._auto_mode = bool(on)
            win = self._window
            if win is None or not bool(win.winfo_exists()):
                return
            if on and self._hint_label is None:
                try:
                    from modern_ui import AppColors, AppFonts
                    bg = AppColors.BG_ELEVATED
                    fg = AppColors.TEXT_SECONDARY
                    font_hint = AppFonts.CAPTION
                except Exception:
                    bg = '#1e1e1e'
                    fg = '#aaaaaa'
                    font_hint = ("Segoe UI", 9)
                try:
                    self._hint_label = tk.Label(
                        win, text="Auto-advancing — press ESC to stop",
                        font=font_hint, bg=bg, fg=fg)
                    self._hint_label.pack(pady=(0, 12))
                    win.geometry(f"{self._W}x{self._H_AUTO}")
                except Exception:
                    self._hint_label = None
            elif not on and self._hint_label is not None:
                try:
                    self._hint_label.destroy()
                except Exception:
                    pass
                self._hint_label = None
                try:
                    win.geometry(f"{self._W}x{self._H}")
                except Exception:
                    pass
            try:
                win.update()
            except Exception:
                pass
        except Exception:
            pass

    def destroy(self):
        """Close the toast and release any grab (defensive)."""
        try:
            if self._bar is not None:
                try:
                    self._bar.stop()
                except Exception:
                    pass
            if self._window is not None:
                try:
                    self._window.grab_release()
                except Exception:
                    pass
                try:
                    self._window.destroy()
                except Exception:
                    pass
        except Exception:
            pass
        finally:
            self._window = None
            self._bar = None
            self._status_var = None

    @property
    def is_showing(self):
        """True if the overlay window exists."""
        try:
            return (self._window is not None
                    and bool(self._window.winfo_exists()))
        except Exception:
            return False
