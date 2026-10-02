#!/usr/bin/env python3
# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Central mouse-wheel routing for scrollable canvases.

Root cause of the "wheel doesn't scroll the screen in front of you" bug:
every scrollable canvas called ``canvas.bind_all("<MouseWheel>", handler)``.
``bind_all`` registers at the *application* level, so the last canvas created
silently replaced all previous bindings -- the wheel always scrolled the
most-recently-created screen, not the one under the cursor.

This module replaces that pattern with a single global handler that routes
the wheel event to the scrollable canvas under the mouse pointer:

    from scroll_manager import register_scrollable
    register_scrollable(canvas)   # explicit registration (optional)

The global handler is installed once (idempotent) and covers:
  - Windows/macOS: <MouseWheel> (event.delta)
  - Linux: <Button-4> (up) / <Button-5> (down)
  - Shift+wheel: horizontal scroll where the canvas supports it

Auto-detection: canvases with a scrollbar attached (yscrollcommand or
xscrollcommand configured) are detected automatically -- explicit
registration is optional but recommended for clarity.

All handlers are try/except guarded and never raise.
"""

import weakref

_registry = weakref.WeakSet()
_installed_roots = weakref.WeakSet()
_last_active = None


def register_scrollable(canvas):
    """Register a scrollable canvas for global wheel routing.

    Safe to call multiple times on the same canvas. The canvas is held
    weakly, so destroying it auto-unregisters (no leaks).
    """
    try:
        _registry.add(canvas)
    except Exception:
        pass


def unregister_scrollable(canvas):
    """Remove a canvas from wheel routing (optional; weak refs handle it)."""
    try:
        _registry.discard(canvas)
    except Exception:
        pass


def _is_scrollable_canvas(w):
    """Check if widget is a Canvas with a scrollbar attached (yscrollcommand
    or xscrollcommand configured). Auto-detects scrollable canvases that
    were never explicitly registered. Never raises."""
    try:
        # Must be a Canvas (or subclass)
        try:
            cls = w.winfo_class()
        except Exception:
            return False
        if cls != "Canvas":
            return False
        # Must have a scrollbar attached via yscrollcommand/xscrollcommand
        try:
            yscroll = w.cget("yscrollcommand")
            if yscroll:
                return True
        except Exception:
            pass
        try:
            xscroll = w.cget("xscrollcommand")
            if xscroll:
                return True
        except Exception:
            pass
    except Exception:
        pass
    return False


def _find_scrollable(widget, root):
    """Walk up from widget to find the nearest scrollable canvas.

    Checks the explicit registry first, then auto-detects any Canvas with
    a scrollbar attached (yscrollcommand/xscrollcommand). This means
    scrollable canvases work even if they were never registered.
    """
    try:
        w = widget
        seen = set()
        while w is not None and w not in seen:
            seen.add(w)
            try:
                if w in _registry:
                    return w
            except Exception:
                pass
            # Auto-detect: Canvas with scrollbar attached
            try:
                if _is_scrollable_canvas(w):
                    return w
            except Exception:
                pass
            try:
                parent_name = w.winfo_parent()
                if not parent_name:
                    break
                w = root.nametowidget(parent_name)
            except Exception:
                break
    except Exception:
        pass
    return None


def _scroll_canvas(canvas, units, horizontal=False):
    """Scroll a canvas by units; never raises."""
    try:
        if horizontal:
            try:
                canvas.xview_scroll(units, "units")
                return True
            except Exception:
                return False
        canvas.yview_scroll(units, "units")
        return True
    except Exception:
        return False


def _has_own_wheel_binding(widget, root, stop_at):
    """Check if widget or any ancestor up to (not incl.) stop_at has a
    widget-level wheel binding. If so, that binding already scrolled --
    the global handler must skip to avoid double-scrolling."""
    try:
        w = widget
        seen = set()
        while w is not None and w not in seen and w != stop_at:
            seen.add(w)
            try:
                for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                    try:
                        if w.bind(seq):
                            return True
                    except Exception:
                        pass
            except Exception:
                pass
            try:
                parent_name = w.winfo_parent()
                if not parent_name:
                    break
                w = root.nametowidget(parent_name)
            except Exception:
                break
        # Also check stop_at itself (the canvas may have its own binding).
        try:
            for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                try:
                    if stop_at is not None and stop_at.bind(seq):
                        return True
                except Exception:
                    pass
        except Exception:
            pass
    except Exception:
        pass
    return False


def _on_wheel(event):
    """Global wheel handler: route to the canvas under the cursor."""
    global _last_active
    try:
        # Determine scroll direction / magnitude across platforms.
        units = 0
        horizontal = bool(getattr(event, "state", 0) & 0x1)  # Shift held
        ev_type = getattr(event, "type", None)
        ev_type_name = str(ev_type)
        if getattr(event, "num", None) == 4 or "Button-4" in ev_type_name or event.type == "4":
            units = -1
        elif getattr(event, "num", None) == 5 or "Button-5" in ev_type_name or event.type == "5":
            units = 1
        else:
            delta = getattr(event, "delta", 0) or 0
            if delta == 0:
                return
            # Windows: delta is multiples of 120. macOS: smaller deltas.
            units = int(-1 * (delta / 120)) if abs(delta) >= 120 else (-1 if delta > 0 else 1)

        if units == 0:
            return

        root = event.widget.winfo_toplevel() if hasattr(event.widget, "winfo_toplevel") else None
        target = None
        under = None
        try:
            x_root = getattr(event, "x_root", None)
            y_root = getattr(event, "y_root", None)
            if x_root is not None and y_root is not None and root is not None:
                under = root.winfo_containing(x_root, y_root)
                if under is not None:
                    target = _find_scrollable(under, root)
        except Exception:
            target = None

        # Fallback: last canvas the pointer was over (tracked via <Enter>).
        if target is None:
            target = _last_active
            try:
                if target is not None and target not in _registry:
                    target = None
            except Exception:
                target = None

        if target is not None:
            # Dedup: if the widget under the cursor (or an ancestor up to the
            # canvas) has its own widget-level wheel binding, it already
            # scrolled -- skip to avoid double-scrolling.
            try:
                if under is not None and root is not None and _has_own_wheel_binding(under, root, target):
                    return None
            except Exception:
                pass
            _scroll_canvas(target, units, horizontal=horizontal)
            return "break"  # stop further handling
    except Exception:
        pass
    return None


def _track_enter(event):
    """Remember the scrollable canvas the pointer is over (fallback routing).
    Uses auto-detection so unregistered canvases are tracked too."""
    global _last_active
    try:
        w = event.widget
        try:
            if w in _registry:
                _last_active = w
                return
        except Exception:
            pass
        # Auto-detect unregistered scrollable canvases
        try:
            if _is_scrollable_canvas(w):
                _last_active = w
        except Exception:
            pass
    except Exception:
        pass


def install_global_handler(root):
    """Install the single global wheel handler on root. Idempotent."""
    try:
        if root in _installed_roots:
            return
        _installed_roots.add(root)
        root.bind_all("<MouseWheel>", _on_wheel, add="+")
        root.bind_all("<Button-4>", _on_wheel, add="+")
        root.bind_all("<Button-5>", _on_wheel, add="+")
        # Track pointer-over-canvas for fallback routing.
        root.bind_class("Canvas", "<Enter>", _track_enter, add="+")
    except Exception:
        pass
