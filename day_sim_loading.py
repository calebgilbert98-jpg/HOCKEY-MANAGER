# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
# day_sim_loading.py
#
# Modal loading overlay shown during day simulation ("Next Day").
# The day sim blocks the main thread (1.6s average, up to 78s on outlier
# days). Without feedback the app looks crashed. This overlay shows a
# spinner + status text that updates as the sim moves through phases.
#
# All methods are try/except guarded and never raise.

import tkinter as tk
from tkinter import ttk


class DaySimLoadingOverlay:
    """Modal loading overlay for day simulation.

    Shows a spinner (indeterminate progress bar) and a status label that
    updates as the sim progresses through phases ("Simulating games...",
    "Processing AI decisions...", etc.).

    Usage:
        overlay = DaySimLoadingOverlay(parent)
        overlay.set_status("Simulating games...")
        ...
        overlay.destroy()
    """

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
            font_title = AppFonts.HEADING
            font_status = AppFonts.BODY
        except Exception:
            bg = '#1e1e1e'
            fg = '#ffffff'
            accent = '#00ceb8'
            font_title = ("Segoe UI", 14, "bold")
            font_status = ("Segoe UI", 11)

        win = tk.Toplevel(parent) if parent else tk.Tk()
        self._window = win
        win.title("Simulating...")
        win.geometry("380x160")
        win.configure(bg=bg)
        win.resizable(False, False)
        win.transient(parent)
        # Modal: block input to main window while sim runs
        try:
            win.grab_set()
        except Exception:
            pass
        # Stay on top so it's visible during the blocking sim
        try:
            win.attributes('-topmost', True)
        except Exception:
            pass
        # Escape never destroys this dialog mid-sim (the app-wide Esc
        # handler would otherwise tear it down). During auto-advance it
        # stops the loop instead -- see set_auto_mode().
        try:
            win.bind('<Escape>', self._on_escape, add='+')
        except Exception:
            pass

        # Center on parent
        try:
            if parent:
                parent.update_idletasks()
                x = parent.winfo_x() + (parent.winfo_width() // 2) - 190
                y = parent.winfo_y() + (parent.winfo_height() // 2) - 80
                win.geometry(f"380x160+{x}+{y}")
        except Exception:
            pass

        # Title
        try:
            title = tk.Label(win, text="Simulating Day",
                             font=font_title, bg=bg, fg=accent)
            title.pack(pady=(20, 10))
        except Exception:
            pass

        # Status label (updates per phase)
        try:
            self._status_var = tk.StringVar(value="Starting...")
            status = tk.Label(win, textvariable=self._status_var,
                              font=font_status, bg=bg, fg=fg,
                              wraplength=340)
            status.pack(pady=(0, 15))
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
                                        length=300)
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
                    win.geometry("380x190")
                except Exception:
                    self._hint_label = None
            elif not on and self._hint_label is not None:
                try:
                    self._hint_label.destroy()
                except Exception:
                    pass
                self._hint_label = None
                try:
                    win.geometry("380x160")
                except Exception:
                    pass
            try:
                win.update()
            except Exception:
                pass
        except Exception:
            pass

    def _on_escape(self, event=None):
        """Escape on the overlay: stop auto-advance, never close mid-sim."""
        try:
            parent = self._parent
            if (parent is not None
                    and getattr(parent, '_auto_advance', False)):
                try:
                    parent._auto_advance_stop("esc")
                except Exception:
                    pass
        except Exception:
            pass
        return 'break'

    def destroy(self):
        """Close the overlay and release the modal grab."""
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
