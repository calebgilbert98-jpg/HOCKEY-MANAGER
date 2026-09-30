"""TRACK C #1 -- Ice-Time Deployment visibility.

The missing layer between "the coach exists" and "who skates how much".
Read-only over deployment_policy: the coach's deployment policy in effect
(style, concentration, soft-cap triggers), per-line deployment shares for a
neutral (0-0, 1st period) game state, honored GM advice, and the cap
exceptions. Numbers come straight from deployment_policy.deployment_weights;
nothing here simulates.
"""

import customtkinter as ctk

import trackc_common as tc

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


def _concentration_label(c):
    for cutoff, label in _CONC_LABELS:
        if c >= cutoff:
            return label
    return "Balanced deployment"


class TrackCDeploymentView(ctk.CTkFrame):
    TITLE = "Ice-Time Deployment"
    SUBTITLE = "How your coach distributes ice time — live policy, read from the engine"

    def __init__(self, parent, app=None):
        tc.init_trackc_view(self, parent, app)
        self.body = tc.make_body(self)
        self.refresh()

    def refresh(self):
        for w in self.body.winfo_children():
            w.destroy()
        team = tc.user_team(self)
        if team is None:
            self._body(self.body, text="No team loaded.").pack(padx=16, pady=16)
            return
        policy = self._read_policy(team)
        self._policy_card(team, policy)
        self._shares_card(policy)
        self._caps_card(team, policy)
        self._advice_card(policy)

    # ------------------------------------------------------------------
    # engine reads
    # ------------------------------------------------------------------
    def _read_policy(self, team):
        import deployment_policy as dp
        policy = {"style_key": "balanced", "style_label": "Balanced",
                  "family": "balanced", "weights": {}, "meta": {},
                  "advice": [], "coach": None}
        try:
            coach = dp._head_coach_for(team)
            policy["coach"] = coach
        except Exception:
            coach = None
        try:
            import reputation_system as rs
            cs = rs.coach_style(coach) if coach is not None else {}
            policy["style_key"] = (cs or {}).get("key", "balanced")
            policy["style_label"] = (cs or {}).get("label", "Balanced")
        except Exception:
            pass
        try:
            import tactics as tx
            policy["family"] = tx.team_family(team) or "balanced"
        except Exception:
            pass
        try:
            w = dp.deployment_weights(
                team,
                {"key": policy["style_key"]},
                policy["family"] if policy["family"] in (
                    "pressure", "structure", "balanced") else "balanced",
                dict(_NEUTRAL_STATE))
            policy["weights"] = {k: v for k, v in w.items() if k != "meta"}
            policy["meta"] = w.get("meta", {}) or {}
        except Exception:
            pass
        try:
            adv = dp._honored_advice(team) or []
            policy["advice"] = [str(a) for a in adv]
        except Exception:
            pass
        return policy

    # ------------------------------------------------------------------
    # cards
    # ------------------------------------------------------------------
    def _policy_card(self, team, policy):
        meta = policy["meta"]
        conc = meta.get("concentration")
        lines = []
        coach_name = "?"
        try:
            c = policy["coach"]
            coach_name = (f"{getattr(c, 'first_name', '')} "
                          f"{getattr(c, 'last_name', '')}").strip() or "?"
        except Exception:
            pass
        lines.append(f"Head coach: {coach_name}")
        lines.append(f"Style: {policy['style_label']}  ·  Tactical family: "
                     f"{policy['family'].title()}")
        if conc is not None:
            lines.append(f"Deployment posture: {_concentration_label(float(conc))}")
        if meta.get("overload"):
            lines.append("Star-overload mode: top talent soaks up the big minutes")
        card = tc.section(self, self.body, "Deployment policy in effect",
                          "Neutral game state (0-0, 1st period) — score and clock tilt this live.")
        for ln in lines:
            self._body(card, text="• " + ln).pack(anchor="w", padx=4, pady=1)

    def _shares_card(self, policy):
        card = tc.section(self, self.body, "Line deployment shares",
                          "Share of each unit's ice the coach plans at the base policy.")
        weights = policy["weights"]
        if not weights:
            self._body(card, text="No deployment data available.", dim=True).pack(anchor="w")
            return
        for key, title, labels in _GROUPS:
            shares = weights.get(key) or []
            if not shares:
                continue
            self._heading(card, text=title, size=12).pack(anchor="w", padx=4, pady=(8, 2))
            for label, share in zip(labels, shares):
                try:
                    s = float(share)
                except (TypeError, ValueError):
                    s = 0.0
                rowf = ctk.CTkFrame(card, fg_color="transparent")
                rowf.pack(fill="x", padx=4, pady=1)
                ctk.CTkLabel(rowf, text=label, width=70, anchor="w",
                             font=("Segoe UI", 12)).pack(side="left")
                tc.hbar(self, rowf, s, width=220).pack(side="left", padx=8)
                ctk.CTkLabel(rowf, text=f"{s * 100:.0f}%",
                             width=52, anchor="w",
                             font=("Segoe UI", 12)).pack(side="left")

    def _caps_card(self, team, policy):
        import deployment_policy as dp
        card = tc.section(
            self, self.body, "Soft-cap governor",
            "Elite skaters are sheltered once total TOI binds; deployment shifts to the next lines.")
        rows = [
            ("Standard soft cap", "~30:00 per game"),
            ("Short-bench cap", "35:00 (fewer than 15 dressed skaters)"),
            ("Full stand-down", "must-win playoff games, OT marathons"),
        ]
        for name, val in rows:
            tc.row(self, card, [name, val], widths=[220, 0])
        # Exceptions evaluated against the neutral state (all off) -- honest baseline.
        exc = {}
        try:
            exc = dp.soft_cap_exceptions(dict(_NEUTRAL_STATE)) or {}
        except Exception:
            pass
        active = [k for k, v in exc.items() if v]
        self._body(card,
                   text=("Cap exceptions active right now: " + ", ".join(active)
                         if active else "No cap exceptions active at the base policy."),
                   dim=True).pack(anchor="w", padx=4, pady=(6, 0))

    def _advice_card(self, policy):
        card = tc.section(self, self.body, "Honored GM advice",
                          "Standing instructions from Advise Coach the coach is carrying.")
        advice = policy["advice"]
        if not advice:
            self._body(card, text="None on file — the coach deploys on his own read.",
                       dim=True).pack(anchor="w", padx=4)
            return
        for a in advice[:10]:
            self._body(card, text="• " + a).pack(anchor="w", padx=4, pady=1)
