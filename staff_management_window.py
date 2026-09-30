# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""
Enhanced Staff Management Window for Hockey Manager
Provides comprehensive staff hiring, firing, and management with EHM-style depth.

CustomTkinter rebuild: CTkToplevel, CTkTabview tabs, pill/segmented filters,
styled dark treeview with rating-tier and morale tags, CTk dialogs.
"""

import tkinter as tk
from tkinter import ttk
from popup_system import messagebox, InGamePopup
from typing import List

import customtkinter as ctk

from game_classes import Staff, StaffRole
from game_classes import debug_print
from ctk_theme import (
    init_ctk_theme, primary_button, secondary_button, heading, body,
    TEAL, TEAL_HOVER, TEAL_DARK, BG, PANEL, CARD, BORDER,
    TEXT, TEXT_DIM, TEXT_FAINT, GOLD, GREEN, RED, BLUE,
    ROW_HOVER, ROW_SELECTED,
)


# ---------------------------------------------------------------------------
# Gating: staff negotiate-chain persist/resume (Chris's design call).
#
# negotiate_selected_staff() used to run a closure-only chain: each step
# opened a StaffContractView and the next step fired from on_done. Navigating
# away mid-chain destroyed the view without on_done, silently killing the
# rest of the chain -- no digest, remaining staff never negotiated.
#
# Now the chain is Tier-B persisted in app.pending_sessions
# ("staff_negotiate_chain", JSON-safe: staff IDs + result strings only):
#   - write-through on start and every advance (step_open tracks the
#     currently-open negotiation step),
#   - navigating away mid-step parks it: a RESUMABLE registry entry, an
#     inbox notice (priority 3 -> "!" pill), and the standard navbar resume
#     chip (via the session's dialogs["resume"] registry spec),
#   - returning to the Staff screen re-presents the resume question card
#     (dismiss = keep parked, never auto-answer),
#   - the named DIALOG_RESOLVERS entry "staff_chain_resume" makes the
#     continuation save/load-safe: IDs revalidate against the live roster,
#     stale IDs are skipped with an honest digest note, never a crash.
# ---------------------------------------------------------------------------
_CHAIN_SESSION_ID = "staff_negotiate_chain"
_CHAIN_RESUME_DIALOG = "resume"
_CHAIN_RESOLVER = "staff_chain_resume"
_CHAIN_ITEM_ID = _CHAIN_SESSION_ID + ":" + _CHAIN_RESUME_DIALOG
_CHAIN_SCREEN_ID = "staff_management"
_CHAIN_CONTRACT_SCREEN_ID = "staff_contract"

# Process-wide app handle for the named resolver (resolvers don't receive
# the app; the view sets this on every chain touchpoint). Falls back to
# tkinter's default root when unset (fresh process, chip-click path).
_CHAIN_APP = None


def _set_chain_app(app):
    global _CHAIN_APP
    try:
        if app is not None and hasattr(app, "pending_sessions"):
            _CHAIN_APP = app
    except Exception:
        pass


def _chain_app():
    app = _CHAIN_APP
    if app is not None:
        return app
    try:
        import tkinter as _tk
        _root = _tk._default_root
        if _root is not None and hasattr(_root, "pending_sessions"):
            return _root
    except Exception:
        pass
    return None


def _chain_session(app):
    """Tier-B session dict for the negotiate chain (created on demand)."""
    try:
        from popup_system import get_pending_session
        return get_pending_session(app, _CHAIN_SESSION_ID)
    except Exception:
        return None


def _write_chain_session(app, remaining_ids, results, step_open,
                         staff_names=None):
    """Write-through: persist the chain's in-progress state.

    remaining_ids: staff IDs still to negotiate (includes the open step).
    step_open: staff ID of the currently-open negotiation screen, or None
    between steps. An active step clears any stale resume dialog.
    """
    try:
        sess = _chain_session(app)
        if not isinstance(sess, dict):
            return None
        sess["kind"] = "staff_negotiate_chain"
        sess["remaining_staff_ids"] = [str(i) for i in (remaining_ids or [])]
        sess["completed_results"] = [str(r) for r in (results or [])]
        sess["total"] = int(sess.get("total") or len(remaining_ids or []) or 0)
        sess["step_open"] = (str(step_open) if step_open is not None
                             else None)
        if staff_names:
            try:
                names = dict(sess.get("staff_names") or {})
                for _k, _v in dict(staff_names).items():
                    names[str(_k)] = str(_v)
                sess["staff_names"] = names
            except Exception:
                pass
        if step_open is not None:
            # Active step: no resume question while the chain is live.
            try:
                (sess.get("dialogs") or {}).pop(_CHAIN_RESUME_DIALOG, None)
            except Exception:
                pass
        return sess
    except Exception:
        return None


def _chain_staff_view(app):
    """The StaffManagementView, opening the screen if needed."""
    try:
        view = (getattr(app, "open_windows", None) or {}).get(
            _CHAIN_SCREEN_ID)
        if view is not None:
            return view
    except Exception:
        pass
    try:
        opener = getattr(app, "open_staff_management_window", None)
        if callable(opener):
            return opener()
    except Exception:
        pass
    return None


def _clear_chain_notice(app, sess):
    """Delete the park-time inbox notice, if it still exists."""
    try:
        mid = (sess or {}).get("notice_message_id")
        if not mid:
            return
        inbox = getattr(getattr(app, "user_team", None), "inbox", None)
        deleter = getattr(inbox, "delete_message", None)
        if callable(deleter):
            deleter(mid)
        try:
            updater = getattr(app, "update_inbox_notification", None)
            if callable(updater):
                updater()
        except Exception:
            pass
        try:
            sess["notice_message_id"] = None
        except Exception:
            pass
    except Exception:
        pass


def _park_staff_negotiate_chain(app, sess):
    """Park a mid-step chain: registry entry + inbox notice + resume card.

    Called when the open negotiation screen is torn down without its
    on_done firing (the user navigated away). Idempotent: re-parking an
    already-parked chain refreshes counts, never duplicates the notice.
    """
    try:
        from popup_system import register_pending_item
        remaining = [str(i) for i in (sess.get("remaining_staff_ids") or [])]
        results = list(sess.get("completed_results") or [])
        total = int(sess.get("total") or len(remaining) or 0)
        done = len(results)
        names = sess.get("staff_names") or {}
        first_names = [str(names.get(sid, sid)) for sid in remaining[:3]]
        detail = (f"{len(remaining)} of {total} negotiations remaining"
                  + (f" ({', '.join(first_names)}"
                     + ("..." if len(remaining) > 3 else "") + ")"
                     if first_names else ""))
        title = "Staff negotiations parked"
        message = (
            f"Contract negotiations paused -- {detail}.\n\n"
            "Resume where you left off, or discard the remaining "
            "negotiations.")
        # The resume question: standard ask_card schema so the navbar chip
        # path, represent_screen_questions, and post-load represent_dialog
        # all work unchanged. Dismiss = keep parked (defer).
        try:
            dialogs = sess.get("dialogs")
            if not isinstance(dialogs, dict):
                dialogs = {}
                sess["dialogs"] = dialogs
            dialogs[_CHAIN_RESUME_DIALOG] = {
                "dialog_id": _CHAIN_RESUME_DIALOG,
                "title": title,
                "message": message,
                "options": ["Resume", "Discard"],
                "option_values": [True, False],
                "option_styles": ["primary", "secondary"],
                "answer": None,
                "parked": True,
                "resolver": _CHAIN_RESOLVER,
                "resolver_args": {},
                "default_on_dismiss": "defer",
                "registry": {
                    "item_id": _CHAIN_ITEM_ID,
                    "kind": "RESUMABLE",
                    "title": title,
                    "detail": detail,
                    "screen_id": _CHAIN_SCREEN_ID,
                },
            }
        except Exception:
            pass
        try:
            register_pending_item(
                app, _CHAIN_ITEM_ID, kind="RESUMABLE", title=title,
                detail=detail, screen_id=_CHAIN_SCREEN_ID,
                resolver="dialog:" + _CHAIN_RESOLVER, resolver_args={})
        except Exception:
            pass
        # User-visible notice at park time: inbox entry with the priority
        # pill (priority 3 -> "!"). One notice per parked chain; the
        # message id is kept so completion/discard can clear it.
        try:
            if not sess.get("notice_message_id"):
                from game_classes import EmailMessage
                from datetime import date
                msg = EmailMessage(
                    sender="System", sender_type="System",
                    date_sent=date.today(), category="Contracts",
                    priority=3, subject=title,
                    content=(f"Contract negotiations paused -- {detail}.\n"
                             "Resume any time from the Staff screen, or use "
                             "the resume chip in the nav bar."))
                app.send_email_to_user(msg)
                sess["notice_message_id"] = msg.id
        except Exception:
            pass
        try:
            refresher = getattr(app, "refresh_screen_navbar", None)
            if callable(refresher):
                refresher()
        except Exception:
            pass
        return True
    except Exception:
        return False


def park_staff_negotiate_chain_if_needed(app, screen_id):
    """Screen-teardown hook (called from the app's _teardown_screen).

    Parks the staff negotiate chain when its open negotiation screen is
    torn down without on_done firing -- i.e. the user navigated away
    mid-step. Between-step teardowns (chain advancing to the next screen)
    have step_open cleared already and are ignored.
    """
    try:
        if screen_id != _CHAIN_CONTRACT_SCREEN_ID:
            return False
        sess = _chain_session(app)
        if not isinstance(sess, dict):
            return False
        if not sess.get("step_open"):
            return False
        try:
            if getattr(app, "_staff_chain_advancing", False):
                # Intra-chain handoff (old step -> next step): not a park.
                return False
        except Exception:
            pass
        # The open step never resolved: keep it in remaining and park.
        sess["step_open"] = None
        return bool(_park_staff_negotiate_chain(app, sess))
    except Exception:
        return False


def _staff_chain_resume_answer(session_id, dialog_id, value, **kwargs):
    """DIALOG_RESOLVERS['staff_chain_resume']: answer the resume card.

    value True  -> revalidate IDs and resume the chain where it parked.
    value False -> explicit discard: clear everything (the "dismissed" case).
    Card dismissal never reaches here (defer = keep parked).
    Stale staff IDs are skipped with an honest digest note, never a crash.
    """
    try:
        app = _chain_app()
        if app is None:
            return False
        from popup_system import get_pending_session, unregister_pending_item
        sess = get_pending_session(app, session_id)
        if not isinstance(sess, dict):
            return False
        # Consume the question first: exactly-once continuation.
        try:
            (sess.get("dialogs") or {}).pop(dialog_id, None)
        except Exception:
            pass
        try:
            unregister_pending_item(app, _CHAIN_ITEM_ID)
        except Exception:
            pass
        _clear_chain_notice(app, sess)
        try:
            refresher = getattr(app, "refresh_screen_navbar", None)
            if callable(refresher):
                refresher()
        except Exception:
            pass
        if not value:
            # Explicit discard: drop the persisted chain entirely.
            try:
                sessions = getattr(app, "pending_sessions", None)
                if isinstance(sessions, dict):
                    sessions.pop(session_id, None)
            except Exception:
                pass
            return True
        remaining_ids = [str(i)
                         for i in (sess.get("remaining_staff_ids") or [])]
        results = list(sess.get("completed_results") or [])
        names = sess.get("staff_names") or {}
        staff_by_id = {}
        try:
            team = getattr(app, "user_team", None)
            for s in (getattr(team, "staff", None) or []):
                staff_by_id[str(getattr(s, "id", ""))] = s
        except Exception:
            pass
        staff_objs = []
        for sid in remaining_ids:
            s = staff_by_id.get(sid)
            if s is None:
                _nm = str(names.get(sid) or sid)
                results.append(f"{_nm}: no longer on staff -- skipped")
            else:
                staff_objs.append(s)
        view = _chain_staff_view(app)
        if view is None:
            return False
        if not staff_objs:
            view._chain_complete(results)
            return True
        view._negotiate_chain(list(staff_objs), list(results))
        return True
    except Exception:
        return False


try:
    from popup_system import register_dialog_resolver as _chain_reg_resolver
    _chain_reg_resolver(_CHAIN_RESOLVER, _staff_chain_resume_answer)
except Exception:
    pass


class StaffManagementView(ctk.CTkFrame):
    """Comprehensive staff management interface with EHM-style functionality."""

    # Roles whose attributes are verifiably read by the sim engine (scouting.py)
    _SCOUT_ROLES = {StaffRole.HEAD_SCOUT, StaffRole.PROFESSIONAL_SCOUT,
                    StaffRole.AMATEUR_SCOUT, StaffRole.EUROPEAN_SCOUT,
                    StaffRole.ADVANCE_SCOUT}

    def __init__(self, parent, app=None):
        init_ctk_theme()
        self._ct = dict(TEAL=TEAL, TEAL_HOVER=TEAL_HOVER, TEAL_DARK=TEAL_DARK,
                        BG=BG, PANEL=PANEL, CARD=CARD, BORDER=BORDER,
                        TEXT=TEXT, TEXT_DIM=TEXT_DIM, TEXT_FAINT=TEXT_FAINT,
                        GOLD=GOLD, GREEN=GREEN, RED=RED, BLUE=BLUE,
                        ROW_HOVER=ROW_HOVER, ROW_SELECTED=ROW_SELECTED)
        self._primary_button = primary_button
        self._secondary_button = secondary_button
        self._heading = heading
        self._body = body
        self._ff = getattr(parent, 'FONT_FAMILY', 'Segoe UI')
        ctk.CTkFrame.__init__(self, parent)

        self.app = app if app is not None else parent
        self._close_screen = None  # set by show_screen() or the StaffManagementWindow wrapper
        self.configure(fg_color=BG)
        # Gating: chain-resume resolver needs the app handle.
        _set_chain_app(self.app)

        # Staff candidates hired through the Free Agency window land here briefly
        # during negotiation; the authoritative lists live on the team/league.
        self.available_staff: List[Staff] = []

        # Checkbox-style multi-select state (like the trade block)
        self.selected_staff = set()
        self.staff_map = {}
        self.sort_column = None
        self.sort_reverse = False

        self._setup_tree_style()
        self.create_widgets()

        # Update current staff view only (hiring is handled in the Free Agency window)
        self.update_current_staff_view()

        # Track window under the same key the main app uses
        self.app.open_windows['staff_management'] = self

    def _sfont(self, size, weight=""):
        """Scale-aware font tuple (honors Settings -> Font size).

        CustomTkinter widgets don't safely accept tkinter Font objects,
        so sizes are scaled at build time via ui_scale.scaled().
        """
        try:
            from ui_scale import scaled as _scaled
            size = _scaled(size)
        except Exception:
            pass
        return (self._ff, size, weight) if weight else (self._ff, size)
    def close_view(self):
        """Close this screen (dashboard in screen mode, card in popup mode)."""
        fn = getattr(self, '_close_screen', None)
        if callable(fn):
            fn()
        else:
            self.destroy()

    def _on_close(self):
        """Unregister from the main app's window tracker and close."""
        try:
            self.app.open_windows.pop('staff_management', None)
        except Exception:
            pass
        self.close_view()

    def _get_user_team(self):
        """Return the user's team from live game state (never fabricated).

        Prefers the game manager's canonical user_team reference, falling back
        to the is_user_team scan used elsewhere in the codebase.
        """
        gm = getattr(self.app, 'game_manager', None)
        team = getattr(gm, 'user_team', None) if gm is not None else None
        if team is not None:
            return team
        league = getattr(gm, 'league', None) if gm is not None else None
        if league is not None:
            return next((t for t in league.teams if t.is_user_team), None)
        return None

    # ------------------------------------------------------------------
    # Styling
    # ------------------------------------------------------------------
    def _setup_tree_style(self):
        """Dark, flat styling for the staff table (styled ttk.Treeview, per the
        migration guide -- the table carries 11 sortable columns and several
        color tags)."""
        ct = self._ct
        style = ttk.Style(self)
        style.configure('Staff.Treeview',
                        background=ct['CARD'],
                        fieldbackground=ct['CARD'],
                        foreground=ct['TEXT'],
                        borderwidth=0,
                        relief='flat',
                        rowheight=28,
                        font=self._sfont(10))
        style.configure('Staff.Treeview.Heading',
                        background=ct['PANEL'],
                        foreground=ct['TEXT'],
                        font=self._sfont(10, 'bold'),
                        relief='flat',
                        borderwidth=0)
        style.map('Staff.Treeview',
                  background=[('selected', ct['ROW_SELECTED'])],
                  foreground=[('selected', ct['TEXT'])])
        style.layout('Staff.Treeview',
                     [('Treeview.treearea', {'sticky': 'nswe'})])
        style.configure('Staff.Vertical.TScrollbar',
                        background=ct['CARD'],
                        troughcolor=ct['BG'],
                        borderwidth=0,
                        relief='flat',
                        arrowcolor=ct['TEXT_DIM'])
        style.map('Staff.Vertical.TScrollbar',
                  background=[('active', ct['BORDER'])])

    def _rating_tag(self, rating):
        """Tier tag for the staff table's Rating column.

        Staff overall_rating is a 0-20 computed property (displayed raw,
        matching the Free Agency staff list), so tiers are scaled to it.
        """
        if rating >= 16:
            return 'rating_elite'
        if rating >= 13:
            return 'rating_good'
        if rating >= 10:
            return 'rating_avg'
        return None

    def _card(self, parent, **kw):
        """Rounded dark card frame."""
        kw.setdefault('fg_color', self._ct['CARD'])
        kw.setdefault('corner_radius', 10)
        return ctk.CTkFrame(parent, **kw)

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def create_widgets(self):
        """Create the main interface widgets."""
        ct = self._ct
        main = ctk.CTkFrame(self, fg_color=ct['BG'], corner_radius=0)
        main.pack(fill="both", expand=True, padx=12, pady=12)

        # Header card
        header = self._card(main)
        header.pack(fill="x", pady=(0, 10))
        top = ctk.CTkFrame(header, fg_color="transparent")
        top.pack(fill="x", padx=16, pady=(12, 4))
        self._heading(top, text="Staff Management", size=20).pack(side="left")
        accent = ctk.CTkFrame(header, fg_color=ct['TEAL'], height=3, corner_radius=2)
        accent.pack(fill="x", padx=16, pady=(4, 12))

        # Tabs (CTkTabview instead of ttk.Notebook)
        self.tabview = ctk.CTkTabview(
            main,
            fg_color=ct['PANEL'],
            corner_radius=12,
            border_width=1,
            border_color=ct['BORDER'],
            segmented_button_fg_color=ct['PANEL'],
            segmented_button_selected_color=ct['TEAL'],
            segmented_button_selected_hover_color=ct['TEAL_HOVER'],
            segmented_button_unselected_color=ct['CARD'],
            segmented_button_unselected_hover_color=ct['BORDER'],
            text_color=ct['TEXT'],
            command=self._on_tabview_change,
        )
        self.tabview.pack(fill="both", expand=True)
        for name in ("Current Staff", "Hire Staff", "Organization"):
            self.tabview.add(name)

        self.create_current_staff_tab()
        self.create_available_staff_auto_redirect_tab()
        self.create_staff_overview_tab()

    def create_current_staff_tab(self):
        """Current staff management tab with trade-block-style interaction."""
        ct = self._ct
        frame = self.tabview.tab("Current Staff")
        frame.configure(fg_color=ct['PANEL'])

        # Staff summary card
        summary_card = self._card(frame)
        summary_card.pack(fill="x", padx=12, pady=(10, 0))
        self.staff_summary_label = ctk.CTkLabel(
            summary_card, text="", font=self._sfont(11, 'bold'),
            text_color=ct['TEXT'], anchor="w")
        self.staff_summary_label.pack(fill="x", padx=14, pady=10)

        # Filter card
        filter_card = self._card(frame)
        filter_card.pack(fill="x", padx=12, pady=(10, 0))
        finner = ctk.CTkFrame(filter_card, fg_color="transparent")
        finner.pack(fill="x", padx=14, pady=10)

        def _flabel(text):
            return ctk.CTkLabel(finner, text=text, font=self._sfont(10),
                                text_color=ct['TEXT_DIM'])

        _flabel("Department:").pack(side="left")
        dept_options = ["All", "Management", "Coaching", "Development",
                        "Scouting", "Medical", "Analytics"]
        self.dept_combo = ctk.CTkComboBox(
            finner, values=dept_options, width=140, state="readonly",
            fg_color=ct['BG'], border_color=ct['BORDER'],
            button_color=ct['CARD'], button_hover_color=ct['BORDER'],
            dropdown_fg_color=ct['PANEL'], dropdown_text_color=ct['TEXT'],
            dropdown_hover_color=ct['ROW_HOVER'], text_color=ct['TEXT'],
            command=lambda v: self.update_current_staff_view())
        self.dept_combo.set("All")
        self.dept_combo.pack(side="left", padx=(4, 10))

        _flabel("Min Rating:").pack(side="left")
        self.min_rating_entry = ctk.CTkEntry(
            finner, width=56, placeholder_text="0",
            fg_color=ct['BG'], border_color=ct['BORDER'], text_color=ct['TEXT'])
        self.min_rating_entry.pack(side="left", padx=(4, 10))

        _flabel("Max Salary:").pack(side="left")
        self.max_salary_entry = ctk.CTkEntry(
            finner, width=90, placeholder_text="$",
            fg_color=ct['BG'], border_color=ct['BORDER'], text_color=ct['TEXT'])
        self.max_salary_entry.pack(side="left", padx=(4, 10))

        _flabel("Contract:").pack(side="left")
        self.contract_combo = ctk.CTkComboBox(
            finner, values=["All", "Expiring", "Long-term"], width=120,
            state="readonly",
            fg_color=ct['BG'], border_color=ct['BORDER'],
            button_color=ct['CARD'], button_hover_color=ct['BORDER'],
            dropdown_fg_color=ct['PANEL'], dropdown_text_color=ct['TEXT'],
            dropdown_hover_color=ct['ROW_HOVER'], text_color=ct['TEXT'],
            command=lambda v: self.update_current_staff_view())
        self.contract_combo.set("All")
        self.contract_combo.pack(side="left", padx=(4, 10))

        self._secondary_button(finner, text="Apply Filter",
                               command=self.update_current_staff_view,
                               width=110, height=32).pack(side="left", padx=8)

        # Main staff list card
        panel_card = self._card(frame)
        panel_card.pack(fill="both", expand=True, padx=12, pady=10)

        # Staff treeview with trade-block-style columns
        columns = {
            'sel': ('', 30),
            'name': ('Name', 170),
            'role': ('Position', 170),
            'dept': ('Department', 110),
            'overall': ('Rating', 60),
            'experience': ('Exp', 50),
            'salary': ('Salary', 100),
            'contract': ('Contract', 80),
            'morale': ('Morale', 70),
            'status': ('Status', 90),
            'key_skills': ('Key Skills', 200)
        }

        tree_holder = ctk.CTkFrame(panel_card, fg_color="transparent")
        tree_holder.pack(fill="both", expand=True, padx=10, pady=10)

        self.current_staff_tree = ttk.Treeview(
            tree_holder, columns=list(columns.keys()), show='headings',
            height=15, style='Staff.Treeview')

        for col, (text, width) in columns.items():
            self.current_staff_tree.heading(
                col, text=text, command=lambda c=col: self._sort_staff_treeview(c))
            self.current_staff_tree.column(
                col, width=width,
                anchor='center' if col != 'key_skills' else 'w')

        scrollbar = ttk.Scrollbar(tree_holder, orient="vertical",
                                  command=self.current_staff_tree.yview,
                                  style='Staff.Vertical.TScrollbar')
        self.current_staff_tree.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        self.current_staff_tree.pack(side="left", fill="both", expand=True)

        # Bind events like trade block
        self.current_staff_tree.bind("<Button-1>", self._handle_staff_checkbox_click)
        self.current_staff_tree.bind("<Double-1>", self._handle_staff_double_click)
        self.current_staff_tree.bind("<Button-3>", self.show_staff_context_menu)

        # Row tags: selection + morale + rating tiers
        self.current_staff_tree.tag_configure('selected',
                                              background=ct['ROW_SELECTED'])
        self.current_staff_tree.tag_configure('high_morale', foreground=ct['GREEN'])
        self.current_staff_tree.tag_configure('low_morale', foreground=ct['RED'])
        self.current_staff_tree.tag_configure('rating_elite', foreground=ct['GREEN'])
        self.current_staff_tree.tag_configure('rating_good', foreground=ct['TEAL'])
        self.current_staff_tree.tag_configure('rating_avg', foreground=ct['GOLD'])

        # Action buttons
        button_frame = ctk.CTkFrame(panel_card, fg_color="transparent")
        button_frame.pack(fill="x", padx=10, pady=(0, 10))

        self._secondary_button(button_frame, text="View Details",
                               command=self.view_selected_staff,
                               width=130, height=36).pack(side="left", padx=5)
        self._secondary_button(button_frame, text="Negotiate Contract",
                               command=self.negotiate_selected_staff,
                               width=160, height=36).pack(side="left", padx=5)
        self._secondary_button(button_frame, text="Reassign Role",
                               command=self.reassign_selected_staff,
                               width=130, height=36).pack(side="left", padx=5)
        self._secondary_button(button_frame, text="Release Staff",
                               command=self.release_selected_staff,
                               width=130, height=36).pack(side="left", padx=5)
        self._secondary_button(button_frame, text="Org Chart",
                               command=self.show_organizational_chart,
                               width=110, height=36).pack(side="right", padx=5)
        self._secondary_button(button_frame, text="Staff Report",
                               command=self.show_staff_report,
                               width=130, height=36).pack(side="right", padx=5)

    def create_available_staff_auto_redirect_tab(self):
        """The 'Hire Staff' tab jumps to the Free Agency staff page when selected."""
        frame = self.tabview.tab("Hire Staff")
        frame.configure(fg_color=self._ct['PANEL'])
        ctk.CTkLabel(
            frame, text="Opening Free Agency...", font=self._sfont(12),
            text_color=self._ct['TEXT_DIM']).pack(expand=True, pady=40)

    def _on_tabview_change(self, tab_name):
        """Detect the Hire Staff tab selection and redirect to Free Agency."""
        if tab_name == "Hire Staff":
            self.after_idle(self._redirect_to_free_agency)

    def _redirect_to_free_agency(self):
        """Redirect to Free Agency staff page and close this window."""
        # Unregister this window before opening Free Agency
        try:
            self.app.open_windows.pop('staff_management', None)
        except Exception:
            pass

        # Open the enhanced free agency window
        self.app.open_free_agency_window()

        # Select the staff tab ("Free Agent Staff") once it is ready.
        # (The CTk rebuild dropped FA's old ttk `notebook` attribute, so the
        # legacy `notebook.select(1)` call is replaced with the tabview API.)
        def select_staff_tab():
            fa_window = self.app.open_windows.get('free_agency')
            if fa_window is not None and hasattr(fa_window, 'tabview'):
                try:
                    if fa_window.winfo_exists():
                        fa_window.tabview.set("Free Agent Staff")
                        fa_window.focus_set()
                except Exception:
                    pass

        # Schedule the tab selection for after the window is fully created
        self.app.after_idle(select_staff_tab)

        # Close this window
        self.close_view()

    def create_staff_overview_tab(self):
        """Staff overview and organizational chart."""
        ct = self._ct
        frame = self.tabview.tab("Organization")
        frame.configure(fg_color=ct['PANEL'])

        # Organizational chart card
        org_card = self._card(frame)
        org_card.pack(fill="both", expand=True, padx=12, pady=(10, 6))
        ctk.CTkLabel(org_card, text="Organizational Chart",
                     font=self._sfont(13, 'bold'),
                     text_color=ct['TEXT'], anchor="w").pack(
                         anchor="w", padx=14, pady=(10, 6))

        chart_holder = ctk.CTkFrame(org_card, fg_color="transparent")
        chart_holder.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.org_text = ctk.CTkTextbox(
            chart_holder, font=self._sfont(10), wrap="word",
            fg_color=ct['BG'], text_color=ct['TEXT'],
            border_color=ct['BORDER'], border_width=1, corner_radius=8)
        self.org_text.pack(side="left", fill="both", expand=True)

        # Staff statistics card
        stats_card = self._card(frame)
        stats_card.pack(fill="x", padx=12, pady=(6, 10))
        ctk.CTkLabel(stats_card, text="Staff Statistics",
                     font=self._sfont(13, 'bold'),
                     text_color=ct['TEXT'], anchor="w").pack(
                         anchor="w", padx=14, pady=(10, 4))
        self.stats_label = ctk.CTkLabel(
            stats_card, text="", font=self._sfont(10),
            text_color=ct['TEXT_DIM'], anchor="w", justify="left")
        self.stats_label.pack(anchor="w", padx=14, pady=(0, 10))

    # ------------------------------------------------------------------
    # Data / filtering / sorting
    # ------------------------------------------------------------------
    def update_views(self):
        """Update all views with current data."""
        self.update_current_staff_view()
        self.update_staff_overview()
        self.update_staff_summary()

    def update_current_staff_view(self):
        """Update the current staff treeview with trade-block-style interaction."""
        # R8 (UI repairs): busy cursor while the staff list rebuilds.
        try:
            from ctk_theme import busy_cursor
            _cm = busy_cursor(self)
            _cm.__enter__()
        except Exception:
            _cm = None
        try:
            self._update_current_staff_view_inner()
        finally:
            try:
                if _cm is not None:
                    _cm.__exit__(None, None, None)
            except Exception:
                pass

    def _update_current_staff_view_inner(self):
        """Inner staff-list rebuild (wrapped with a busy cursor above)."""
        # Clear existing items
        for item in self.current_staff_tree.get_children():
            self.current_staff_tree.delete(item)

        self.staff_map = {}

        user_team = self._get_user_team()
        if not user_team:
            return

        # Apply filters
        filtered_staff = self._filter_staff(user_team.staff)

        # Update summary like trade block
        total_staff = len(user_team.staff)
        filtered_count = len(filtered_staff)
        total_salary = sum(staff.salary for staff in user_team.staff)
        avg_rating = sum(staff.overall_rating for staff in user_team.staff) / total_staff if total_staff > 0 else 0
        selected_count = len(self.selected_staff)

        summary_text = f"Total Staff: {total_staff} | Showing: {filtered_count} | Selected: {selected_count} | "
        summary_text += f"Total Salary: ${total_salary:,} | Avg Rating: {avg_rating:.1f}"
        self.staff_summary_label.configure(text=summary_text)

        # Populate tree like trade block
        for staff in sorted(filtered_staff, key=lambda s: (s.role.value, s.overall_rating), reverse=True):
            # Checkbox like trade block
            sel = "☑" if staff.id in self.selected_staff else "☐"

            # Get department for staff
            department = self.get_staff_department(staff)

            # Calculate key skills display
            key_skills = self.get_key_skills_display(staff)

            # Get morale and status
            morale = getattr(staff, 'morale', 10)
            status = self.get_staff_status(staff)

            # Format salary
            salary_str = f"${staff.salary:,}"
            contract_str = f"{staff.contract_years}y"

            # Staff morale is a 1-100 scale (game_classes.Staff.morale); the
            # denominator must match that scale, not a 0-20 rating.
            values = (
                sel,
                staff.full_name,
                staff.role.value,
                department,
                staff.overall_rating,
                f"{staff.experience}y",
                salary_str,
                contract_str,
                f"{morale}/100",
                status,
                key_skills
            )

            # Determine tags for visual styling (morale is 1-100)
            tags = []
            if staff.id in self.selected_staff:
                tags.append('selected')
            rating_tag = self._rating_tag(staff.overall_rating)
            if rating_tag:
                tags.append(rating_tag)
            if morale >= 75:
                tags.append('high_morale')
            elif morale <= 40:
                tags.append('low_morale')

            item_id = self.current_staff_tree.insert('', 'end', values=values, tags=tags)
            self.staff_map[item_id] = staff

    def _filter_staff(self, staff_list):
        """Filter staff based on current filter settings."""
        filtered = []

        # Get filter values
        department = self.dept_combo.get() if hasattr(self, 'dept_combo') else "All"
        min_rating = self.min_rating_entry.get() if hasattr(self, 'min_rating_entry') else ""
        max_salary = self.max_salary_entry.get() if hasattr(self, 'max_salary_entry') else ""
        contract_status = self.contract_combo.get() if hasattr(self, 'contract_combo') else "All"

        for staff in staff_list:
            # Department filter
            if department != "All":
                staff_dept = self.get_staff_department(staff)
                if staff_dept != department:
                    continue

            # Rating filter
            if min_rating:
                try:
                    if staff.overall_rating < int(min_rating):
                        continue
                except ValueError:
                    pass

            # Salary filter
            if max_salary:
                try:
                    max_val = int(max_salary.replace(',', '').replace('$', ''))
                    if staff.salary > max_val:
                        continue
                except ValueError:
                    pass

            # Contract status filter
            if contract_status != "All":
                if contract_status == "Expiring" and staff.contract_years > 1:
                    continue
                elif contract_status == "Long-term" and staff.contract_years <= 1:
                    continue

            filtered.append(staff)

        return filtered

    def get_staff_department(self, staff):
        """Get department name for a staff member."""
        role_departments = {
            # Management
            StaffRole.GENERAL_MANAGER: 'Management',
            StaffRole.ASSISTANT_GENERAL_MANAGER: 'Management',

            # Coaching
            StaffRole.HEAD_COACH: 'Coaching',
            StaffRole.ASSISTANT_COACH: 'Coaching',
            StaffRole.ASSOCIATE_COACH: 'Coaching',
            StaffRole.GOALIE_COACH: 'Coaching',
            StaffRole.POWER_PLAY_COACH: 'Coaching',
            StaffRole.PENALTY_KILL_COACH: 'Coaching',

            # Development
            StaffRole.SKILLS_COACH: 'Development',
            StaffRole.CONDITIONING_COACH: 'Development',
            StaffRole.SKATING_COACH: 'Development',
            StaffRole.STRENGTH_COACH: 'Development',

            # Scouting
            StaffRole.HEAD_SCOUT: 'Scouting',
            StaffRole.PROFESSIONAL_SCOUT: 'Scouting',
            StaffRole.AMATEUR_SCOUT: 'Scouting',
            StaffRole.EUROPEAN_SCOUT: 'Scouting',
            StaffRole.ADVANCE_SCOUT: 'Scouting',

            # Medical
            StaffRole.TEAM_DOCTOR: 'Medical',
            StaffRole.PHYSIOTHERAPIST: 'Medical',
            StaffRole.EQUIPMENT_MANAGER: 'Medical',

            # Analytics
            StaffRole.VIDEO_COACH: 'Analytics',
            StaffRole.STATISTICIAN: 'Analytics',
            StaffRole.MEDIA_RELATIONS: 'Analytics'
        }

        return role_departments.get(staff.role, 'Other')

    def _sort_staff_treeview(self, col):
        """Sort staff treeview by column like trade block."""
        # Toggle sort order
        if self.sort_column == col:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = col
            self.sort_reverse = False

        # Sort items by column
        def get_val(item_id):
            val = self.current_staff_tree.set(item_id, col)
            # Handle different data types
            if col in ['overall', 'experience']:
                try:
                    return int(val.replace('y', ''))
                except ValueError:
                    return 0
            elif col == 'salary':
                try:
                    return int(val.replace('$', '').replace(',', ''))
                except ValueError:
                    return 0
            elif col == 'morale':
                try:
                    return int(val.split('/')[0])
                except (ValueError, IndexError):
                    return 0
            else:
                return val.lower() if isinstance(val, str) else val

        items = list(self.current_staff_tree.get_children())
        items.sort(key=get_val, reverse=self.sort_reverse)
        for idx, item_id in enumerate(items):
            self.current_staff_tree.move(item_id, '', idx)

    def _handle_staff_checkbox_click(self, event):
        """Handle checkbox clicks like trade block."""
        col = self.current_staff_tree.identify_column(event.x)
        if col == '#1':  # Checkbox column
            item_id = self.current_staff_tree.identify_row(event.y)
            if item_id:
                staff = self.staff_map.get(item_id)
                if staff:
                    if staff.id in self.selected_staff:
                        self.selected_staff.remove(staff.id)
                    else:
                        self.selected_staff.add(staff.id)
                    self.update_current_staff_view()

    def _handle_staff_double_click(self, event):
        """Handle double-click to view staff details."""
        item_id = self.current_staff_tree.identify_row(event.y)
        if item_id:
            staff = self.staff_map.get(item_id)
            if staff:
                self.show_staff_details_window(staff, is_current=True)

    def update_staff_overview(self):
        """Update the organizational chart and overview."""
        user_team = self._get_user_team()
        if not user_team:
            return

        # Clear text widget
        self.org_text.delete("1.0", "end")

        # Organize staff by category
        staff_by_category = {
            'Management': [],
            'Coaching': [],
            'Development': [],
            'Scouting': [],
            'Medical': [],
            'Analytics': [],
            'Other': []
        }

        role_categories = {
            # Management
            StaffRole.GENERAL_MANAGER: 'Management',
            StaffRole.ASSISTANT_GENERAL_MANAGER: 'Management',

            # Coaching
            StaffRole.HEAD_COACH: 'Coaching',
            StaffRole.ASSISTANT_COACH: 'Coaching',
            StaffRole.ASSOCIATE_COACH: 'Coaching',
            StaffRole.GOALIE_COACH: 'Coaching',
            StaffRole.POWER_PLAY_COACH: 'Coaching',
            StaffRole.PENALTY_KILL_COACH: 'Coaching',

            # Development
            StaffRole.SKILLS_COACH: 'Development',
            StaffRole.CONDITIONING_COACH: 'Development',
            StaffRole.SKATING_COACH: 'Development',
            StaffRole.STRENGTH_COACH: 'Development',

            # Scouting
            StaffRole.HEAD_SCOUT: 'Scouting',
            StaffRole.PROFESSIONAL_SCOUT: 'Scouting',
            StaffRole.AMATEUR_SCOUT: 'Scouting',
            StaffRole.EUROPEAN_SCOUT: 'Scouting',
            StaffRole.ADVANCE_SCOUT: 'Scouting',

            # Medical
            StaffRole.TEAM_DOCTOR: 'Medical',
            StaffRole.PHYSIOTHERAPIST: 'Medical',

            # Analytics
            StaffRole.VIDEO_COACH: 'Analytics',
            StaffRole.STATISTICIAN: 'Analytics',
            StaffRole.MEDIA_RELATIONS: 'Analytics',

            # Other
            StaffRole.EQUIPMENT_MANAGER: 'Other'
        }

        # Categorize current staff
        for staff in user_team.staff:
            category = role_categories.get(staff.role, 'Other')
            staff_by_category[category].append(staff)

        # Build organizational chart text
        org_text = f"{user_team.team_name} Organizational Chart\n"
        org_text += "=" * 50 + "\n\n"

        # Add staff validation status
        validation_issues = user_team.validate_staff_structure()
        if validation_issues['errors'] or validation_issues['warnings']:
            org_text += "STAFF ISSUES:\n"
            for error in validation_issues['errors']:
                org_text += f"  ERROR: {error}\n"
            for warning in validation_issues['warnings']:
                org_text += f"  WARNING: {warning}\n"
            org_text += "\n"
        else:
            org_text += "Staff structure validated - No issues found.\n\n"

        for category, staff_list in staff_by_category.items():
            if staff_list:
                org_text += f"{category} Department:\n"
                org_text += "-" * 20 + "\n"
                for staff in staff_list:
                    org_text += f"  • {staff.full_name} - {staff.role.value} (Overall: {staff.overall_rating})\n"
                org_text += "\n"
            else:
                org_text += f"{category} Department: [VACANT]\n\n"

        # Add vacant positions
        all_roles = set(StaffRole)
        filled_roles = {staff.role for staff in user_team.staff}
        vacant_roles = all_roles - filled_roles

        if vacant_roles:
            org_text += "Vacant Positions:\n"
            org_text += "-" * 15 + "\n"
            for role in sorted(vacant_roles, key=lambda x: x.value):
                category = role_categories.get(role, 'Other')
                org_text += f"  • {role.value} ({category})\n"

        self.org_text.insert("1.0", org_text)

    def update_staff_summary(self):
        """Update the staff summary information."""
        user_team = self._get_user_team()
        if not user_team:
            return

        total_staff = len(user_team.staff)
        total_payroll = sum(staff.salary for staff in user_team.staff)
        avg_overall = sum(staff.overall_rating for staff in user_team.staff) / max(1, total_staff)
        avg_experience = sum(staff.experience for staff in user_team.staff) / max(1, total_staff)

        # Count by category
        coaching_count = sum(1 for s in user_team.staff if 'COACH' in s.role.value.upper())
        scouting_count = sum(1 for s in user_team.staff if 'SCOUT' in s.role.value.upper())

        summary_text = (
            f"Total Staff: {total_staff} | "
            f"Coaching: {coaching_count} | "
            f"Scouting: {scouting_count} | "
            f"Payroll: ${total_payroll:,} | "
            f"Avg Overall: {avg_overall:.1f} | "
            f"Avg Experience: {avg_experience:.1f} years"
        )

        self.staff_summary_label.configure(text=summary_text)

        # Update stats for organization tab
        if hasattr(self, 'stats_label'):
            stats_text = f"""Staff Statistics:
• Total Staff Members: {total_staff}
• Total Staff Payroll: ${total_payroll:,}
• Average Overall Rating: {avg_overall:.1f}
• Average Experience: {avg_experience:.1f} years
• Coaching Staff: {coaching_count} members
• Scouting Staff: {scouting_count} members
• Highest Paid: {max(user_team.staff, key=lambda s: s.salary).full_name if user_team.staff else 'N/A'} (${max((s.salary for s in user_team.staff), default=0):,})
• Most Experienced: {max(user_team.staff, key=lambda s: s.experience).full_name if user_team.staff else 'N/A'} ({max((s.experience for s in user_team.staff), default=0)} years)"""

            self.stats_label.configure(text=stats_text)

    def get_key_skills_display(self, staff: Staff) -> str:
        """Get a display string of the staff member's key skills."""
        # Define key attributes by role
        role_skills = {
            StaffRole.HEAD_COACH: ['tactical_knowledge', 'man_management', 'motivating'],
            StaffRole.ASSISTANT_COACH: ['coaching_forwards', 'coaching_defensemen', 'game_preparation'],
            StaffRole.GOALIE_COACH: ['coaching_goalies', 'technical_coaching', 'working_with_youngsters'],
            StaffRole.HEAD_SCOUT: ['judging_player_ability', 'judging_player_potential', 'determination'],
            StaffRole.PROFESSIONAL_SCOUT: ['judging_player_ability', 'adaptability'],
            StaffRole.AMATEUR_SCOUT: ['judging_player_potential', 'working_with_youngsters'],
            StaffRole.GENERAL_MANAGER: ['judging_player_ability', 'tactical_knowledge', 'media_handling']
        }

        skills = role_skills.get(staff.role, ['determination', 'adaptability', 'man_management'])
        skill_values = []

        for skill in skills[:3]:  # Top 3 skills
            if hasattr(staff, skill):
                value = getattr(staff, skill)
                skill_name = skill.replace('_', ' ').title()
                skill_values.append(f"{skill_name}: {value}")

        return " | ".join(skill_values)

    def _staff_impact_lines(self, staff: Staff):
        """What this staffer's attributes verifiably affect.

        Only effects confirmed by reading the sim code are reported;
        everything else gets an honest "no direct effect" line.
        Returns [(text, kind)] where kind is 'ok' | 'warn' | 'info'.
        """
        lines = []
        if staff.role in self._SCOUT_ROLES:
            ja = getattr(staff, 'judging_player_ability', 0) or 0
            jp = getattr(staff, 'judging_player_potential', 0) or 0
            eff = (ja + jp) / 40.0
            lines.append(
                (f"Judging Ability {ja} / Judging Potential {jp} drive the scouting engine: "
                 f"this scout files prospect reports at about {eff:.0%} efficiency, and higher "
                 "values raise report accuracy and reliability.", 'ok'))
            mm = getattr(staff, 'man_management', 0) or 0
            if mm > 12:
                lines.append(
                    ("Man Management 13+ unlocks prospect interviews once a report reaches "
                     "3+ viewings (further boosts report reliability).", 'ok'))
            else:
                lines.append(
                    (f"Man Management is {mm}: reaching 13 unlocks prospect interviews once a "
                     "report reaches 3+ viewings.", 'info'))
        elif staff.role in (StaffRole.TEAM_DOCTOR, StaffRole.PHYSIOTHERAPIST):
            # W4 (icetime-ecosystem): medical staff now have a real sim
            # effect -- see injury_data.medical_staff_quality /
            # recovery_time_mult / roll_setback.
            lines.append(
                ("Team Doctor + Physiotherapist: their average overall rating "
                 "shortens every injury recovery (up to ~20% faster at elite "
                 "ratings, ~20% slower with a poor medical team) and roughly "
                 "halves/doubles rehab-setback odds. The diagnosis sets each "
                 "injury's recovery timeline.", 'ok'))
        else:
            key = self.get_key_skills_display(staff)
            if key:
                lines.append((f"Role focus: {key}.", 'info'))
            lines.append(
                ("No direct simulation effect currently: this role's attributes are tracked "
                 "and displayed, but the sim engine does not read them.", 'warn'))
        return lines

    # ------------------------------------------------------------------
    # Selection actions
    # ------------------------------------------------------------------
    def get_current_team_staff(self):
        """Get current team staff list."""
        user_team = self._get_user_team()
        return user_team.staff if user_team else []

    def get_staff_status(self, staff):
        """Determine staff status based on various factors (morale is 1-100)."""
        morale = getattr(staff, 'morale', 60)
        years_left = staff.contract_years

        if years_left <= 1:
            return "Expiring"
        elif morale >= 75:
            return "Happy"
        elif morale >= 55:
            return "Content"
        elif morale >= 35:
            return "Concerned"
        else:
            return "Unhappy"

    def filter_current_staff(self, event=None):
        """Filter current staff based on selected category - updated for new system."""
        # This is now handled by the filter dropdowns in the new interface
        self.update_current_staff_view()

    def show_staff_context_menu(self, event):
        """Show right-click context menu for current staff like trade block."""
        item_id = self.current_staff_tree.identify_row(event.y)
        if not item_id:
            return

        self.current_staff_tree.selection_set(item_id)
        staff = self.staff_map.get(item_id)
        if not staff:
            return

        # Toggle selection when right-clicking
        if staff.id not in self.selected_staff:
            self.selected_staff.add(staff.id)
            self.update_current_staff_view()

        context_menu = tk.Menu(self, tearoff=0, bg=self._ct['PANEL'],
                               fg=self._ct['TEXT'],
                               activebackground=self._ct['ROW_SELECTED'],
                               activeforeground=self._ct['TEXT'])
        context_menu.add_command(label=f"View {staff.full_name} Details",
                                 command=lambda: self.show_staff_details_window(staff, True))
        context_menu.add_command(label="Negotiate Contract",
                                 command=self.negotiate_selected_staff)
        context_menu.add_command(label="Reassign Role",
                                 command=self.reassign_selected_staff)
        # R6 (UI repairs): personal beefs are declared from the person's
        # card -- the Morale window's DeclareRivalPopup already points here.
        context_menu.add_command(label="Declare Rival",
                                 command=lambda: self._declare_rival_staff(staff))
        context_menu.add_separator()
        context_menu.add_command(label="Release Staff",
                                 command=self.release_selected_staff)

        try:
            context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            context_menu.grab_release()

    def _declare_rival_staff(self, staff):
        """Declare a personal rivalry with a staff member (R6).

        Wires the staff table into the EXISTING rivalry system
        (reputation_system.declare_rivalry) -- the same entry point the
        Morale window's DeclareRivalPopup uses. Staff on the user's own
        club are refused with an explanation; feed + inbox go through
        headlines.announce_rivalry_declaration. Never raises.
        """
        try:
            gm = getattr(self.app, 'game_manager', None) or self.app
            league = getattr(gm, 'league', None)
            team = self._get_user_team()
            if league is None or team is None:
                messagebox.showwarning(
                    "Declare Rival",
                    "No active league to declare a rivalry in.")
                return
            own_ids = {getattr(s, "id", None)
                       for s in self.get_current_team_staff()}
            if getattr(staff, "id", None) in own_ids:
                messagebox.showinfo(
                    "Declare Rival",
                    f"{getattr(staff, 'full_name', 'They')} work for your "
                    "club.\n\nDeclare rival is for opposing staff -- "
                    "right-click their card to start a personal beef.")
                return
            import reputation_system as rs
            try:
                existing = rs.rivalry_between(
                    getattr(league, "rivalries", None) or [],
                    rs.gm_persona(team), staff, kind="gm_coach")
            except Exception:
                existing = None
            if existing and existing.get("user_declared"):
                messagebox.showinfo(
                    "Declare Rival",
                    f"You already declared "
                    f"{getattr(staff, 'full_name', 'them')} a personal "
                    f"rival (heat {existing.get('intensity', 0):.0f}).")
                return
            # NOTE: kind="gm_coach" is the existing personal-beef kind the
            # rivalry system already understands (GM vs a person); _ekey
            # keys staff as ('staff', id) so it never collides.
            rec = rs.declare_rivalry(league, rs.gm_persona(team), staff,
                                     kind="gm_coach")
            if not rec:
                messagebox.showwarning("Declare Rival",
                                       "Could not register the rivalry.")
                return
            try:
                import headlines as hl
                gui = self.app if hasattr(self.app, "add_news") else (
                    getattr(self.app, "app", None) or self.app)
                target_team_name = "?"
                for t in (getattr(league, "teams", None) or []):
                    if any(getattr(s, "id", None) == getattr(staff, "id", None)
                           for s in (getattr(t, "staff", None) or [])):
                        target_team_name = getattr(t, "team_name", "?")
                        break
                hl.announce_rivalry_declaration(
                    gui, getattr(team, "team_name", "?"), target_team_name,
                    getattr(staff, "full_name", "?"), "coach")
            except Exception:
                pass
            messagebox.showinfo(
                "Rival Declared",
                f"Declared: {getattr(staff, 'full_name', '?')} "
                f"(heat {rec.get('intensity', 70):.0f}). "
                "Those games just got personal.")
        except Exception as e:
            try:
                messagebox.showerror("Declare Rival",
                                     f"Could not declare rival: {e}")
            except Exception:
                pass

    def view_selected_staff(self):
        """View details of selected staff members."""
        if not self.selected_staff:
            messagebox.showwarning("No Selection", "Please select staff members to view details.")
            return

        # If only one selected, show detailed view
        if len(self.selected_staff) == 1:
            staff_id = next(iter(self.selected_staff))
            staff = next((s for s in self.get_current_team_staff() if s.id == staff_id), None)
            if staff:
                self.show_staff_details_window(staff, is_current=True)
        else:
            # Multiple selected - show summary
            self.show_multiple_staff_summary()

    def negotiate_selected_staff(self):
        """Negotiate contracts with selected staff members.

        Gating Phase 2: the sequential modal dialogs are a chained series
        of non-modal negotiation screens. Results still reflect what
        actually happened; one inbox digest lands at the end.
        """
        if not self.selected_staff:
            messagebox.showwarning("No Selection", "Please select staff members to negotiate contracts.")
            return

        selected_staff_list = [s for s in self.get_current_team_staff() if s.id in self.selected_staff]
        # Gating: persist the chain (Tier B) before the first step so a
        # mid-chain navigation can park and resume instead of dying silent.
        _set_chain_app(self.app)
        _write_chain_session(
            self.app, [s.id for s in selected_staff_list], [],
            None,
            staff_names={s.id: s.full_name for s in selected_staff_list})
        self._negotiate_chain(list(selected_staff_list), [])

    def _negotiate_chain(self, remaining, results):
        """Open the next renegotiation screen; the digest lands when the
        chain completes.

        Gating: the chain is write-through persisted (Tier B). Each open
        step records step_open; the app's screen-teardown hook parks the
        chain when the step's screen goes away without on_done firing.
        """
        app = getattr(self, "app", None)
        _set_chain_app(app)
        _write_chain_session(
            app, [s.id for s in remaining], list(results),
            remaining[0].id if remaining else None,
            staff_names={s.id: s.full_name for s in remaining})
        if not remaining:
            self._chain_complete(results)
            return
        staff = remaining[0]

        def _one_done(accepted, _staff=staff):
            # Guard: ignore late/duplicate callbacks. Only the currently
            # open step may advance the chain.
            try:
                _sess = _chain_session(app)
                if (not isinstance(_sess, dict)
                        or str(_sess.get("step_open") or "")
                        != str(_staff.id)):
                    return
            except Exception:
                return
            results.append(
                f"{_staff.full_name}: "
                f"{'agreement reached' if accepted else 'no agreement'}")
            _write_chain_session(
                app, [s.id for s in remaining[1:]], list(results), None)
            self._negotiate_chain(remaining[1:], results)

        # Intra-chain transition: the old step's screen is torn down by
        # show_screen() below. Mark it on the app (NOT the persisted
        # session) so the teardown hook does not mistake the handoff for
        # navigating away and park the chain mid-advance.
        try:
            setattr(app, "_staff_chain_advancing", True)
        except Exception:
            pass
        try:
            self.open_contract_negotiation(staff, is_hiring=False,
                                           on_done=_one_done)
        finally:
            try:
                if getattr(app, "_staff_chain_advancing", False):
                    app._staff_chain_advancing = False
            except Exception:
                pass

    def _chain_complete(self, results):
        """Land the chain: exactly-once digest, then clear all parked state.

        The session is consumed FIRST so re-entrant completions (resume
        with zero live staff, double callbacks) can never double-fire the
        digest. The park-time inbox notice and registry entry are cleared.
        """
        app = getattr(self, "app", None)
        try:
            sessions = getattr(app, "pending_sessions", None)
            sess = (sessions.pop(_CHAIN_SESSION_ID, None)
                    if isinstance(sessions, dict) else None)
        except Exception:
            sess = None
        try:
            from popup_system import unregister_pending_item
            unregister_pending_item(app, _CHAIN_ITEM_ID)
        except Exception:
            pass
        _clear_chain_notice(app, sess if isinstance(sess, dict) else None)
        try:
            refresher = getattr(app, "refresh_screen_navbar", None)
            if callable(refresher):
                refresher()
        except Exception:
            pass
        if results:
            # One inbox digest instead of a popup (FM24/EHM style).
            # Exactly-once: the identical digest may already be in the
            # inbox if _chain_complete re-enters (e.g. a late callback
            # racing completion) -- skip rather than double-post.
            content = ("Contract negotiations complete:\n" + "\n".join(
                f"• {r}" for r in results))
            already = False
            try:
                inbox = getattr(getattr(app, "user_team", None),
                                "inbox", None)
                for m in (getattr(inbox, "messages", None) or []):
                    if (getattr(m, "subject", "")
                            == "Staff Negotiation Results"
                            and getattr(m, "content", "") == content):
                        already = True
                        break
            except Exception:
                already = False
            if not already:
                try:
                    from game_classes import EmailMessage
                    from datetime import date
                    self.app.send_email_to_user(EmailMessage(
                        sender="System", sender_type="System",
                        date_sent=date.today(), category="Contracts",
                        priority=2,
                        subject="Staff Negotiation Results",
                        content=content))
                except Exception:
                    pass
        self.update_current_staff_view()

    def reassign_selected_staff(self):
        """Reassign roles for selected staff members."""
        if not self.selected_staff:
            messagebox.showwarning("No Selection", "Please select staff members to reassign.")
            return

        selected_staff_list = [s for s in self.get_current_team_staff() if s.id in self.selected_staff]

        if len(selected_staff_list) == 1:
            # Single staff - use detailed reassignment
            self.reassign_single_staff(selected_staff_list[0])
        else:
            # Multiple staff - bulk reassignment
            self.reassign_multiple_staff(selected_staff_list)

    def release_selected_staff(self):
        """Release selected staff members."""
        if not self.selected_staff:
            messagebox.showwarning("No Selection", "Please select staff members to release.")
            return

        selected_staff_list = [s for s in self.get_current_team_staff() if s.id in self.selected_staff]

        # Confirm release
        if len(selected_staff_list) == 1:
            staff_name = selected_staff_list[0].full_name
            msg = f"Are you sure you want to release {staff_name}?"
        else:
            msg = f"Are you sure you want to release {len(selected_staff_list)} staff members?"

        if not messagebox.askyesno("Confirm Release", msg):
            return

        user_team = self._get_user_team()
        if not user_team:
            return

        released_count = 0
        for staff in selected_staff_list:
            if staff in user_team.staff:
                user_team.staff.remove(staff)
                released_count += 1

        # Clear selection
        self.selected_staff.clear()

        messagebox.showinfo("Staff Released", f"Successfully released {released_count} staff member(s).")
        self.update_current_staff_view()

    # ------------------------------------------------------------------
    # Dialogs
    # ------------------------------------------------------------------
    def _dialog_card(self, parent, title):
        """Labeled card section inside a dialog; returns the inner frame."""
        ct = self._ct
        card = self._card(parent)
        card.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(card, text=title, font=self._sfont(11, 'bold'),
                     text_color=ct['TEXT'], anchor="w").pack(
                         anchor="w", padx=12, pady=(10, 4))
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=12, pady=(0, 10))
        return inner

    def _info_label(self, parent, text):
        ctk.CTkLabel(parent, text=text, font=self._sfont(10),
                     text_color=self._ct['TEXT_DIM'], anchor="w",
                     justify="left").pack(anchor="w", padx=4, pady=2)

    def show_staff_details_window(self, staff: Staff, is_current: bool):
        """Show detailed staff information window -- FM24-style tabs."""
        ct = self._ct
        details_window = InGamePopup(self)
        details_window.title(f"Staff Details - {staff.full_name}")
        details_window.configure(fg_color=ct['BG'])
        details_window.geometry("680x820")
        details_window.transient(self)

        # Fixed header
        header = ctk.CTkFrame(details_window, fg_color="transparent")
        header.pack(fill="x", padx=14, pady=(14, 4))
        self._heading(header, text=staff.full_name, size=18).pack(
            anchor="w", pady=(0, 2))
        ctk.CTkLabel(header,
                     text=f"{staff.role.value}  •  Rating {staff.overall_rating}",
                     font=self._sfont(11), text_color=ct['TEAL']).pack(
                         anchor="w", pady=(0, 4))
        # FM24-style identity line: coaching style, ambition, boyhood team
        self._staff_identity_line(header, staff, ct)

        # FM24-style tab strip
        tabbar = ctk.CTkFrame(details_window, fg_color="transparent")
        tabbar.pack(fill="x", padx=14, pady=(6, 0))
        tab_pages = {}
        tab_buttons = {}

        def switch_tab(name):
            for tname, page in tab_pages.items():
                if tname == name:
                    page.pack(fill="both", expand=True)
                else:
                    page.pack_forget()
            for tname, btn in tab_buttons.items():
                active = tname == name
                btn.configure(
                    text_color=ct['TEXT'] if active else ct['TEXT_DIM'],
                    fg_color=ct['CARD'] if active else "transparent")

        # Scrollable page host (a single scroll region; pages swap inside)
        pages_frame = ctk.CTkScrollableFrame(details_window,
                                             fg_color="transparent")
        pages_frame.pack(fill="both", expand=True, padx=14, pady=(6, 6))

        # -- Overview page ------------------------------------------------
        overview = ctk.CTkFrame(pages_frame, fg_color="transparent")
        info_inner = self._dialog_card(overview, "Basic Information")
        self._info_label(info_inner, f"Age: {staff.age}")
        self._info_label(info_inner, f"Nationality: {staff.nationality}")
        self._info_label(info_inner, f"Experience: {staff.experience} years")
        self._info_label(info_inner, f"Overall Rating: {staff.overall_rating}")
        self._info_label(info_inner, f"Reputation: {staff.reputation}")

        contract_inner = self._dialog_card(overview, "Contract Information")
        self._info_label(contract_inner, f"Salary: ${staff.salary:,}")
        self._info_label(contract_inner,
                         f"Contract Length: {staff.contract_years} years")

        desc_inner = self._dialog_card(overview, "Role Description")
        ctk.CTkLabel(desc_inner, text=staff.get_role_description(),
                     font=self._sfont(10), text_color=ct['TEXT_DIM'],
                     wraplength=580, justify="left",
                     anchor="w").pack(anchor="w", padx=4, pady=4)
        tab_pages["Overview"] = overview

        # -- Attributes page ----------------------------------------------
        attrs_page = ctk.CTkFrame(pages_frame, fg_color="transparent")
        attr_inner = self._dialog_card(attrs_page, "Attributes")
        self._staff_attribute_groups(attr_inner, staff, ct)
        tab_pages["Attributes"] = attrs_page

        # -- Standing page -------------------------------------------------
        standing_page = ctk.CTkFrame(pages_frame, fg_color="transparent")
        standing_inner = self._dialog_card(standing_page, "Standing")
        self._staff_standing_lines(standing_inner, staff, ct)

        impact_inner = self._dialog_card(standing_page, "On-Ice Impact")
        for line, kind in self._staff_impact_lines(staff):
            fg = {'ok': ct['GREEN'], 'warn': ct['GOLD'],
                  'info': ct['TEXT_FAINT']}.get(kind, ct['TEXT_FAINT'])
            ctk.CTkLabel(impact_inner, text=f"•  {line}",
                         font=self._sfont(9), text_color=fg,
                         wraplength=560, justify="left",
                         anchor="w").pack(anchor="w", padx=8, pady=2)
        tab_pages["Standing"] = standing_page

        # -- Personality page ----------------------------------------------
        personality_page = ctk.CTkFrame(pages_frame, fg_color="transparent")
        self._staff_personality_tab(personality_page, staff, ct)
        tab_pages["Personality"] = personality_page

        # -- Track Record page (scouts): the ledger, not the resume -----
        # -- Record page (coaches): year-by-year W/L, playoff results, and
        #    honours -- the hiring/firing evidence, for head coaches AND
        #    assistants.
        # -- Analytics page (directors): what the department behind the
        #    numbers actually does for the club.
        try:
            from game_classes import StaffRole as _SR
            _scout_roles = {_SR.HEAD_SCOUT, _SR.PROFESSIONAL_SCOUT,
                            _SR.AMATEUR_SCOUT, _SR.EUROPEAN_SCOUT}
            _is_scout = staff.role in _scout_roles
            _is_director = staff.role == _SR.ANALYTICS_DIRECTOR
            try:
                import coach_records as _crw
                _is_coach = _crw.is_coaching_role(staff)
            except Exception:
                _is_coach = False
        except Exception:
            _is_scout = _is_director = _is_coach = False
        if _is_coach:
            record_page = ctk.CTkFrame(pages_frame, fg_color="transparent")
            self._staff_coaching_record_tab(record_page, staff, ct)
            tab_pages["Record"] = record_page
        if _is_scout:
            track_page = ctk.CTkFrame(pages_frame, fg_color="transparent")
            self._staff_track_record_tab(track_page, staff, ct)
            tab_pages["Track Record"] = track_page
        if _is_director:
            analytics_page = ctk.CTkFrame(pages_frame,
                                          fg_color="transparent")
            self._staff_analytics_tab(analytics_page, staff, ct,
                                      is_current)
            tab_pages["Analytics"] = analytics_page

        _tab_widths = {"Overview": 89, "Attributes": 97, "Standing": 85,
                       "Personality": 104, "Track Record": 115,
                       "Analytics": 88, "Record": 78}
        for tname in tab_pages:
            btn = ctk.CTkButton(
                tabbar, text=tname, fg_color="transparent",
                text_color=ct['TEXT_DIM'], hover_color=ct['CARD'],
                font=self._sfont(11, 'bold'), corner_radius=8,
                width=_tab_widths.get(tname, 100),
                command=lambda n=tname: switch_tab(n))
            btn.pack(side="left", padx=(0, 2))
            tab_buttons[tname] = btn
        switch_tab("Overview")

        # Fixed button bar
        button_frame = ctk.CTkFrame(details_window, fg_color="transparent")
        button_frame.pack(fill="x", padx=14, pady=(0, 14))

        if is_current:
            self._secondary_button(button_frame, text="Negotiate Contract",
                                   command=lambda: self._negotiate_current_staff(staff, details_window),
                                   width=170, height=36).pack(side="left", padx=5)
            self._secondary_button(button_frame, text="Release",
                                   command=lambda: self.release_staff_action(staff, details_window),
                                   width=110, height=36).pack(side="left", padx=5)
        else:
            self._primary_button(button_frame, text="Make Offer",
                                 command=lambda: self.make_staff_offer_action(staff, details_window),
                                 width=130, height=36).pack(side="left", padx=5)

        self._secondary_button(button_frame, text="Close",
                               command=details_window.destroy,
                               width=110, height=36).pack(side="right", padx=5)

    def _staff_coaching_record_tab(self, parent, staff, ct):
        """Record page (head coaches AND assistants): year-by-year W-L-OTL,
        playoff result, and honours -- the hiring/firing evidence. Recorded
        at every season rollover by coach_records; empty for coaches hired
        mid-save before their first rollover.
        """
        try:
            import coach_records as _cr
            import accolades as _acc
        except Exception:
            _cr = _acc = None
        record = list(getattr(staff, "career_record", None) or [])

        totals_inner = self._dialog_card(parent, "Career Totals")
        if _cr is not None:
            t = _cr.career_totals(record)
            self._info_label(
                totals_inner,
                f"Record: {t['w']}-{t['l']}-{t['otl']}  "
                f"({t['win_pct']:.3f}) over {t['seasons']} seasons")
            self._info_label(
                totals_inner,
                f"Stanley Cups: {t['cups']}   Jack Adams Awards: {t['adams']}")

        honours_inner = self._dialog_card(parent, "Honours")
        honours = _acc.group_accolades(staff) if _acc is not None else []
        if honours:
            for label, years in honours:
                self._info_label(
                    honours_inner,
                    f"{label} Winner: {', '.join(years)}")
        else:
            self._info_label(honours_inner, "No honours banked yet.")

        hist_inner = self._dialog_card(parent, "Season by Season")
        if not record:
            self._info_label(
                hist_inner,
                "No completed seasons on record yet -- the first entry "
                "lands at season rollover.")
            return
        cols = ("Season", "Team", "Role", "W-L-OTL", "Playoffs", "Award")
        widths = (10, 22, 16, 10, 24, 12)
        header = ctk.CTkFrame(hist_inner, fg_color="transparent")
        header.pack(fill="x", padx=4, pady=(2, 4))
        for i, c in enumerate(cols):
            ctk.CTkLabel(header, text=c, font=self._sfont(9, "bold"),
                         text_color=ct["TEXT_DIM"], anchor="w",
                         width=widths[i] * 7).grid(row=0, column=i,
                                                   sticky="w", padx=2)
        for e in reversed(record):
            if not isinstance(e, dict):
                continue
            row = ctk.CTkFrame(hist_inner, fg_color="transparent")
            row.pack(fill="x", padx=4, pady=1)
            vals = (
                str(e.get("season", "?")),
                str(e.get("team", "?"))[:26],
                str(e.get("role", "?"))[:18],
                f"{e.get('w', 0)}-{e.get('l', 0)}-{e.get('otl', 0)}",
                str(e.get("playoff", "?"))[:28],
                "\U0001f3c6" if e.get("jack_adams") else "",
            )
            cup = e.get("playoff") == "Won Stanley Cup"
            fg = ct["GOLD"] if (cup or e.get("jack_adams")) else ct["TEXT"]
            for i, v in enumerate(vals):
                ctk.CTkLabel(row, text=v, font=self._sfont(9),
                             text_color=fg, anchor="w",
                             width=widths[i] * 7).grid(
                                 row=0, column=i, sticky="w", padx=2)

    def _staff_track_record_tab(self, parent, staff, ct):
        """Track Record page: graded calls, hit rate, recent history, and
        how a scout's validated finds (and misses) ripple through the
        club -- GM respect, player confidence, fan buzz, and the scout's
        own job security. The record is what you judge a scout by;
        hidden ability never appears.
        """
        import analytics_scouting as _as
        try:
            _as.ensure_analytics_fields(staff)
            record_line = _as.scout_record_line(staff)
            history = list(getattr(staff, "tip_history", []) or [])
        except Exception:
            record_line = "no graded calls yet"
            history = []
        inner = self._dialog_card(parent, "Scout Track Record")
        ctk.CTkLabel(inner, text=f"Graded calls: {record_line}",
                     font=self._sfont(12, 'bold'), text_color=ct['TEXT'],
                     anchor="w").pack(anchor="w", padx=8, pady=(4, 2))
        ctk.CTkLabel(
            inner,
            text=("Every read this scout files is graded against what happens "
                  "next. A validated breakout banks the club: GM respect up, "
                  "the player's confidence up, fan buzz, and the scout's name "
                  "in lights. A miss plants doubt -- and clubs fire scouts "
                  "under 40% on 10+ graded calls."),
            font=self._sfont(10), text_color=ct['TEXT_DIM'],
            wraplength=560, justify="left", anchor="w").pack(
                anchor="w", padx=8, pady=(0, 6))
        if history:
            hist_inner = self._dialog_card(parent, "Recent Reads")
            for h in list(reversed(history[-8:])):
                try:
                    kind = h.get("kind", "")
                    res = h.get("result", "?")
                    pname = h.get("player_name", h.get("player", "?"))
                    hdate = h.get("date", "")
                    mark = ("✓" if res == "hit" else "✗"
                            if res == "miss" else "·")
                    color = (ct['GREEN'] if res == "hit"
                             else ct['RED'] if res == "miss"
                             else ct['TEXT_DIM'])
                    row = ctk.CTkFrame(hist_inner, fg_color="transparent")
                    row.pack(fill="x", padx=8, pady=1)
                    ctk.CTkLabel(row, text=mark,
                                 font=self._sfont(10, 'bold'),
                                 text_color=color, width=18).pack(side="left")
                    ctk.CTkLabel(row,
                                 text=f"{pname} — {kind} read, {hdate}",
                                 font=self._sfont(10),
                                 text_color=ct['TEXT'],
                                 anchor="w").pack(side="left")
                except Exception:
                    pass
        else:
            ctk.CTkLabel(inner, text="No graded reads yet -- a blank ledger.",
                         font=self._sfont(10), text_color=ct['TEXT_DIM'],
                         anchor="w").pack(anchor="w", padx=8, pady=(0, 4))

    def _staff_analytics_tab(self, parent, staff, ct, is_current):
        """Analytics page: what this director's department does for the
        club's numbers -- sharper models, fresher data, tighter
        confidence intervals. Display only; never player outcomes.
        """
        import analytics_scouting as _as
        import advanced_metrics as _am
        try:
            personal = _as.analytics_director_quality(staff)
            tier = _as.department_tier_label(personal)
        except Exception:
            personal, tier = 35, "Thin analytics department"
        inner = self._dialog_card(parent, "Analytics Department")
        if is_current:
            try:
                team = getattr(getattr(self, "app", None),
                               "game_manager", None)
                team = getattr(team, "user_team", None)
                club_q = int(getattr(team, "analytics_quality",
                                     personal) or personal)
            except Exception:
                club_q = personal
            line = (f"Club department quality: {club_q}/100 -- {tier}. "
                    f"Models rebuild every "
                    f"{_am.department_refresh_days(club_q)} days.")
        else:
            line = (f"Would run your department at {personal}/100 -- {tier}.")
        ctk.CTkLabel(inner, text=line,
                     font=self._sfont(12, 'bold'), text_color=ct['TEAL'],
                     wraplength=560, justify="left", anchor="w").pack(
                         anchor="w", padx=8, pady=(4, 2))
        ctk.CTkLabel(
            inner,
            text=("A better department sharpens the picture, never the "
                  "players: tighter confidence intervals on modeled metrics, "
                  "fresher model snapshots, less visible noise. Box-score "
                  "facts stay exact at every tier; awards, sim outcomes and "
                  "development never touch this. Hire the director, upgrade "
                  "the lens."),
            font=self._sfont(10), text_color=ct['TEXT_DIM'],
            wraplength=560, justify="left", anchor="w").pack(
                anchor="w", padx=8, pady=(0, 6))

    def _staff_personality_tab(self, parent, staff, ct):
        """Personality page: coaching style writeup, ambition, control style,
        management manner -- who he is behind the bench."""
        import reputation_system as rs
        inner = self._dialog_card(parent, "Personality")
        try:
            style = rs.coach_style(staff)
            ctk.CTkLabel(inner, text=style.get("label", "Balanced"),
                         font=self._sfont(13, 'bold'),
                         text_color=ct['TEAL'], anchor="w").pack(
                             anchor="w", padx=8, pady=(4, 2))
            if style.get("description"):
                ctk.CTkLabel(inner, text=style["description"],
                             font=self._sfont(10), text_color=ct['TEXT_DIM'],
                             wraplength=560, justify="left",
                             anchor="w").pack(anchor="w", padx=8, pady=2)
        except Exception:
            pass
        ambition_text = {
            "stanley_cup": "Burning to win the Stanley Cup.",
            "climb": "Climbing -- wants a bigger chair.",
            "developer": "Lives to develop young players.",
            "hometown": "Dreams of coaching his hometown team.",
            "lifer": "A lifer -- happy wherever the game takes him.",
        }.get(str(getattr(staff, "ambition", "") or ""), "")
        lines = []
        if ambition_text:
            lines.append(f"Ambition: {ambition_text}")
        fav = getattr(staff, "favorite_team", None)
        if fav:
            lines.append(f"Boyhood team: {fav}")
        try:
            cn = float(getattr(staff, "control_need", 50))
            if cn >= 75:
                lines.append("Runs the room his way -- needs full control.")
            elif cn >= 45:
                lines.append("Comfortable sharing the room with his staff.")
            else:
                lines.append("Collaborative -- delegates freely to assistants.")
        except Exception:
            pass
        try:
            mot = float(getattr(staff, "motivating", 50))
            disc = float(getattr(staff, "discipline", 50))
            if mot >= 75 and disc >= 75:
                lines.append("Demanding and inspiring in equal measure.")
            elif mot >= 75 and disc < 60:
                lines.append("An arm-around-the-shoulder motivator.")
            elif disc >= 75 and mot < 60:
                lines.append("A demanding disciplinarian.")
            elif mot < 45 and disc < 45:
                lines.append("Hands-off -- lets the leaders run the room.")
        except Exception:
            pass
        for line in lines:
            ctk.CTkLabel(inner, text=f"\u2022  {line}", font=self._sfont(10),
                         text_color=ct['TEXT_FAINT'], wraplength=560,
                         justify="left", anchor="w").pack(
                             anchor="w", padx=8, pady=2)

    # ------------------------------------------------------------------
    # FM24-style staff card sections
    # ------------------------------------------------------------------
    _STAFF_ATTR_GROUPS = [
        ("Coaching", ["coaching_forwards", "coaching_defensemen",
                      "coaching_goalies", "attacking_coaching",
                      "defensive_coaching", "technical_coaching",
                      "mental_coaching"]),
        ("Tactical", ["tactical_knowledge", "game_preparation",
                      "match_preparation"]),
        ("Development", ["working_with_youngsters", "player_development",
                         "judging_player_ability", "judging_player_potential"]),
        ("Management", ["man_management", "motivating", "discipline",
                        "level_of_discipline", "media_handling"]),
        ("Personality", ["leadership", "determination", "adaptability"]),
    ]

    def _staff_identity_line(self, parent, staff, ct):
        """FM24-style identity line: coaching style, ambition, boyhood team."""
        import reputation_system as rs
        bits = []
        try:
            if "COACH" in str(getattr(getattr(staff, "role", None), "name", "")):
                style = rs.coach_style(staff)
                label = style.get("label") if isinstance(style, dict) else None
                if label:
                    bits.append(label)
        except Exception:
            pass
        amb = getattr(staff, "ambition", None)
        if amb:
            bits.append(str(amb).replace("_", " ").title())
        fav = getattr(staff, "favorite_team", None)
        if fav:
            bits.append(f"Boyhood: {fav}")
        cn = getattr(staff, "control_need", None)
        if cn is not None:
            try:
                cn = float(cn)
                bits.append("Authoritarian" if cn >= 70 else
                            "Collaborative" if cn <= 35 else "Balanced control")
            except Exception:
                pass
        ctk.CTkLabel(parent,
                     text="   •   ".join(bits) if bits else "",
                     font=self._sfont(10), text_color=ct['TEXT_DIM'],
                     anchor="w").pack(anchor="w", pady=(0, 12))

    def _attr_bar_ctk(self, parent, label, value, max_val=100):
        """Single attribute bar on the native 1-100 scale."""
        ct = self._ct
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=2)
        ctk.CTkLabel(row, text=label, font=self._sfont(10),
                     text_color=ct['TEXT_DIM'], width=130,
                     anchor="w").pack(side="left")
        bar = ctk.CTkProgressBar(row, width=110, height=8,
                                 progress_color=ct['TEAL'])
        bar.pack(side="left", padx=(4, 8))
        try:
            bar.set(max(0.0, min(1.0, float(value) / max_val)))
            vtext = str(int(value))
        except Exception:
            bar.set(0.0)
            vtext = "?"
        ctk.CTkLabel(row, text=vtext, font=self._sfont(10, 'bold'),
                     text_color=ct['TEXT'], width=28,
                     anchor="e").pack(side="left")

    def _staff_attribute_groups(self, parent, staff, ct):
        """FM24-style grouped attribute bars (native 1-100 scale)."""
        grid = ctk.CTkFrame(parent, fg_color="transparent")
        grid.pack(fill="x")
        for gi, (gname, fields) in enumerate(self._STAFF_ATTR_GROUPS):
            col = ctk.CTkFrame(grid, fg_color="transparent")
            col.grid(row=gi // 2, column=gi % 2, sticky="nsew", padx=(0, 18),
                     pady=(0, 10))
            ctk.CTkLabel(col, text=gname, font=self._sfont(10, 'bold'),
                         text_color=ct['TEAL'], anchor="w").pack(anchor="w",
                                                                 pady=(0, 4))
            for f in fields:
                if not hasattr(staff, f):
                    continue
                self._attr_bar_ctk(col, f.replace("_", " ").title(),
                                   getattr(staff, f), 100)
        grid.grid_columnconfigure(0, weight=1)
        grid.grid_columnconfigure(1, weight=1)

    def _staff_standing_lines(self, parent, staff, ct):
        """Room standing, GM trust, control, assistant effectiveness."""
        import reputation_system as rs
        lines = []
        try:
            st = rs.room_status(staff)
            if isinstance(st, dict):
                level = st.get("level", "Secure")
                risk = float(st.get("risk", 0.0) or 0.0)
                kind = "warn" if risk >= 0.45 else "info"
                lines.append((f"Room standing: {level} "
                              f"({risk:.0%} losing-the-room risk)", kind))
        except Exception:
            pass
        try:
            if str(getattr(getattr(staff, "role", None), "name", "")) == "HEAD_COACH":
                lines.append((f"GM trust: {getattr(staff, 'gm_trust', 70)}/100",
                              "info"))
        except Exception:
            pass
        try:
            eff = getattr(staff, "assistant_effect", None)
            if eff:
                lines.append((f"Assistant effectiveness: {float(eff):.0f}",
                              "ok"))
        except Exception:
            pass
        try:
            cn = getattr(staff, "control_need", None)
            if cn is not None:
                lines.append((f"Control need: {float(cn):.0f}/100", "info"))
        except Exception:
            pass
        if not lines:
            lines.append(("No standing data recorded.", "info"))
        for text, kind in lines:
            fg = {"ok": ct["GREEN"], "warn": ct["GOLD"],
                  "info": ct["TEXT_FAINT"]}.get(kind, ct["TEXT_FAINT"])
            ctk.CTkLabel(parent, text=f"•  {text}", font=self._sfont(10),
                         text_color=fg, wraplength=560, justify="left",
                         anchor="w").pack(anchor="w", padx=8, pady=2)

    def _negotiate_current_staff(self, staff: Staff, details_window):
        """Negotiate with a current staffer from the details window.

        Gating Phase 2: non-modal screen; the result arrives via on_done.
        """
        def _on_done(accepted):
            if not accepted:
                return
            # Result lands in the inbox (FM24/EHM style), not a popup.
            try:
                from game_classes import EmailMessage
                from datetime import date
                self.app.send_email_to_user(EmailMessage(
                    sender="System", sender_type="System",
                    date_sent=date.today(), category="Contracts", priority=2,
                    subject=f"Staff re-signed: {staff.full_name}",
                    content=(f"Contract renegotiated with {staff.full_name} "
                             f"({staff.role.value}).")))
            except Exception:
                pass
            try:
                details_window.destroy()
            except Exception:
                pass
            self.update_views()

        self.open_contract_negotiation(staff, is_hiring=False,
                                       on_done=_on_done)

    def format_staff_attributes(self, staff: Staff) -> str:
        """Format staff attributes for display."""
        attr_text = "COACHING ATTRIBUTES:\n"
        attr_text += f"Coaching Forwards: {staff.coaching_forwards}\n"
        attr_text += f"Coaching Defensemen: {staff.coaching_defensemen}\n"
        attr_text += f"Coaching Goalies: {staff.coaching_goalies}\n\n"

        attr_text += "TACTICAL KNOWLEDGE:\n"
        attr_text += f"Tactical Knowledge: {staff.tactical_knowledge}\n"
        attr_text += f"Game Preparation: {staff.game_preparation}\n"
        attr_text += f"Match Preparation: {staff.match_preparation}\n\n"

        attr_text += "PLAYER DEVELOPMENT:\n"
        attr_text += f"Working with Youngsters: {staff.working_with_youngsters}\n"
        attr_text += f"Player Development: {staff.player_development}\n\n"

        attr_text += "MANAGEMENT SKILLS:\n"
        attr_text += f"Man Management: {staff.man_management}\n"
        attr_text += f"Motivating: {staff.motivating}\n"
        attr_text += f"Discipline: {staff.discipline}\n\n"

        attr_text += "SCOUTING ABILITIES:\n"
        attr_text += f"Judging Player Ability: {staff.judging_player_ability}\n"
        attr_text += f"Judging Player Potential: {staff.judging_player_potential}\n\n"

        attr_text += "COMMUNICATION:\n"
        attr_text += f"Media Handling: {staff.media_handling}\n"
        attr_text += f"Determination: {staff.determination}\n"
        attr_text += f"Adaptability: {staff.adaptability}\n\n"

        attr_text += "SPECIALIZED COACHING:\n"
        attr_text += f"Level of Discipline: {staff.level_of_discipline}\n"
        attr_text += f"Attacking Coaching: {staff.attacking_coaching}\n"
        attr_text += f"Defensive Coaching: {staff.defensive_coaching}\n"
        attr_text += f"Mental Coaching: {staff.mental_coaching}\n"
        attr_text += f"Technical Coaching: {staff.technical_coaching}\n"

        return attr_text

    def open_contract_negotiation(self, staff: Staff, is_hiring: bool = False,
                                    on_done=None):
        """Route staff contract negotiation to the StaffContractView screen.

        Gating Phase 2: the modal InGamePopup (grab_set + wait_window) is
        gone. The negotiation is a non-modal screen shift; the outcome
        arrives via on_done(accepted: bool) -- True on agreement, False on
        cancel/dismiss. is_hiring=True runs the hire flow; is_hiring=False
        renegotiates an existing staffer's terms (same mechanics as the
        old dialog: demands + offer + staff.negotiate_contract roll).
        Half-typed offers live in app.pending_sessions (Tier B,
        write-through) so navigating away never loses them.
        """
        from windows import StaffContractView
        app = getattr(self, "app", None)
        if app is None or not hasattr(app, "show_screen"):
            # Headless/legacy fallback: keep the old honesty contract.
            try:
                from popup_system import messagebox
                messagebox.showwarning(
                    "Negotiation unavailable",
                    "Staff contract negotiation needs the app screen host.")
            except Exception:
                pass
            if callable(on_done):
                try:
                    on_done(False)
                except Exception:
                    pass
            return None
        title = (f"Contract Offer - {staff.full_name}" if is_hiring
                 else f"Contract Negotiation - {staff.full_name}")
        return app.show_screen("staff_contract", title, StaffContractView,
                               staff, fresh=True, hire_source="free_agent",
                               renegotiate=not is_hiring, on_done=on_done)

    def release_staff_action(self, staff: Staff, details_window=None):
        """Perform staff release action."""
        result = messagebox.askyesno("Confirm Release",
                                    f"Are you sure you want to release {staff.full_name}?\n"
                                    f"This will end their contract immediately.")

        if result:
            user_team = self._get_user_team()
            if user_team and staff in user_team.staff:
                user_team.staff.remove(staff)
                messagebox.showinfo("Staff Released", f"{staff.full_name} has been released.")

                if details_window:
                    details_window.destroy()

                self.update_views()

    def make_staff_offer_action(self, staff: Staff, details_window=None):
        """Make offer to a hiring candidate.

        Gating Phase 2: routes to the StaffContractView screen; the hire
        result arrives via on_done.
        """
        if details_window:
            details_window.destroy()

        def _on_done(accepted):
            if accepted:
                messagebox.showinfo("Success",
                                    f"{staff.full_name} has been hired!")
                self.update_views()

        self.open_contract_negotiation(staff, is_hiring=True,
                                       on_done=_on_done)

    def categorize_staff(self, staff_list):
        """Categorize staff by their roles for filtering."""
        categories = {
            'Management': [],
            'Coaching': [],
            'Development': [],
            'Scouting': [],
            'Medical': [],
            'Analytics': []
        }

        role_categories = {
            # Management
            StaffRole.GENERAL_MANAGER: 'Management',
            StaffRole.ASSISTANT_GENERAL_MANAGER: 'Management',

            # Coaching
            StaffRole.HEAD_COACH: 'Coaching',
            StaffRole.ASSISTANT_COACH: 'Coaching',
            StaffRole.ASSOCIATE_COACH: 'Coaching',
            StaffRole.GOALIE_COACH: 'Coaching',
            StaffRole.POWER_PLAY_COACH: 'Coaching',
            StaffRole.PENALTY_KILL_COACH: 'Coaching',

            # Development
            StaffRole.SKILLS_COACH: 'Development',
            StaffRole.CONDITIONING_COACH: 'Development',
            StaffRole.SKATING_COACH: 'Development',
            StaffRole.STRENGTH_COACH: 'Development',

            # Scouting
            StaffRole.HEAD_SCOUT: 'Scouting',
            StaffRole.PROFESSIONAL_SCOUT: 'Scouting',
            StaffRole.AMATEUR_SCOUT: 'Scouting',
            StaffRole.EUROPEAN_SCOUT: 'Scouting',
            StaffRole.ADVANCE_SCOUT: 'Scouting',

            # Medical
            StaffRole.TEAM_DOCTOR: 'Medical',
            StaffRole.PHYSIOTHERAPIST: 'Medical',
            StaffRole.EQUIPMENT_MANAGER: 'Medical',

            # Analytics
            StaffRole.VIDEO_COACH: 'Analytics',
            StaffRole.STATISTICIAN: 'Analytics',
            StaffRole.MEDIA_RELATIONS: 'Analytics'
        }

        for staff in staff_list:
            category = role_categories.get(staff.role, 'Other')
            if category in categories:
                categories[category].append(staff)
            else:
                # Add to Analytics if no specific category
                categories[category].append(staff) if category in categories else categories['Analytics'].append(staff)

        return categories

    def show_multiple_staff_summary(self):
        """Show summary window for multiple selected staff."""
        ct = self._ct
        selected_staff_list = [s for s in self.get_current_team_staff() if s.id in self.selected_staff]

        summary_window = InGamePopup(self)
        summary_window.title(f"Selected Staff Summary ({len(selected_staff_list)} staff)")
        summary_window.configure(fg_color=ct['BG'])
        summary_window.geometry("600x520")
        summary_window.transient(self)

        main_frame = ctk.CTkFrame(summary_window, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=18, pady=18)

        self._heading(main_frame,
                      text=f"Selected Staff Summary ({len(selected_staff_list)} staff)",
                      size=14).pack(anchor="w", pady=(0, 12))

        text_widget = ctk.CTkTextbox(
            main_frame, wrap="word", font=self._sfont(11),
            fg_color=ct['PANEL'], text_color=ct['TEXT'],
            border_color=ct['BORDER'], border_width=1, corner_radius=8)
        text_widget.pack(fill="both", expand=True)

        # Generate summary content
        summary_content = "SELECTED STAFF SUMMARY\n"
        summary_content += "=" * 30 + "\n\n"

        total_salary = sum(s.salary for s in selected_staff_list)
        avg_rating = sum(s.overall_rating for s in selected_staff_list) / len(selected_staff_list)
        avg_experience = sum(s.experience for s in selected_staff_list) / len(selected_staff_list)

        summary_content += f"Total Selected: {len(selected_staff_list)}\n"
        summary_content += f"Combined Salary: ${total_salary:,}\n"
        summary_content += f"Average Rating: {avg_rating:.1f}\n"
        summary_content += f"Average Experience: {avg_experience:.1f} years\n\n"

        # Department breakdown
        departments = {}
        for staff in selected_staff_list:
            dept = self.get_staff_department(staff)
            if dept not in departments:
                departments[dept] = []
            departments[dept].append(staff)

        summary_content += "DEPARTMENT BREAKDOWN\n"
        summary_content += "-" * 20 + "\n"
        for dept, staff_list in departments.items():
            summary_content += f"{dept}: {len(staff_list)} staff\n"

        summary_content += "\nSTAFF DETAILS\n"
        summary_content += "-" * 20 + "\n"
        for staff in sorted(selected_staff_list, key=lambda s: s.role.value):
            morale = getattr(staff, 'morale', 10)
            summary_content += f"• {staff.full_name} ({staff.role.value})\n"
            summary_content += f"  Rating: {staff.overall_rating} | Salary: ${staff.salary:,} | Morale: {morale}/100\n\n"

        text_widget.insert('1.0', summary_content)
        text_widget.configure(state='disabled')

        # Close button
        self._secondary_button(main_frame, text="Close",
                               command=summary_window.destroy,
                               width=110, height=36).pack(pady=10)

    def reassign_single_staff(self, staff):
        """Reassign role for a single staff member."""
        ct = self._ct
        reassign_window = InGamePopup(self)
        reassign_window.title(f"Reassign {staff.full_name}")
        reassign_window.configure(fg_color=ct['BG'])
        reassign_window.geometry("420x340")
        reassign_window.transient(self)

        main_frame = ctk.CTkFrame(reassign_window, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=18, pady=18)

        self._heading(main_frame, text=f"Reassign {staff.full_name}",
                      size=14).pack(anchor="w", pady=(0, 6))
        ctk.CTkLabel(main_frame, text=f"Current Role: {staff.role.value}",
                     font=self._sfont(10), text_color=ct['TEXT_DIM']).pack(
                         anchor="w", pady=(0, 12))

        ctk.CTkLabel(main_frame, text="New Role:",
                     font=self._sfont(10), text_color=ct['TEXT_DIM']).pack(anchor='w')
        # Every reassignable role is listed (not just the current one); the
        # unique-role guard (GM / Head Coach) runs at confirm time.
        role_combo = ctk.CTkComboBox(
            main_frame, values=[role.value for role in StaffRole],
            state='readonly',
            fg_color=ct['CARD'], border_color=ct['BORDER'],
            button_color=ct['PANEL'], button_hover_color=ct['BORDER'],
            dropdown_fg_color=ct['PANEL'], dropdown_text_color=ct['TEXT'],
            dropdown_hover_color=ct['ROW_HOVER'], text_color=ct['TEXT'])
        role_combo.set("Select new role\u2026")
        role_combo.pack(fill='x', pady=(4, 0))

        def confirm_reassignment():
            new_role_name = role_combo.get()
            new_role = next((role for role in StaffRole if role.value == new_role_name), None)

            if new_role and new_role != staff.role:
                # Guard unique roles (e.g. only one Head Coach / GM)
                if Staff.is_unique_role(new_role):
                    team = self._get_user_team()
                    conflict = [s for s in (team.staff if team else [])
                                if s.role == new_role and s.id != staff.id]
                    if conflict:
                        messagebox.showerror(
                            "Role Conflict",
                            f"Team already has a {new_role.value}: {conflict[0].full_name}.\n"
                            f"Reassign or release them first.")
                        return
                staff.role = new_role
                messagebox.showinfo("Success", f"{staff.full_name} has been reassigned to {new_role.value}")
                reassign_window.destroy()
                self.update_current_staff_view()
            else:
                messagebox.showwarning("No Change", "Please select a different role.")

        button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        button_frame.pack(fill='x', pady=20)

        self._primary_button(button_frame, text="Confirm",
                             command=confirm_reassignment,
                             width=120, height=36).pack(side='left', padx=5)
        self._secondary_button(button_frame, text="Cancel",
                               command=reassign_window.destroy,
                               width=110, height=36).pack(side='right', padx=5)

    def reassign_multiple_staff(self, staff_list):
        """Reassign roles for multiple staff members."""
        ct = self._ct
        reassign_window = InGamePopup(self)
        reassign_window.title(f"Bulk Reassign ({len(staff_list)} staff)")
        reassign_window.configure(fg_color=ct['BG'])
        reassign_window.geometry("620x520")
        reassign_window.transient(self)

        main_frame = ctk.CTkFrame(reassign_window, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=18, pady=18)

        self._heading(main_frame,
                      text=f"Bulk Reassign {len(staff_list)} Staff Members",
                      size=14).pack(anchor="w", pady=(0, 12))

        # Scrollable list of staff with role dropdowns (CTkScrollableFrame)
        scroll = ctk.CTkScrollableFrame(main_frame, fg_color=ct['PANEL'],
                                        corner_radius=10)
        scroll.pack(fill="both", expand=True)

        # Role selection for each staff member
        role_combos = {}
        for staff in staff_list:
            staff_frame = ctk.CTkFrame(scroll, fg_color="transparent")
            staff_frame.pack(fill='x', pady=5, padx=10)

            ctk.CTkLabel(staff_frame, text=f"{staff.full_name}:",
                         font=self._sfont(10),
                         text_color=ct['TEXT']).pack(side='left')

            role_combo = ctk.CTkComboBox(
                staff_frame, values=[role.value for role in StaffRole],
                state='readonly', width=200,
                fg_color=ct['CARD'], border_color=ct['BORDER'],
                button_color=ct['PANEL'], button_hover_color=ct['BORDER'],
                dropdown_fg_color=ct['PANEL'], dropdown_text_color=ct['TEXT'],
                dropdown_hover_color=ct['ROW_HOVER'], text_color=ct['TEXT'])
            # Neutral prompt: the full role list is one click away, and the
            # closed combo no longer reads as "only the current role".
            role_combo.set("Select new role\u2026")
            role_combo.pack(side='right')
            role_combos[staff.id] = role_combo

        def apply_reassignments():
            # Resolve requested roles first, then validate unique roles across
            # the whole team before applying anything.
            new_roles = {}
            for staff in staff_list:
                new_role_name = role_combos[staff.id].get()
                new_role = next((role for role in StaffRole if role.value == new_role_name), None)
                new_roles[staff.id] = new_role if new_role else staff.role

            team = self._get_user_team()
            team_staff = team.staff if team else []
            for role in StaffRole:
                if Staff.is_unique_role(role):
                    holders = [s for s in team_staff
                               if new_roles.get(s.id, s.role) == role]
                    if len(holders) > 1:
                        names = ", ".join(h.full_name for h in holders)
                        messagebox.showerror(
                            "Role Conflict",
                            f"Only one {role.value} is allowed.\nConflicting: {names}.")
                        return

            changes_made = 0
            for staff in staff_list:
                if new_roles[staff.id] != staff.role:
                    staff.role = new_roles[staff.id]
                    changes_made += 1

            if changes_made > 0:
                messagebox.showinfo("Success", f"Reassigned {changes_made} staff member(s)")
                reassign_window.destroy()
                self.update_current_staff_view()
            else:
                messagebox.showinfo("No Changes", "No role changes were made.")

        button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        button_frame.pack(fill='x', pady=10)

        self._primary_button(button_frame, text="Apply Changes",
                             command=apply_reassignments,
                             width=150, height=36).pack(side='left', padx=5)
        self._secondary_button(button_frame, text="Cancel",
                               command=reassign_window.destroy,
                               width=110, height=36).pack(side='right', padx=5)

    def _report_window(self, title, content):
        """Shared modern scrollable-text dialog used by the report/chart views."""
        ct = self._ct
        win = InGamePopup(self)
        win.title(title)
        win.configure(fg_color=ct['BG'])
        win.geometry("800x620")
        win.transient(self)

        main_frame = ctk.CTkFrame(win, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=18, pady=18)

        self._heading(main_frame, text=title, size=14).pack(anchor="w",
                                                           pady=(0, 12))

        text_widget = ctk.CTkTextbox(
            main_frame, wrap="word", font=self._sfont(11),
            fg_color=ct['PANEL'], text_color=ct['TEXT'],
            border_color=ct['BORDER'], border_width=1, corner_radius=8)
        text_widget.pack(fill="both", expand=True)

        text_widget.insert('1.0', content)
        text_widget.configure(state='disabled')

        # Close button
        self._secondary_button(main_frame, text="Close",
                               command=win.destroy,
                               width=110, height=36).pack(pady=10)

    def show_staff_report(self):
        """Show comprehensive staff report."""
        user_team = self._get_user_team()
        if not user_team:
            return

        self._report_window(f"{user_team.team_name} Staff Report",
                            self.generate_staff_report(user_team))

    def show_organizational_chart(self):
        """Show organizational chart of current staff."""
        user_team = self._get_user_team()
        if not user_team:
            return

        self._report_window(f"{user_team.team_name} Organizational Chart",
                            self.generate_organizational_chart(user_team))

    def generate_staff_report(self, team):
        """Generate comprehensive staff report."""
        staff_categories = self.categorize_staff(team.staff)

        report = f"{team.team_name} Staff Analysis Report\n"
        report += "=" * 50 + "\n\n"

        # Overall summary
        total_staff = len(team.staff)
        total_salary = sum(staff.salary for staff in team.staff)
        avg_experience = sum(staff.experience for staff in team.staff) / total_staff if total_staff > 0 else 0
        avg_overall = sum(staff.overall_rating for staff in team.staff) / total_staff if total_staff > 0 else 0

        report += f"EXECUTIVE SUMMARY\n"
        report += f"Total Staff: {total_staff}\n"
        report += f"Total Salary: ${total_salary:,}\n"
        report += f"Average Experience: {avg_experience:.1f} years\n"
        report += f"Average Overall Rating: {avg_overall:.1f}\n\n"

        # Department breakdown
        for category, staff_list in staff_categories.items():
            if staff_list:
                report += f"{category.upper()} DEPARTMENT\n"
                report += "-" * 30 + "\n"

                for staff in sorted(staff_list, key=lambda s: s.overall_rating, reverse=True):
                    morale = getattr(staff, 'morale', 10)
                    status = self.get_staff_status(staff)
                    report += f"• {staff.full_name} ({staff.role.value})\n"
                    report += f"  Overall: {staff.overall_rating} | Experience: {staff.experience}y | Morale: {morale}/100\n"
                    report += f"  Salary: ${staff.salary:,} | Contract: {staff.contract_years}y | Status: {status}\n\n"

                dept_avg = sum(s.overall_rating for s in staff_list) / len(staff_list)
                dept_salary = sum(s.salary for s in staff_list)
                report += f"Department Average: {dept_avg:.1f} | Department Salary: ${dept_salary:,}\n\n"

        # Contract expiration analysis
        expiring_staff = [staff for staff in team.staff if staff.contract_years <= 1]
        if expiring_staff:
            report += "CONTRACT EXPIRATIONS\n"
            report += "-" * 30 + "\n"
            for staff in expiring_staff:
                report += f"• {staff.full_name} ({staff.role.value}) - {staff.contract_years} year(s) remaining\n"
            report += "\n"

        return report

    def generate_organizational_chart(self, team):
        """Generate organizational chart text."""
        debug_print(f"DEBUG: Generating org chart for {team.team_name}")
        debug_print(f"DEBUG: Team has {len(team.staff)} staff members")

        staff_categories = self.categorize_staff(team.staff)
        debug_print(f"DEBUG: Staff categories: {[(k, len(v)) for k, v in staff_categories.items()]}")

        chart = f"{team.team_name} Organizational Chart\n"
        chart += "=" * 50 + "\n\n"

        # If no staff, show empty message
        if not team.staff:
            chart += "No staff members currently employed.\n"
            return chart

        # Management hierarchy
        if staff_categories['Management']:
            chart += "MANAGEMENT\n"
            chart += "├── General Manager\n"
            gm_staff = [s for s in staff_categories['Management'] if s.role == StaffRole.GENERAL_MANAGER]
            if gm_staff:
                chart += f"│   └── {gm_staff[0].full_name}\n"

            chart += "└── Assistant General Manager\n"
            agm_staff = [s for s in staff_categories['Management'] if s.role == StaffRole.ASSISTANT_GENERAL_MANAGER]
            for agm in agm_staff:
                chart += f"    └── {agm.full_name}\n"
            chart += "\n"

        # Coaching staff
        if staff_categories['Coaching']:
            chart += "COACHING STAFF\n"
            chart += "├── Head Coach\n"
            hc_staff = [s for s in staff_categories['Coaching'] if s.role == StaffRole.HEAD_COACH]
            if hc_staff:
                chart += f"│   └── {hc_staff[0].full_name}\n"

            chart += "├── Assistant Coaches\n"
            asst_coaches = [s for s in staff_categories['Coaching'] if s.role in [StaffRole.ASSISTANT_COACH, StaffRole.ASSOCIATE_COACH]]
            for coach in asst_coaches:
                chart += f"│   ├── {coach.full_name} ({coach.role.value})\n"

            chart += "└── Specialized Coaches\n"
            spec_coaches = [s for s in staff_categories['Coaching'] if s.role in [StaffRole.GOALIE_COACH, StaffRole.POWER_PLAY_COACH, StaffRole.PENALTY_KILL_COACH]]
            for coach in spec_coaches:
                chart += f"    ├── {coach.full_name} ({coach.role.value})\n"
            chart += "\n"

        # Other departments
        for dept_name in ['Development', 'Scouting', 'Medical', 'Analytics']:
            if staff_categories[dept_name]:
                chart += f"{dept_name.upper()}\n"
                for staff in staff_categories[dept_name]:
                    chart += f"├── {staff.full_name} ({staff.role.value})\n"
                chart += "\n"

        return chart

class StaffManagementWindow(InGamePopup):
    """Popup wrapper around StaffManagementView (backward compatibility)."""
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent)
        self.title("Staff Management - Hockey Manager")
        self._view = StaffManagementView(self, app=parent, *args, **kwargs)
        self._view._close_screen = self.destroy
        self._view.pack(fill="both", expand=True)
    def __getattr__(self, name):
        view = self.__dict__.get("_view")
        if view is not None:
            try:
                return getattr(view, name)
            except AttributeError:
                pass
        return InGamePopup.__getattr__(self, name)
