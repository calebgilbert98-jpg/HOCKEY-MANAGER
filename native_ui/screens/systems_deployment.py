"""Systems: Ice-Time Deployment (read-only).

Read-only over deployment_policy: the coach's deployment policy in
effect (style, concentration, soft-cap triggers), per-line deployment
shares for a neutral (0-0, 1st period) game state, honored GM advice,
and the cap exceptions. Numbers come straight from
deployment_policy.deployment_weights; nothing here simulates.
"""
from PySide6.QtWidgets import (QLabel, QFrame, QVBoxLayout, QHBoxLayout,
                               QScrollArea, QWidget, QProgressBar)

from .base import BaseScreen
from .systems_common import (user_team, tone_color, explainer_label,
                             section_title, no_game_label, clear_layout)
from .systems_common import systems_nav_bar


class SystemsDeploymentScreen(BaseScreen):
    """Ice-Time Deployment -- the coach's ice plan at a neutral state."""

    title = "Deployment"

    #: Neutral game state: the coach's BASE policy, before score/clock tilt it.
    _NEUTRAL_STATE = {
        "score_diff": 0, "period": 1, "clock": 1200.0,
        "is_playoff": False, "must_win": False, "bench_short": False,
        "ot_marathon": False, "is_home": True,
    }

    _GROUPS = [
        ("F", "Forwards", ["L1", "L2", "L3", "L4"]),
        ("D", "Defense", ["Pair 1", "Pair 2", "Pair 3"]),
        ("PP", "Power play", ["PP1", "PP2"]),
        ("PK", "Penalty kill", ["PK1", "PK2"]),
    ]

    _CONC_LABELS = [
        (0.70, "Rides the top units (star-heavy)"),
        (0.55, "Leans on the top units"),
        (0.38, "Balanced deployment"),
        (0.00, "Rolls four lines / three pairs"),
    ]

    @classmethod
    def _concentration_label(cls, c):
        for cutoff, label in cls._CONC_LABELS:
            if c >= cutoff:
                return label
        return "Balanced deployment"

    def _build_body(self):
        self._layout.addLayout(systems_nav_bar(self))
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        inner = QWidget()
        self._content = QVBoxLayout(inner)
        self._content.setSpacing(12)
        scroll.setWidget(inner)
        self._layout.addWidget(scroll)
        self.refresh()

    def refresh(self):
        content = getattr(self, "_content", None)
        if content is None:
            return
        clear_layout(content)
        team = user_team(self.game)
        if team is None:
            content.addWidget(no_game_label())
            content.addStretch()
            return

        coach_name, style_label = "?", "Balanced"
        style_key = "balanced"
        family = "balanced"
        try:
            import deployment_policy as dp
        except Exception:
            dp = None
        if dp is not None:
            try:
                coach = dp._head_coach_for(team)
                if coach is not None:
                    first = getattr(coach, "first_name", "") or ""
                    last = getattr(coach, "last_name", "") or ""
                    coach_name = f"{first} {last}".strip() or "?"
                    try:
                        import reputation_system as rs
                        cs = rs.coach_style(coach) or {}
                        style_key = cs.get("key", "balanced")
                        style_label = cs.get("label", "Balanced")
                    except Exception:
                        pass
                try:
                    import tactics as tx
                    family = tx.team_family(team) or "balanced"
                except Exception:
                    pass
            except Exception:
                pass
        if family not in ("pressure", "structure", "balanced"):
            family = "balanced"

        # --- Policy in effect ---
        content.addWidget(section_title("Deployment policy in effect"))
        content.addWidget(explainer_label(
            "Neutral game state (0-0, 1st period) \u2014 score and clock "
            "tilt this live."))
        pcard = QFrame()
        pcard.setObjectName("tile")
        pl = QVBoxLayout(pcard)
        header = QLabel(f"{style_label}  \u00b7  {family.capitalize()} family")
        header.setObjectName("tile-title")
        sub = QLabel(f"Head coach: {coach_name}")
        sub.setObjectName("tile-sub")
        pl.addWidget(header)
        pl.addWidget(sub)

        conc = conc_label = None
        overload = False
        if dp is not None:
            try:
                w = dp.deployment_weights(team, {"key": style_key},
                                          family,
                                          dict(self._NEUTRAL_STATE)) or {}
                meta = w.get("meta", {}) or {}
                c = meta.get("concentration")
                if c is not None:
                    conc = round(float(c), 3)
                    conc_label = self._concentration_label(float(c))
                overload = bool(meta.get("overload"))
            except Exception:
                w = {}
        else:
            w = {}
        if conc is not None:
            cl = QLabel(f"Concentration {conc:.3f} \u2014 {conc_label}")
        else:
            cl = QLabel(conc_label or "Balanced deployment")
        cl.setStyleSheet(
            f"color: {tone_color('gold' if overload else 'slate')}; "
            "font-size: 13px;")
        pl.addWidget(cl)
        if overload:
            pl.addWidget(explainer_label(
                "Overload: the coach is leaning on the top units beyond "
                "the normal policy."))
        content.addWidget(pcard)

        # --- Line deployment shares ---
        content.addWidget(section_title("Line deployment shares"))
        content.addWidget(explainer_label(
            "Share of each unit's ice the coach plans at the base policy."))
        for gkey, gtitle, labels in self._GROUPS:
            shares = (w.get(gkey) or []) if isinstance(w, dict) else []
            rows = []
            for label, share in zip(labels, shares):
                try:
                    s = float(share)
                except (TypeError, ValueError):
                    s = 0.0
                rows.append((label, round(s, 3)))
            if not rows:
                continue
            gcard = QFrame()
            gcard.setObjectName("tile")
            gl = QVBoxLayout(gcard)
            gt = QLabel(gtitle)
            gt.setObjectName("tile-title")
            gl.addWidget(gt)
            for label, s in rows:
                rl = QHBoxLayout()
                nl = QLabel(label)
                nl.setFixedWidth(70)
                bar = QProgressBar()
                bar.setRange(0, 100)
                bar.setValue(int(round(s * 100)))
                bar.setTextVisible(True)
                bar.setFormat(f"{s * 100:.1f}%")
                bar.setStyleSheet(
                    "QProgressBar { background: #111a2e; border: none; "
                    "height: 14px; }"
                    "QProgressBar::chunk { background: #3B82F6; }")
                rl.addWidget(nl)
                rl.addWidget(bar)
                gl.addLayout(rl)
            content.addWidget(gcard)

        # --- Soft-cap governor ---
        content.addWidget(section_title("Soft-cap governor"))
        content.addWidget(explainer_label(
            "Elite skaters are sheltered once total TOI binds; deployment "
            "shifts to the next lines."))
        exceptions = []
        if dp is not None:
            try:
                exc = dp.soft_cap_exceptions(dict(self._NEUTRAL_STATE)) or {}
                exceptions = sorted(str(k) for k, v in exc.items() if v)
            except Exception:
                pass
        if exceptions:
            ecard = QFrame()
            ecard.setObjectName("tile")
            el = QVBoxLayout(ecard)
            for e in exceptions:
                lbl = QLabel(f"\u2022 {e}")
                lbl.setStyleSheet("color: #e8edf5; font-size: 13px;")
                el.addWidget(lbl)
            content.addWidget(ecard)
        else:
            content.addWidget(explainer_label(
                "No soft-cap triggers at the neutral state."))

        # --- Honored GM advice ---
        content.addWidget(section_title("Honored GM advice"))
        content.addWidget(explainer_label(
            "Standing instructions from Advise Coach the coach is carrying."))
        advice = []
        if dp is not None:
            try:
                adv = dp._honored_advice(team) or {}
                keys = adv.get("keys", set()) if isinstance(adv, dict) else set()
                label_of = {v: k for k, v in
                            getattr(dp, "_ADVICE_LABELS", {}).items()}
                advice = sorted(
                    str(label_of.get(k, k)).capitalize() for k in keys)
            except Exception:
                pass
        if advice:
            acard = QFrame()
            acard.setObjectName("tile")
            al = QVBoxLayout(acard)
            for a in advice:
                lbl = QLabel(f"\u2022 {a}")
                lbl.setStyleSheet("color: #e8edf5; font-size: 13px;")
                al.addWidget(lbl)
            content.addWidget(acard)
        else:
            content.addWidget(explainer_label("None."))

        content.addStretch()
