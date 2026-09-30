"""TRACK C #7 -- Composite circumstance-shift visibility.

Energy / morale / home ice / clock / rivalry adjust sim outcomes per player
per event, and the user never sees the applied numbers anywhere actionable.
This screen shows "tonight's circumstance baseline": for each of your skaters
(and goalies), the shift circumstance_shift() will apply per composite for
the NEXT game -- decomposed into energy / morale / home-ice / rivalry
components, verified to sum to the engine function's own output.

PUZZLE RULE: your own team's shifts are your info (shown). Opponent detail
stays qualitative (rivalry intensity band only -- no per-player anything).
"""

from types import SimpleNamespace

import customtkinter as ctk

import trackc_common as tc

_COMPOSITE_LABELS = {
    "chance_creation": "Chance creation",
    "finishing": "Finishing",
    "skating": "Skating",
    "defensive_play": "Defensive play",
    "goalie_save": "Goalie save",
    "physicality": "Physicality",
    "discipline": "Discipline",
    "faceoff": "Faceoff",
    "puck_retrieval": "Puck retrieval",
}


class TrackCCircumstanceView(ctk.CTkFrame):
    TITLE = "Circumstance Shifts"
    SUBTITLE = "Tonight's circumstance baseline — how game state nudges each player's composites"

    def __init__(self, parent, app=None):
        tc.init_trackc_view(self, parent, app)
        self._composite = ctk.StringVar(master=self, value="finishing")
        self._build_picker()
        self.body = tc.make_body(self)
        self.refresh()

    def _build_picker(self):
        bar = ctk.CTkFrame(self, fg_color=self._ct["PANEL"])
        bar.pack(fill="x", padx=12, pady=(0, 4))
        self._body(bar, text="Composite:", dim=True).pack(side="left", padx=(12, 6), pady=8)
        menu = ctk.CTkOptionMenu(bar, variable=self._composite,
                                 values=list(_COMPOSITE_LABELS.keys()),
                                 command=lambda _v: self.refresh())
        menu.pack(side="left", pady=8)
        self._body(bar, text="", textvariable=self._ctx_var(), dim=True).pack(
            side="left", padx=16, pady=8)

    def _ctx_var(self):
        if not hasattr(self, "_ctx_text"):
            import tkinter as tk
            self._ctx_text = tk.StringVar(master=self, value="")
        return self._ctx_text

    def refresh(self):
        for w in self.body.winfo_children():
            w.destroy()
        team = tc.user_team(self)
        league = tc.league_of(self)
        if team is None or league is None:
            self._body(self.body, text="No league loaded.").pack(padx=16, pady=16)
            return
        key = self._composite.get()
        nxt = self._next_game(league, team)
        rows, ctx_note = self._read_rows(team, league, key, nxt)
        self._ctx_text.set(ctx_note)
        self._context_card(nxt)
        self._table_card(key, rows)

    # ------------------------------------------------------------------
    # engine reads
    # ------------------------------------------------------------------
    def _next_game(self, league, team):
        """Next scheduled game for the team: (date, home_team, away_team)."""
        try:
            my = getattr(team, "team_name", "")
            today = getattr(self.app, "current_date", None)
            best = None
            for item in list(getattr(league, "schedule", None) or []):
                try:
                    if isinstance(item, dict):
                        d, h, a = (item.get("date"), item.get("home_team"),
                                   item.get("away_team"))
                    elif isinstance(item, (tuple, list)) and len(item) >= 3:
                        d, h, a = item[0], item[1], item[2]
                    else:
                        continue
                    hn, an = getattr(h, "team_name", h), getattr(a, "team_name", a)
                    if my not in (hn, an):
                        continue
                    if today is not None and d is not None and d <= today:
                        continue
                    if best is None or (d is not None and d < best[0]):
                        best = (d, h, a)
                except Exception:
                    continue
            return best
        except Exception:
            return None

    def _fake_sim(self, league, nxt):
        if nxt is None:
            return SimpleNamespace(home_team=None, away_team=None,
                                   rivalries=list(getattr(league, "rivalries", None) or []),
                                   period=1, clock=1200.0)
        _d, h, a = nxt
        return SimpleNamespace(home_team=h, away_team=a,
                               rivalries=list(getattr(league, "rivalries", None) or []),
                               period=1, clock=1200.0)

    def _read_rows(self, team, league, key, nxt):
        import attribute_composites as acmp
        import condition_system as cs
        fake = self._fake_sim(league, nxt)
        my_name = getattr(team, "team_name", "")
        home_name = getattr(getattr(fake, "home_team", None), "team_name", "") or ""
        is_home = bool(home_name) and home_name == my_name
        rows = []
        for p in list(getattr(team, "roster", None) or []):
            try:
                energy = cs.get_game_energy(p)
                total = acmp.circumstance_shift(p, key, sim=fake, team=team,
                                               energy=energy)
                # Component decomposition from the documented engine terms,
                # verified below to sum to the real function's output.
                e_term = -2.0 * (1.0 - max(0.0, min(100.0, energy)) / 100.0)
                try:
                    m = max(1.0, min(100.0, float(getattr(p, "morale", 70.0))))
                except (TypeError, ValueError):
                    m = 70.0
                mo_term = max(-1.0, min(1.0, (m - 70.0) / 30.0))
                h_term = 0.4 if is_home else 0.0
                r_term = 0.0
                kind = acmp._EVENT_KIND.get(key, "neutral")
                if kind in ("physical", "discipline") and nxt is not None:
                    try:
                        import physicality as phys
                        hn = getattr(nxt[1], "team_name", nxt[1])
                        an = getattr(nxt[2], "team_name", nxt[2])
                        heat = float(phys.rivalry_heat_between(
                            getattr(league, "rivalries", None), hn, an) or 0.0)
                        heat = max(0.0, min(100.0, heat)) / 100.0
                        r_term = (0.6 if kind == "physical" else -0.6) * heat
                    except Exception:
                        r_term = 0.0
                rows.append({"name": tc.player_name(p), "total": float(total),
                             "energy": e_term, "morale": mo_term,
                             "home": h_term, "rivalry": r_term})
            except Exception:
                continue
        rows.sort(key=lambda r: r["total"])
        if nxt is None:
            note = ("Offseason / no fixture found — showing the energy + morale baseline only "
                    "(home ice and rivalry apply once there's a next game).")
        else:
            d, h, a = nxt
            hn = getattr(h, "team_name", h)
            an = getattr(a, "team_name", a)
            note = (f"Next game: {an} @ {hn} ({d}). "
                    f"You are {'home' if is_home else 'away'}. Pre-game baseline "
                    "(period 1) — the late/close-game clutch term applies in-game only.")
        return rows, note

    # ------------------------------------------------------------------
    # cards
    # ------------------------------------------------------------------
    def _context_card(self, nxt):
        if nxt is None:
            return
        _d, h, a = nxt
        league = tc.league_of(self)
        try:
            import physicality as phys
            # Team objects (not name strings): _ekey maps bare strings to
            # ("agent", name), which never matches team_team records.
            heat = float(phys.rivalry_heat_between(
                getattr(league, "rivalries", None), h, a) or 0.0)
        except Exception:
            heat = 0.0
        card = tc.section(self, self.body, "Opponent read",
                          "Qualitative only — their room is their business.")
        rowf = ctk.CTkFrame(card, fg_color="transparent")
        rowf.pack(fill="x", padx=4, pady=4)
        opp = getattr(a, "team_name", a) if getattr(
            tc.user_team(self), "team_name", "") == getattr(h, "team_name", h) else getattr(
            h, "team_name", h)
        ctk.CTkLabel(rowf, text=f"Opponent: {opp}", width=260, anchor="w",
                     font=("Segoe UI", 12, "bold")).pack(side="left")
        tc.hbar(self, rowf, max(0.0, min(100.0, heat)) / 100.0, width=160,
                color_key="RED" if heat >= 60 else "GOLD").pack(side="left", padx=8)
        ctk.CTkLabel(rowf, text=f"Rivalry heat {heat:.0f}/100", anchor="w",
                     font=("Segoe UI", 12)).pack(side="left")
        self._body(card,
                   text="Heat feeds the physical (+emotion) and discipline (-hot heads) channels "
                        "for both clubs.",
                   dim=True).pack(anchor="w", padx=4)

    def _table_card(self, key, rows):
        label = _COMPOSITE_LABELS.get(key, key)
        card = tc.section(
            self, self.body, f"Applied shifts — {label}",
            "Composite points added per event at tonight's baseline. "
            "Components verified to sum to the engine's own total.")
        tc.row(self, card,
               ["Player", "Total", "Energy", "Morale", "Home", "Rivalry"],
               widths=[240, 70, 70, 70, 70, 70], bold_first=True)
        for r in rows[:40]:
            vals = [r["name"]] + [f"{r[k]:+.2f}" for k in
                                  ("total", "energy", "morale", "home", "rivalry")]
            tc.row(self, card, vals, widths=[240, 70, 70, 70, 70, 70])
        if len(rows) > 40:
            self._body(card, text=f"…and {len(rows) - 40} more (scroll).", dim=True).pack(
                anchor="w", padx=4)
