"""Season Meeting screen (native Qt).

Pre-season conversation with the head coach to agree on expectations,
rookie stance, tactics, and line ownership. Produces a stored season
mandate via coach_season_meeting.store_mandate.

Mirrors coach_meeting_window.SeasonMeetingView (Tkinter) stage-for-stage:
opening -> expectations -> rookies -> tactics -> lines -> tactics_own
-> deployer -> closing -> done.
"""

import random

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame,
)
from PySide6.QtCore import Qt

from .base import BaseScreen


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


class SeasonMeetingScreen(BaseScreen):
    """Qt port of the Tkinter SeasonMeetingView."""

    title = "Season Meeting"

    STAGES = ["opening", "expectations", "rookies", "tactics",
              "lines", "tactics_own", "deployer", "closing", "done"]

    def __init__(self, game, main_window, parent=None):
        self._transcript_layout = None
        self._transcript_inner = None
        self._prompt_label = None
        self._options_layout = None
        self._options_inner = None
        self._rng = random.Random()
        self.draft = {}
        self.team = None
        self.coach = None
        self._board_exp = None
        super().__init__(game, main_window, parent)

    # ------------------------------------------------------------------
    # game access
    # ------------------------------------------------------------------
    def _gm(self):
        return getattr(self.game, "game_manager", None) or self.game

    def _user_team(self):
        gm = self._gm()
        return (_safe(lambda: getattr(gm, "user_team", None))
                or _safe(lambda: getattr(self.game, "user_team", None)))

    # ------------------------------------------------------------------
    # layout
    # ------------------------------------------------------------------
    def _build_body(self):
        self.team = self._user_team()
        self._load_draft()

        # Header
        header = QLabel("SEASON MEETING")
        header.setStyleSheet("font-size: 20px; font-weight: 800; "
                             "letter-spacing: 2px; color: #f0c75e;")
        self._layout.addWidget(header)

        sub = QLabel("Sit down with your head coach and agree on the season.")
        sub.setStyleSheet("color: #9aa4b8; font-size: 13px;")
        sub.setWordWrap(True)
        self._layout.addWidget(sub)

        # Transcript (scrollable)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setMinimumHeight(300)
        self._transcript_inner = QWidget()
        self._transcript_layout = QVBoxLayout(self._transcript_inner)
        self._transcript_layout.setSpacing(8)
        self._transcript_layout.addStretch()
        scroll.setWidget(self._transcript_inner)
        self._layout.addWidget(scroll, 1)

        # Prompt
        self._prompt_label = QLabel("")
        self._prompt_label.setWordWrap(True)
        self._prompt_label.setStyleSheet("font-size: 14px; font-weight: 700; "
                                         "color: #e8eaf0; padding: 8px 0;")
        self._layout.addWidget(self._prompt_label)

        # Options
        opt_scroll = QScrollArea()
        opt_scroll.setWidgetResizable(True)
        opt_scroll.setFrameShape(QFrame.NoFrame)
        opt_scroll.setMaximumHeight(220)
        self._options_inner = QWidget()
        self._options_layout = QVBoxLayout(self._options_inner)
        self._options_layout.setSpacing(6)
        opt_scroll.setWidget(self._options_inner)
        self._layout.addWidget(opt_scroll)

        # Initialize
        self._init_meeting()

    def _init_meeting(self):
        """Set up team/coach and start or resume the conversation."""
        try:
            from coach_meeting_window import (
                _get_head_coach, _coach_name, _board_expectation,
                _meeting_reason, _opening_line, coach_assessment,
            )
            from coach_season_meeting import is_meeting_pending
        except ImportError:
            self._show_degraded("Meeting system unavailable.")
            return

        if self.team is None:
            self._show_degraded("No team loaded.")
            return

        self.coach = _safe(lambda: _get_head_coach(self.team))
        if self.coach is None:
            self._show_degraded("No head coach found.")
            return

        self._board_exp = _safe(lambda: _board_expectation(self._gm()))

        # Coach assessment
        if "coach_assessment" not in self.draft:
            self.draft["coach_assessment"] = _safe(
                lambda: coach_assessment(self.team, self.coach), "")
            self._persist()

        # Check if already done
        if not self.draft.get("opened"):
            if not _safe(lambda: is_meeting_pending(self.team), True):
                mandate = getattr(self.team, "season_mandate", None)
                if isinstance(mandate, dict) and mandate.get("meeting_done"):
                    self.draft["opened"] = True
                    self.draft["stage"] = "done"
                    self._persist()
                    self._render_all()
                    return
            self._log("coach", _safe(
                lambda: _opening_line(
                    self.coach, self._rng,
                    reason=_safe(lambda: _meeting_reason(self.team), "")),
                "Let's talk about the season."))
            self.draft["opened"] = True
            self.draft["stage"] = "opening"
            self._persist()

        self._render_all()

    def _show_degraded(self, msg):
        if self._prompt_label:
            self._prompt_label.setText(msg)

    # ------------------------------------------------------------------
    # draft persistence
    # ------------------------------------------------------------------
    def _load_draft(self):
        d = getattr(self.team, "season_meeting_draft", None) \
            if self.team else None
        if not isinstance(d, dict):
            d = {}
        self.draft = d
        self.draft.setdefault("stage", "opening")
        self.draft.setdefault("log", [])
        self.draft.setdefault("choices", {})
        self.draft.setdefault("notes", [])
        self._persist()

    def _persist(self):
        try:
            if self.team is not None:
                self.team.season_meeting_draft = self.draft
        except Exception:
            pass

    def _log(self, speaker, text, trust_delta=None):
        self.draft["log"].append(
            {"speaker": speaker, "text": text, "trust": trust_delta})
        self._persist()

    # ------------------------------------------------------------------
    # rendering
    # ------------------------------------------------------------------
    def _render_all(self):
        self._render_transcript()
        self._render_stage()

    def _render_transcript(self):
        if not self._transcript_layout:
            return
        # Clear (keep stretch at end)
        while self._transcript_layout.count() > 1:
            item = self._transcript_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        coach_name = _safe(lambda: self._coach_name(), "Coach")
        for entry in self.draft.get("log", []):
            speaker = entry.get("speaker", "")
            text = entry.get("text", "")
            if speaker == "coach":
                prefix, color = f"{coach_name}:", "#7fb3ff"
            elif speaker == "gm":
                prefix, color = "You:", "#f0c75e"
            else:
                prefix, color = "", "#9aa4b8"

            lbl = QLabel()
            if prefix:
                lbl.setText(f'<b style="color:{color};">{prefix}</b> {text}')
            else:
                lbl.setText(f'<i style="color:{color};">{text}</i>')
            lbl.setTextFormat(Qt.RichText)
            lbl.setWordWrap(True)
            lbl.setStyleSheet("font-size: 13px; color: #e8eaf0; "
                              "padding: 4px 0;")
            # Insert before stretch
            self._transcript_layout.insertWidget(
                self._transcript_layout.count() - 1, lbl)

    def _coach_name(self):
        try:
            from coach_meeting_window import _coach_name, _get_head_coach
            coach = _get_head_coach(self.team)
            return _coach_name(coach) or "Coach"
        except Exception:
            return "Coach"

    def _render_stage(self):
        stage = self.draft.get("stage", "opening")
        if stage == "done":
            self._render_done()
            return
        render = getattr(self, f"_stage_{stage}", None)
        if callable(render):
            render()
        else:
            # Unknown stage: fail forward to closing
            self._advance_to("closing")

    def _clear_options(self):
        if not self._options_layout:
            return
        while self._options_layout.count():
            item = self._options_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _option_button(self, label, callback):
        btn = QPushButton(label)
        btn.setObjectName("primary-btn")
        btn.setStyleSheet("text-align: left; padding: 10px 14px;")
        btn.clicked.connect(callback)
        self._options_layout.addWidget(btn)

    def _set_prompt(self, text):
        if self._prompt_label:
            self._prompt_label.setText(text)

    # ------------------------------------------------------------------
    # stages
    # ------------------------------------------------------------------
    def _stage_opening(self):
        self._set_prompt("The meeting is yours to run.")
        self._clear_options()
        self._option_button("Sit down and talk.",
                            lambda: self._choose("opening", "begin"))

    def _stage_expectations(self):
        self._set_prompt(
            "Set the season expectation. The menu is built from your "
            "roster's strength and the board's mandate.")
        self._clear_options()
        try:
            from coach_meeting_window import (
                _EXPECT_LABELS, expectation_options,
            )
            from coach_season_meeting import coach_assessment as _ca
            # expected_pace may not exist; use default
            pace = {}
            try:
                from coach_meeting_window import expected_pace
                pace = expected_pace()
            except ImportError:
                pass
            for rung in expectation_options(self.team, self._board_exp):
                label, desc = _EXPECT_LABELS.get(rung, (rung, ""))
                p = pace.get(rung, 0.55) if pace else 0.55
                self._option_button(
                    f"{label} -- {desc}  (~{p:.3f} pace)",
                    lambda r=rung: self._choose("expectations", r))
        except Exception as e:
            self._set_prompt(f"Error loading expectations: {e}")

    def _stage_rookies(self):
        self._set_prompt("Set the rookie playing-time stance.")
        self._clear_options()
        try:
            from coach_meeting_window import _ROOKIE_LABELS
            for key in ("heavy", "earned", "sheltered", "none"):
                label, desc = _ROOKIE_LABELS.get(key, (key, ""))
                self._option_button(
                    f"{label} -- {desc}",
                    lambda k=key: self._choose("rookies", k))
        except Exception as e:
            self._set_prompt(f"Error loading rookie options: {e}")

    def _stage_tactics(self):
        self._set_prompt(
            "Pick the tactical identity. The coach reacts to how well it "
            "fits the way he coaches.")
        self._clear_options()
        try:
            from coach_meeting_window import _identity_presets
            for key, preset in _identity_presets().items():
                name = preset.get("name", key)
                tagline = preset.get("tagline", "")
                label = f"{name} -- {tagline}" if tagline else name
                self._option_button(
                    label, lambda k=key: self._choose("tactics", k))
        except Exception as e:
            self._set_prompt(f"Error loading tactics: {e}")

    def _stage_lines(self):
        self._set_prompt("Who owns the lineup card?")
        self._clear_options()
        self._option_button("I set the lines -- you deploy them.",
                            lambda: self._choose("lines", "gm"))
        self._option_button("The bench is yours.",
                            lambda: self._choose("lines", "coach"))

    def _stage_tactics_own(self):
        self._set_prompt("Who owns the systems?")
        self._clear_options()
        self._option_button("I set the tactical direction.",
                            lambda: self._choose("tactics_own", "gm"))
        self._option_button("Your systems, your call.",
                            lambda: self._choose("tactics_own", "coach"))

    def _stage_deployer(self):
        self._set_prompt(
            "He's deploying your vision this year. Address it directly -- "
            "this beat is mandatory.")
        self._clear_options()
        try:
            from coach_meeting_window import _DEPLOYER_OPTIONS
            for key, label, full in _DEPLOYER_OPTIONS:
                self._option_button(
                    f'{label}: "{full}"',
                    lambda k=key: self._choose("deployer", k))
        except Exception as e:
            self._set_prompt(f"Error loading options: {e}")

    def _stage_closing(self):
        try:
            from coach_meeting_window import (
                build_mandate, mandate_summary_lines,
                _identity_presets, _closing_line, _season_label,
            )
            from coach_season_meeting import build_mandate as _bm
        except ImportError:
            self._set_prompt("Error loading mandate builder.")
            return

        mandate = _safe(
            lambda: build_mandate(
                self.team, self.draft,
                _safe(lambda: _season_label(self._gm()), "")))
        if not self.draft.get("closing_logged"):
            self._log("coach", _safe(
                lambda: _closing_line(
                    self.coach,
                    not self.draft.get("misaligned", False), self._rng),
                "Let's get to work."))
            self.draft["closing_logged"] = True
            self._persist()
            self._render_transcript()

        self._set_prompt(
            "The agreement, as it stands. Seal it and the season begins.")
        self._clear_options()

        try:
            presets = _identity_presets()
            summary = "\n".join(
                "• " + ln
                for ln in mandate_summary_lines(mandate or {}, presets))
        except Exception:
            summary = "Agreement details unavailable."

        sum_lbl = QLabel(summary or "No mandate details.")
        sum_lbl.setWordWrap(True)
        sum_lbl.setStyleSheet("color: #9aa4b8; font-size: 12px;")
        self._options_layout.addWidget(sum_lbl)
        self._option_button("Seal the agreement.",
                            lambda: self._seal(mandate))

    def _render_done(self):
        self._set_prompt("Meeting complete -- sealed agreement:")
        self._clear_options()
        try:
            from coach_meeting_window import (
                mandate_summary_lines, _identity_presets,
            )
            mandate = getattr(self.team, "season_mandate", None) or {}
            presets = _identity_presets()
            summary = "\n".join(
                "• " + ln
                for ln in mandate_summary_lines(mandate, presets))
        except Exception:
            summary = "No mandate on file."

        sum_lbl = QLabel(summary or "No mandate on file.")
        sum_lbl.setWordWrap(True)
        sum_lbl.setStyleSheet("color: #9aa4b8; font-size: 12px;")
        self._options_layout.addWidget(sum_lbl)
        self._option_button("Back to the hub.",
                            lambda: self._navigate("hub"))

    def _navigate(self, name):
        fn = getattr(self.main_window, "show_screen", None)
        if callable(fn):
            try:
                fn(name)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # choices
    # ------------------------------------------------------------------
    def _advance_to(self, stage):
        self.draft["stage"] = stage
        try:
            from coach_meeting_window import _stage_prompt \
                as _sp  # may not exist
            prompt = _sp(stage)
            if prompt:
                self._log("sys", prompt)
        except ImportError:
            pass
        self._persist()
        self._render_all()

    def _gm_line(self, stage, key):
        lines = {
            "opening": "Let's talk about the season.",
            "expectations": f"Here's what I expect: {key}.",
            "rookies": f"On rookies: {key}.",
            "tactics": f"We'll play: {key}.",
            "lines": "I'll set the lines." if key == "gm"
                     else "The bench is yours.",
            "tactics_own": "I'll set the direction." if key == "gm"
                           else "Your systems.",
            "deployer": "Let's be clear about roles.",
        }
        return lines.get(stage, "")

    def _choose(self, stage, key):
        """GM picks -> coach reacts -> next beat."""
        if stage != self.draft.get("stage"):
            return  # stale click

        try:
            from coach_meeting_window import (
                _expectation_reaction, _rookie_reaction,
                _tactics_reaction, _lines_reaction,
                _tactics_owner_reaction, _deployer_reaction,
                apply_trust_delta,
            )
            from coach_season_meeting import coach_assessment
        except ImportError:
            return

        gm_line = self._gm_line(stage, key)
        if gm_line:
            self._log("gm", gm_line)

        text, delta, note, misaligned = "", 0, "", False
        nxt = None

        if stage == "opening":
            nxt = "expectations"
        elif stage == "expectations":
            assessed = self.draft.get("coach_assessment") or _safe(
                lambda: coach_assessment(self.team, self.coach), "")
            self.draft["coach_assessment"] = assessed
            self.draft["choices"]["expectation"] = key
            text, delta, note, misaligned = _safe(
                lambda: _expectation_reaction(
                    self.team, self.coach, key, assessed, self._rng),
                ("", 0, "", False))
            nxt = "rookies"
        elif stage == "rookies":
            self.draft["choices"]["rookie_stance"] = key
            exp = self.draft["choices"].get("expectation", "playoffs")
            text, delta, note = _safe(
                lambda: _rookie_reaction(
                    self.team, self.coach, key, exp, self._rng)[:3],
                ("", 0, ""))
            nxt = "tactics"
        elif stage == "tactics":
            self.draft["choices"]["tactical_approach"] = key
            text, delta, note = _safe(
                lambda: _tactics_reaction(
                    self.team, self.coach, key, self._rng)[:3],
                ("", 0, ""))
            nxt = "lines"
        elif stage == "lines":
            self.draft["choices"]["lines_owner"] = key
            text, delta, note = _safe(
                lambda: _lines_reaction(
                    self.team, self.coach, key, self._rng)[:3],
                ("", 0, ""))
            nxt = "tactics_own"
        elif stage == "tactics_own":
            self.draft["choices"]["tactics_owner"] = key
            text, delta, note = _safe(
                lambda: _tactics_owner_reaction(
                    self.team, self.coach, key, self._rng)[:3],
                ("", 0, ""))
            ch = self.draft["choices"]
            if ch.get("lines_owner") == "gm" and ch.get("tactics_owner") == "gm":
                nxt = "deployer"
            else:
                nxt = "closing"
        elif stage == "deployer":
            self.draft["deployer_choice"] = key
            res = _safe(
                lambda: _deployer_reaction(
                    self.team, self.coach, key, self._rng),
                ("", 0, "", "", False))
            text, delta, note, deployer_note, misaligned = res
            self.draft["deployer_note"] = deployer_note
            nxt = "closing"

        if delta:
            apply_trust_delta(self.coach, delta)
        if text:
            self._log("coach", text,
                      trust_delta=delta if delta else None)
        if note:
            self._log("sys", note)
        if misaligned:
            self.draft["misaligned"] = True
        self._persist()

        if nxt:
            self._advance_to(nxt)

    def _seal(self, mandate):
        try:
            from coach_meeting_window import _finalize_meeting
            ok = _safe(lambda: _finalize_meeting(self.team, mandate), False)
        except ImportError:
            ok = False
            # Fallback: store mandate directly
            try:
                from coach_season_meeting import store_mandate
                ok = bool(_safe(lambda: store_mandate(
                    self.team, mandate or {}), False))
            except ImportError:
                pass

        self.draft = {"stage": "done",
                      "log": self.draft.get("log", []),
                      "choices": {}, "notes": []}
        self._log("sys", "Agreement sealed." if ok
                  else "Agreement recorded (finalize reported a problem).")
        try:
            if hasattr(self.team, "season_meeting_draft"):
                delattr(self.team, "season_meeting_draft")
        except Exception:
            pass
        self._persist()
        self._render_all()

    def refresh(self):
        # Re-render on return; draft persists on team, so reload it in
        # case it was edited elsewhere while this screen was parked.
        try:
            self.team = self._user_team()
            self._load_draft()
            self._render_all()
        except Exception:
            pass
