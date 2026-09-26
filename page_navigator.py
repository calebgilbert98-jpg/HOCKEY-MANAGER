# page_navigator.py
# Single-window navigation system for Puck Dynasty.
#
# Replaces the old pattern of opening a new tk.Toplevel for every screen
# (Roster, Trade, Schedule, etc.) with a single content area that swaps
# between cached pages. Switching pages preserves state -- e.g. you can
# leave a trade in progress, check a player profile, and come back to the
# trade exactly as you left it.
#
# Two pieces:
#   EmbeddedWindow -- drop-in replacement base class for the old
#       tk.Toplevel-based Window classes. It IS a tk.Frame (so it embeds
#       in the navigator) but provides no-op shims for the Toplevel-only
#       APIs the window code calls (title, geometry, transient, grab_set,
#       protocol, ...). Converting a window is:
#           class RosterWindow(tk.Toplevel):
#               def __init__(self, parent):
#                   super().__init__(parent)
#                   self.parent = parent
#       becomes:
#           class RosterWindow(EmbeddedWindow):
#               def __init__(self, parent, app=None):
#                   super().__init__(parent)
#                   self.parent = app if app is not None else parent
#       Everything else (widget building on self, app access via
#       self.parent) works unchanged.
#
#   PageNavigator -- owns the central content frame, a page cache
#       (page_id -> page instance), a back stack, and a breadcrumb bar
#       with a Back button.

import tkinter as tk
from tkinter import ttk


class EmbeddedWindow(tk.Frame):
    """A tk.Frame that quacks like a tk.Toplevel.

    Lets the legacy Window classes (written against Toplevel) run embedded
    in the single-window navigator without rewriting their widget code.
    All window-manager calls become harmless no-ops.
    """

    def __init__(self, parent, **kwargs):
        # Force our dark background; individual pages may override.
        kwargs.setdefault("bg", "#0e0e11")
        super().__init__(parent, **kwargs)
        self._is_embedded = True

    # -- Toplevel API shims (no-ops when embedded) ---------------------
    def title(self, *args, **kwargs):
        return ""

    def geometry(self, *args, **kwargs):
        return ""

    def minsize(self, *args, **kwargs):
        return None

    def maxsize(self, *args, **kwargs):
        return None

    def resizable(self, *args, **kwargs):
        return None

    def transient(self, *args, **kwargs):
        return None

    def grab_set(self, *args, **kwargs):
        return None

    def grab_release(self, *args, **kwargs):
        return None

    def protocol(self, *args, **kwargs):
        return None

    def iconbitmap(self, *args, **kwargs):
        return None

    def iconphoto(self, *args, **kwargs):
        return None

    def attributes(self, *args, **kwargs):
        return None

    def wm_title(self, *args, **kwargs):
        return ""

    def wm_geometry(self, *args, **kwargs):
        return ""

    # focus_set / lift / destroy / winfo_exists are real Frame methods
    # and work fine embedded, so we leave them alone.

    def refresh(self):
        """Optional hook: pages can override to reload data when shown."""
        pass


class PageNavigator:
    """Single-window page manager with caching and back navigation.

    Usage:
        nav = PageNavigator(content_frame, app)
        nav.register_page("roster", RosterWindow, "Roster")
        nav.show_page("roster")          # builds once, caches, shows
        nav.show_page("trade")           # roster stays cached with state
        nav.go_back()                    # back to roster, state intact
    """

    def __init__(self, container, app, breadcrumb_parent=None):
        """
        container: the Frame that pages live in (only one visible at a time).
        app: the main application object (passed to pages as app=).
        breadcrumb_parent: Frame where the breadcrumb bar goes. If None,
            no breadcrumb bar is created.
        """
        self.container = container
        self.app = app
        self._registry = {}      # page_id -> (window_class, title)
        self._cache = {}         # page_id -> page instance
        self._back_stack = []    # page_ids, most recent last
        self._current = None

        self.breadcrumb_bar = None
        self._crumb_label = None
        self._back_btn = None
        if breadcrumb_parent is not None:
            self._build_breadcrumb_bar(breadcrumb_parent)

    # -- registration --------------------------------------------------
    def register_page(self, page_id, window_class, title):
        """Register a page. window_class must accept (parent, app=...)."""
        self._registry[page_id] = (window_class, title)

    def is_registered(self, page_id):
        return page_id in self._registry

    # -- navigation ----------------------------------------------------
    def show_page(self, page_id, **kwargs):
        """Show a page, building and caching it on first use.

        Extra kwargs are passed to the window class constructor.
        If the page takes a focus_tab-style kwarg it is forwarded.
        Returns the page instance.
        """
        if page_id not in self._registry:
            raise KeyError(f"Page '{page_id}' is not registered")

        # Push current onto back stack (avoid duplicates)
        if self._current is not None and self._current != page_id:
            if not self._back_stack or self._back_stack[-1] != self._current:
                self._back_stack.append(self._current)

        page = self._get_or_create(page_id, **kwargs)

        # Hide current, show new
        if self._current is not None and self._current in self._cache:
            self._cache[self._current].pack_forget()
        page.pack(fill="both", expand=True)
        self._current = page_id

        # Let the page refresh its data when revisited
        try:
            page.refresh()
        except Exception:
            pass

        self._update_breadcrumb()
        return page

    def go_back(self):
        """Return to the previous page, preserving its state."""
        if not self._back_stack:
            return None
        prev_id = self._back_stack.pop()
        if prev_id not in self._registry:
            return self.go_back()

        if self._current is not None and self._current in self._cache:
            self._cache[self._current].pack_forget()

        page = self._cache.get(prev_id)
        if page is None:
            page = self._get_or_create(prev_id)
        page.pack(fill="both", expand=True)
        self._current = prev_id
        try:
            page.refresh()
        except Exception:
            pass
        self._update_breadcrumb()
        return page

    def current_page(self):
        return self._current

    def get_page(self, page_id):
        """Return the cached page instance, or None."""
        return self._cache.get(page_id)

    def invalidate(self, page_id):
        """Drop a page from the cache so it rebuilds next visit."""
        page = self._cache.pop(page_id, None)
        if page is not None:
            try:
                page.destroy()
            except Exception:
                pass
        self._back_stack = [p for p in self._back_stack if p != page_id]
        if self._current == page_id:
            self._current = None

    def invalidate_all(self):
        for page_id in list(self._cache.keys()):
            self.invalidate(page_id)

    # -- internals -----------------------------------------------------
    def _get_or_create(self, page_id, **kwargs):
        if page_id not in self._cache:
            window_class, _title = self._registry[page_id]
            try:
                page = window_class(self.container, app=self.app, **kwargs)
            except TypeError:
                # Fall back for classes that only take (parent)
                page = window_class(self.container, **kwargs)
                if hasattr(page, "parent"):
                    try:
                        page.parent = self.app
                    except Exception:
                        pass
            self._cache[page_id] = page
        return self._cache[page_id]

    # -- breadcrumb bar ------------------------------------------------
    def _build_breadcrumb_bar(self, parent):
        try:
            from modern_ui import AppColors, AppFonts
            bg = AppColors.BG_ELEVATED
            fg = AppColors.TEXT_SECONDARY
            accent = AppColors.ACCENT
            font = AppFonts.SMALL_BOLD
        except Exception:
            bg, fg, accent = "#16161a", "#a1a1aa", "#00ceb8"
            font = ("Segoe UI", 10, "bold")

        bar = tk.Frame(parent, bg=bg)
        bar.pack(fill="x", padx=0, pady=0)

        self._back_btn = tk.Button(
            bar, text="< Back", font=font, fg=accent, bg=bg,
            activebackground=bg, activeforeground=accent,
            bd=0, relief="flat", cursor="hand2",
            command=self.go_back, state="disabled",
        )
        self._back_btn.pack(side="left", padx=(12, 4), pady=6)

        sep = tk.Frame(bar, bg="#26262e", width=1)
        sep.pack(side="left", fill="y", padx=4, pady=8)

        self._crumb_label = tk.Label(
            bar, text="", font=font, fg=fg, bg=bg, anchor="w",
        )
        self._crumb_label.pack(side="left", padx=4, pady=6)

        self.breadcrumb_bar = bar

    def _update_breadcrumb(self):
        if self._crumb_label is None:
            return
        # Build "A > B > Current" from back stack + current
        titles = []
        for pid in self._back_stack[-3:]:  # last 3 to keep it short
            titles.append(self._registry.get(pid, (None, pid))[1])
        if self._current:
            titles.append(self._registry.get(self._current, (None, self._current))[1])
        self._crumb_label.config(text="  >  ".join(titles))

        # Back button enabled only when there is somewhere to go
        if self._back_btn is not None:
            self._back_btn.config(
                state="normal" if self._back_stack else "disabled"
            )
