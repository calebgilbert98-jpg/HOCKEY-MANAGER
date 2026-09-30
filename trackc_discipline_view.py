"""TRACK C #3b -- Mid-season discipline list.

A suspended player is silently unavailable in the lineup builder. This screen
is the league-wide ledger: who's suspended right now (games remaining) and
each club's season suspension history. Reads Player.suspension_games_remaining
and the controversy_history suspension events (the same source the year-end
Discipline Report reads). The roster "SUSPENDED (n)" badge itself is a small
additive edit in RosterView's status column.
"""

import customtkinter as ctk

import trackc_common as tc


class TrackCDisciplineView(ctk.CTkFrame):
    TITLE = "Discipline List"
    SUBTITLE = "League DoPS ledger — active suspensions and the season's rap sheet"

    def __init__(self, parent, app=None):
        tc.init_trackc_view(self, parent, app)
        self.body = tc.make_body(self)
        self.refresh()

    def refresh(self):
        for w in self.body.winfo_children():
            w.destroy()
        league = tc.league_of(self)
        if league is None:
            self._body(self.body, text="No league loaded.").pack(padx=16, pady=16)
            return
        active, history = self._read_ledger(league)
        self._active_card(active)
        self._history_card(history)

    # ------------------------------------------------------------------
    # engine reads
    # ------------------------------------------------------------------
    def _read_ledger(self, league):
        active, history = [], {}
        teams = list(getattr(league, "teams", None) or [])
        for team in teams:
            tname = getattr(team, "team_name", "?")
            for p in list(getattr(team, "roster", None) or []):
                try:
                    rem = int(getattr(p, "suspension_games_remaining", 0) or 0)
                except (TypeError, ValueError):
                    rem = 0
                if rem > 0:
                    active.append({"name": tc.player_name(p), "team": tname,
                                   "games": rem})
                susp_evs = []
                for e in (getattr(p, "controversy_history", None) or []):
                    if not isinstance(e, dict):
                        continue
                    if str(e.get("type", "") or "").lower() == "suspension":
                        susp_evs.append(e)
                if susp_evs:
                    latest = susp_evs[-1]
                    history[tname] = history.get(tname, []) + [(
                        tc.player_name(p), len(susp_evs),
                        str(latest.get("description", "") or "").strip(),
                        str(latest.get("date", "") or ""))]
        active.sort(key=lambda a: -a["games"])
        return active, history

    # ------------------------------------------------------------------
    # cards
    # ------------------------------------------------------------------
    def _active_card(self, active):
        card = tc.section(self, self.body, "Serving suspensions right now",
                          f"{len(active)} player{'s' if len(active) != 1 else ''} "
                          "sidelined by DoPS." if active else "No active suspensions.")
        if not active:
            self._body(card, text="The league is behaving itself.", dim=True).pack(
                anchor="w", padx=4)
            return
        tc.row(self, card, ["Player", "Team", "Games left"], widths=[260, 200, 0],
               bold_first=True)
        for a in active:
            rowf = ctk.CTkFrame(card, fg_color="transparent")
            rowf.pack(fill="x", pady=1)
            tc.chip(self, rowf, "SUSPENDED", "RED").pack(side="left", padx=(0, 8))
            ctk.CTkLabel(rowf, text=a["name"], width=180, anchor="w",
                         font=("Segoe UI", 12)).pack(side="left")
            ctk.CTkLabel(rowf, text=a["team"], width=200, anchor="w",
                         font=("Segoe UI", 12)).pack(side="left")
            ctk.CTkLabel(rowf, text=f"{a['games']} game{'s' if a['games'] != 1 else ''}",
                         anchor="w", font=("Segoe UI", 12, "bold")).pack(side="left")

    def _history_card(self, history):
        card = tc.section(self, self.body, "Season rap sheet",
                          "Suspension events by club, repeat offenders flagged.")
        if not history:
            self._body(card, text="No suspensions recorded this season.", dim=True).pack(
                anchor="w", padx=4)
            return
        for tname in sorted(history):
            self._heading(card, text=tname, size=12).pack(anchor="w", padx=4, pady=(8, 2))
            for name, n, desc, date in sorted(history[tname], key=lambda x: -x[1])[:6]:
                tag = f" — repeat offender ({n}x)" if n >= 2 else ""
                line = f"• {name}: {n} suspension{'s' if n != 1 else ''}{tag}"
                if desc:
                    line += f" — {desc[:90]}"
                if date:
                    line += f" ({date})"
                self._body(card, text=line).pack(anchor="w", padx=12, pady=1)
