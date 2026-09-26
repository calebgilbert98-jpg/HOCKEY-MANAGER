# modern_widgets.py
# Rounded, modern Tkinter widgets: soft buttons, cards and pill badges.
# Tkinter's stock tk.Button / LabelFrame look sharp and dated; these
# canvas-drawn widgets give the UI rounded corners, hover states and flair
# while staying dependency-free (stdlib only).

import tkinter as tk

# Defaults mirror ui_theme_system.ColorScheme so the widgets blend in even
# when the caller doesn't pass explicit colors.
_DEFAULTS = {
    "primary_bg": "#0e0e11",
    "secondary_bg": "#16161a",
    "tertiary_bg": "#1e1e24",
    "primary_text": "#FFFFFF",
    "secondary_text": "#a1a1aa",
    "muted_text": "#71717a",
    "primary_accent": "#00ceb8",
    "secondary_accent": "#58a6ff",
    "success": "#3fb950",
    "warning": "#d29922",
    "border_light": "#2e2e38",
    "hover_bg": "#1e1e24",
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
                 radius=None, bg=None, fg=None, font=None,
                 padx=20, pady=10, width=None, height=None,
                 hover_bg=None, press_bg=None, state="normal",
                 blend_bg=None, **kw):
        self._bg = bg or _DEFAULTS["primary_accent"]
        self._hover_bg = hover_bg or _shade(self._bg, 1.18)
        self._press_bg = press_bg or _shade(self._bg, 0.82)
        self._fg = fg or _DEFAULTS["primary_text"]
        self._font = font or _FONT
        self._radius = radius  # None -> full pill
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
        self._radius = h / 2 - 2 if radius is None else radius

        # Match the parent background so corners look transparent.
        parent_bg = _blend_bg(parent, blend_bg)
        kw.setdefault("highlightthickness", 0)
        kw.setdefault("bd", 0)
        super().__init__(parent, width=w, height=h, bg=parent_bg, **kw)

        self._rect = self.create_polygon(
            _rounded_polygon_points(2, 2, w - 2, h - 2, self._radius),
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

    def set_fill(self, bg):
        """Change the pill fill color (updates hover/press shades too)."""
        self._bg = bg
        self._hover_bg = _shade(bg, 1.18)
        self._press_bg = _shade(bg, 0.82)
        if self._state == "disabled":
            self._set_disabled_look()
        else:
            self._paint(bg)

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
                               else "#0d2b28")],
                  foreground=[("selected", _DEFAULTS["primary_text"])])
    except Exception:
        pass


# ----------------------------------------------------------------------
# Dark input family: replaces white tk.Entry / Text / Combobox boxes.
# ----------------------------------------------------------------------

_INPUT_BG = "#161D29"
_INPUT_BORDER = "#2e2e38"
_INPUT_FOCUS = "#58a6ff"


class DarkEntry(tk.Canvas):
    """A dark, pill-shaped text entry. Drop-in-ish replacement for tk.Entry.

    Delegates the common Entry API (get/insert/delete/bind/focus_set) to the
    inner widget: ``entry = DarkEntry(parent); entry.get()``.
    """

    def __init__(self, parent, *, radius=None, width=24, font=None,
                 textvariable=None, show=None, state="normal",
                 blend_bg=None, **kw):
        self._radius = radius
        self._input_bg = kw.pop("bg", _INPUT_BG)
        self._border = _INPUT_BORDER
        self._font = font or ("Segoe UI", 10)
        try:
            import tkinter.font as tkfont
            fnt = tkfont.Font(font=self._font)
            cw, ch = fnt.measure("0") * width, fnt.metrics("linespace")
        except Exception:
            cw, ch = width * 8, 20
        w, h = cw + 24, ch + 14
        self._radius = h / 2 - 2 if radius is None else radius
        parent_bg = _blend_bg(parent, blend_bg)
        kw.setdefault("highlightthickness", 0)
        kw.setdefault("bd", 0)
        super().__init__(parent, width=w, height=h, bg=parent_bg, **kw)
        self._frame = self.create_polygon(
            _rounded_polygon_points(2, 2, w - 2, h - 2, self._radius),
            smooth=True, fill=self._input_bg, outline=self._border, width=1)
        self.entry = tk.Entry(self, bg=self._input_bg,
                              fg=_DEFAULTS["primary_text"],
                              insertbackground=_DEFAULTS["primary_text"],
                              relief="flat", bd=0, highlightthickness=0,
                              font=self._font, textvariable=textvariable,
                              show=show, state=state,
                              disabledbackground=self._input_bg,
                              disabledforeground=_DEFAULTS["muted_text"])
        self.create_window(12, h / 2, anchor="w", window=self.entry,
                           width=cw)
        self.entry.bind("<FocusIn>", lambda _e: self._set_border(_INPUT_FOCUS))
        self.entry.bind("<FocusOut>", lambda _e: self._set_border(_INPUT_BORDER))

    def _set_border(self, color):
        self._border = color
        self.itemconfig(self._frame, outline=color)

    # -- Entry API delegation -------------------------------------------
    def get(self):
        return self.entry.get()

    def insert(self, index, text):
        return self.entry.insert(index, text)

    def delete(self, first, last=None):
        return self.entry.delete(first, last) if last is not None \
            else self.entry.delete(first)

    def index(self, i):
        return self.entry.index(i)

    def icursor(self, i):
        return self.entry.icursor(i)

    def selection_clear(self):
        return self.entry.selection_clear()

    def focus_set(self):
        return self.entry.focus_set()

    def bind(self, sequence, func=None, add=None):
        return self.entry.bind(sequence, func, add)

    def config(self, **kw):
        if "state" in kw:
            self.entry.config(state=kw.pop("state"))
        if "textvariable" in kw:
            self.entry.config(textvariable=kw.pop("textvariable"))
        if "show" in kw:
            self.entry.config(show=kw.pop("show"))
        if kw:
            super().config(**kw)

    configure = config


class DarkText(tk.Text):
    """Dark multi-line text box (no white background, no harsh border)."""

    def __init__(self, parent, *, font=None, **kw):
        kw.setdefault("bg", _INPUT_BG)
        kw.setdefault("fg", _DEFAULTS["primary_text"])
        kw.setdefault("insertbackground", _DEFAULTS["primary_text"])
        kw.setdefault("selectbackground", "#0d2b28")
        kw.setdefault("selectforeground", _DEFAULTS["primary_text"])
        kw.setdefault("relief", "flat")
        kw.setdefault("bd", 0)
        kw.setdefault("highlightthickness", 1)
        kw.setdefault("highlightbackground", _INPUT_BORDER)
        kw.setdefault("highlightcolor", _INPUT_FOCUS)
        kw.setdefault("font", font or ("Segoe UI", 10))
        kw.setdefault("padx", 8)
        kw.setdefault("pady", 8)
        super().__init__(parent, **kw)


def style_combobox(style, style_name="Dark.TCombobox"):
    """Register a dark ttk.Combobox style; apply with style=style_name."""
    try:
        style.configure(style_name,
                        fieldbackground=_INPUT_BG,
                        background=_INPUT_BG,
                        foreground=_DEFAULTS["primary_text"],
                        arrowcolor=_DEFAULTS["secondary_text"],
                        borderwidth=1,
                        relief="flat")
        style.map(style_name,
                  fieldbackground=[("readonly", _INPUT_BG),
                                   ("disabled", _INPUT_BG)],
                  foreground=[("readonly", _DEFAULTS["primary_text"]),
                              ("disabled", _DEFAULTS["muted_text"])])
        # The dropdown is a plain tk Listbox; recolor it via the option db.
        try:
            root = style.master
            root.option_add("*TCombobox*Listbox.background", _INPUT_BG)
            root.option_add("*TCombobox*Listbox.foreground",
                            _DEFAULTS["primary_text"])
            root.option_add("*TCombobox*Listbox.selectBackground", "#0d2b28")
            root.option_add("*TCombobox*Listbox.selectForeground",
                            _DEFAULTS["primary_text"])
        except Exception:
            pass
    except Exception:
        pass
    return style_name


class DarkListbox(tk.Listbox):
    """Dark listbox matching the input family."""

    def __init__(self, parent, *, font=None, **kw):
        kw.setdefault("bg", _INPUT_BG)
        kw.setdefault("fg", _DEFAULTS["secondary_text"])
        kw.setdefault("selectbackground", "#0d2b28")
        kw.setdefault("selectforeground", _DEFAULTS["primary_text"])
        kw.setdefault("relief", "flat")
        kw.setdefault("bd", 0)
        kw.setdefault("highlightthickness", 1)
        kw.setdefault("highlightbackground", _INPUT_BORDER)
        kw.setdefault("highlightcolor", _INPUT_FOCUS)
        kw.setdefault("font", font or ("Segoe UI", 10))
        kw.setdefault("activestyle", "none")
        super().__init__(parent, **kw)


def apply_dark_form_theme(root):
    """Recolor every form control in the app: no more white text boxes.

    Call once, right after the Tk root exists and before windows are built.
    Uses the option database for tk.Entry/Text/Listbox/Spinbox and the
    default ttk styles for TEntry/TCombobox, so all existing call sites pick
    it up without edits. Explicit per-widget colors still win.
    """
    _pt = _DEFAULTS["primary_text"]
    _st = _DEFAULTS["secondary_text"]
    for cls in ("Entry", "Text", "Listbox", "Spinbox"):
        root.option_add(f"*{cls}.background", _INPUT_BG)
        root.option_add(f"*{cls}.foreground", _pt if cls != "Listbox" else _st)
        root.option_add(f"*{cls}.insertBackground", _pt)
        root.option_add(f"*{cls}.selectBackground", "#0d2b28")
        root.option_add(f"*{cls}.selectForeground", _pt)
        root.option_add(f"*{cls}.highlightBackground", _INPUT_BORDER)
        root.option_add(f"*{cls}.highlightColor", _INPUT_FOCUS)
        root.option_add(f"*{cls}.highlightThickness", 1)
        root.option_add(f"*{cls}.relief", "flat")
        root.option_add(f"*{cls}.borderWidth", 0)
    # Combobox dropdown listbox.
    root.option_add("*TCombobox*Listbox.background", _INPUT_BG)
    root.option_add("*TCombobox*Listbox.foreground", _pt)
    root.option_add("*TCombobox*Listbox.selectBackground", "#0d2b28")
    root.option_add("*TCombobox*Listbox.selectForeground", _pt)

    try:
        from tkinter import ttk as _ttk
        style = _ttk.Style(root)
        style.configure("TEntry",
                        fieldbackground=_INPUT_BG,
                        foreground=_pt,
                        insertcolor=_pt,
                        borderwidth=1,
                        relief="flat")
        style.map("TEntry",
                  fieldbackground=[("disabled", _INPUT_BG)],
                  foreground=[("disabled", _DEFAULTS["muted_text"])])
        style.configure("TCombobox",
                        fieldbackground=_INPUT_BG,
                        background=_INPUT_BG,
                        foreground=_pt,
                        arrowcolor=_st,
                        borderwidth=1,
                        relief="flat")
        style.map("TCombobox",
                  fieldbackground=[("readonly", _INPUT_BG),
                                   ("disabled", _INPUT_BG),
                                   ("active", _INPUT_BG)],
                  foreground=[("readonly", _pt),
                              ("disabled", _DEFAULTS["muted_text"])],
                  background=[("readonly", _INPUT_BG)])
        style.configure("TSpinbox",
                        fieldbackground=_INPUT_BG,
                        background=_INPUT_BG,
                        foreground=_pt,
                        arrowcolor=_st)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Mini canvas icons (no emoji, no image files — drawn with primitives)
# ---------------------------------------------------------------------------
def draw_mini_icon(canvas, cx, cy, size, kind, color):
    """Draw a small geometric icon centered at (cx, cy). Returns item ids."""
    s = size / 2
    k = kind.lower()
    ids = []
    if k == "trophy":
        ids.append(canvas.create_arc(cx - s, cy - s, cx + s, cy + s * 0.6,
                                     start=0, extent=180, style="arc",
                                     outline=color, width=max(2, size // 8)))
        ids.append(canvas.create_rectangle(cx - s * 0.5, cy - s * 0.2,
                                           cx + s * 0.5, cy + s * 0.5,
                                           fill=color, outline=""))
        ids.append(canvas.create_rectangle(cx - s * 0.7, cy + s * 0.5,
                                           cx + s * 0.7, cy + s * 0.75,
                                           fill=color, outline=""))
        ids.append(canvas.create_rectangle(cx - s * 0.9, cy + s * 0.75,
                                           cx + s * 0.9, cy + s,
                                           fill=color, outline=""))
    elif k == "puck":
        ids.append(canvas.create_oval(cx - s, cy - s * 0.7, cx + s, cy + s * 0.7,
                                      fill="#111111", outline=color,
                                      width=max(1, size // 12)))
        ids.append(canvas.create_line(cx - s * 0.9, cy, cx + s * 0.9, cy,
                                      fill=color, width=max(1, size // 12)))
    elif k == "chart":
        for i, h in enumerate((0.45, 0.75, 1.0)):
            x0 = cx - s + i * (size / 3) + 1
            ids.append(canvas.create_rectangle(
                x0, cy + s - h * size * 0.9, x0 + size / 3 - 2, cy + s,
                fill=color, outline=""))
    elif k == "mail":
        ids.append(canvas.create_rectangle(cx - s, cy - s * 0.7, cx + s, cy + s * 0.7,
                                           outline=color, width=max(2, size // 8)))
        ids.append(canvas.create_line(cx - s, cy - s * 0.5, cx, cy + s * 0.2,
                                      fill=color, width=max(2, size // 10)))
        ids.append(canvas.create_line(cx + s, cy - s * 0.5, cx, cy + s * 0.2,
                                      fill=color, width=max(2, size // 10)))
    elif k == "calendar":
        ids.append(canvas.create_rectangle(cx - s, cy - s * 0.6, cx + s, cy + s,
                                           outline=color, width=max(2, size // 8)))
        ids.append(canvas.create_line(cx - s, cy - s * 0.1, cx + s, cy - s * 0.1,
                                      fill=color, width=max(2, size // 10)))
        for dx in (-s * 0.5, s * 0.5):
            ids.append(canvas.create_line(cx + dx, cy - s, cx + dx, cy - s * 0.3,
                                          fill=color, width=max(2, size // 8)))
    elif k == "whistle":
        ids.append(canvas.create_oval(cx - s, cy - s * 0.8, cx + s * 0.2, cy + s * 0.8,
                                      outline=color, width=max(2, size // 8)))
        ids.append(canvas.create_oval(cx - s * 0.35, cy - s * 0.15,
                                      cx + s * 0.05, cy + s * 0.25,
                                      fill=color, outline=""))
        ids.append(canvas.create_rectangle(cx + s * 0.2, cy - s * 0.25,
                                           cx + s, cy + s * 0.25,
                                           fill=color, outline=""))
    elif k == "star":
        import math
        pts = []
        for i in range(10):
            r = s if i % 2 == 0 else s * 0.45
            a = -math.pi / 2 + i * math.pi / 5
            pts += [cx + r * math.cos(a), cy + r * math.sin(a)]
        ids.append(canvas.create_polygon(pts, fill=color, outline=""))
    elif k == "users":
        ids.append(canvas.create_oval(cx - s * 0.9, cy - s, cx - s * 0.1, cy - s * 0.2,
                                      fill=color, outline=""))
        ids.append(canvas.create_arc(cx - s * 1.1, cy - s * 0.1, cx + s * 0.1, cy + s,
                                     start=0, extent=180, style="arc",
                                     outline=color, width=max(2, size // 8)))
        ids.append(canvas.create_oval(cx + s * 0.1, cy - s * 0.8, cx + s * 0.9, cy,
                                      fill=color, outline=""))
    elif k == "shield":
        ids.append(canvas.create_polygon(
            cx - s, cy - s * 0.8, cx + s, cy - s * 0.8,
            cx + s, cy, cx, cy + s, cx - s, cy,
            fill="", outline=color, width=max(2, size // 8)))
    elif k == "bolt":
        ids.append(canvas.create_polygon(
            cx + s * 0.2, cy - s, cx - s * 0.5, cy + s * 0.2,
            cx, cy + s * 0.2, cx - s * 0.2, cy + s,
            cx + s * 0.5, cy - s * 0.2, cx, cy - s * 0.2,
            fill=color, outline=""))
    else:  # "dot" fallback
        ids.append(canvas.create_oval(cx - s * 0.5, cy - s * 0.5,
                                      cx + s * 0.5, cy + s * 0.5,
                                      fill=color, outline=""))
    return ids


# ---------------------------------------------------------------------------
# SegmentedControl — pill toggle group replacing small dropdowns
# ---------------------------------------------------------------------------
class SegmentedControl(tk.Frame):
    """A row of pill segments; exactly one selected. Drop-in for 2-6 option dropdowns."""

    def __init__(self, parent, options, initial=0, command=None, *,
                 accent=None, bg=None, fg=None, font=("Segoe UI", 10, "bold"),
                 padx=10, pady=6):
        super().__init__(parent, bg=_blend_bg(parent, bg),
                         highlightthickness=0, bd=0)
        self._seg_options = list(options)
        self._command = command
        self._accent = accent or _DEFAULTS["primary_accent"]
        self._fg = fg or _DEFAULTS["primary_text"]
        self._font = font
        self._selected = None
        self._buttons = []
        self._ready = False
        for i, opt in enumerate(self._seg_options):
            b = RoundedButton(self, text=str(opt), radius=999,
                              bg=_DEFAULTS["tertiary_bg"], fg=self._fg,
                              font=font, padx=padx, pady=pady,
                              command=lambda v=opt: self.set(v))
            b.pack(side="left", padx=2)
            self._buttons.append(b)
        self.set(self._seg_options[initial] if self._seg_options else None)
        self._ready = True

    def set(self, value):
        if value not in self._seg_options:
            return
        self._selected = value
        for b, opt in zip(self._buttons, self._seg_options):
            if opt == value:
                b.set_fill(self._accent)
            else:
                b.set_fill(_DEFAULTS["tertiary_bg"])
        if self._command and getattr(self, "_ready", False):
            self._command(value)

    def get(self):
        return self._selected


# ---------------------------------------------------------------------------
# IconTile — tappable visual tile replacing text-only action buttons
# ---------------------------------------------------------------------------
class IconTile(tk.Canvas):
    """A rounded tile with a drawn icon, title and subtitle. For dashboards."""

    def __init__(self, parent, *, icon="star", title="", subtitle="",
                 command=None, width=160, height=104,
                 bg=None, accent=None, icon_color=None,
                 title_font=("Segoe UI", 11, "bold"),
                 sub_font=("Segoe UI", 9)):
        self._bg = bg or _DEFAULTS["secondary_bg"]
        self._accent = accent or _DEFAULTS["primary_accent"]
        parent_bg = _blend_bg(parent)
        super().__init__(parent, width=width, height=height, bg=parent_bg,
                         highlightthickness=0, bd=0)
        self._tw, self._th = width, height
        self._command = command
        self._icon = icon
        self._icon_color = icon_color or _DEFAULTS["primary_text"]
        self._title = title
        self._subtitle = subtitle
        self._title_font = title_font
        self._sub_font = sub_font
        self._draw(False)
        if command:
            self.configure(cursor="hand2")
            self.bind("<Button-1>", lambda e: command())
            self.bind("<Enter>", lambda e: self._draw(True))
            self.bind("<Leave>", lambda e: self._draw(False))

    def _draw(self, hover):
        self.delete("all")
        w, h = self._tw, self._th
        fill = _shade(self._bg, 1.18) if hover else self._bg
        self.create_polygon(_rounded_polygon_points(2, 2, w - 2, h - 2, 12),
                            smooth=True, fill=fill, outline="")
        # accent bar on the left edge
        self.create_polygon(_rounded_polygon_points(2, 2, 8, h - 2, 4),
                            smooth=True, fill=self._accent, outline="")
        draw_mini_icon(self, 34, 32, 30, self._icon, self._icon_color)
        self.create_text(20, 58, text=self._title, anchor="w",
                         fill=_DEFAULTS["primary_text"], font=self._title_font)
        if self._subtitle:
            self.create_text(20, 80, text=self._subtitle, anchor="w",
                             fill=_DEFAULTS["muted_text"], font=self._sub_font)


# ---------------------------------------------------------------------------
# FormStreak — W/L/OTL dots for recent form
# ---------------------------------------------------------------------------
class FormStreak(tk.Canvas):
    """Row of colored dots: W green, L red, OTL/T yellow. Most recent last."""

    COLORS = {"W": "#3fb950", "L": "#00ceb8", "O": "#d29922", "T": "#d29922"}

    def __init__(self, parent, results, *, dot=14, gap=6, bg=None, **kw):
        self._results = [r.upper() for r in results]
        w = len(self._results) * (dot + gap) + gap
        h = dot + gap * 2
        kw.setdefault("highlightthickness", 0)
        kw.setdefault("bd", 0)
        super().__init__(parent, width=w, height=h, bg=_blend_bg(parent, bg), **kw)
        y = h / 2
        for i, r in enumerate(self._results):
            x = gap + dot / 2 + i * (dot + gap)
            color = self.COLORS.get(r, "#71717a")
            self.create_oval(x - dot / 2, y - dot / 2, x + dot / 2, y + dot / 2,
                             fill=color, outline="")
            self.create_text(x, y, text=r, fill="#0e0e11",
                             font=("Segoe UI", 8, "bold"))
