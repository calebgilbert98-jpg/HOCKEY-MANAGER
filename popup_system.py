"""In-game popup system for Puck Dynasty.

Every dialog and window in the game now lives INSIDE the main game window.
No floating OS-level Toplevels, no native messageboxes -- popups are
centered cards on a dimmed backdrop, Football Manager style.

Components
----------
PopupManager
    Owned by the app root (``root.popup_manager``). Creates/destroys the
    full-window overlay and hosts cards on it.
InGamePopup
    Drop-in base class for every former ``tk.Toplevel`` / ``ctk.CTkToplevel``
    window. It is a ``tk.Frame`` that quacks like a Toplevel: ``title()``,
    ``geometry()``, ``grab_set()``, ``protocol()``, ``destroy()`` etc. all
    keep working, and ``wait_window()`` still blocks synchronously because
    ``wait_window`` works on any widget.
messagebox / simpledialog
    Facades with the exact tkinter signatures (``showinfo``, ``askyesno``,
    ``askstring`` ...). They render styled in-game cards and block via
    ``wait_window``, so all 400+ call sites keep working unchanged. When no
    app is registered (launcher before wiring, headless tests) they fall back
    to the real tkinter dialogs.

Usage
-----
    # app startup (once)
    from popup_system import register
    register(self)   # self = tk.Tk root

    # open a migrated window class
    self.popup_manager.show(TradeWindow, self, arg1, arg2)

    # inline-built popup (replaces win = tk.Toplevel(...))
    host, close = self.popup_manager.show_card("Title", 520, 360)
    tk.Label(host, text="...").pack()
    host.wait_window()
"""

import tkinter as tk

# ---------------------------------------------------------------------------
# App registration
# ---------------------------------------------------------------------------

_default_manager = None


def register(root):
    """Attach a PopupManager to a tk root and make it the default target."""
    global _default_manager
    mgr = getattr(root, "popup_manager", None)
    if mgr is None:
        mgr = PopupManager(root)
        root.popup_manager = mgr
    _default_manager = mgr
    return mgr


def _manager_for(widget):
    """Find the PopupManager for a widget by walking up to its root."""
    w = widget
    seen = set()
    while w is not None and id(w) not in seen:
        seen.add(id(w))
        mgr = getattr(w, "popup_manager", None)
        if mgr is not None:
            return mgr
        mgr = getattr(w, "_popup_manager", None)
        if mgr is not None:
            return mgr
        w = getattr(w, "master", None)
    return _default_manager


# ---------------------------------------------------------------------------
# Styling constants (match the game's charcoal/teal theme)
# ---------------------------------------------------------------------------

_BG = "#14161b"          # card body
_TITLE_BG = "#1a1d24"   # title bar
_BACKDROP = "#05060a"   # dim behind modal cards
_BORDER = "#2e323b"
_TEXT = "#e8eaf0"
_TEXT_DIM = "#9aa0ab"
_ACCENT = "#14b8a6"      # teal fallback; dialogs ask the app for its accent
_DANGER = "#e5484d"


def _app_accent(root):
    try:
        return root.ACCENT_COLOR
    except Exception:
        pass
    try:
        return root.modern_theme.colors.primary_accent
    except Exception:
        return _ACCENT


# ---------------------------------------------------------------------------
# InGamePopup: a Frame that quacks like a Toplevel
# ---------------------------------------------------------------------------

# kwargs only understood by customtkinter -- mapped or dropped so migrated
# ctk.CTkToplevel subclasses keep working unchanged.
_CTK_DROP = {"corner_radius", "border_width", "border_color", "text_color"}


class InGamePopup(tk.Frame):
    """Base class for migrated windows: a tk.Frame with a Toplevel API.

    The PopupManager instantiates these inside a card; ``super().__init__``
    calls from old code keep working because the first constructor arg is
    still the "parent" (now the card body frame).

    Attribute reads that miss on the frame (``self.parent.BG_COLOR``,
    ``self.parent.open_windows`` ...) fall through to the app root, which is
    what old code expected ``self.parent`` to be.

    AUTO-ROUTING: ``__new__`` intercepts ``X(opener, ...)`` construction and
    builds the card immediately, so existing call sites need NO changes --
    the window opens in-game instead of as a floating Toplevel. Final card
    placement is deferred to ``after_idle`` so ``title()`` / ``geometry()``
    calls inside ``__init__`` are picked up.
    """

    def __new__(cls, master=None, *args, **kwargs):
        # Every construction -- subclass or direct -- is routed into a card
        # on the in-game overlay. (Direct `InGamePopup(parent)` therefore
        # behaves exactly like the old `tk.Toplevel(parent)` call sites it
        # replaces: a visible, titled, closable dialog surface.)
        mgr = _manager_for(master) if master is not None else _default_manager
        if mgr is None:
            # No in-game manager (pre-registration): degrade to a plain frame.
            return super().__new__(cls)
        entry = mgr._make_entry("", 560, 420, False, False)
        inst = super().__new__(cls)
        tk.Frame.__init__(inst, entry["body"])
        inst._init_popup_metadata(entry)
        object.__setattr__(inst, "_prebuilt_entry", entry)
        return inst

    def _init_popup_metadata(self, entry):
        mgr = entry.get("_mgr_ref")
        object.__setattr__(self, "_delegating", False)
        object.__setattr__(self, "_popup_manager", mgr)
        object.__setattr__(self, "_popup_entry", entry)
        object.__setattr__(self, "_app_root", None)
        object.__setattr__(self, "_popup_title", "")
        object.__setattr__(self, "_popup_size", (560, 420))
        object.__setattr__(self, "_popup_minsize", (0, 0))
        object.__setattr__(self, "_modal_requested", False)
        object.__setattr__(self, "_dismissible", True)
        object.__setattr__(self, "_dismiss_on_backdrop", False)
        object.__setattr__(self, "_handles_escape", False)
        object.__setattr__(self, "_wm_delete_cb", None)
        object.__setattr__(self, "_closed", False)
        try:
            object.__setattr__(self, "_app_root", self.winfo_toplevel())
        except Exception:
            pass
        try:
            self.parent = self._app_root
        except Exception:
            pass

    def __init__(self, master=None, modal=None, dismiss_on_backdrop=None, **kw):
        # modal=True requests a grabbed (blocking) card; modal=False pins it
        # non-modal. dismiss_on_backdrop=True adds a click-catcher behind a
        # non-modal card so clicking out of it dismisses the card.
        _modal_kw = modal
        _backdrop_kw = dismiss_on_backdrop
        if getattr(self, "_prebuilt_entry", None) is not None:
            # Widget already created inside the card by __new__; the passed
            # master is the *opener* (kept for the subclass's own use) --
            # do NOT re-run tk.Frame.__init__ (would recreate the widget).
            # NOTE: _prebuilt_entry is intentionally kept on the instance so
            # PopupManager.show_card() can adopt synchronously.
            entry = self._prebuilt_entry
            kw = _map_ctk_kwargs(kw)
            if kw:
                try:
                    tk.Frame.configure(self, **kw)
                except tk.TclError:
                    pass
            mgr = self._popup_manager
            if _modal_kw is True:
                object.__setattr__(self, "_modal_requested", True)
            elif _modal_kw is False:
                object.__setattr__(self, "_modal_requested", False)
            if _backdrop_kw is not None:
                object.__setattr__(self, "_dismiss_on_backdrop", bool(_backdrop_kw))
            if mgr is not None:
                # Adopt after the subclass __init__ finishes so title/size
                # set there are applied to the card.
                self.after_idle(lambda: mgr._adopt_prebuilt(self, entry))
            object.__setattr__(self, "_delegating", True)
            return
        object.__setattr__(self, "_delegating", False)
        object.__setattr__(self, "_popup_manager", _manager_for(master))
        object.__setattr__(self, "_popup_entry", None)
        object.__setattr__(self, "_app_root", None)
        object.__setattr__(self, "_popup_title", "")
        object.__setattr__(self, "_popup_size", (560, 420))
        object.__setattr__(self, "_popup_minsize", (0, 0))
        object.__setattr__(self, "_modal_requested", False)
        object.__setattr__(self, "_dismissible", True)
        object.__setattr__(self, "_dismiss_on_backdrop", False)
        object.__setattr__(self, "_handles_escape", False)
        object.__setattr__(self, "_wm_delete_cb", None)
        object.__setattr__(self, "_closed", False)
        # ctk-only ctor kwargs (fg_color=...) mapped like configure()
        kw = _map_ctk_kwargs(kw)
        tk.Frame.__init__(self, master, **kw)
        # default app root: the tk root at the top of the master chain
        try:
            object.__setattr__(self, "_app_root", self.winfo_toplevel())
        except Exception:
            pass
        # convention: old windows set self.parent themselves; default to root
        try:
            self.parent = self._app_root
        except Exception:
            pass
        object.__setattr__(self, "_delegating", True)

    # -- attribute fall-through to the app root ---------------------------
    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        try:
            if not object.__getattribute__(self, "_delegating"):
                raise AttributeError(name)
        except AttributeError:
            raise AttributeError(name)
        try:
            app_root = object.__getattribute__(self, "_app_root")
        except AttributeError:
            raise AttributeError(name)
        if app_root is not None and hasattr(app_root, name):
            return getattr(app_root, name)
        raise AttributeError(
            f"{type(self).__name__!r} has no attribute {name!r}")

    # -- Toplevel API ------------------------------------------------------
    def title(self, text=None):
        if text is None:
            return self._popup_title
        self._popup_title = str(text)
        mgr = self._popup_manager
        if mgr is not None:
            mgr._apply_title(self)
        return None

    def geometry(self, spec=None):
        """Accept 'WxH', 'WxH+X+Y', '+X+Y'. Position is ignored: cards are
        always centered in the game window."""
        if spec is None:
            w, h = self._popup_size
            return f"{w}x{h}"
        try:
            size = spec.split("+")[0]
            w, h = size.lower().split("x")
            self._popup_size = (int(w), int(h))
        except Exception:
            pass
        mgr = self._popup_manager
        if mgr is not None:
            mgr._apply_size(self)
        return None

    def minsize(self, w, h):
        self._popup_minsize = (w, h)

    def maxsize(self, w, h):  # noqa: D102 - compat no-op
        pass

    def resizable(self, w=None, h=None):  # noqa: D102 - compat no-op
        pass

    def transient(self, master=None):  # noqa: D102 - compat no-op
        pass

    def attributes(self, *args, **kwargs):  # noqa: D102 - compat no-op
        # Topmost/alpha are meaningless for an in-game card; swallow so the
        # call can't fall through to the app root (would pin the whole app).
        pass

    def withdraw(self):  # noqa: D102 - compat no-op
        # A card can't be iconified; swallow so this can't fall through to
        # the app root (would hide the entire game window).
        pass

    def deiconify(self):  # noqa: D102 - compat no-op
        pass

    def iconify(self):  # noqa: D102 - compat no-op
        pass

    def overrideredirect(self, *args):  # noqa: D102 - compat no-op
        # Borderless floaters (tooltips/toasts) stay real Toplevels; a card
        # must never strip the main window's chrome.
        pass

    def grab_set(self):
        self._modal_requested = True
        mgr = self._popup_manager
        if mgr is not None:
            mgr._apply_modal(self)

    def grab_release(self):
        self._modal_requested = False
        mgr = self._popup_manager
        if mgr is not None:
            mgr._release_modal(self)

    def protocol(self, name, func=None):
        if name == "WM_DELETE_WINDOW":
            if func is None:
                return self._wm_delete_cb
            self._wm_delete_cb = func
            return None
        return None

    def attributes(self, *args, **kw):  # noqa: D102 - compat no-op
        return None

    def state(self, newstate=None):
        """Map 'zoomed' to a near-full-window card; everything else no-op."""
        if newstate == "zoomed":
            try:
                root = self._app_root
                w = root.winfo_width() if root else 0
                h = root.winfo_height() if root else 0
                self._popup_size = (max(800, w - 40), max(600, h - 40))
                mgr = self._popup_manager
                if mgr is not None:
                    mgr._apply_size(self)
            except Exception:
                pass
        return None

    def lift(self, aboveThis=None):  # noqa: D102 - raise the card
        mgr = self._popup_manager
        if mgr is not None:
            mgr._raise(self)
        else:
            super().lift(aboveThis)

    def lower(self, belowThis=None):  # noqa: D102 - compat
        pass

    def configure(self, *args, **kw):
        kw = _map_ctk_kwargs(kw)
        try:
            return super().configure(*args, **kw)
        except tk.TclError:
            # last resort: drop anything still unrecognized
            return super().configure(*args)

    config = configure

    def destroy(self):
        if self._closed:
            return
        self._closed = True
        mgr = self._popup_manager
        # break the fall-through before teardown so __getattr__ can't fire
        # mid-destroy on half-dead state
        object.__setattr__(self, "_app_root", None)
        if mgr is not None:
            mgr._close_popup(self)
        else:
            try:
                super().destroy()
            except tk.TclError:
                pass

    # alias used all over the codebase
    close = destroy


def _map_ctk_kwargs(kw):
    out = {}
    for k, v in kw.items():
        if k in _CTK_DROP:
            continue
        if k == "fg_color":
            k = "bg"
        elif k == "bg_color":
            k = "background"
        out[k] = v
    return out


# ---------------------------------------------------------------------------
# PopupManager
# ---------------------------------------------------------------------------

class PopupManager:
    """Hosts in-game cards on the app root window."""

    def __init__(self, root):
        self.root = root
        self._stack = []  # each: dict(shell, backdrop, popup, modal)
        root.popup_manager = self
        global _default_manager
        if _default_manager is None:
            _default_manager = self

    # -- public API ---------------------------------------------------------
    def show(self, content_cls, *args, **kwargs):
        """Open a migrated window class inside a card. Returns the content
        instance (the old ``win``). Extra args pass straight through.
        Construction auto-routes through __new__; the card is placed once
        the subclass __init__ finishes (after_idle)."""
        return content_cls(*args, **kwargs)

    def show_modal(self, content_cls, *args, **kwargs):
        """Like show(), but dimmed + grabbed from the start."""
        popup = content_cls(*args, **kwargs)
        try:
            popup._modal_requested = True
        except Exception:
            pass
        return popup

    def _adopt_prebuilt(self, popup, entry):
        """Place a __new__-routed card now that __init__ has finished."""
        if self._entry_for(popup) is not None:
            return  # already adopted (e.g. show_card did it synchronously)
        if getattr(popup, "_closed", False):
            self._teardown_entry(entry)
            return
        entry["popup"] = popup
        self._stack.append(entry)
        popup.pack(fill="both", expand=True)
        self._place_entry(entry)
        self._arm_dismiss_on_backdrop(popup, entry)
        self._apply_title(popup)
        self._apply_size(popup)
        if getattr(popup, "_modal_requested", False):
            self._apply_modal(popup)
        try:
            popup.bind("<Escape>", lambda e: self._on_escape(popup))
        except Exception:
            pass

    def show_card(self, title="", width=520, height=360, modal=True,
                  on_close=None, dismiss_on_backdrop=False):
        """Bare card for inline-built popups. Returns (host, close_fn).

        Build widgets into ``host`` (it quacks like a Toplevel); ``close_fn``
        or ``host.destroy()`` dismisses the card. Adopted synchronously so
        the entry is in the stack before this returns.
        """
        host = InGamePopup(self.root, modal=modal,
                             dismiss_on_backdrop=dismiss_on_backdrop)
        host.title(title)
        host.geometry(f"{width}x{height}")
        if on_close is not None:
            host.protocol("WM_DELETE_WINDOW", on_close)
        # Adopt now (the scheduled idle adoption becomes a no-op via the
        # _adopt_prebuilt guard) so _entry_for() works immediately.
        self._adopt_prebuilt(host, host._prebuilt_entry)
        if modal:
            self._apply_modal(host)
        return host, host.destroy

    def close(self, popup):
        """Close the card hosting ``popup``."""
        self._close_popup(popup)

    def close_top(self):
        if self._stack:
            self._close_popup(self._stack[-1]["popup"])

    def close_all(self):
        while self._stack:
            entry = self._stack.pop()
            self._teardown_entry(entry)

    @property
    def is_open(self):
        return bool(self._stack)

    # -- dialogs -------------------------------------------------------------
    def alert(self, title, message, kind="info", parent=None):
        """Non-blocking-feel info/warning/error. Blocks like messagebox."""
        return _dialog(self, kind, title, message,
                       [("OK", True, "primary")])

    def confirm(self, title, message, kind="question", parent=None,
                ok_text="Yes", cancel_text="No"):
        val = _dialog(self, kind, title, message,
                      [(ok_text, True, "primary"),
                       (cancel_text, False, "secondary")])
        return bool(val)

    # -- internals ------------------------------------------------------------

    def _make_entry(self, title, width, height, modal, dismiss_on_backdrop=False):
        root = self.root
        backdrop = None
        if modal:
            backdrop = tk.Frame(root, bg=_BACKDROP)
        shell = tk.Frame(root, bg=_BG, highlightbackground=_BORDER,
                         highlightthickness=1)
        # title bar
        tbar = tk.Frame(shell, bg=_TITLE_BG, height=34)
        tbar.pack(fill="x", side="top")
        tbar.pack_propagate(False)
        try:
            from ui_scale import scaled as _scaled
            _tfs = _scaled(11)
        except Exception:
            _tfs = 11
        tlabel = tk.Label(tbar, text=title, bg=_TITLE_BG, fg=_TEXT,
                         font=("Segoe UI", _tfs, "bold"), anchor="w")
        tlabel.pack(side="left", padx=12)
        xbtn = tk.Label(tbar, text="\u2715", bg=_TITLE_BG, fg=_TEXT_DIM,
                       font=("Segoe UI", 11, "bold"), cursor="hand2", padx=10)
        xbtn.pack(side="right")

        body = tk.Frame(shell, bg=_BG)
        body.pack(fill="both", expand=True)
        entry = {"shell": shell, "backdrop": backdrop, "body": body,
                 "popup": None, "modal": modal, "tlabel": tlabel,
                 "width": width, "height": height, "_mgr_ref": self,
                 "dismiss_on_backdrop": bool(dismiss_on_backdrop) and not modal,
                 "clickout_bind": None}
        xbtn.bind("<Button-1>", lambda e: self._on_x(entry))
        xbtn.bind("<Enter>", lambda e: xbtn.configure(fg=_DANGER))
        xbtn.bind("<Leave>", lambda e: xbtn.configure(fg=_TEXT_DIM))
        return entry

    def _entry_for(self, popup):
        for entry in self._stack:
            if entry["popup"] is popup:
                return entry
        return None

    def _place_entry(self, entry):
        root = self.root
        try:
            rw = root.winfo_width()
            rh = root.winfo_height()
        except Exception:
            rw, rh = 1, 1
        if rw < 10:
            rw = 1400
        if rh < 10:
            rh = 800
        w = min(entry["width"], rw - 40)
        h = min(entry["height"], rh - 40)
        entry["width"], entry["height"] = w, h
        if entry["backdrop"] is not None:
            entry["backdrop"].place(relx=0, rely=0, relwidth=1, relheight=1)
        entry["shell"].place(relx=0.5, rely=0.5, anchor="center",
                             width=w, height=h)
        entry["shell"].lift()

    def _apply_title(self, popup):
        entry = self._entry_for(popup)
        if entry is not None:
            entry["tlabel"].configure(text=popup._popup_title)

    def _apply_size(self, popup):
        entry = self._entry_for(popup)
        if entry is None:
            return
        w, h = popup._popup_size
        mw, mh = popup._popup_minsize
        w, h = max(w, mw), max(h, mh)
        entry["width"], entry["height"] = w, h
        self._place_entry(entry)

    def _apply_modal(self, popup):
        entry = self._entry_for(popup)
        if entry is None:
            return
        entry["modal"] = True
        if entry["backdrop"] is None:
            entry["backdrop"] = tk.Frame(self.root, bg=_BACKDROP)
        self._place_entry(entry)
        try:
            entry["shell"].grab_set()
            entry["shell"].focus_set()
        except Exception:
            pass

    def _release_modal(self, popup):
        entry = self._entry_for(popup)
        if entry is None:
            return
        entry["modal"] = False
        try:
            entry["shell"].grab_release()
        except Exception:
            pass
        if entry["backdrop"] is not None:
            try:
                entry["backdrop"].place_forget()
            except Exception:
                pass
            entry["backdrop"] = None

    def _raise(self, popup):
        entry = self._entry_for(popup)
        if entry is not None:
            entry["shell"].lift()

    def _on_x(self, entry):
        popup = entry["popup"]
        cb = getattr(popup, "_wm_delete_cb", None)
        if callable(cb):
            try:
                cb()
                return
            except Exception:
                pass
        if popup is not None:
            self._close_popup(popup)

    def _arm_dismiss_on_backdrop(self, popup, entry):
        """Arm FM24-style click-out: the first click outside a non-modal
        card dismisses it AND lands where the user aimed, so they can
        immediately explore (no dimmed locked-screen feel)."""
        if entry.get("clickout_bind") is not None:
            return
        if not getattr(popup, "_dismiss_on_backdrop", False):
            # also honor the entry flag set via show_card()
            if not entry.get("dismiss_on_backdrop"):
                return
        if entry.get("modal"):
            return
        # Sync the entry flag: __new__ builds the entry before __init__
        # kwargs are known, so the popup-level request lands here.
        entry["dismiss_on_backdrop"] = True
        try:
            shell_path = str(entry["shell"])
            def _catcher(event, en=entry, sp=shell_path):
                try:
                    if not en.get("dismiss_on_backdrop"):
                        return
                    if not self._stack or self._stack[-1] is not en:
                        return  # only the top card answers click-out
                    popup = en.get("popup")
                    if popup is None or not getattr(popup, "_dismissible", True):
                        return
                    try:
                        inside = str(event.widget).startswith(sp)
                    except Exception:
                        inside = False
                    if not inside:
                        self._on_x(en)
                except Exception:
                    pass
            bind_id = self.root.bind("<Button-1>", _catcher, add="+")
            entry["clickout_bind"] = bind_id
        except Exception:
            pass

    def _disarm_dismiss_on_backdrop(self, entry):
        try:
            bind_id = entry.get("clickout_bind")
            if bind_id:
                self.root.unbind("<Button-1>", bind_id)
        except Exception:
            pass
        entry["clickout_bind"] = None

    def _on_backdrop_click(self, entry):
        """Kept for API compat; click-out is now handled at root level."""
        return

    def _on_escape(self, popup):
        if getattr(popup, "_handles_escape", False):
            return
        if not getattr(popup, "_dismissible", True):
            return
        # only the top card answers Escape
        if self._stack and self._stack[-1]["popup"] is popup:
            self._on_x(self._stack[-1])

    def _close_popup(self, popup):
        entry = self._entry_for(popup)
        if entry is None:
            # Never adopted (destroyed before after_idle ran, or ctor
            # failed): fall back to the stashed prebuilt entry.
            entry = getattr(popup, "_popup_entry", None)
        if entry is None:
            try:
                tk.Frame.destroy(popup)
            except Exception:
                pass
            return
        if entry in self._stack:
            self._stack.remove(entry)
        self._teardown_entry(entry)

    def _teardown_entry(self, entry):
        try:
            self._disarm_dismiss_on_backdrop(entry)
        except Exception:
            pass
        try:
            entry["shell"].grab_release()
        except Exception:
            pass
        for key in ("shell", "backdrop"):
            w = entry.get(key)
            if w is not None:
                try:
                    w.destroy()
                except Exception:
                    pass


# ---------------------------------------------------------------------------
# In-game dialogs (messagebox/simpledialog facades)
# ---------------------------------------------------------------------------

_KIND_STYLE = {
    "info": ("\u2139", "#38bdf8"),
    "warning": ("\u26a0", "#f5a524"),
    "error": ("\u2716", "#e5484d"),
    "question": ("?", "#14b8a6"),
}


def _dialog(manager, kind, title, message, buttons, parent=None):
    """Blocking styled dialog. buttons = [(label, value, style)]."""
    glyph, color = _KIND_STYLE.get(kind, _KIND_STYLE["info"])
    host, close = manager.show_card(title, width=470, height=200, modal=True)
    host.configure(bg=_BG)

    top = tk.Frame(host, bg=_BG)
    top.pack(fill="both", expand=True, padx=18, pady=(14, 6))
    icon = tk.Label(top, text=glyph, bg=_BG, fg=color,
                    font=("Segoe UI", 22, "bold"), width=3, anchor="n")
    icon.pack(side="left", padx=(0, 10))
    msg = tk.Label(top, text=message, bg=_BG, fg=_TEXT,
                   font=("Segoe UI", 11), wraplength=360, justify="left",
                   anchor="nw")
    msg.pack(side="left", fill="both", expand=True)

    # grow the card for long messages
    lines = max(1, len(message) // 48)
    if lines > 3:
        manager._apply_size(host)  # no-op guard; resize explicitly below
        entry = manager._entry_for(host)
        if entry is not None:
            entry["height"] = min(420, 200 + (lines - 3) * 20)
            manager._place_entry(entry)

    result = {}

    def pick(value):
        result["value"] = value
        close()

    brow = tk.Frame(host, bg=_BG)
    brow.pack(fill="x", padx=18, pady=(6, 14))
    accent = _app_accent(manager.root)
    for label, value, style in buttons:
        bg = accent if style == "primary" else "#2a2e37"
        fg = "#ffffff" if style == "primary" else _TEXT
        b = tk.Button(brow, text=label, bg=bg, fg=fg,
                      activebackground="#0e7c72" if style == "primary" else "#343945",
                      activeforeground="#ffffff",
                      font=("Segoe UI", 11, "bold"), padx=22, pady=6,
                      relief="flat", bd=0, cursor="hand2",
                      command=lambda v=value: pick(v))
        b.pack(side="right", padx=(8, 0))

    host.protocol("WM_DELETE_WINDOW", lambda: pick(buttons[-1][1]
                                                  if buttons else None))
    host.wait_window()
    return result.get("value")


def _prompt(manager, title, prompt, initial="", as_int=False, parent=None):
    host, close = manager.show_card(title, width=440, height=190, modal=True)
    host.configure(bg=_BG)
    tk.Label(host, text=prompt, bg=_BG, fg=_TEXT, font=("Segoe UI", 11),
             wraplength=390, justify="left").pack(anchor="w", padx=18,
                                                  pady=(14, 8))
    var = tk.StringVar(value="" if initial is None else str(initial))
    ent = tk.Entry(host, textvariable=var, bg="#0f1115", fg=_TEXT,
                   insertbackground=_TEXT, font=("Segoe UI", 12),
                   relief="flat", highlightbackground=_BORDER,
                   highlightthickness=1)
    ent.pack(fill="x", padx=18, pady=(0, 12))
    ent.focus_set()
    result = {}

    def ok(event=None):
        val = var.get()
        if as_int:
            try:
                val = int(val)
            except ValueError:
                ent.configure(highlightbackground=_DANGER)
                return
        result["value"] = val
        close()

    def cancel(event=None):
        result["value"] = None
        close()

    ent.bind("<Return>", ok)
    host.bind("<Escape>", lambda e: cancel())
    brow = tk.Frame(host, bg=_BG)
    brow.pack(fill="x", padx=18, pady=(0, 14))
    accent = _app_accent(manager.root)
    okb = tk.Button(brow, text="OK", bg=accent, fg="#ffffff",
                    activebackground="#0e7c72", activeforeground="#ffffff",
                    font=("Segoe UI", 11, "bold"), padx=22, pady=6,
                    relief="flat", bd=0, cursor="hand2", command=ok)
    okb.pack(side="right")
    cb = tk.Button(brow, text="Cancel", bg="#2a2e37", fg=_TEXT,
                   activebackground="#343945", activeforeground=_TEXT,
                   font=("Segoe UI", 11, "bold"), padx=18, pady=6,
                   relief="flat", bd=0, cursor="hand2", command=cancel)
    cb.pack(side="right", padx=(0, 8))
    host.protocol("WM_DELETE_WINDOW", cancel)
    host.wait_window()
    return result.get("value")


def _resolve_manager(parent):
    mgr = _manager_for(parent) if parent is not None else _default_manager
    return mgr


def _fallback(kind):
    import tkinter.messagebox as _mb
    return _mb


class _MessageBoxFacade:
    """tkinter.messagebox-compatible, rendered in-game."""

    def _show(self, kind, title, message, parent=None, **kw):
        detail = kw.get("detail")
        if detail:
            message = f"{message}\n\n{detail}"
        mgr = _resolve_manager(parent)
        if mgr is None:
            return _fallback(kind).showinfo(title, message)
        return _dialog(mgr, kind, title or "", message or "",
                       [("OK", True, "primary")])

    def showinfo(self, title=None, message=None, parent=None, **kw):
        return self._show("info", title, message, parent, **kw)

    def showwarning(self, title=None, message=None, parent=None, **kw):
        return self._show("warning", title, message, parent, **kw)

    def showerror(self, title=None, message=None, parent=None, **kw):
        return self._show("error", title, message, parent, **kw)

    def _ask(self, kind, title, message, parent, buttons, map_result):
        mgr = _resolve_manager(parent)
        if mgr is None:
            fb = _fallback(kind)
            return getattr(fb, "askyesno" if kind == "question" else "askokcancel")(
                title, message)
        val = _dialog(mgr, kind, title or "", message or "", buttons)
        return map_result(val)

    def askyesno(self, title=None, message=None, parent=None, **kw):
        return self._ask("question", title, message, parent,
                         [("Yes", True, "primary"), ("No", False, "secondary")],
                         lambda v: True if v is True else False)

    def askokcancel(self, title=None, message=None, parent=None, **kw):
        return self._ask("question", title, message, parent,
                         [("OK", True, "primary"),
                          ("Cancel", False, "secondary")],
                         lambda v: True if v is True else False)

    def askquestion(self, title=None, message=None, parent=None, **kw):
        mgr = _resolve_manager(parent)
        if mgr is None:
            return _fallback("question").askquestion(title, message)
        val = _dialog(mgr, "question", title or "", message or "",
                      [("Yes", "yes", "primary"), ("No", "no", "secondary")])
        return "yes" if val == "yes" else "no"

    def askretrycancel(self, title=None, message=None, parent=None, **kw):
        return self._ask("warning", title, message, parent,
                         [("Retry", True, "primary"),
                          ("Cancel", False, "secondary")],
                         lambda v: True if v is True else False)

    def askyesnocancel(self, title=None, message=None, parent=None, **kw):
        mgr = _resolve_manager(parent)
        if mgr is None:
            return _fallback("question").askyesnocancel(title, message)
        val = _dialog(mgr, "question", title or "", message or "",
                      [("Yes", True, "primary"), ("No", False, "secondary"),
                       ("Cancel", None, "secondary")])
        return val


class _SimpleDialogFacade:
    """tkinter.simpledialog-compatible askstring/askinteger, in-game."""

    def askstring(self, title, prompt, parent=None, initialvalue=None, **kw):
        mgr = _resolve_manager(parent)
        if mgr is None:
            import tkinter.simpledialog as _sd
            return _sd.askstring(title, prompt, initialvalue=initialvalue)
        return _prompt(mgr, title or "", prompt or "",
                       initial="" if initialvalue is None else initialvalue)

    def askinteger(self, title, prompt, parent=None, initialvalue=None,
                   minvalue=None, maxvalue=None, **kw):
        mgr = _resolve_manager(parent)
        if mgr is None:
            import tkinter.simpledialog as _sd
            return _sd.askinteger(title, prompt, initialvalue=initialvalue,
                                  minvalue=minvalue, maxvalue=maxvalue)
        val = _prompt(mgr, title or "", prompt or "",
                      initial="" if initialvalue is None else initialvalue,
                      as_int=True)
        if val is None:
            return None
        if minvalue is not None:
            val = max(minvalue, val)
        if maxvalue is not None:
            val = min(maxvalue, val)
        return val


messagebox = _MessageBoxFacade()
simpledialog = _SimpleDialogFacade()
