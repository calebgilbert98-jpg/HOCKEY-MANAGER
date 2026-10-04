# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
# branding.py
# Shared helpers for loading Puck Dynasty brand graphics (logo, banners).
#
# Every function here is defensive: if an asset is missing or PIL fails,
# the caller gets None / a collapsed widget and the UI keeps working.

import os
import sys
import tkinter as tk


def assets_dir():
    """Location of the bundled assets folder (dev tree or PyInstaller bundle)."""
    meipass = getattr(sys, '_MEIPASS', None)
    if meipass:
        return os.path.join(meipass, 'assets')
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets')


def asset_path(name):
    return os.path.join(assets_dir(), name)


def cover_photo(name, width, height):
    """Load an asset cover-cropped to exactly (width, height).

    Returns an ImageTk.PhotoImage, or None if anything fails.
    The caller MUST keep a reference (e.g. on self) to avoid GC.
    """
    try:
        from PIL import Image, ImageTk
        path = asset_path(name)
        if not os.path.exists(path):
            return None
        img = Image.open(path).convert('RGBA')
        scale = max(width / img.width, height / img.height)
        nw = max(int(img.width * scale + 0.5), 1)
        nh = max(int(img.height * scale + 0.5), 1)
        resized = img.resize((nw, nh), Image.LANCZOS)
        left = (nw - width) // 2
        top = (nh - height) // 2
        cropped = resized.crop((left, top, left + width, top + height))
        return ImageTk.PhotoImage(cropped)
    except Exception:
        return None


def load_logo(master=None, size=48):
    """Load the Puck Dynasty logo as a square PhotoImage thumbnail.

    Returns None on any failure. Caller must keep a reference.
    """
    try:
        from PIL import Image, ImageTk
        path = asset_path('puck_dynasty_logo.png')
        if not os.path.exists(path):
            return None
        img = Image.open(path).convert('RGBA')
        img.thumbnail((size, size), Image.LANCZOS)
        if master is not None:
            return ImageTk.PhotoImage(img, master=master)
        return ImageTk.PhotoImage(img)
    except Exception:
        return None


class HeroBanner(tk.Frame):
    """Taller hero strip with the title composited ON the banner image.

    Cover-crops `asset_name` to (current width x height), darkens it
    slightly for legibility, pastes the logo centered above the title, and
    draws title + subtitle text on the canvas. Re-renders (debounced) on
    resize. If the banner asset is missing, falls back to a plain charcoal
    strip with logo + text still shown.
    """

    def __init__(self, parent, asset_name, height=180, title="",
                 subtitle="", logo_size=64,
                 title_font=("Segoe UI", 32, "bold"),
                 subtitle_font=("Segoe UI", 11),
                 title_fg="#ffffff", subtitle_fg="#3B82F6",
                 bg="#0e0e11", **kwargs):
        super().__init__(parent, height=height, bg=bg, **kwargs)
        self.pack_propagate(False)
        self._asset_name = asset_name
        self._height = height
        self._title = title
        self._subtitle = subtitle
        self._logo_size = logo_size
        self._title_font = title_font
        self._subtitle_font = subtitle_font
        self._title_fg = title_fg
        self._subtitle_fg = subtitle_fg
        self._bg = bg
        self._photo = None
        self._banner_src = None
        self._logo_src = None
        self._pending = None
        self._canvas = tk.Canvas(self, height=height, highlightthickness=0,
                                 bg=bg)
        self._canvas.pack(fill="both", expand=True)
        self._load_sources()
        self.bind("<Configure>", self._on_resize)

    def _load_sources(self):
        try:
            from PIL import Image
            bpath = asset_path(self._asset_name)
            if os.path.exists(bpath):
                self._banner_src = Image.open(bpath).convert("RGBA")
            lpath = asset_path("puck_dynasty_logo.png")
            if os.path.exists(lpath):
                logo = Image.open(lpath).convert("RGBA")
                logo.thumbnail((self._logo_size, self._logo_size),
                               Image.LANCZOS)
                self._logo_src = logo
        except Exception:
            pass
        self._render()

    def _on_resize(self, _event=None):
        if self._pending:
            try:
                self.after_cancel(self._pending)
            except Exception:
                pass
        try:
            self._pending = self.after_idle(self._render)
        except Exception:
            pass

    def _render(self):
        self._pending = None
        try:
            from PIL import Image, ImageTk
            w = self.winfo_width()
            h = self._height
            if w < 2:
                return
            if self._banner_src is not None:
                img = self._banner_src
                scale = max(w / img.width, h / img.height)
                nw = max(int(img.width * scale + 0.5), 1)
                nh = max(int(img.height * scale + 0.5), 1)
                resized = img.resize((nw, nh), Image.LANCZOS)
                left = (nw - w) // 2
                top = (nh - h) // 2
                base = resized.crop((left, top, left + w, top + h)).convert("RGBA")
                # Darken for text legibility
                overlay = Image.new("RGBA", (w, h), (0, 0, 0, 110))
                base = Image.alpha_composite(base, overlay)
            else:
                base = Image.new("RGBA", (w, h), (14, 14, 17, 255))

            # Paste logo centered near the top
            logo_h = 0
            if self._logo_src is not None:
                lw, lh = self._logo_src.size
                base.paste(self._logo_src, ((w - lw) // 2, 14),
                           self._logo_src)
                logo_h = lh

            self._photo = ImageTk.PhotoImage(base)
            c = self._canvas
            c.delete("all")
            c.create_image(w // 2, h // 2, image=self._photo)

            # Title / subtitle below the logo
            ty = 14 + logo_h + 26
            if self._title:
                c.create_text(w // 2 + 1, ty + 1, text=self._title,
                              font=self._title_font, fill="#000000")
                c.create_text(w // 2, ty, text=self._title,
                              font=self._title_font, fill=self._title_fg)
            if self._subtitle:
                sy = ty + 30
                c.create_text(w // 2, sy, text=self._subtitle,
                              font=self._subtitle_font,
                              fill=self._subtitle_fg)
        except Exception:
            pass


class SlimBanner(tk.Frame):
    """Slim full-width image strip (hero/banner).

    The asset is cover-cropped to (current width x height) and re-rendered
    (debounced) when the strip is resized. If the asset is missing the strip
    collapses to ~1px so layout is unaffected.
    """

    def __init__(self, parent, asset_name, height=84, bg='#0e0e11', **kwargs):
        super().__init__(parent, height=height, bg=bg, **kwargs)
        self.pack_propagate(False)
        self._asset_name = asset_name
        self._height = height
        self._photo = None
        self._src = None
        self._pending = None
        self._canvas = tk.Canvas(self, height=height, highlightthickness=0, bg=bg)
        self._canvas.pack(fill='both', expand=True)
        self._load_source()
        self.bind('<Configure>', self._on_resize)

    def _load_source(self):
        try:
            from PIL import Image
            path = asset_path(self._asset_name)
            if os.path.exists(path):
                self._src = Image.open(path).convert('RGBA')
        except Exception:
            self._src = None
        if self._src is None:
            # No asset: collapse so the strip takes no space.
            try:
                self.configure(height=1)
                self._canvas.configure(height=1)
            except Exception:
                pass
        else:
            self._render()

    def _on_resize(self, _event=None):
        if self._pending:
            try:
                self.after_cancel(self._pending)
            except Exception:
                pass
        try:
            self._pending = self.after_idle(self._render)
        except Exception:
            pass

    def _render(self):
        self._pending = None
        if self._src is None:
            return
        try:
            w = self.winfo_width()
            h = self._height
            if w < 2:
                return
            from PIL import Image, ImageTk
            img = self._src
            scale = max(w / img.width, h / img.height)
            nw = max(int(img.width * scale + 0.5), 1)
            nh = max(int(img.height * scale + 0.5), 1)
            resized = img.resize((nw, nh), Image.LANCZOS)
            left = (nw - w) // 2
            top = (nh - h) // 2
            cropped = resized.crop((left, top, left + w, top + h))
            self._photo = ImageTk.PhotoImage(cropped)
            self._canvas.delete('all')
            self._canvas.create_image(w // 2, h // 2, image=self._photo)
        except Exception:
            pass
