# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Multiplayer action routing (tkinter-free engine module).

Extracted verbatim from ``windows._mp_is_client`` / ``windows._mp_route``
(R18 bundle hygiene): the PyInstaller bundle hard-excludes tkinter, so
engine code (e.g. ``game_manager``) can no longer route MP actions through
the Tk-only ``windows`` module -- importing it there raises ImportError
and multiplayer routes silently no-op in the bundle.

This module has no UI imports at module level. The two spectator/send-
failure messagebox calls resolve ``popup_system.messagebox`` lazily via
``importlib`` *inside* the already-present ``try/except`` guards -- never
via a static ``import`` statement. That is deliberate: PyInstaller's
static analysis follows every static import (including function-level
ones) and would pull tkinter back into the bundle graph; a string-based
``importlib.import_module`` is invisible to it. Behavior is identical in
every environment:

- dev/legacy Tk: ``popup_system`` imports fine, the dialogs show exactly
  as before;
- bundle/headless: ``popup_system`` is absent, the ImportError is caught
  by the surrounding guards, the call fail-softs exactly as today.

The differential contract is covered by the R18 closure test
(``tests/test_r18_bundle_hygiene.py``): this module must never grow a
static reference to ``tkinter``/``customtkinter``/``popup_system``.
"""


def _mp_is_client(app):
    """True when this app instance is an MP client (not host, not SP)."""
    try:
        return getattr(app, "mp_client", None) is not None
    except Exception:
        return False


def _messagebox():
    """Tk messagebox shim, resolved lazily (see module docstring)."""
    import importlib
    return importlib.import_module("popup_system").messagebox


def _mp_route(app, action, params, on_sent=None):
    """Route a management action to the host in MP client mode.

    Returns True when routed -- the caller must NOT mutate local state.
    The host validates, applies to the canonical state, and the next
    STATE_SYNC refreshes the UI (the action_ack/action_rejected toast
    confirms the outcome). Returns False on the host / in single-player,
    where the caller keeps its normal local behavior.

    If the send itself fails, the action is CONSUMED (True): the caller
    must not fall through to its local branch, which would mutate a
    snapshot the next sync wipes. The user gets an honest error instead,
    and on_sent is NOT called -- success UX must live in on_sent, never
    after this call, or a failed send would show a false confirmation.
    """
    try:
        client = getattr(app, "mp_client", None)
        if client is None:
            return False
        if getattr(app, "_mp_spectator", False):
            try:
                _messagebox().showinfo(
                    "Spectating",
                    "You're watching as a spectator -- claim a team to "
                    "manage.")
            except Exception:
                pass
            return True
        p = dict(params or {})
        team = getattr(app, "user_team", None)
        p.setdefault("team_id",
                     getattr(team, "team_name", "") if team else "")
        try:
            client.send_action(action, p)
        except Exception as e:
            try:
                _messagebox().showerror(
                    "Not Sent",
                    f"Couldn't reach the host ({e}). Nothing changed -- "
                    f"try again.")
            except Exception:
                pass
            return True
        if on_sent is not None:
            try:
                on_sent()
            except Exception:
                pass
        return True
    except Exception:
        return False
