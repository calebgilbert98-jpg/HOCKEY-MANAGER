"""Systems: Discipline List (read-only).

The league-wide DoPS ledger: who's suspended right now (games
remaining) and each club's season suspension history. Reads
Player.suspension_games_remaining and the controversy_history
suspension events (the same source the year-end Discipline Report
reads).
"""
from PySide6.QtWidgets import (QLabel, QFrame, QVBoxLayout, QHBoxLayout)

from .base import BaseScreen
from .systems_common import (league_of, tone_color, explainer_label,
                             section_title, no_game_label, clear_layout,
                             player_name,
                             add_scroll_content)


class SystemsDisciplineScreen(BaseScreen):
    """Discipline List -- the league DoPS ledger."""

    title = "Discipline"

    def _build_body(self):
        self._layout.addLayout(systems_nav_bar(self))
        self._content = add_scroll_content(self)
        self.refresh()

    def refresh(self):
        content = getattr(self, "_content", None)
        if content is None:
            return
        clear_layout(content)
        league = league_of(self.game)
        if league is None:
            content.addWidget(no_game_label())
            content.addStretch()
            return

        active, history = [], {}
        for team in list(getattr(league, "teams", None) or []):
            tname = str(getattr(team, "team_name", "?"))
            for p in list(getattr(team, "roster", None) or []):
                try:
                    rem = int(getattr(p, "suspension_games_remaining",
                                      0) or 0)
                except (TypeError, ValueError):
                    rem = 0
                if rem > 0:
                    active.append({"name": player_name(p), "team": tname,
                                   "games": rem})
                susp_evs = []
                for e in (getattr(p, "controversy_history", None) or []):
                    if not isinstance(e, dict):
                        continue
                    if str(e.get("type", "") or "").lower() == "suspension":
                        susp_evs.append(e)
                if susp_evs:
                    latest = susp_evs[-1]
                    history.setdefault(tname, []).append({
                        "name": player_name(p),
                        "count": len(susp_evs),
                        "desc": str(latest.get("description", "") or ""
                                    ).strip()[:90],
                        "date": str(latest.get("date", "") or ""),
                    })
        active.sort(key=lambda a: -a["games"])

        # --- Serving suspensions right now ---
        content.addWidget(section_title("Serving suspensions right now"))
        if not active:
            content.addWidget(explainer_label(
                "No one is suspended right now."))
        for a in active:
            row = QFrame()
            row.setObjectName("tile")
            rl = QHBoxLayout(row)
            name = QLabel(a["name"])
            name.setObjectName("tile-title")
            games = QLabel(f"{a['games']} game{'s' if a['games'] != 1 else ''}")
            games.setStyleSheet(
                f"color: {tone_color('red')}; font-size: 14px; "
                "font-weight: 700;")
            team_lbl = QLabel(a["team"])
            team_lbl.setObjectName("tile-sub")
            rl.addWidget(name)
            rl.addWidget(team_lbl)
            rl.addStretch()
            rl.addWidget(games)
            content.addWidget(row)

        # --- Season rap sheet ---
        content.addWidget(section_title("Season rap sheet"))
        content.addWidget(explainer_label(
            "Suspension events by club, repeat offenders flagged."))
        hist = [{"team": t,
                 "entries": sorted(v, key=lambda e: -e["count"])[:6]}
                for t, v in sorted(history.items())]
        if not hist:
            content.addWidget(explainer_label(
                "No suspension events recorded this season."))
        for h in hist:
            card = QFrame()
            card.setObjectName("tile")
            cl = QVBoxLayout(card)
            ct = QLabel(h["team"])
            ct.setObjectName("tile-title")
            cl.addWidget(ct)
            for e in h["entries"]:
                repeat = (f"  \u00d7{e['count']}"
                          if e["count"] > 1 else "")
                line = QLabel(f"{e['name']}{repeat}")
                line.setStyleSheet("color: #e8edf5; font-size: 13px; "
                                   "font-weight: 600;")
                detail = f"{e['desc']}" + (
                    f"  \u00b7  {e['date']}" if e["date"] else "")
                dl = QLabel(detail)
                dl.setObjectName("tile-sub")
                dl.setWordWrap(True)
                cl.addWidget(line)
                cl.addWidget(dl)
            content.addWidget(card)

        content.addStretch()
