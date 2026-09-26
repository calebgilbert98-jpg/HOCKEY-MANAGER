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
