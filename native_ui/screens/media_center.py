"""Media Center screen: native Qt port.

Ports main.py media_center_window.MediaCenterView (held back from the
Sept 27 merge; web-ui only had references in news.py).

Sections:
  - Journalists: media_engine reporters with relationship descriptors
  - Press conferences: pending media events as interactive cards
    (Handle Interview / Skip / Auto-Handle) backed by the real MediaSystem
  - Narratives & beefs: league.media_narratives, coach_media_beefs
  - Fines ledger: league.media_fines (same source as the fines tab)

Interactive features (Team F):
  - Engagement slider: DISABLED / MINIMAL / STANDARD / FULL, session-only
    (MediaSystem.engagement_level is not serialized by save_load_system,
    so it resets to DISABLED on load).
  - InterviewView (QDialog): open a media event, see the questions, pick
    one of 6 response styles with a live answer preview, then give the
    interview or skip it. Resolution flows through the real
    MediaSystem.handle_media_response.

Game data used (all real):
  - media_system.MediaSystem on the game manager: pending events,
    engagement level, gm_reputation, journalist relationships, morale
  - media_engine: ensure_media_state, reporters_for, Reporter
  - league.media_narratives, league.coach_media_beefs, league.media_fines

Backend quirk this file works around (media_system.py is owned by another
team and intentionally not touched): MediaSystem.handle_media_response and
_apply_media_consequences are dict-shaped only (they do
``event['status'] = ...`` / ``event.get(...)``), but pending_events holds
MediaEvent dataclasses, so the backend call raises before applying any
consequences. _resolve_event catches that and applies the identical
consequence math via the normalized view, so responses genuinely move
gm_reputation, journalist relationships and morale. Flagged for the
media_system owner to fix at the source.
"""
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QFrame, QGroupBox, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QMessageBox, QPushButton, QRadioButton,
    QScrollArea, QSlider, QTabWidget, QTableWidget, QTableWidgetItem,
    QTextEdit, QVBoxLayout, QWidget,
)
from PySide6.QtCore import Qt

from ..dialogs import modal as _modal
from .base import BaseScreen


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def _resolve_gm(game):
    return _safe(lambda: getattr(game, "game_manager", None)) or game


def _media_system(gm):
    """Resolve (or lazily create) the MediaSystem for this game manager."""
    ms = _safe(lambda: getattr(gm, "media_system", None))
    if ms is not None:
        return ms
    try:
        import media_system as _msys
        ms = _msys.MediaSystem(gm)
        try:
            gm.media_system = ms
        except Exception:
            pass
        return ms
    except Exception:
        return None


def _engagement_levels():
    import media_system as _msys
    return [
        _msys.MediaEngagementLevel.DISABLED,
        _msys.MediaEngagementLevel.MINIMAL,
        _msys.MediaEngagementLevel.STANDARD,
        _msys.MediaEngagementLevel.FULL,
    ]


_ENGAGEMENT_DESCRIPTIONS = {
    "Disabled": "Media system disabled. Focus on pure hockey management!",
    "Minimal": "Minimal coverage. Major events only (trades, big signings).",
    "Standard": "Standard coverage. Pre/post-game interviews included.",
    "Full Immersion": "Full immersion. Complete storyline experience!",
}

# Response styles offered in the interview dialog, ported from mainline
# media_center_window.InterviewView.
_RESPONSE_STYLES = [
    ("professional", "Professional",
     "Balanced, diplomatic responses"),
    ("supportive", "Supportive",
     "Back your players and organization"),
    ("confident", "Confident",
     "Express strong confidence in team direction"),
    ("diplomatic", "Diplomatic",
     "Avoid controversy, redirect questions"),
    ("honest", "Brutally Honest",
     "Tell it like it is, consequences be damned"),
    ("dismissive", "Dismissive",
     "Short answers, show irritation"),
]

# Sample answers per style, ported from mainline InterviewView
# (what the preview pane shows before the user commits).
_SAMPLE_RESPONSES = {
    "professional": [
        "We're focused on continuing to improve as a team.",
        "I have confidence in our players and our system.",
        "We'll evaluate our options and make the best decisions for "
        "the organization.",
    ],
    "supportive": [
        "I couldn't be prouder of how our guys competed tonight.",
        "This group has tremendous character and we believe in them.",
        "Our players give everything they have every single night.",
    ],
    "confident": [
        "We know exactly where we're headed and we're excited about it.",
        "This team has what it takes to compete at the highest level.",
        "We're building something special here.",
    ],
    "diplomatic": [
        "That's something we'll discuss internally.",
        "Our focus remains on the next game and getting better each day.",
        "We prefer to keep those conversations private.",
    ],
    "honest": [
        "Look, we didn't execute tonight and that's on everyone.",
        "Some tough decisions need to be made if we want to win.",
        "The results speak for themselves - we need to be better.",
    ],
    "dismissive": [
        "Next question.",
        "We've addressed this already.",
        "I'm not getting into that.",
    ],
}

_IMPACT_MESSAGES = {
    "low": "Your response was noted by the media.",
    "medium": "Your response will be discussed in tomorrow's coverage.",
    "high": "Your response is making headlines across the hockey world.",
}


def _is_completed(event):
    """True when the backend already considers this event resolved."""
    if event is None:
        return True
    if isinstance(event, dict):
        return (event.get("status") == "completed"
                or bool(event.get("completed")))
    return bool(_safe(lambda: getattr(event, "completed", False), False))


def _mark_completed(event, response_choice):
    """Force-complete an event on either backend shape."""
    if isinstance(event, dict):
        try:
            event["status"] = "completed"
            event["response"] = response_choice
        except Exception:
            pass
    else:
        try:
            event.completed = True
        except Exception:
            pass
        try:
            event.response = response_choice
        except Exception:
            pass


class InterviewView(QDialog):
    """Interactive interview for a media event (native port of mainline
    InterviewView).

    Shows the journalist context, the questions, six response styles with
    a live answer preview, and Give Interview / Skip / Cancel actions.
    """

    def __init__(self, screen, event, view=None, parent=None):
        super().__init__(parent)
        self._screen = screen
        self._event = event
        self._view = (view if view is not None
                      else screen._event_view(event))
        self.setWindowTitle("Media Interview")
        self.setMinimumWidth(560)
        self.setMinimumHeight(520)
        self._radios = []
        self._build()
        self._refresh_preview()
        self.set_response_style("professional")

    # -- public API (also used by tests) ---------------------------------
    def response_styles(self):
        return list(_RESPONSE_STYLES)

    def current_style(self):
        for value, _rb in self._radios:
            if _rb.isChecked():
                return value
        return "professional"

    def set_response_style(self, value):
        for v, rb in self._radios:
            rb.setChecked(v == value)
        self._refresh_preview()

    def preview_for(self, style):
        questions = self._view.get("questions") or []
        samples = _SAMPLE_RESPONSES.get(
            style, _SAMPLE_RESPONSES["professional"])
        if not questions:
            return (f"Response Style: {style.title()}\n\n"
                    f"{samples[0]}")
        lines = [f"Response Style: {style.title()}", "=" * 40, ""]
        for i, q in enumerate(questions, 1):
            lines.append(f"Q{i}: {q}")
            lines.append("")
            lines.append(f"A{i}: {samples[min(i - 1, len(samples) - 1)]}")
            lines.append("")
            lines.append("-" * 40)
            lines.append("")
        return "\n".join(lines)

    def current_preview_text(self):
        return self._preview.toPlainText()

    # -- construction -----------------------------------------------------
    def _build(self):
        layout = QVBoxLayout(self)
        view = self._view

        journalist = view.get("journalist")
        if journalist is not None:
            name = getattr(journalist, "name", "?")
            outlet = getattr(journalist, "outlet", "?")
            jtype = _safe(
                lambda: journalist.type.value, "?")
            header = QLabel(f"{name} ({outlet}) — {jtype}")
            header.setStyleSheet("font-weight: bold; font-size: 14px;")
            layout.addWidget(header)
            rel = _safe(lambda: int(getattr(journalist, "relationship", 0)),
                        0)
            rel_lbl = QLabel(f"Relationship: {rel:+d}")
            rel_lbl.setStyleSheet("color: #8b95ab;")
            layout.addWidget(rel_lbl)

        ctx = self._screen._event_context(view)
        if ctx:
            ctx_lbl = QLabel(ctx)
            ctx_lbl.setStyleSheet("color: #8b95ab; font-style: italic;")
            ctx_lbl.setWordWrap(True)
            layout.addWidget(ctx_lbl)

        q_lbl = QLabel("Interview Questions")
        q_lbl.setStyleSheet("font-weight: bold;")
        layout.addWidget(q_lbl)
        self._questions = QTextEdit()
        self._questions.setReadOnly(True)
        questions = view.get("questions") or []
        self._questions.setPlainText(
            "\n\n".join(f"Q{i}: {q}" for i, q in enumerate(questions, 1))
            or "No questions available.")
        self._questions.setMaximumHeight(140)
        layout.addWidget(self._questions)

        style_box = QGroupBox("Choose Your Response Style")
        style_layout = QVBoxLayout(style_box)
        for value, label, desc in _RESPONSE_STYLES:
            row = QWidget()
            row_l = QHBoxLayout(row)
            row_l.setContentsMargins(0, 0, 0, 0)
            rb = QRadioButton(label)
            rb.setToolTip(desc)
            rb.toggled.connect(
                lambda checked, _rb=rb: self._on_radio_toggled(_rb,
                                                               checked))
            self._radios.append((value, rb))
            row_l.addWidget(rb)
            desc_lbl = QLabel(f"— {desc}")
            desc_lbl.setStyleSheet("color: #8b95ab; font-size: 11px;")
            row_l.addWidget(desc_lbl, 1)
            style_layout.addWidget(row)
        layout.addWidget(style_box)

        pv_lbl = QLabel("Answer Preview")
        pv_lbl.setStyleSheet("font-weight: bold;")
        layout.addWidget(pv_lbl)
        self._preview = QTextEdit()
        self._preview.setReadOnly(True)
        self._preview.setMaximumHeight(150)
        layout.addWidget(self._preview)

        btn_row = QHBoxLayout()
        self._preview_btn = QPushButton("Preview Answers")
        self._preview_btn.clicked.connect(self._refresh_preview)
        btn_row.addWidget(self._preview_btn)
        btn_row.addStretch(1)
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self._cancel_btn)
        if view.get("optional"):
            self._skip_btn = QPushButton("Skip Interview")
            self._skip_btn.clicked.connect(self._on_skip)
            btn_row.addWidget(self._skip_btn)
        else:
            self._skip_btn = None
        self._give_btn = QPushButton("Give Interview")
        self._give_btn.setDefault(True)
        self._give_btn.clicked.connect(self._on_give)
        btn_row.addWidget(self._give_btn)
        layout.addLayout(btn_row)

    def _on_radio_toggled(self, rb, checked):
        if checked:
            for _v, other in self._radios:
                if other is not rb and other.isChecked():
                    other.setChecked(False)
            self._refresh_preview()

    def _refresh_preview(self):
        self._preview.setPlainText(self.preview_for(self.current_style()))

    def _on_give(self):
        style = self.current_style()
        completed = self._screen._resolve_event(self._event, style)
        if completed:
            impact = self._view.get("impact_level", "low")
            _modal.information(
                self, "Interview Complete",
                "Interview completed successfully!\n\n"
                f"{_IMPACT_MESSAGES.get(impact, _IMPACT_MESSAGES['low'])}")
        else:
            _modal.information(
                self, "Interview Not Completed",
                "The interview could not be completed (no media system "
                "available or the event is no longer pending).")
        self.accept()

    def _on_skip(self):
        self._screen._skip_event(self._event)
        self.accept()


# Alias: the task names this feature InterviewView; InterviewDialog is the
# Qt-idiomatic name for the same modal window.
InterviewDialog = InterviewView


class MediaCenterScreen(BaseScreen):
    title = "Media Center"

    def _build_body(self):
        # --- Engagement bar (always visible, above the tabs) ---
        eng_box = QGroupBox("Media Engagement")
        eng_layout = QVBoxLayout(eng_box)
        slider_row = QHBoxLayout()
        slider_row.addWidget(QLabel("Off"))
        self._engagement_slider = QSlider(Qt.Horizontal)
        self._engagement_slider.setRange(0, 3)
        self._engagement_slider.setTickPosition(QSlider.TicksBelow)
        self._engagement_slider.setTickInterval(1)
        self._engagement_slider.valueChanged.connect(
            self._on_engagement_slider)
        slider_row.addWidget(self._engagement_slider, 1)
        slider_row.addWidget(QLabel("Full"))
        eng_layout.addLayout(slider_row)
        tick_row = QHBoxLayout()
        for label in ("Disabled", "Minimal", "Standard", "Full"):
            lab = QLabel(label)
            lab.setStyleSheet("color: #8b95ab; font-size: 10px;")
            lab.setAlignment(Qt.AlignCenter)
            tick_row.addWidget(lab, 1)
        eng_layout.addLayout(tick_row)
        self._engagement_desc = QLabel("")
        self._engagement_desc.setStyleSheet("color: #8b95ab;")
        self._engagement_desc.setWordWrap(True)
        eng_layout.addWidget(self._engagement_desc)
        opts_row = QHBoxLayout()
        self._auto_handle_check = QCheckBox("Auto-handle minor events")
        self._auto_handle_check.stateChanged.connect(
            self._on_auto_handle_change)
        opts_row.addWidget(self._auto_handle_check)
        opts_row.addStretch(1)
        self._skip_all_btn = QPushButton("Skip All Events")
        self._skip_all_btn.clicked.connect(self._skip_all_events)
        opts_row.addWidget(self._skip_all_btn)
        eng_layout.addLayout(opts_row)
        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet("color: #8b95ab; font-size: 11px;")
        eng_layout.addWidget(self._status_lbl)
        self._layout.addWidget(eng_box)
        self._syncing_engagement = False

        self.tabs = QTabWidget()
        self._layout.addWidget(self.tabs, 1)

        # --- Tab 1: Journalists ---
        j_page = QWidget()
        j_layout = QVBoxLayout(j_page)
        j_note = QLabel(
            "The press corps covering your team. Relationships affect "
            "how stories are written.")
        j_note.setStyleSheet("color: #8b95ab; font-size: 12px;")
        j_note.setWordWrap(True)
        j_layout.addWidget(j_note)
        self._journalist_table = QTableWidget()
        self._journalist_table.setColumnCount(4)
        self._journalist_table.setHorizontalHeaderLabels(
            ["Journalist", "Outlet", "Style", "Relationship"])
        self._journalist_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._journalist_table.setSelectionBehavior(QTableWidget.SelectRows)
        j_layout.addWidget(self._journalist_table, 1)
        self.tabs.addTab(j_page, "Journalists")

        # --- Tab 2: Press Conferences ---
        pc_page = QWidget()
        pc_layout = QVBoxLayout(pc_page)
        self._events_scroll = QScrollArea()
        self._events_scroll.setWidgetResizable(True)
        self._events_container = QWidget()
        self._events_layout = QVBoxLayout(self._events_container)
        self._events_layout.setAlignment(Qt.AlignTop)
        self._events_scroll.setWidget(self._events_container)
        pc_layout.addWidget(self._events_scroll, 1)
        self.tabs.addTab(pc_page, "Press Conferences")
        self._event_cards = []

        # --- Tab 3: Narratives ---
        n_page = QWidget()
        n_layout = QVBoxLayout(n_page)
        self._narr_list = QListWidget()
        n_layout.addWidget(self._narr_list, 1)
        self.tabs.addTab(n_page, "Narratives")

        # --- Tab 4: Fines ---
        f_page = QWidget()
        f_layout = QVBoxLayout(f_page)
        self._fines_table = QTableWidget()
        self._fines_table.setColumnCount(4)
        self._fines_table.setHorizontalHeaderLabels(
            ["Date", "Player/Staff", "Amount", "Reason"])
        self._fines_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._fines_table.setSelectionBehavior(QTableWidget.SelectRows)
        f_layout.addWidget(self._fines_table, 1)
        self.tabs.addTab(f_page, "Fines")

    # ------------------------------------------------------------------
    # Event helpers
    # ------------------------------------------------------------------
    def _event_view(self, event):
        """Return a uniform dict-like view of a pending media event.

        media_system.py is inconsistent internally: ``get_pending_media_events``
        yields ``MediaEvent`` dataclasses (attribute access), while
        ``handle_media_response`` treats events as dicts (item access), and
        ``_generate_post_game_media_event``-style events are plain dicts.
        Normalize here (media_system.py is intentionally not touched) so the
        UI never crashes on either shape.
        """
        if event is None:
            return {"type": "media_event", "journalist": None,
                    "questions": [], "optional": True,
                    "impact_level": "low", "details": {}}
        if isinstance(event, dict):
            return dict(event)
        ms = _media_system(_resolve_gm(self.game))
        details = _safe(lambda: getattr(event, "details", None), None) or {}
        questions = []
        if ms is not None and hasattr(ms, "get_interview_questions"):
            try:
                questions = ms.get_interview_questions(event) or []
            except Exception:
                questions = []
        importance = _safe(lambda: getattr(event, "importance", 5), 5) or 5
        return {
            "type": _safe(lambda: getattr(event, "type", "media_event"),
                          "media_event"),
            "journalist": details.get("journalist"),
            "questions": questions,
            "optional": bool(
                _safe(lambda: getattr(event, "auto_handled", False), False)),
            "impact_level": ("low" if importance < 4 else
                             "medium" if importance < 7 else "high"),
            "details": details,
        }

    @staticmethod
    def _event_context(view):
        """One-line context for an interview, ported from mainline."""
        event_type = view.get("type", "")
        if event_type == "post_game_interview":
            game_result = view.get("game_result", {}) or {}
            if game_result.get("won", False):
                return "Post-game interview following your team's victory"
            return "Post-game interview following your team's loss"
        if event_type == "trade_announcement":
            return "Press conference to discuss recent trade"
        if event_type == "contract_signing":
            player = view.get("player")
            if player:
                name = getattr(player, "full_name",
                               getattr(player, "name", "?"))
                return f"Media availability regarding {name}'s contract"
        return "Media availability"

    def _apply_media_consequences(self, view, response_choice, ms):
        """Apply response consequences via the normalized view.

        Mirrors MediaSystem._apply_media_consequences exactly; used when the
        backend's dict-shaped handler raises on MediaEvent dataclasses so
        the response still moves game state.
        """
        impact_level = view.get("impact_level", "low")

        # GM reputation
        reputation_change = 0
        if response_choice in ["professional", "thoughtful", "diplomatic"]:
            reputation_change = 1 if impact_level == "low" else 2
        elif response_choice in ["dismissive", "hostile", "controversial"]:
            reputation_change = -1 if impact_level == "low" else -3
        ms.gm_reputation = max(
            0, min(100, ms.gm_reputation + reputation_change))

        # Journalist relationship
        journalist = view.get("journalist")
        if journalist is not None:
            try:
                if response_choice in ["professional", "thoughtful"]:
                    journalist.relationship = min(
                        10, journalist.relationship + 1)
                elif response_choice in ["dismissive", "hostile"]:
                    journalist.relationship = max(
                        -10, journalist.relationship - 1)
            except Exception:
                pass

        # Team morale (only matters for medium/high impact stories)
        if impact_level in ["medium", "high"]:
            morale_change = 0
            if response_choice in ["supportive", "confident"]:
                morale_change = 5
            elif response_choice in ["uncertain", "critical"]:
                morale_change = -5
            if morale_change:
                team = _safe(
                    lambda: getattr(ms.game_manager, "user_team", None))
                for player in _safe(
                        lambda: list(getattr(team, "roster", None) or []),
                        []) if team is not None else []:
                    if hasattr(player, "morale"):
                        try:
                            player.morale = max(
                                1, min(100, player.morale + morale_change))
                        except Exception:
                            pass

    def _run_press_cascade(self, event, response_choice, ms):
        """Dressing-room cascade the backend runs for dict events only."""
        try:
            import dressing_room as _dr
            team = _safe(lambda: getattr(ms.game_manager, "user_team", None))
            if team is not None:
                _dr.cascade_on_press(team, event, response_choice)
        except Exception:
            pass

    def _resolve_event(self, event, response_choice):
        """Resolve a pending event with the given response style.

        Returns True when the event ended up completed. Safe to call on an
        already-completed event (no-op) or with no media system (False).
        """
        if event is None:
            return False
        ms = _media_system(_resolve_gm(self.game))
        if ms is None:
            return False
        if _is_completed(event):
            return False
        view = self._event_view(event)
        disabled = False
        try:
            import media_system as _msys
            disabled = (ms.engagement_level
                        is _msys.MediaEngagementLevel.DISABLED)
        except Exception:
            pass
        try:
            ms.handle_media_response(event, response_choice)
        except Exception:
            # Dict-shaped backend raises on MediaEvent dataclasses; the
            # fallback below completes the event and applies consequences.
            pass
        if not _is_completed(event):
            # Backend is dict-shaped only and raised on this MediaEvent
            # dataclass before doing anything. Apply the same consequences
            # via the normalized view so the response genuinely changes
            # game state, then force-complete the event.
            if response_choice != "skipped" and not disabled:
                self._apply_media_consequences(view, response_choice, ms)
                self._run_press_cascade(event, response_choice, ms)
            _mark_completed(event, response_choice)
        try:
            self.refresh()
        except Exception:
            pass
        return True

    def _skip_event(self, event):
        """Skip a specific event: resolved as skipped, no state changes."""
        return self._resolve_event(event, "skipped")

    def _auto_handle_event(self, event):
        """Auto-handle an event with a professional response."""
        if self._resolve_event(event, "professional"):
            _modal.information(self, "Event Handled",
                               "Interview handled with professional "
                               "responses.")

    def _handle_event(self, event, view=None):
        """Open the interactive interview dialog for an event."""
        if event is None or _is_completed(event):
            return
        dlg = InterviewView(self, event,
                            view if view is not None
                            else self._event_view(event),
                            parent=self)
        _modal.exec_dialog(dlg)
        try:
            self.refresh()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Engagement controls
    # ------------------------------------------------------------------
    def _on_engagement_slider(self, value):
        """Engagement slider moved: sync the new level to the MediaSystem
        (session-only; not serialized into saves)."""
        if self._syncing_engagement:
            return
        try:
            pos = max(0, min(3, int(value)))
        except (TypeError, ValueError):
            return
        ms = _media_system(_resolve_gm(self.game))
        if ms is None:
            return
        level = _engagement_levels()[pos]
        if ms.engagement_level is not level:
            ms.set_engagement_level(level)
        try:
            self._engagement_desc.setText(
                _ENGAGEMENT_DESCRIPTIONS.get(level.value, ""))
        except Exception:
            pass
        try:
            self.refresh()
        except Exception:
            pass

    def _on_auto_handle_change(self, _state=None):
        ms = _media_system(_resolve_gm(self.game))
        if ms is not None:
            try:
                ms.auto_handle_minor_events = bool(
                    self._auto_handle_check.isChecked())
            except Exception:
                pass

    def _skip_all_events(self):
        """Skip every pending event (auto-handled professionally)."""
        ms = _media_system(_resolve_gm(self.game))
        if ms is None:
            return
        pending = _safe(lambda: list(ms.get_pending_media_events()), [])
        if not pending:
            _modal.information(self, "No Events",
                               "There are no pending media events.")
            return
        ans = _modal.question(
            self, "Skip All Events",
            f"Skip all {len(pending)} pending media events?\n\n"
            "They will be auto-handled professionally.")
        if ans != QMessageBox.Yes:
            return
        # NOTE: backend skip_all_pending_events() calls the dict-shaped
        # handle_media_response, which raises on MediaEvent dataclasses
        # before marking them complete. Resolve each event through our own
        # path instead so nothing is left stuck pending.
        for event in list(pending):
            try:
                self._resolve_event(event, "professional")
            except Exception:
                continue
        _modal.information(self, "Events Skipped",
                           f"All {len(pending)} events handled "
                           "professionally.")

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------
    @staticmethod
    def _relationship_descriptor(rel):
        try:
            r = float(rel)
        except (TypeError, ValueError):
            return str(rel or "—")
        if r >= 70:
            return "Friendly"
        if r >= 40:
            return "Neutral"
        return "Hostile"

    def _sync_engagement_controls(self, ms):
        self._syncing_engagement = True
        try:
            levels = _engagement_levels()
            try:
                pos = levels.index(ms.engagement_level)
            except ValueError:
                pos = 2
            self._engagement_slider.setValue(pos)
            level_value = _safe(lambda: ms.engagement_level.value,
                                str(ms.engagement_level))
            self._engagement_desc.setText(
                _ENGAGEMENT_DESCRIPTIONS.get(level_value, ""))
            self._auto_handle_check.setChecked(
                bool(getattr(ms, "auto_handle_minor_events", True)))
            status = _safe(lambda: ms.get_system_status(), {}) or {}
            self._status_lbl.setText(
                f"Level: {status.get('engagement_level', '?')} | "
                f"Pending: {status.get('pending_events', 0)} | "
                f"Reputation: {status.get('gm_reputation', '?')}/100")
        finally:
            self._syncing_engagement = False

    def _rebuild_event_cards(self, ms):
        for card in self._event_cards:
            try:
                card["frame"].deleteLater()
            except Exception:
                pass
        self._event_cards = []
        # Drop the placeholder empty-state label if present
        while self._events_layout.count():
            item = self._events_layout.takeAt(0)
            w = item.widget() if hasattr(item, "widget") else None
            if w is not None:
                w.deleteLater()

        pending = _safe(lambda: list(ms.get_pending_media_events()), [])
        if not pending:
            note = ("Media system disabled — no events will be generated."
                    if _safe(lambda: ms.engagement_level.value) == "Disabled"
                    else "No pending media events.\nEvents will appear here "
                         "based on your engagement level and recent team "
                         "activities.")
            empty = QLabel(note)
            empty.setStyleSheet("color: #8b95ab;")
            empty.setWordWrap(True)
            empty.setAlignment(Qt.AlignCenter)
            self._events_layout.addWidget(empty)
            return

        for event in pending[:50]:
            view = self._event_view(event)
            frame = QFrame()
            frame.setFrameShape(QFrame.Box)
            card_l = QVBoxLayout(frame)

            header_row = QHBoxLayout()
            event_type = str(view.get("type", "media_event")).replace(
                "_", " ").title()
            title = QLabel(event_type)
            title.setStyleSheet("font-weight: bold; font-size: 13px;")
            header_row.addWidget(title)
            header_row.addStretch(1)
            if view.get("optional"):
                badge = QLabel("OPTIONAL")
                badge.setStyleSheet("color: #4CAF50; font-weight: bold;")
            else:
                badge = QLabel("REQUIRED")
                badge.setStyleSheet("color: #FF5722; font-weight: bold;")
            header_row.addWidget(badge)
            card_l.addLayout(header_row)

            journalist = view.get("journalist")
            if journalist is not None:
                jname = getattr(journalist, "name", "?")
                joutlet = getattr(journalist, "outlet", "?")
                jtype = _safe(lambda: journalist.type.value, "")
                rel = _safe(lambda: int(getattr(journalist,
                                                "relationship", 0)), 0)
                j_lbl = QLabel(f"{jname} ({joutlet})"
                               + (f" — {jtype}" if jtype else ""))
                j_lbl.setStyleSheet("color: #FFB300;")
                j_lbl.setWordWrap(True)
                card_l.addWidget(j_lbl)
                rel_lbl = QLabel(f"Relationship: {rel:+d}")
                rel_lbl.setStyleSheet("color: #8b95ab; font-size: 11px;")
                card_l.addWidget(rel_lbl)

            questions = view.get("questions") or []
            if questions:
                q_head = QLabel("Questions:")
                q_head.setStyleSheet("color: #8b95ab;")
                card_l.addWidget(q_head)
                for i, q in enumerate(questions[:2], 1):
                    ql = QLabel(f"{i}. {q}")
                    ql.setWordWrap(True)
                    card_l.addWidget(ql)
                if len(questions) > 2:
                    more = QLabel(f"+ {len(questions) - 2} more questions...")
                    more.setStyleSheet("color: #8b95ab; font-size: 10px;")
                    card_l.addWidget(more)

            btn_row = QHBoxLayout()
            buttons = []
            handle_btn = QPushButton("Handle Interview")
            handle_btn.clicked.connect(
                lambda _checked=False, e=event, v=view:
                self._handle_event(e, v))
            btn_row.addWidget(handle_btn)
            buttons.append(handle_btn)
            if view.get("optional"):
                skip_btn = QPushButton("Skip Interview")
                skip_btn.clicked.connect(
                    lambda _checked=False, e=event: self._skip_event(e))
                btn_row.addWidget(skip_btn)
                buttons.append(skip_btn)
            auto_btn = QPushButton("Auto-Handle")
            auto_btn.clicked.connect(
                lambda _checked=False, e=event: self._auto_handle_event(e))
            btn_row.addWidget(auto_btn)
            buttons.append(auto_btn)
            btn_row.addStretch(1)
            card_l.addLayout(btn_row)

            self._events_layout.addWidget(frame)
            self._event_cards.append({"frame": frame, "event": event,
                                      "view": view, "buttons": buttons})

    def refresh(self):
        gm = _resolve_gm(self.game)
        league = _safe(lambda: gm.league)
        team = _safe(lambda: gm.user_team)
        ms = _media_system(gm)

        # Ensure media state exists
        try:
            import media_engine as me
            if league is not None:
                me.ensure_media_state(league)
        except Exception:
            pass

        if ms is not None:
            self._sync_engagement_controls(ms)
            self._rebuild_event_cards(ms)
        else:
            self._status_lbl.setText("Media system unavailable.")

        # Journalists
        reporters = []
        try:
            import media_engine as me
            if hasattr(me, "reporters_for") and team is not None:
                reporters = me.reporters_for(team) or []
            elif league is not None:
                reporters = _safe(
                    lambda: list(getattr(league, "reporters", None) or []), [])
        except Exception:
            pass
        if not reporters and ms is not None:
            reporters = _safe(lambda: list(ms.journalists or []), [])
        self._journalist_table.setRowCount(len(reporters))
        for i, r in enumerate(reporters):
            self._journalist_table.setItem(
                i, 0, QTableWidgetItem(
                    getattr(r, "name", str(r))))
            self._journalist_table.setItem(
                i, 1, QTableWidgetItem(
                    getattr(r, "outlet", getattr(r, "publication", "—"))))
            self._journalist_table.setItem(
                i, 2, QTableWidgetItem(
                    getattr(r, "style", getattr(r, "bias", "—"))))
            rel = getattr(r, "relationship", getattr(r, "rapport", None))
            self._journalist_table.setItem(
                i, 3, QTableWidgetItem(
                    self._relationship_descriptor(rel)))

        # Narratives & beefs
        self._narr_list.clear()
        narrs = _safe(lambda: list(
            getattr(league, "media_narratives", None) or []), []) \
            if league is not None else []
        beefs = _safe(lambda: list(
            getattr(league, "coach_media_beefs", None) or []), []) \
            if league is not None else []
        for n in narrs:
            title = getattr(n, "title", getattr(n, "headline", str(n)))
            self._narr_list.addItem(f"📰 {title}")
        for b in beefs:
            self._narr_list.addItem(f"🥩 {b}")
        if not narrs and not beefs:
            self._narr_list.addItem("No active storylines.")

        # Fines ledger
        fines = _safe(lambda: list(
            getattr(league, "media_fines", None) or []), []) \
            if league is not None else []
        self._fines_table.setRowCount(len(fines))
        for i, f in enumerate(fines):
            if isinstance(f, dict):
                date = str(f.get("date", "—"))
                who = str(f.get("player", f.get("name", "—")))
                amt = f.get("amount", 0)
                reason = str(f.get("reason", "—"))
            else:
                date = str(getattr(f, "date", "—"))
                who = str(getattr(f, "player", getattr(f, "name", "—")))
                amt = getattr(f, "amount", 0)
                reason = str(getattr(f, "reason", "—"))
            try:
                amt_s = f"${int(amt):,}"
            except (TypeError, ValueError):
                amt_s = str(amt)
            self._fines_table.setItem(i, 0, QTableWidgetItem(date))
            self._fines_table.setItem(i, 1, QTableWidgetItem(who))
            self._fines_table.setItem(i, 2, QTableWidgetItem(amt_s))
            self._fines_table.setItem(i, 3, QTableWidgetItem(reason))
