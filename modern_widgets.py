# modern_widgets.py
# Rounded, modern Tkinter widgets: soft buttons, cards and pill badges.
# Tkinter's stock tk.Button / LabelFrame look sharp and dated; these
# canvas-drawn widgets give the UI rounded corners, hover states and flair
# while staying dependency-free (stdlib only).

import tkinter as tk

# Defaults mirror ui_theme_system.ColorScheme so the widgets blend in even
# when the caller doesn't pass explicit colors.
_DEFAULTS = {
    "primary_bg": "#0F1419",
    "secondary_bg": "#1B2332",
    "tertiary_bg": "#242F42",
    "primary_text": "#FFFFFF",
    "secondary_text": "#B8C5D6",
    "muted_text": "#7A8AA3",
    "primary_accent": "#DC3545",
    "secondary_accent": "#4A9EFF",
    "success": "#46C93A",
    "warning": "#FF9F43",
    "border_light": "#3A4A63",
    "hover_bg": "#2A3441",
}

try:  # Prefer the live theme palette when available.
    from ui_theme_system import create_modern_theme as _mk_theme

    _c = _mk_theme().colors
    for _k in _DEFAULTS:
        if hasattr(_c, _k):
            _DEFAULTS[_k] = getattr(_c, _k)
except Exception:
    pass

_FONT = ("Segoe UI", 11, "bold")


def _blend_bg(parent, override=None):
    """Canvas background so rounded corners blend into the parent."""
    if override:
        return override
    try:
        return parent.cget("bg")
    except Exception:
        pass
    # ttk widgets have no 'bg' option: try the style's background.
    try:
        from tkinter import ttk as _ttk
        style_name = parent.cget("style")
        if style_name:
            st = _ttk.Style(parent)
            bg = st.lookup(style_name, "background")
            if bg:
                return bg
    except Exception:
        pass
    return _DEFAULTS["primary_bg"]


def _shade(hex_color, factor):
    """Lighten (>1) or darken (<1) a #rrggbb color."""
    hex_color = hex_color.lstrip("#")
    try:
        r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    except Exception:
        return "#" + hex_color
    r = max(0, min(255, int(r * factor)))
    g = max(0, min(255, int(g * factor)))
    b = max(0, min(255, int(b * factor)))
    return f"#{r:02x}{g:02x}{b:02x}"


def _rounded_polygon_points(x1, y1, x2, y2, r):
    r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    return [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]


class RoundedButton(tk.Canvas):
    """A soft rounded button with hover and press states.

    Usage mirrors tk.Button for the common cases:
        RoundedButton(parent, text="Save", command=fn).pack(pady=8)
    """

    def __init__(self, parent, text="", command=None, *,
                 radius=12, bg=None, fg=None, font=None,
                 padx=20, pady=10, width=None, height=None,
                 hover_bg=None, press_bg=None, state="normal",
                 blend_bg=None, **kw):
        self._bg = bg or _DEFAULTS["primary_accent"]
        self._hover_bg = hover_bg or _shade(self._bg, 1.18)
        self._press_bg = press_bg or _shade(self._bg, 0.82)
        self._fg = fg or _DEFAULTS["primary_text"]
        self._font = font or _FONT
        self._radius = radius
        self._command = command
        self._state = state
        self._text = text
        self._padx, self._pady = padx, pady

        # Auto-size from the label unless explicit dimensions are given.
        try:
            import tkinter.font as tkfont
            fnt = tkfont.Font(font=self._font)
            tw, th = fnt.measure(text), fnt.metrics("linespace")
        except Exception:
            tw, th = len(text) * 9, 20
        w = width or (tw + padx * 2)
        h = height or (th + pady * 2)

        # Match the parent background so corners look transparent.
        parent_bg = _blend_bg(parent, blend_bg)
        kw.setdefault("highlightthickness", 0)
        kw.setdefault("bd", 0)
        super().__init__(parent, width=w, height=h, bg=parent_bg, **kw)

        self._rect = self.create_polygon(
            _rounded_polygon_points(2, 2, w - 2, h - 2, radius),
            smooth=True, fill=self._bg, outline="")
        self._label = self.create_text(
            w / 2, h / 2, text=text, fill=self._fg, font=self._font)

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        if state == "disabled":
            self._set_disabled_look()

    # -- state -----------------------------------------------------------
    def _paint(self, color):
        self.itemconfig(self._rect, fill=color)

    def _on_enter(self, _e=None):
        if self._state == "disabled":
            return
        self._paint(self._hover_bg)
        self.config(cursor="hand2")

    def _on_leave(self, _e=None):
        if self._state == "disabled":
            return
        self._paint(self._bg)
        self.config(cursor="")

    def _on_press(self, _e=None):
        if self._state == "disabled":
            return
        self._paint(self._press_bg)

    def _on_release(self, _e=None):
        if self._state == "disabled":
            return
        self._paint(self._hover_bg)
        if callable(self._command):
            self._command()

    def _set_disabled_look(self):
        self._paint(_shade(self._bg, 0.55))
        self.itemconfig(self._label, fill=_DEFAULTS["muted_text"])

    def set_state(self, state):
        self._state = state
        if state == "disabled":
            self._set_disabled_look()
        else:
            self.itemconfig(self._label, fill=self._fg)
            self._paint(self._bg)

    def set_text(self, text):
        self._text = text
        self.itemconfig(self._label, text=text)

    # -- tk.Button-compatible shims -------------------------------------
    def config(self, **kw):
        if "text" in kw:
            self.set_text(kw.pop("text"))
        if "state" in kw:
            self.set_state(kw.pop("state"))
        if kw:
            super().config(**kw)

    configure = config

    def cget(self, key):
        if key == "text":
            return self._text
        if key == "state":
            return self._state
        return super().cget(key)


class Card(tk.Canvas):
    """A rounded-corner card panel with a subtle border.

    Put content widgets into ``card.body``:
        card = Card(parent)
        card.pack(fill="x", padx=12, pady=8)
        tk.Label(card.body, ...).pack()
    """

    def __init__(self, parent, *, radius=14, bg=None, border=None,
                 padx=14, pady=12, width=0, height=0, blend_bg=None, **kw):
        self._radius = radius
        self._card_bg = bg or _DEFAULTS["tertiary_bg"]
        self._border = border or _DEFAULTS["border_light"]
        self._padx, self._pady = padx, pady
        parent_bg = _blend_bg(parent, blend_bg)
        kw.setdefault("highlightthickness", 0)
        kw.setdefault("bd", 0)
        super().__init__(parent, bg=parent_bg, **kw)
        if width:
            self.config(width=width)
        if height:
            self.config(height=height)
        self.body = tk.Frame(self, bg=self._card_bg)
        self._win = self.create_window(padx, pady, anchor="nw", window=self.body)
        self._auto_size = not (width or height)
        self.bind("<Configure>", self._redraw)
        # Keep the card sized to its content when no explicit size given.
        self.body.bind("<Configure>", self._fit_to_body)

    def _redraw(self, _e=None):
        w = self.winfo_width()
        h = self.winfo_height()
        self.delete("cardbg")
        if w > 4 and h > 4:
            self.create_polygon(
                _rounded_polygon_points(1, 1, w - 1, h - 1, self._radius),
                smooth=True, fill=self._card_bg,
                outline=self._border, width=1, tags="cardbg")
            self.tag_lower("cardbg")

    def _fit_to_body(self, _e=None):
        if not self._auto_size:
            return  # explicit size: don't fight the caller
        req_w = self.body.winfo_reqwidth() + self._padx * 2
        req_h = self.body.winfo_reqheight() + self._pady * 2
        if req_w > 10 and req_h > 10:
            self.config(width=req_w, height=req_h)


class Pill(tk.Canvas):
    """A small rounded badge, e.g. for archetypes or statuses."""

    def __init__(self, parent, text="", *, bg=None, fg=None,
                 font=("Segoe UI", 9, "bold"), padx=12, pady=5,
                 blend_bg=None, **kw):
        self._bg = bg or _DEFAULTS["secondary_accent"]
        self._fg = fg or _DEFAULTS["primary_text"]
        try:
            import tkinter.font as tkfont
            fnt = tkfont.Font(font=font)
            tw, th = fnt.measure(text), fnt.metrics("linespace")
        except Exception:
            tw, th = len(text) * 8, 16
        w, h = tw + padx * 2, th + pady * 2
        parent_bg = _blend_bg(parent, blend_bg)
        kw.setdefault("highlightthickness", 0)
        kw.setdefault("bd", 0)
        super().__init__(parent, width=w, height=h, bg=parent_bg, **kw)
        self.create_polygon(
            _rounded_polygon_points(1, 1, w - 1, h - 1, h / 2 - 1),
            smooth=True, fill=self._bg, outline="")
        self.create_text(w / 2, h / 2, text=text, fill=self._fg, font=font)


def style_treeview(style, *, row_bg=None, alt_bg=None):
    """Soften a ttk.Treeview: row height, selection color, no harsh gridlines."""
    row_bg = row_bg or _DEFAULTS["secondary_bg"]
    alt_bg = alt_bg or _DEFAULTS["tertiary_bg"]
    try:
        style.configure("Treeview",
                        background=row_bg,
                        fieldbackground=row_bg,
                        foreground=_DEFAULTS["secondary_text"],
                        rowheight=26,
                        borderwidth=0)
        style.configure("Treeview.Heading",
                        background=_DEFAULTS["border_dark"],
                        foreground=_DEFAULTS["primary_text"],
                        font=("Segoe UI", 10, "bold"),
                        borderwidth=0)
        style.map("Treeview",
                  background=[("selected", _DEFAULTS["selected_bg"]
                               if "selected_bg" in _DEFAULTS
                               else "#335577")],
                  foreground=[("selected", _DEFAULTS["primary_text"])])
    except Exception:
        pass
