"""TRACK C #8 -- In-season fan-favourite surface.

The engine marks is_fan_favourite, but the only surface is a year-end recap
suffix and headline tags. This screen is the in-season fan buzz panel: who
the fans adore right now, who's on the rise, and why (the score's own
reasons -- production, tenure, leadership, the C, box-office theatre).
Reads reputation_system.fan_favourite_score; nothing invented.
"""

import customtkinter as ctk

import trackc_common as tc


class TrackCFanBuzzView(ctk.CTkFrame):
    TITLE = "Fan Buzz"
    SUBTITLE = "Who the fans adore right now — and why"

    def __init__(self, parent, app=None):
        tc.init_trackc_view(self, parent, app)
        self.body = tc.make_body(self)
        self.refresh()

    def refresh(self):
        for w in self.body.winfo_children():
            w.destroy()
        team = tc.user_team(self)
        league = tc.league_of(self)
        if team is None:
            self._body(self.body, text="No team loaded.").pack(padx=16, pady=16)
            return
        rows = self._read_rows(team, league)
        favs = [r for r in rows if r["score"] >= 70]
        rising = [r for r in rows if 55 <= r["score"] < 70]
        self._favs_card(favs)
        self._rising_card(rising)
        self._coach_card(team)

    # ------------------------------------------------------------------
    # engine reads
    # ------------------------------------------------------------------
    def _read_rows(self, team, league):
        rows = []
        try:
            import reputation_system as rs
            rivs = list(getattr(league, "rivalries", None) or []) if league else []
            for p in list(getattr(team, "roster", None) or []):
                try:
                    res = rs.fan_favourite_score(p, team, rivalries=rivs) or {}
                    score = float(res.get("score", 0) or 0)
                    rows.append({"name": tc.player_name(p), "score": score,
                                 "tier": str(res.get("tier", "")),
                                 "reasons": [str(x) for x in
                                             (res.get("reasons", None) or [])]})
                except Exception:
                    continue
        except Exception:
            pass
        rows.sort(key=lambda r: -r["score"])
        return rows

    # ------------------------------------------------------------------
    # cards
    # ------------------------------------------------------------------
    def _player_block(self, card, r, color):
        head = ctk.CTkFrame(card, fg_color="transparent")
        head.pack(fill="x", padx=4, pady=(8, 0))
        tc.chip(self, head, f"{r['score']:.0f}", color).pack(side="left", padx=(0, 10))
        ctk.CTkLabel(head, text=r["name"], anchor="w",
                     font=("Segoe UI", 13, "bold")).pack(side="left")
        if r["tier"]:
            self._body(head, text=f"·  {r['tier']}", dim=True).pack(side="left", padx=(8, 0))
        tc.hbar(self, head, max(0.0, min(100.0, r["score"])) / 100.0, width=140,
                color_key=color).pack(side="left", padx=(12, 0))
        for reason in r["reasons"][:4]:
            self._body(card, text="• " + reason, dim=True).pack(anchor="w", padx=28)

    def _favs_card(self, favs):
        card = tc.section(self, self.body, "Fan favourites",
                          f"{len(favs)} player{'s' if len(favs) != 1 else ''} "
                          "the building would run through a wall for." if favs else
                          "Nobody has cracked the fans' hearts yet (score 70+).")
        for r in favs[:10]:
            self._player_block(card, r, "GOLD")

    def _rising_card(self, rising):
        card = tc.section(self, self.body, "On the rise",
                          "One hot stretch from favourite status (55-69).")
        if not rising:
            self._body(card, text="Nobody bubbling under right now.", dim=True).pack(
                anchor="w", padx=4)
            return
        for r in rising[:8]:
            self._player_block(card, r, "TEAL")

    def _coach_card(self, team):
        try:
            import reputation_system as rs
            import deployment_policy as dp
            coach = dp._head_coach_for(team)
            if coach is None:
                return
            res = rs.coach_fan_appeal(coach, {"team_name": getattr(team, "team_name", "")}) or {}
            score = float(res.get("score", 0) or 0)
        except Exception:
            return
        card = tc.section(self, self.body, "Behind the bench")
        rowf = ctk.CTkFrame(card, fg_color="transparent")
        rowf.pack(fill="x", padx=4, pady=4)
        try:
            cname = (f"{getattr(coach, 'first_name', '')} "
                     f"{getattr(coach, 'last_name', '')}").strip() or "Head coach"
        except Exception:
            cname = "Head coach"
        ctk.CTkLabel(rowf, text=f"{cname}: fan appeal {score:.0f}/100",
                     anchor="w", font=("Segoe UI", 12, "bold")).pack(side="left")
        for reason in (res.get("reasons", None) or [])[:3]:
            self._body(card, text="• " + str(reason), dim=True).pack(anchor="w", padx=12)
