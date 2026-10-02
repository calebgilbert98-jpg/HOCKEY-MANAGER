# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""TRACK C #2 -- Roster-wide condition / fatigue view.

Rest decisions are a daily loop, but fatigue is only visible one card at a
time. This screen puts the whole roster's condition on one surface, worst
first. Every number is an exact engine read (condition_system); nothing is
re-derived or invented.
"""

import customtkinter as ctk

import trackc_common as tc

_TIER_COLORS = {"FRESH": "GREEN", "GOOD": "TEAL", "WORN": "GOLD", "GASSED": "RED"}


class TrackCConditionView(ctk.CTkFrame):
    TITLE = "Roster Condition"
    SUBTITLE = "Who's gassed, who's fresh — one surface for the daily rest call"

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
        rows = self._read_rows(team)
        self._summary_card(rows)
        self._table_card(team, rows)

    # ------------------------------------------------------------------
    # engine reads
    # ------------------------------------------------------------------
    def _read_rows(self, team):
        import condition_system as cs
        rows = []
        for p in list(getattr(team, "roster", None) or []):
            try:
                cond = cs.get_condition(p)
                tier = cs.condition_tier(p)
                energy = cs.get_game_energy(p)
                risk = cs.fatigue_injury_risk_mult(p)
                last_toi = float(getattr(p, "_w3_last_toi_min", 0.0) or 0.0)
                pos = getattr(getattr(p, "primary_position", None), "name", "?")
                rows.append({"player": p, "name": tc.player_name(p), "pos": pos,
                             "cond": cond, "tier": tier, "energy": energy,
                             "risk": risk, "last_toi": last_toi})
            except Exception:
                continue
        # Worst first: gassed/worn at the top so the rest call is obvious.
        tier_rank = {"GASSED": 0, "WORN": 1, "GOOD": 2, "FRESH": 3}
        rows.sort(key=lambda r: (tier_rank.get(r["tier"], 4), r["cond"]))
        return rows

    def _rest_days(self, team):
        try:
            import condition_system as cs
            league = tc.league_of(self)
            schedule = getattr(league, "schedule", None)
            date = getattr(self.app, "current_date", None)
            return cs.rest_days_after(schedule, team, date)
        except Exception:
            return None

    # ------------------------------------------------------------------
    # cards
    # ------------------------------------------------------------------
    def _summary_card(self, rows):
        counts = {}
        for r in rows:
            counts[r["tier"]] = counts.get(r["tier"], 0) + 1
        bits = [f"{counts.get(t, 0)} {t.title()}" for t in ("FRESH", "GOOD", "WORN", "GASSED")]
        gassed_names = [r["name"] for r in rows if r["tier"] == "GASSED"][:5]
        note = " · ".join(bits)
        rest = self._rest_days(tc.user_team(self))
        if rest is not None:
            note += f"   ·   {rest} rest day{'s' if rest != 1 else ''} before the next game"
        card = tc.section(self, self.body, "Room at a glance", note)
        if gassed_names:
            self._body(card, text="Needs rest: " + ", ".join(gassed_names)).pack(
                anchor="w", padx=4, pady=2)

    def _table_card(self, team, rows):
        card = tc.section(
            self, self.body, "Skater condition",
            "Condition = season wear (0-100). Energy = current in-game pool. "
            "Injury risk = engine multiplier right now (1.00 = fresh).")
        tc.row(self, card,
               ["Player", "Pos", "Condition", "Tier", "Energy", "Inj risk", "Last TOI"],
               widths=[220, 60, 170, 90, 70, 70, 80], bold_first=True)
        for r in rows:
            rowf = ctk.CTkFrame(card, fg_color="transparent")
            rowf.pack(fill="x", pady=2)
            _nm = ctk.CTkLabel(rowf, text=r["name"], width=220, anchor="w",
                         font=("Segoe UI", 12))
            _nm.pack(side="left")
            # EHM/FM24: right-click the name -> player menu.
            try:
                from player_context_menu import bind_player_context
                _cp = r.get("player")
                if _cp is not None and hasattr(_cp, 'full_name'):
                    bind_player_context(_nm, _cp, self)
            except Exception:
                pass
            ctk.CTkLabel(rowf, text=r["pos"], width=60, anchor="w",
                         font=("Segoe UI", 12)).pack(side="left")
            barw = ctk.CTkFrame(rowf, fg_color="transparent", width=170, height=22)
            barw.pack(side="left")
            barw.pack_propagate(False)
            tc.hbar(self, barw, r["cond"] / 100.0, width=100,
                    color_key=_TIER_COLORS.get(r["tier"], "TEAL")).pack(side="left")
            ctk.CTkLabel(barw, text=f"{r['cond']:.0f}", width=56, anchor="w",
                         font=("Segoe UI", 12)).pack(side="left", padx=(6, 0))
            tc.chip(self, rowf, r["tier"],
                    _TIER_COLORS.get(r["tier"], "TEAL")).pack(side="left", padx=(0, 8))
            ctk.CTkLabel(rowf, text=f"{r['energy']:.0f}", width=70, anchor="w",
                         font=("Segoe UI", 12)).pack(side="left")
            ctk.CTkLabel(rowf, text=f"{r['risk']:.2f}x", width=70, anchor="w",
                         font=("Segoe UI", 12)).pack(side="left")
            ctk.CTkLabel(rowf, text=f"{r['last_toi']:.0f} min", width=80, anchor="w",
                         font=("Segoe UI", 12)).pack(side="left")
