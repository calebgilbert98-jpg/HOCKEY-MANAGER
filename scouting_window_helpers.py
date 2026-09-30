# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Shared real-system helpers for the scouting windows.

Wires ModernScoutingView (modern_scouting_window.py) and
ProfessionalScoutingView (professional_scouting_window.py) to the REAL
scouting machinery instead of the fabricated stubs they shipped with:

- app.scouting_assignments  (the {Player: Staff} dict the engine processes
  daily in main.process_scouting_assignments)
- user_team.scouting_reports (real ScoutingReport objects built up by
  report.update_report)
- ShortlistManager           (the real shortlist store; "Trade Targets" is
  the canonical category the trade market also reads)
- scouting.report_summary / report_potential_display (fog-of-war-safe
  report rendering -- graded information only, never raw attributes)

Eastside grammar: everything here is non-modal. No grab_set, no
transient-modal dialogs. Dismissing a dialog defers the action -- it never
answers it.

Additive only: no shipped logic is overridden; these are new thin entry
points over existing systems.
"""

from __future__ import annotations

import math
import tkinter as tk
from tkinter import ttk

from popup_system import messagebox, InGamePopup

# Cap mirrors the standing-assignment cap used by the war-room quick scout
# and ScoutingView._assign_scout_to_prospect.
_MAX_ACTIVE_ASSIGNMENTS = 30


# ----------------------------------------------------------------------
# Live-state accessors
# ----------------------------------------------------------------------

def _session_store(app):
    """app.pending_sessions dict, created if missing. Never raises."""
    try:
        store = getattr(app, "pending_sessions", None)
    except Exception:
        store = None
    if not isinstance(store, dict):
        try:
            app.pending_sessions = store = {}
        except Exception:
            return {}
    return store


def _get_session(app, session_id, seed):
    """Get-or-create a serializable Tier-B session. Never raises."""
    store = _session_store(app)
    sess = store.get(session_id)
    if not isinstance(sess, dict):
        sess = dict(seed or {})
        sess["id"] = session_id
        store[session_id] = sess
    return sess


def _write_session(app, session_id, **fields):
    """Write-through: every meaningful interaction updates the session
    immediately so navigation can never lose half-built input."""
    try:
        sess = _get_session(app, session_id, {})
        if isinstance(sess, dict):
            sess.update(fields)
    except Exception:
        pass


def _all_scoutable_players(app):
    """All real players searchable as scouting targets (league rosters +
    prospects + free agents). Never raises."""
    out, seen = [], set()
    try:
        lg = league_of(app)
        teams = getattr(lg, "teams", None) or []
        for team in teams:
            for attr in ("roster", "ahl_roster", "prospects"):
                for p in (getattr(team, attr, None) or []):
                    pid = getattr(p, "id", None)
                    if pid not in seen:
                        seen.add(pid)
                        out.append(p)
        gm = getattr(app, "game_manager", None)
        for p in (getattr(gm, "free_agents", None) or []):
            pid = getattr(p, "id", None)
            if pid not in seen:
                seen.add(pid)
                out.append(p)
    except Exception:
        pass
    return out


def _find_player_by_id(app, pid):
    """Resolve a session-stored player id back to the live player object
    (honest None when the world moved). Never raises."""
    try:
        want = str(pid or "")
        if not want:
            return None
        for p in _all_scoutable_players(app):
            if str(getattr(p, "id", "")) == want:
                return p
    except Exception:
        pass
    return None


def _find_scout_by_id(app, sid):
    """Resolve a session-stored scout id. Never raises."""
    try:
        want = str(sid or "")
        if not want:
            return None
        for s in scouts_of(app):
            if str(getattr(s, "id", "")) == want:
                return s
    except Exception:
        pass
    return None


def user_team_of(app):
    """The user's team, via app or game_manager fallback. Never raises."""
    try:
        ut = getattr(app, "user_team", None)
        if ut is not None:
            return ut
    except Exception:
        pass
    try:
        gm = getattr(app, "game_manager", None)
        return getattr(gm, "user_team", None) if gm else None
    except Exception:
        return None


def league_of(app):
    """The league, via app or game_manager fallback. Never raises."""
    try:
        lg = getattr(app, "league", None)
        if lg is not None:
            return lg
    except Exception:
        pass
    try:
        gm = getattr(app, "game_manager", None)
        return getattr(gm, "league", None) if gm else None
    except Exception:
        return None


def scouts_of(app):
    """Real scouting staff on the user's team. Never raises."""
    try:
        from scouting import is_scout as _is_scout
    except Exception:
        _is_scout = None
    team = user_team_of(app)
    staff = getattr(team, "staff", []) or []
    out = []
    for s in staff:
        try:
            if _is_scout is not None and _is_scout(s):
                out.append(s)
                continue
            # Fallback mirrors the windows' duck-typing: scout-ish role or
            # scouting attributes.
            role_str = str(getattr(s, "role", "")).lower()
            if any(k in role_str for k in ("scout", "evaluate", "assess")):
                out.append(s)
            elif any(hasattr(s, a) for a in
                     ("judging_player_ability", "judging_player_potential",
                      "scouting_network")):
                out.append(s)
        except Exception:
            continue
    return out


def assignments_of(app):
    """The real scouting_assignments dict, created if missing. Never raises."""
    try:
        assigns = getattr(app, "scouting_assignments", None)
        if assigns is None:
            assigns = {}
            app.scouting_assignments = assigns
        return assigns
    except Exception:
        return {}


def shortlist_manager_of(app):
    """The real ShortlistManager (app's, or a fresh persisted one)."""
    try:
        mgr = getattr(app, "shortlist_manager", None)
        if mgr is not None:
            return mgr
    except Exception:
        pass
    try:
        from shortlist_system import ShortlistManager
        return ShortlistManager()
    except Exception:
        return None


def reports_of(app):
    """The real user-team scouting reports dict. Never raises."""
    try:
        team = user_team_of(app)
        return getattr(team, "scouting_reports", None) or {}
    except Exception:
        return {}


# ----------------------------------------------------------------------
# Real assignment create / cancel
# ----------------------------------------------------------------------

def create_scout_assignment(app, player, scout):
    """Write a REAL scouting assignment into app.scouting_assignments.

    Returns (ok: bool, message: str). Honors the standing 30-assignment cap
    and refuses duplicates, like the war-room quick scout and ScoutingView.
    The engine's process_scouting_assignments picks it up daily.
    """
    if player is None:
        return False, "No player selected."
    if scout is None:
        return False, "No scout selected."
    try:
        assigns = assignments_of(app)
        if player in assigns:
            other = assigns[player]
            return False, (
                f"{getattr(player, 'full_name', 'That player')} is already "
                f"being scouted by {getattr(other, 'full_name', 'a scout')}.")
        if len(assigns) >= _MAX_ACTIVE_ASSIGNMENTS:
            return False, (
                f"You have {_MAX_ACTIVE_ASSIGNMENTS} active assignments "
                "already. Cancel one to free up a scout.")
        assigns[player] = scout
        days = estimate_completion_days(app, player, scout)
        pace = f" (~{days} days at this scout's pace)" if days else ""
        return True, (
            f"{getattr(scout, 'full_name', 'Scout')} will scout "
            f"{getattr(player, 'full_name', 'the player')}{pace}.\n"
            "The report builds up day by day in the Reports tab.")
    except Exception as e:
        return False, f"Could not create the assignment: {e}"


def cancel_scout_assignment(app, player):
    """Remove a REAL scouting assignment. Returns (ok: bool, message: str)."""
    if player is None:
        return False, "No assignment selected."
    try:
        assigns = assignments_of(app)
        if player not in assigns:
            return False, "That assignment is no longer active."
        scout = assigns.pop(player)
        return True, (
            f"Assignment cancelled: {getattr(scout, 'full_name', 'Scout')} "
            f"is no longer scouting {getattr(player, 'full_name', 'the player')}.")
    except Exception as e:
        return False, f"Could not cancel the assignment: {e}"


def estimate_completion_days(app, player, scout):
    """Real estimated days until the report reaches 'A' accuracy.

    Derived from live state using the engine's own constants from
    main.process_scouting_assignments (0.25 * efficiency viewing chance per
    day) and ScoutingReport.update_report (accuracy thresholds with the
    scout-skill viewing bonus). Returns an int, 0 if already complete, or
    None when it cannot be estimated.
    """
    try:
        jpa = float(getattr(scout, "judging_player_ability", 10) or 10)
        jpp = float(getattr(scout, "judging_player_potential", 10) or 10)
        efficiency = (jpa + jpp) / 40.0
        viewing_chance = 0.25 * efficiency
        if viewing_chance <= 0:
            return None
        skill_bonus = int((jpa + jpp) // 10)
        viewings = 0
        reports = reports_of(app)
        report = reports.get(getattr(player, "id", None))
        if report is not None:
            viewings = int(getattr(report, "viewings", 0) or 0)
            if getattr(report, "accuracy", "") == "A":
                return 0
        # Engine completes the assignment at effective viewings >= 20.
        need = 20 - skill_bonus - viewings
        if need <= 0:
            return 0
        return max(1, math.ceil(need / viewing_chance))
    except Exception:
        return None


# ----------------------------------------------------------------------
# Add-to-shortlist screen (was: non-modal InGamePopup)
# ----------------------------------------------------------------------

class ShortlistAddView(tk.Frame):
    """Full-screen "Add to Shortlist" form.

    Gating Phase 2: the dialog becomes a Tier-1 screen (screen id
    "shortlist_add"). Same categories/priorities, same real
    ShortlistManager write. Category/priority/notes write through to
    app.pending_sessions on every change, so half-typed notes survive
    navigation. Dismissing defers (adds nothing).
    """

    def __init__(self, parent, player=None,
                 default_category="Trade Targets", app=None):
        tk.Frame.__init__(self, parent, bg="#1E1E1E")
        self.app = app
        self.player = player
        self._default_category = default_category
        self._close_screen = None  # set by show_screen()
        self._build()

    def close_view(self):
        fn = getattr(self, "_close_screen", None)
        if callable(fn):
            fn()
        else:
            self.destroy()

    def _session_id(self):
        try:
            pid = str(getattr(self.player, "id", "") or "")
        except Exception:
            pid = ""
        return "shortlist_add:%s" % (pid or "unknown")

    def _build(self):
        try:
            from shortlist_system import ShortlistManager
        except Exception:
            messagebox.showerror("Shortlist", "Shortlist system unavailable.")
            return
        mgr = shortlist_manager_of(self.app)
        player = self.player
        if mgr is None or player is None:
            messagebox.showerror("Shortlist", "Shortlist manager not available.")
            return

        pri_labels = list(ShortlistManager.PRIORITY_LEVELS.values())
        app = self.app
        sid = self._session_id()
        sess = _get_session(app, sid, {
            "kind": "shortlist_add",
            "player_id": str(getattr(player, "id", "") or ""),
            "player_name": str(getattr(player, "full_name", "?") or "?"),
            "category": (self._default_category
                         if self._default_category in ShortlistManager.CATEGORIES
                         else ShortlistManager.CATEGORIES[0]),
            "priority": ShortlistManager.PRIORITY_LEVELS.get(2, pri_labels[0] if pri_labels else ""),
            "notes": "",
        })

        bg = "#1E1E1E"
        wrap = tk.Frame(self, bg=bg)
        wrap.pack(fill="both", expand=True)
        inner = tk.Frame(wrap, bg=bg, width=440)
        inner.pack(pady=14)

        tk.Label(inner,
                 text=f"Add {getattr(player, 'full_name', '?')} to Shortlist",
                 font=("Segoe UI", 13, "bold"),
                 fg="white", bg=bg).pack(pady=(14, 6))

        cat_frame = tk.LabelFrame(inner, text="Category", fg="white", bg=bg)
        cat_frame.pack(fill="x", padx=20, pady=8)
        category_var = tk.StringVar(value=str(sess.get("category") or ""))
        category_combo = ttk.Combobox(cat_frame, textvariable=category_var,
                                      values=ShortlistManager.CATEGORIES,
                                      state="readonly")
        category_combo.pack(fill="x", padx=10, pady=8)
        category_combo.bind(
            "<<ComboboxSelected>>",
            lambda _e: _write_session(app, sid, category=category_var.get()))

        pri_frame = tk.LabelFrame(inner, text="Priority", fg="white", bg=bg)
        pri_frame.pack(fill="x", padx=20, pady=8)
        priority_var = tk.StringVar(value=str(sess.get("priority") or ""))
        priority_combo = ttk.Combobox(pri_frame, textvariable=priority_var,
                                      values=list(ShortlistManager.PRIORITY_LEVELS.values()),
                                      state="readonly")
        priority_combo.pack(fill="x", padx=10, pady=8)
        priority_combo.bind(
            "<<ComboboxSelected>>",
            lambda _e: _write_session(app, sid, priority=priority_var.get()))

        notes_frame = tk.LabelFrame(inner, text="Notes", fg="white", bg=bg)
        notes_frame.pack(fill="both", expand=True, padx=20, pady=8)
        notes_text = tk.Text(notes_frame, height=4, wrap="word",
                             bg="#2A2A2A", fg="white")
        notes_text.pack(fill="both", expand=True, padx=10, pady=8)
        _saved_notes = str(sess.get("notes") or "")
        if _saved_notes:
            notes_text.insert("1.0", _saved_notes)

        def _on_notes_key(_e=None):
            _write_session(app, sid,
                           notes=notes_text.get("1.0", "end-1c"))

        notes_text.bind("<KeyRelease>", _on_notes_key)

        btn_frame = tk.Frame(inner, bg=bg)
        btn_frame.pack(fill="x", padx=20, pady=(4, 14))

        def _add():
            category = category_var.get()
            priority = next((k for k, v in ShortlistManager.PRIORITY_LEVELS.items()
                             if v == priority_var.get()), 2)
            notes = notes_text.get("1.0", "end-1c")
            pid = str(getattr(player, "id", "") or "")
            ok = mgr.add_player(pid, getattr(player, "full_name", "?"),
                                category, notes=notes, priority=priority)
            if ok:
                try:
                    _session_store(app).pop(sid, None)
                except Exception:
                    pass
                messagebox.showinfo("Added to Shortlist",
                                    f"{getattr(player, 'full_name', '?')} added to {category}.")
                self.close_view()
            else:
                messagebox.showwarning("Already on Shortlist",
                                       f"{getattr(player, 'full_name', '?')} is already in {category}.")

        ttk.Button(btn_frame, text="Add to Shortlist",
                   command=_add).pack(side="left")
        ttk.Button(btn_frame, text="Cancel",
                   command=self.close_view).pack(side="right")


def open_shortlist_dialog(parent, app, player, default_category="Trade Targets"):
    """Add-to-shortlist entry point (kept name; now a screen jump).

    Gating Phase 2: routes to ShortlistAddView (screen id
    "shortlist_add"). Same validation as before. Never raises.
    """
    try:
        from shortlist_system import ShortlistManager
    except Exception:
        messagebox.showerror("Shortlist", "Shortlist system unavailable.")
        return
    mgr = shortlist_manager_of(app)
    if mgr is None or player is None:
        messagebox.showerror("Shortlist", "Shortlist manager not available.")
        return
    show = getattr(app, "show_screen", None)
    if not callable(show):
        messagebox.showwarning(
            "Shortlist", "Adding to the shortlist needs the app screen host.")
        return
    show("shortlist_add",
         f"Add to Shortlist — {getattr(player, 'full_name', '?')}",
         ShortlistAddView, player, fresh=True,
         default_category=default_category)


# ----------------------------------------------------------------------
# Real report rendering (fog-of-war safe)
# ----------------------------------------------------------------------

def report_display_lines(player, report):
    """Fog-of-war-safe report lines from the real report machinery.

    Uses scouting.report_summary / report_potential_display: graded
    information only, never raw attributes. Returns a list of (label, text)
    rows plus the graded potential string. Never raises.
    """
    rows = []
    try:
        from scouting import report_summary, report_potential_display
    except Exception:
        return rows, "?"
    if report is None:
        return rows, "?"
    try:
        pot = report_potential_display(report, player)
    except Exception:
        pot = "?"
    try:
        info = report_summary(report)
    except Exception:
        return rows, pot
    if not info:
        return rows, pot
    rows.append(("Accuracy", f"{info.get('accuracy', '?')}"))
    rows.append(("Viewings", f"{info.get('viewings', '0')}"))
    rows.append(("Scout", f"{info.get('scout', '—')}"))
    rows.append(("Region", f"{info.get('region', '—')}"))
    strengths = info.get("strengths") or []
    weaknesses = info.get("weaknesses") or []
    rows.append(("Strengths",
                 "\n".join(f"• {s}" for s in strengths) if strengths else "—"))
    rows.append(("Weaknesses",
                 "\n".join(f"• {w}" for w in weaknesses) if weaknesses else "—"))
    if info.get("comparable") and info["comparable"] != "—":
        rows.append(("Comparable", info["comparable"]))
    if info.get("projection") and info["projection"] != "—":
        rows.append(("Projection", info["projection"]))
    if info.get("notes"):
        rows.append(("Notes", info["notes"][:300]))
    return rows, pot


def show_prospect_report(parent, app, player):
    """Open the REAL prospect report (draft war-room report machinery).

    Renders the filed ScoutingReport through the fog-of-war display; when no
    report exists yet, shows the public consensus range and honest guidance
    to assign a scout. Non-modal. Never raises.
    """
    if player is None:
        return
    try:
        from scouting import consensus_range
    except Exception:
        consensus_range = None
    reports = reports_of(app)
    report = reports.get(getattr(player, "id", None))
    rows, pot = report_display_lines(player, report)

    win = InGamePopup(parent)
    win.title(f"Scout Report — {getattr(player, 'full_name', '?')}")
    win.geometry("560x520")
    win.configure(bg=getattr(parent, "BG_COLOR", "#1E1E1E"))
    # Eastside grammar: non-modal. No grab_set.

    try:
        pos = player.primary_position.value
    except Exception:
        pos = str(getattr(player, "primary_position", "?"))
    head = (f"{getattr(player, 'full_name', '?')}  ·  {pos}  ·  "
            f"Age {getattr(player, 'age', '?')}  ·  "
            f"{getattr(player, 'nationality', '?')}")
    tk.Label(win, text=head,
             font=(getattr(parent, "FONT_FAMILY", "Segoe UI"), 12, "bold"),
             fg=getattr(parent, "HEADER_COLOR", "white"),
             bg=getattr(parent, "BG_COLOR", "#1E1E1E"),
             wraplength=520, justify="left").pack(anchor="w", padx=16, pady=(14, 4))

    if report is not None:
        tk.Label(win, text=f"Potential: {pot}",
                 font=(getattr(parent, "FONT_FAMILY", "Segoe UI"), 11, "bold"),
                 fg=getattr(parent, "ACCENT_COLOR", "#7fd4ff"),
                 bg=getattr(parent, "BG_COLOR", "#1E1E1E")).pack(anchor="w", padx=16)
    else:
        crange = consensus_range(player) if consensus_range else "?"
        tk.Label(win, text=f"Potential: {crange}  (public consensus — scout for certainty)",
                 font=(getattr(parent, "FONT_FAMILY", "Segoe UI"), 10),
                 fg=getattr(parent, "TEXT_COLOR", "white"),
                 bg=getattr(parent, "BG_COLOR", "#1E1E1E"),
                 wraplength=520, justify="left").pack(anchor="w", padx=16)

    body = tk.Text(win, wrap="word", height=18,
                   bg=getattr(parent, "CONTENT_BG", "#2A2A2A"),
                   fg=getattr(parent, "TEXT_COLOR", "white"))
    body.pack(fill="both", expand=True, padx=16, pady=10)
    if report is not None and rows:
        for label, text in rows:
            body.insert("end", f"{label.upper()}\n", "hdr")
            body.insert("end", f"{text}\n\n")
        body.tag_config("hdr", font=(getattr(parent, "FONT_FAMILY", "Segoe UI"), 10, "bold"))
    else:
        assigns = assignments_of(app)
        if player in assigns:
            scout = assigns[player]
            body.insert("end",
                        f"No report filed yet — {getattr(scout, 'full_name', 'a scout')} "
                        "is watching this player.\n\nCheck back in the Reports tab; "
                        "the report builds up day by day.")
        else:
            body.insert("end",
                        "No report filed yet.\n\nAssign a scout (Scout Player) to start "
                        "building a real evaluation. Until then all you have is the "
                        "public consensus range above.")
    body.configure(state="disabled")

    btn_row = tk.Frame(win, bg=getattr(parent, "BG_COLOR", "#1E1E1E"))
    btn_row.pack(fill="x", padx=16, pady=(0, 14))
    if report is None and player not in assignments_of(app):
        def _assign_and_close():
            scouts = scouts_of(app)
            if not scouts:
                messagebox.showwarning("No Scouts",
                                       "Hire scouts in the Staff Management section first.")
                return
            ok, msg = create_scout_assignment(app, player, scouts[0])
            (messagebox.showinfo if ok else messagebox.showwarning)(
                "Scout Assignment", msg)
            if ok:
                win.destroy()
        ttk.Button(btn_row, text="Assign Scout",
                   command=_assign_and_close).pack(side="left")
    ttk.Button(btn_row, text="Close", command=win.destroy).pack(side="right")


# ----------------------------------------------------------------------
# New-scouting-assignment screen (was: non-modal InGamePopup)
# ----------------------------------------------------------------------

class ScoutingAssignmentView(tk.Frame):
    """Full-screen "New Scouting Assignment" builder.

    Gating Phase 2: the dialog becomes a Tier-1 screen (screen id
    "scouting_assignment"). Same scout picker, same searchable target
    list, same real estimated completion, same
    create_scout_assignment() write. Scout pick / search text / target
    write through to app.pending_sessions on every interaction, so
    navigating away never loses a half-built assignment. Dismissing
    defers (creates nothing).
    """

    def __init__(self, parent, player=None, preselected_scout=None,
                 request_type="Player Scouting", request_priority="Normal",
                 on_created=None, app=None):
        tk.Frame.__init__(self, parent, bg="#1E1E1E")
        self.app = app
        self._player_arg = player
        self._preselected_scout = preselected_scout
        self._on_created = on_created
        self._close_screen = None  # set by show_screen()
        self._scouts = list(scouts_of(app))
        # Entry-point params are deterministic pane defaults: they seed
        # the session on open; user input writes through afterwards.
        # Seed the full key set on first creation only (_get_session
        # applies the seed solely for a new session, so resumes keep
        # their values instead of being clobbered by defaults).
        sid = self._session_id(player)
        _get_session(app, sid, {
            "kind": "scouting_assignment",
            "scout_id": "",
            "search_text": "",
            "target_player_id": (str(getattr(player, "id", "") or "")
                                 if player is not None else ""),
            "request_type": request_type,
            "request_priority": request_priority,
        })
        self._request_type = request_type
        self._request_priority = request_priority
        self._build()

    def close_view(self):
        fn = getattr(self, "_close_screen", None)
        if callable(fn):
            fn()
        else:
            self.destroy()

    @staticmethod
    def _session_id(player):
        try:
            pid = str(getattr(player, "id", "") or "")
        except Exception:
            pid = ""
        return "scouting_assignment:%s" % (pid or "new")

    def _build(self):
        app = self.app
        scouts = self._scouts
        player = self._player_arg
        sid = self._session_id(player)
        sess = _get_session(app, sid, {
            "kind": "scouting_assignment",
            "scout_id": "",
            "search_text": "",
            "target_player_id": (str(getattr(player, "id", "") or "")
                                 if player is not None else ""),
            "request_type": self._request_type,
            "request_priority": self._request_priority,
        })

        bg = "#1E1E1E"
        wrap = tk.Frame(self, bg=bg)
        wrap.pack(fill="both", expand=True)
        inner = tk.Frame(wrap, bg=bg, width=560)
        inner.pack(pady=10)

        tk.Label(inner, text="New Scouting Assignment",
                 font=("Segoe UI", 13, "bold"),
                 fg="white", bg=bg).pack(pady=(14, 4))
        tk.Label(inner,
                 text=f"{self._request_type} · {self._request_priority} priority",
                 font=("Segoe UI", 9), fg="white", bg=bg).pack(pady=(0, 8))

        tk.Label(inner, text="Scout:", fg="white", bg=bg).pack(
            anchor="w", padx=20)
        scout_var = tk.StringVar()
        scout_combo = ttk.Combobox(
            inner, textvariable=scout_var, state="readonly",
            values=[f"{getattr(s, 'full_name', '?')} "
                    f"(JPA {getattr(s, 'judging_player_ability', '?')}/"
                    f"JPP {getattr(s, 'judging_player_potential', '?')})"
                    for s in scouts])
        scout_combo.pack(fill="x", padx=20, pady=(2, 10))
        # Restore the scout pick: session first, then the entry-point
        # preselection, then the first scout.
        default_idx = 0
        _sess_scout = _find_scout_by_id(app, sess.get("scout_id"))
        if _sess_scout is not None and _sess_scout in scouts:
            default_idx = scouts.index(_sess_scout)
        else:
            try:
                if self._preselected_scout in scouts:
                    default_idx = scouts.index(self._preselected_scout)
            except Exception:
                default_idx = 0
        scout_combo.current(default_idx)

        def _on_scout_pick(_e=None):
            try:
                idx = scout_combo.current()
                s = scouts[idx] if 0 <= idx < len(scouts) else None
                _write_session(app, sid,
                               scout_id=str(getattr(s, "id", "") or ""))
            except Exception:
                pass
            _update_pace()

        scout_combo.bind("<<ComboboxSelected>>", _on_scout_pick)

        chosen = {"player": player}
        tk.Label(inner, text="Target player:", fg="white", bg=bg).pack(
            anchor="w", padx=20)
        target_label = tk.Label(inner, text="",
                                fg="#7fd4ff", bg=bg,
                                font=("Segoe UI", 10, "bold"))
        target_label.pack(anchor="w", padx=20, pady=(2, 6))

        search_var = tk.StringVar()
        if player is None:
            tk.Label(inner, text="Search players:", fg="white",
                     bg=bg).pack(anchor="w", padx=20)
            search_entry = ttk.Entry(inner, textvariable=search_var, width=40)
            search_entry.pack(fill="x", padx=20, pady=(2, 4))
            results = tk.Listbox(inner, height=8)
            results.pack(fill="both", expand=True, padx=20, pady=(0, 6))

            _cache = {"players": None, "shown": []}

            def _refresh_results(*_):
                if _cache["players"] is None:
                    _cache["players"] = _all_scoutable_players(app)
                q = search_var.get().lower().strip()
                results.delete(0, tk.END)
                _cache["shown"] = []
                for p in _cache["players"]:
                    name = str(getattr(p, "full_name", "") or "")
                    if q and q not in name.lower():
                        continue
                    if len(_cache["shown"]) >= 200:
                        break
                    _cache["shown"].append(p)
                    results.insert(tk.END, name)

            def _pick(_evt=None):
                sel = results.curselection()
                if not sel:
                    return
                shown = _cache.get("shown") or []
                p = shown[sel[0]] if sel[0] < len(shown) else None
                if p is not None:
                    chosen["player"] = p
                    target_label.config(
                        text=getattr(p, "full_name", "?"))
                    _write_session(
                        app, sid,
                        target_player_id=str(getattr(p, "id", "") or ""))
                    _update_pace()

            def _on_search_key(*_):
                _write_session(app, sid, search_text=search_var.get())
                _refresh_results()

            search_var.trace_add("write", _on_search_key)
            results.bind("<<ListboxSelect>>", _pick)
            # Restore a half-built search + target from the session.
            _saved_search = str(sess.get("search_text") or "")
            if _saved_search:
                search_var.set(_saved_search)
            else:
                _refresh_results()
            _saved_target = _find_player_by_id(app, sess.get("target_player_id"))
            if _saved_target is not None:
                chosen["player"] = _saved_target
                target_label.config(
                    text=getattr(_saved_target, "full_name", "?"))

        def _set_target():
            p = chosen["player"]
            target_label.config(
                text=getattr(p, "full_name", "Select a target player above")
                if p else "Select a target player above")

        pace_label = tk.Label(inner, text="", fg="white", bg=bg,
                              font=("Segoe UI", 9),
                              wraplength=500, justify="left")
        pace_label.pack(anchor="w", padx=20, pady=(4, 6))

        def _update_pace(*_):
            try:
                scout = scouts[scout_combo.current()]
            except Exception:
                scout = None
            p = chosen["player"]
            if scout is None or p is None:
                pace_label.config(text="")
                return
            days = estimate_completion_days(app, p, scout)
            if days == 0:
                pace_label.config(
                    text="This player already has a complete report.")
            elif days is None:
                pace_label.config(text="Estimated completion: unknown.")
            else:
                pace_label.config(
                    text=f"Estimated completion: ~{days} days at "
                         f"{getattr(scout, 'full_name', 'this scout')}'s pace "
                         "(report reaches 'A' accuracy, then the assignment closes).")

        _set_target()
        _update_pace()

        btn_row = tk.Frame(inner, bg=bg)
        btn_row.pack(fill="x", padx=20, pady=(8, 16))

        def _create():
            try:
                scout = scouts[scout_combo.current()]
            except Exception:
                messagebox.showwarning("No Scout", "Please select a scout.")
                return
            p = chosen["player"]
            if p is None:
                messagebox.showwarning("No Player",
                                       "Please select a target player.")
                return
            ok, msg = create_scout_assignment(app, p, scout)
            (messagebox.showinfo if ok else messagebox.showwarning)(
                "Scouting Assignment", msg)
            if ok:
                try:
                    _session_store(app).pop(sid, None)
                except Exception:
                    pass
                try:
                    if callable(self._on_created):
                        self._on_created()
                except Exception:
                    pass
                self.close_view()

        ttk.Button(btn_row, text="Create Assignment",
                   command=_create).pack(side="left")
        ttk.Button(btn_row, text="Cancel",
                   command=self.close_view).pack(side="right")


def open_assignment_dialog(parent, app, player=None, preselected_scout=None,
                           request_type="Player Scouting",
                           request_priority="Normal", on_created=None):
    """New-scouting-assignment entry point (kept name; now a screen jump).

    Gating Phase 2: routes to ScoutingAssignmentView (screen id
    "scouting_assignment"). Same no-scouts guard as before. Never raises.
    """
    scouts = scouts_of(app)
    if not scouts:
        messagebox.showwarning(
            "No Scouts",
            "You need scouts before you can create assignments.\n\n"
            "Hire scouts via Staff → Hire Staff (free-agent staff market).")
        return
    show = getattr(app, "show_screen", None)
    if not callable(show):
        messagebox.showwarning(
            "Scouting",
            "Creating scouting assignments needs the app screen host.")
        return
    show("scouting_assignment", "New Scouting Assignment",
         ScoutingAssignmentView, fresh=True, player=player,
         preselected_scout=preselected_scout, request_type=request_type,
         request_priority=request_priority, on_created=on_created)


