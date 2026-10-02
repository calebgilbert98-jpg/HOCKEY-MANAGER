# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""TRACK C #6 -- Assistant-coach effect explanations.

Hiring/firing assistants is a money decision made blind: the dev deltas
exist in the engine but nothing explains them. This screen gives each
assistant a number with a story: specialty, prowess, current effectiveness
(and how far form has moved it), plus worked examples from YOUR roster --
the actual development deltas assistant_development_deltas computes for
your U27 players, grouped by coach.
"""

import customtkinter as ctk

import trackc_common as tc


class TrackCAssistantView(ctk.CTkFrame):
    TITLE = "Assistant Coaches"
    SUBTITLE = "What your assistants actually do — numbers with a story"

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
        assistants = self._read_assistants(team)
        deltas = self._read_deltas(team)
        if not assistants:
            tc.section(self, self.body, "Bench",
                       "No assistant coaches on staff. Hire some in Staff Management — "
                       "this screen will show what each one does.").pack()
            return
        self._overview_card(assistants)
        for ac in assistants:
            self._assistant_card(team, ac, deltas)

    # ------------------------------------------------------------------
    # engine reads
    # ------------------------------------------------------------------
    def _read_assistants(self, team):
        out = []
        try:
            import assistant_coaches as aco
            for ac in aco._assistants_of(team) or []:
                try:
                    spec = aco.assistant_specialty(ac)
                    prow = aco.assistant_prowess(ac)
                    eff = aco.assistant_effect(ac)
                    name = (f"{getattr(ac, 'first_name', '')} "
                            f"{getattr(ac, 'last_name', '')}").strip() or "Coach"
                    role = str(getattr(getattr(ac, "role", None), "value", "")
                               or getattr(ac, "role", "") or "")
                    out.append({"staff": ac, "name": name, "role": role,
                                "specialty": spec, "prowess": prow,
                                "effect": eff})
                except Exception:
                    continue
        except Exception:
            pass
        return out

    def _read_deltas(self, team):
        """Real dev deltas for U27 roster players, grouped by coach label."""
        grouped = {}
        try:
            import assistant_coaches as aco
            for p in list(getattr(team, "roster", None) or []):
                try:
                    if (getattr(p, "age", 99) or 99) > 26:
                        continue
                except Exception:
                    continue
                for label, pts in (aco.assistant_development_deltas(p, team) or []):
                    grouped.setdefault(label, []).append(
                        (tc.player_name(p), float(pts)))
        except Exception:
            pass
        return grouped

    # ------------------------------------------------------------------
    # cards
    # ------------------------------------------------------------------
    def _overview_card(self, assistants):
        card = tc.section(
            self, self.body, "The bench",
            "Assistants grow players at their position group (defense / offense / goalie). "
            "Prowess is the résumé; effectiveness is right now — results, mesh and shelf "
            "life move it month to month.")
        tc.row(self, card, ["Coach", "Specialty", "Prowess", "Effectiveness", "Form"],
               widths=[220, 110, 90, 120, 0], bold_first=True)
        for ac in assistants:
            drift = ac["effect"] - ac["prowess"]
            form = f"{drift:+.0f}" if abs(drift) >= 0.5 else "on résumé"
            rowf = ctk.CTkFrame(card, fg_color="transparent")
            rowf.pack(fill="x", pady=2)
            _ac_lbl = ctk.CTkLabel(rowf, text=ac["name"], width=220, anchor="w",
                         font=("Segoe UI", 12))
            _ac_lbl.pack(side="left")
            # EHM/FM24: right-click the coach name -> staff menu.
            try:
                from player_context_menu import bind_staff_context
                _as = ac.get("staff")
                if _as is not None and hasattr(_as, 'full_name'):
                    bind_staff_context(_ac_lbl, _as, self)
            except Exception:
                pass
            ctk.CTkLabel(rowf, text=ac["specialty"].title(), width=110, anchor="w",
                         font=("Segoe UI", 12)).pack(side="left")
            ctk.CTkLabel(rowf, text=f"{ac['prowess']:.0f}", width=90, anchor="w",
                         font=("Segoe UI", 12)).pack(side="left")
            barw = ctk.CTkFrame(rowf, fg_color="transparent", width=120, height=22)
            barw.pack(side="left")
            barw.pack_propagate(False)
            tc.hbar(self, barw, ac["effect"] / 100.0, width=80).pack(side="left")
            ctk.CTkLabel(barw, text=f"{ac['effect']:.0f}", width=34, anchor="w",
                         font=("Segoe UI", 12)).pack(side="left", padx=(6, 0))
            ctk.CTkLabel(rowf, text=form, anchor="w",
                         font=("Segoe UI", 12)).pack(side="left")

    def _assistant_card(self, team, ac, deltas):
        card = tc.section(self, self.body, ac_body_title(ac))
        story = self._story(ac)
        self._body(card, text=story).pack(anchor="w", padx=4, pady=2)
        mine = [(label, pts) for label, pts in deltas.items()
                if ac["name"] in label]
        if not mine:
            self._body(card,
                       text="No U27 players in his position group right now — "
                            "his development effect is idle until the roster gives him kids to work with.",
                       dim=True).pack(anchor="w", padx=4, pady=2)
            return
        self._heading(card, text="Working with your kids", size=12).pack(
            anchor="w", padx=4, pady=(6, 2))
        for label, players in mine:
            names = ", ".join(f"{n} ({p:+.1f})" for n, p in players[:6])
            self._body(card, text=f"• {label}: {names}").pack(
                anchor="w", padx=12, pady=1)
        self._body(card,
                   text="Points per development cycle — modest by design; the head coach "
                        "is the main influence.",
                   dim=True).pack(anchor="w", padx=4, pady=(6, 0))

    def _story(self, ac):
        spec = ac["specialty"]
        group = {"defense": "your defensemen", "offense": "your forwards",
                 "goalie": "your goalies"}.get(spec, "the roster")
        bits = [f"{ac['name']} is a {spec}-specialty assistant."]
        drift = ac["effect"] - ac["prowess"]
        if drift >= 5:
            bits.append("He's outperforming his résumé right now — the room is responding.")
        elif drift <= -5:
            bits.append("His effectiveness has slipped below his résumé — results, mesh or shelf life are biting.")
        else:
            bits.append("He's performing to his résumé.")
        if ac["role"]:
            bits.append(f"Listed role: {ac['role']}.")
        bits.append(f"His development work lands on {group} aged 26 and under.")
        return " ".join(bits)


def ac_body_title(ac):
    role = f" — {ac['role']}" if ac.get("role") else ""
    return f"{ac['name']}{role}"
