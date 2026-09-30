"""TRACK C #4 -- Rivalry dashboard.

Rivalries drive incidents, heat and the physical/discipline channels of the
sim, but the only UI is declare/renounce buried in the Morale window. This
screen shows the user's team's rivalries (ranked by intensity, with the
story behind each) plus the league's hottest team feuds to plan around.
Reads the live rivalry store (league.rivalries) via reputation_system.
"""

import customtkinter as ctk

import trackc_common as tc

_KIND_LABELS = {
    "team_team": "Team feud",
    "gm_coach": "You vs their coach",
    "coach_coach": "Coaches' feud",
    "gm_gm": "GM feud",
    "gm_respect": "Mutual respect",
    "fan_player": "Fan storyline",
}


def _heat_band(intensity):
    if intensity >= 80:
        return "WHITE HOT", "RED"
    if intensity >= 60:
        return "Heated", "GOLD"
    if intensity >= 40:
        return "Simmering", "BLUE"
    return "Cooling", "TEAL"


class TrackCRivalryView(ctk.CTkFrame):
    TITLE = "Rivalry Dashboard"
    SUBTITLE = "The bad blood that moves games — declare / renounce stays in the Morale window"

    def __init__(self, parent, app=None):
        tc.init_trackc_view(self, parent, app)
        self.body = tc.make_body(self)
        self.refresh()

    def refresh(self):
        for w in self.body.winfo_children():
            w.destroy()
        league = tc.league_of(self)
        team = tc.user_team(self)
        if league is None or team is None:
            self._body(self.body, text="No league loaded.").pack(padx=16, pady=16)
            return
        mine = self._read_mine(league, team)
        hottest = self._read_hottest(league, team)
        self._mine_card(mine)
        self._hottest_card(hottest)

    # ------------------------------------------------------------------
    # engine reads
    # ------------------------------------------------------------------
    def _store(self, league):
        try:
            import reputation_system as rs
            return rs._rivalry_store(league)
        except Exception:
            return list(getattr(league, "rivalries", None) or [])

    def _read_mine(self, league, team):
        try:
            import reputation_system as rs
            store = self._store(league)
            return rs.get_rivalries_for(store, team)
        except Exception:
            return []

    def _read_hottest(self, league, team):
        try:
            my_name = getattr(team, "team_name", "")
            recs = [r for r in self._store(league)
                    if isinstance(r, dict) and r.get("kind") == "team_team"
                    and my_name not in (r.get("a_name"), r.get("b_name"))]
            recs.sort(key=lambda r: -float(r.get("intensity", 0) or 0))
            return recs[:8]
        except Exception:
            return []

    # ------------------------------------------------------------------
    # cards
    # ------------------------------------------------------------------
    def _rivalry_block(self, card, r):
        try:
            a, b = r.get("a_name", "?"), r.get("b_name", "?")
            intensity = int(float(r.get("intensity", 0) or 0))
            grudge = int(float(r.get("grudge", 0) or 0))
            kind = _KIND_LABELS.get(r.get("kind"), str(r.get("kind", "")))
            origin = str(r.get("origin", "") or "")
            story = str(r.get("story", "") or "").strip()
            date = str(r.get("date", "") or "")
        except Exception:
            return
        band, color = _heat_band(intensity)
        head = ctk.CTkFrame(card, fg_color="transparent")
        head.pack(fill="x", padx=4, pady=(8, 0))
        tc.chip(self, head, band, color).pack(side="left", padx=(0, 10))
        ctk.CTkLabel(head, text=f"{a}  vs  {b}", anchor="w",
                     font=("Segoe UI", 13, "bold")).pack(side="left")
        self._body(head, text=f"·  {kind}", dim=True).pack(side="left", padx=(8, 0))
        meta = ctk.CTkFrame(card, fg_color="transparent")
        meta.pack(fill="x", padx=4)
        tc.hbar(self, meta, intensity / 100.0, width=200,
                color_key=color).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(meta, text=f"Intensity {intensity}   ·   Grudge {grudge}",
                     anchor="w", font=("Segoe UI", 12)).pack(side="left")
        bits = []
        if origin:
            bits.append(f"Origin: {origin}")
        if date:
            bits.append(f"since {date}")
        if bits:
            self._body(card, text="  ".join(bits), dim=True).pack(anchor="w", padx=4)
        if story:
            self._body(card, text=story[:280], dim=True).pack(
                anchor="w", padx=4, pady=(2, 0))

    def _mine_card(self, mine):
        card = tc.section(self, self.body, "Your rivalries",
                          f"{len(mine)} live record{'s' if len(mine) != 1 else ''} "
                          "involving your club." if mine else
                          "No rivalries on the books — quiet rooms win Cups too.")
        for r in mine[:12]:
            self._rivalry_block(card, r)

    def _hottest_card(self, hottest):
        card = tc.section(self, self.body, "Around the league — hottest feuds",
                          "Team-vs-team heat elsewhere. These games run hotter: "
                          "more incidents, edgier physicality.")
        if not hottest:
            self._body(card, text="Nothing simmering league-wide.", dim=True).pack(
                anchor="w", padx=4)
            return
        for r in hottest:
            self._rivalry_block(card, r)
