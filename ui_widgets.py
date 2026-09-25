"""Shared UI widgets for Puck Dynasty's dark, modern look.

PillButton is a canvas-drawn, fully-rounded pill button (tk.Button can't do
rounded corners on Linux). Use it for selector rows anywhere pills fit.
"""
import tkinter as tk


class PillButton(tk.Canvas):
    """A fully-rounded pill button drawn on a Canvas (tk.Button can't do
    rounded corners on Linux). Used for selector rows in dark UI windows."""

    def __init__(self, parent, text, command=None, font=('Helvetica', 10, 'bold'),
                 padx=16, pady=8, bg=None, fg='#c8d0e0',
                 selected_bg='#E63946', selected_fg='white',
                 hover_bg='#2a3550', **kw):
        self.text = text
        self.command = command
        self.font = font
        self.padx, self.pady = padx, pady
        self.fg = fg
        self.selected_bg = selected_bg
        self.selected_fg = selected_fg
        self.hover_bg = hover_bg
        self._selected = False
        self._hover = False
        # Size from text metrics
        probe = tk.Label(parent, text=text, font=font)
        probe.update_idletasks()
        tw, th = probe.winfo_reqwidth(), probe.winfo_reqheight()
        probe.destroy()
        w, h = tw + padx * 2, th + pady * 2
        if bg is None:
            bg = kw.pop('canvas_bg', None)
        if bg is None:
            try:
                bg = parent.cget('bg')
            except tk.TclError:
                # ttk containers have no -bg; fall back to theme background
                try:
                    from tkinter import ttk as _ttk
                    bg = _ttk.Style().lookup('TFrame', 'background') or '#111826'
                except Exception:
                    bg = '#111826'
        canvas_bg = bg
        super().__init__(parent, width=w, height=h, bg=canvas_bg,
                         highlightthickness=0, bd=0, cursor='hand2', **kw)
        self._pw, self._ph = w, h
        self._draw()
        self.bind('<Button-1>', self._on_click)
        self.bind('<Enter>', lambda e: self._set_hover(True))
        self.bind('<Leave>', lambda e: self._set_hover(False))

    def _draw(self):
        self.delete('all')
        w, h = self._pw, self._ph
        r = h / 2
        if self._selected:
            fill, fg = self.selected_bg, self.selected_fg
        elif self._hover:
            fill, fg = self.hover_bg, 'white'
        else:
            fill, fg = '#1c2436', self.fg
        # Pill = two end caps + middle bar
        self.create_oval(1, 1, 2 * r - 1, h - 1, fill=fill, outline=fill)
        self.create_oval(w - 2 * r + 1, 1, w - 1, h - 1, fill=fill, outline=fill)
        self.create_rectangle(r, 1, w - r, h - 1, fill=fill, outline=fill)
        self.create_text(w / 2, h / 2, text=self.text, font=self.font, fill=fg)

    def _on_click(self, _event):
        if self.command:
            self.command()

    def _set_hover(self, on):
        self._hover = on
        self._draw()

    def set_selected(self, selected):
        self._selected = bool(selected)
        self._draw()
