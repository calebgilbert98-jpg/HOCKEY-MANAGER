"""NHL Awards Ceremony hub.

A full end-of-season awards night: each trophy is presented in ceremony
order with its three finalists, a dramatic winner reveal, and the voting
story (or statistical coronation) behind it. Winners match the official
season awards -- the ceremony is the presentation, not a second election.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any, Dict, List, Optional

TEAL = "#00ceb8"
CHARCOAL = "#1a1d21"
PANEL = "#23272d"
GOLD = "#d4af37"

# Ceremony order: build the drama, biggest trophies last.
# (award_key, trophy name, flavor line)
CEREMONY_ORDER = [
    ("calder", "Calder Memorial Trophy",
     "Rookie of the Year"),
    ("byng", "Lady Byng Memorial Trophy",
     "Sportsmanship and skill"),
    ("selke", "Frank J. Selke Trophy",
     "Best defensive forward"),
    ("adams", "Jack Adams Award",
     "Coach of the year"),
    ("jennings", "William M. Jennings Trophy",
     "Fewest goals against"),
    ("vezina", "Vezina Trophy",
     "Best goaltender"),
    ("norris", "James Norris Memorial Trophy",
     "Best defenseman"),
    ("rocket", 'Maurice "Rocket" Richard Trophy',
     "Most goals"),
    ("art_ross", "Art Ross Trophy",
     "Most points"),
    ("ted_lindsay", "Ted Lindsay Award",
     "Most outstanding player — as voted by the players"),
    ("hart", "Hart Memorial Trophy",
     "League MVP"),
    ("conn_smythe", "Conn Smythe Trophy",
     "Playoff MVP"),
]

# Maps ceremony award keys to the display names used by
# HockeyManagerGUI._calculate_season_awards.
_AWARD_DISPLAY_NAMES = {
    "hart": "Hart Trophy (MVP)",
    "ted_lindsay": "Ted Lindsay Award (Most Outstanding Player)",
    "art_ross": "Art Ross Trophy (Scoring Leader)",
    "rocket": 'Maurice "Rocket" Richard Trophy',
    "vezina": "Vezina Trophy (Best Goalie)",
    "norris": "Norris Trophy (Best Defenseman)",
    "selke": "Selke Trophy (Defensive Forward)",
    "byng": "Lady Byng Trophy (Sportsmanship)",
    "calder": "Calder Trophy (Rookie of the Year)",
    "jennings": "Jennings Trophy (Fewest GA)",
    "adams": "Jack Adams (Best Coach)",
}


def _player_name(p) -> str:
    return getattr(p, "full_name", getattr(p, "name", "?"))


def _player_team(p, roster_map=None) -> str:
    try:
        pid = int(getattr(p, "id", -1) or -1)
    except Exception:
        pid = -1
    if roster_map and pid in roster_map:
        return roster_map[pid]
    return getattr(p, "team_name", "") or ""


def _stat_line(p, award_key: str) -> str:
    """One-line season highlight for the winner/finalist card."""
    st = getattr(p, "stats", None)
    if award_key == "vezina" or "GOALIE" in str(
            getattr(getattr(p, "primary_position", None), "name", "")):
        try:
            sa = getattr(p, "shots_against", 0) or getattr(st, "shots_against", 0) or 0
            sv = getattr(p, "saves", 0) or getattr(st, "saves", 0) or 0
            svp = (sv / sa) if sa else 0
            w = getattr(p, "wins", 0) or getattr(st, "wins", 0) or 0
            return f"{w}W, .{int(svp * 1000):03d} SV%"
        except Exception:
            return ""
    try:
        g = getattr(p, "goals", 0) or getattr(st, "goals", 0) or 0
        a = getattr(p, "assists", 0) or getattr(st, "assists", 0) or 0
        gp = getattr(p, "games_played", 0) or getattr(st, "games_played", 0) or 0
        return f"{g}G {a}A, {g + a} pts in {gp} GP"
    except Exception:
        return ""


def build_ceremony_data(gui) -> List[Dict[str, Any]]:
    """Build the full ceremony script: one entry per trophy.

    Each entry: award_key, trophy, flavor, winner (player or team name),
    winner_team, winner_stats, finalists (list of dicts),
    electorate (who would decide it, or None for pure-stat awards).
    Winners match the official season awards -- the ceremony is the
    presentation, not a second election. No ballots are simulated.
    """
    import awards_race as ar

    league = getattr(gui, "league", None)
    if league is None:
        return []
    teams = list(getattr(league, "teams", []) or [])
    players = [p for t in teams for p in (getattr(t, "roster", None) or [])]
    if not players:
        return []

    season_year = int(getattr(league, "season_year", 0) or 0)
    roster_map = ar.roster_team_map(teams)
    team_pct = {}
    for t in teams:
        gp = getattr(t, "games_played", 0) or 0
        pts = getattr(t, "points", 0) or 0
        team_pct[getattr(t, "team_name", "")] = (pts / (2 * gp)) if gp else 0.5

    # Official winners (the same ones banked to trophy cases).
    try:
        official = gui._calculate_season_awards(players)
    except Exception:
        official = {}

    # Conn Smythe lives on the playoff bracket.
    smythe_name = None
    try:
        br = getattr(gui, "_playoff_bracket", None)
        smythe_name = getattr(br, "conn_smythe_name", None)
    except Exception:
        pass

    def _race_for(key):
        try:
            if key == "hart":
                return ar.hart_race(players, team_pct, roster_map=roster_map)
            if key == "ted_lindsay":
                return ar.lindsay_race(players, team_pct, roster_map=roster_map)
            if key == "art_ross":
                return ar.art_ross_race(players)
            if key == "rocket":
                return ar.rocket_race(players)
            if key == "norris":
                return ar.norris_race(players)
            if key == "selke":
                return ar.selke_race(players)
            if key == "byng":
                return ar.byng_race(players)
            if key == "calder":
                syr = ar.calder_season_year(
                    getattr(gui, "current_date", None))
                return ar.calder_race(players, season_year=syr)
            if key == "vezina":
                goalies = [p for p in players if "GOALIE" in str(
                    getattr(getattr(p, "primary_position", None),
                             "name", ""))]
                return ar.vezina_race(goalies)
        except Exception:
            pass
        return []

    script = []
    for key, trophy, flavor in CEREMONY_ORDER:
        entry = {"award_key": key, "trophy": trophy, "flavor": flavor,
                 "is_team_award": key in ("jennings", "adams"),
                 "winner": None, "winner_team": "", "winner_stats": "",
                 "finalists": [], "electorate": ar.AWARD_ELECTORATE.get(key),
                 "vote_story": ""}
        try:
            if key == "conn_smythe":
                # Playoff MVP: winner from the bracket; finalists are the
                # Cup finalists' top playoff scorers (best available story).
                entry["winner"] = smythe_name or "TBD"
                entry["winner_stats"] = "Playoff MVP"
            elif entry["is_team_award"]:
                disp = _AWARD_DISPLAY_NAMES.get(key)
                info = (official.get(disp) or {}) if disp else {}
                name = (info.get("name") if isinstance(info, dict)
                        else None) or "TBD"
                entry["winner"] = name
                entry["winner_team"] = name
                entry["winner_stats"] = (
                    "Fewest goals against" if key == "jennings"
                    else "Biggest overachievement")
            else:
                race = _race_for(key)
                disp = _AWARD_DISPLAY_NAMES.get(key)
                info = (official.get(disp) or {}) if disp else {}
                winner_name = (info.get("name") if isinstance(info, dict)
                               else None)
                # Find the winner's player object in the race.
                winner_p = None
                for r in race:
                    if _player_name(r.get("player")) == winner_name:
                        winner_p = r.get("player")
                        break
                if winner_p is None and race:
                    winner_p = race[0].get("player")
                if winner_p is not None:
                    entry["winner"] = winner_p
                    entry["winner_team"] = _player_team(winner_p, roster_map)
                    entry["winner_stats"] = _stat_line(winner_p, key)
                    # Finalists: top 3 by race score.
                    for r in race[:3]:
                        fp = r.get("player")
                        if fp is None:
                            continue
                        entry["finalists"].append({
                            "player": fp,
                            "name": _player_name(fp),
                            "team": _player_team(fp, roster_map),
                            "stats": _stat_line(fp, key),
                        })
                    pass
        except Exception:
            pass
        # Vezina: the GM vote is authoritative. Swap in the voted
        # winner and the ballot story.
        if key == "vezina":
            try:
                _vv = getattr(league, "vezina_votes", None) or {}
                _voted = _vv.get(str(season_year))
                if _voted and _voted.get("winner_id") not in (None, -1):
                    _wid = int(_voted["winner_id"])
                    for _pl in players:
                        try:
                            if int(getattr(_pl, "id", -2) or -2) == _wid:
                                entry["winner"] = _pl
                                entry["winner_team"] = _player_team(
                                    _pl, roster_map)
                                entry["winner_stats"] = _stat_line(_pl, key)
                                break
                        except Exception:
                            continue
                    _n = _voted.get("ballots", 32)
                    _ru = _voted.get("runner_up", "")
                    entry["vote_story"] = (
                        f"Decided by a real vote: {_n} GM ballots, 5-3-1 "
                        f"points.{' Edges out ' + _ru + '.' if _ru else ''}")
            except Exception:
                pass
        script.append(entry)
    return script


class AwardsCeremonyWindow(tk.Toplevel):
    """The awards night stage: finalists, dramatic reveals, full results."""

    def __init__(self, parent, gui, script: List[Dict[str, Any]]):
        super().__init__(parent)
        self.gui = gui
        self.script = [s for s in script if s.get("winner") is not None]
        self.idx = 0
        self.phase = "finalists"  # finalists -> winner -> done
        self.revealed_all = False

        season_year = int(getattr(getattr(gui, "league", None),
                                  "season_year", 0) or 0)
        self.title(f"NHL Awards — {season_year + 1} Ceremony")
        self.configure(bg=CHARCOAL)
        try:
            self.state("zoomed")
        except Exception:
            pass
        self._build()
        self._show_current()

    # -- layout ------------------------------------------------------
    def _build(self):
        self._header = tk.Label(self, text="NHL AWARDS", bg=CHARCOAL,
                                fg=TEAL, font=("Segoe UI", 16, "bold"))
        self._header.pack(pady=(18, 2))
        self._progress = tk.Label(self, text="", bg=CHARCOAL, fg="#8a9199",
                                  font=("Segoe UI", 11))
        self._progress.pack(pady=(0, 6))
        # Progress dots
        self._dots = tk.Frame(self, bg=CHARCOAL)
        self._dots.pack(pady=(0, 10))
        self._dot_labels = []
        for _ in self.script:
            d = tk.Label(self._dots, text="●", bg=CHARCOAL, fg="#3a3f45",
                         font=("Segoe UI", 10))
            d.pack(side="left", padx=3)
            self._dot_labels.append(d)

        # Stage
        self._stage = tk.Frame(self, bg=CHARCOAL)
        self._stage.pack(fill="both", expand=True, padx=40, pady=10)

        # Controls
        ctr = tk.Frame(self, bg=CHARCOAL)
        ctr.pack(pady=(6, 22))
        self._btn_reveal = tk.Button(
            ctr, text="Reveal Winner", command=self._reveal,
            bg=TEAL, fg="#0b0e11", font=("Segoe UI", 13, "bold"),
            relief="flat", padx=28, pady=10, cursor="hand2")
        self._btn_reveal.pack(side="left", padx=8)
        self._btn_next = tk.Button(
            ctr, text="Next Award →", command=self._next,
            bg=PANEL, fg="white", font=("Segoe UI", 12),
            relief="flat", padx=24, pady=10, cursor="hand2")
        self._btn_next.pack(side="left", padx=8)
        tk.Button(ctr, text="Reveal All", command=self._reveal_all,
                  bg=PANEL, fg="#8a9199", font=("Segoe UI", 11),
                  relief="flat", padx=18, pady=10,
                  cursor="hand2").pack(side="left", padx=8)

    def _clear_stage(self):
        for w in self._stage.winfo_children():
            w.destroy()

    def _trophy_header(self, entry):
        tk.Label(self._stage, text=entry["trophy"], bg=CHARCOAL, fg=GOLD,
                 font=("Segoe UI", 26, "bold"), wraplength=900,
                 justify="center").pack(pady=(10, 2))
        tk.Label(self._stage, text=entry["flavor"], bg=CHARCOAL, fg="#8a9199",
                 font=("Segoe UI", 13, "italic")).pack(pady=(0, 18))

    # -- phases ------------------------------------------------------
    def _show_current(self):
        if self.idx >= len(self.script):
            self._show_finale()
            return
        entry = self.script[self.idx]
        total = len(self.script)
        self._progress.configure(
            text=f"Award {self.idx + 1} of {total}")
        for i, d in enumerate(self._dot_labels):
            d.configure(fg=TEAL if i < self.idx
                        else (GOLD if i == self.idx else "#3a3f45"))
        self._clear_stage()
        if self.phase == "finalists":
            self._show_finalists(entry)
        else:
            self._show_winner(entry)
        self._btn_reveal.configure(
            state="normal" if self.phase == "finalists" else "disabled")
        self._btn_next.configure(
            text="Finish →" if self.idx == len(self.script) - 1
            and self.phase == "winner" else "Next Award →")

    def _show_finalists(self, entry):
        self._trophy_header(entry)
        tk.Label(self._stage, text="The finalists are…", bg=CHARCOAL,
                 fg="white", font=("Segoe UI", 15)).pack(pady=(0, 14))
        row = tk.Frame(self._stage, bg=CHARCOAL)
        row.pack()
        finalists = entry.get("finalists") or []
        if not finalists and not entry.get("is_team_award"):
            tk.Label(row, text="Finalists to be announced.",
                     bg=CHARCOAL, fg="#8a9199",
                     font=("Segoe UI", 12)).pack()
        for f in finalists[:3]:
            card = tk.Frame(row, bg=PANEL, padx=26, pady=18)
            card.pack(side="left", padx=12)
            tk.Label(card, text=f["name"], bg=PANEL, fg="white",
                     font=("Segoe UI", 14, "bold"), wraplength=220,
                     justify="center").pack()
            tk.Label(card, text=f["team"], bg=PANEL, fg=TEAL,
                     font=("Segoe UI", 12)).pack(pady=(4, 2))
            tk.Label(card, text=f["stats"], bg=PANEL, fg="#8a9199",
                     font=("Segoe UI", 11)).pack()
        if entry.get("is_team_award"):
            tk.Label(self._stage, text="(Team award — no finalists)",
                     bg=CHARCOAL, fg="#8a9199",
                     font=("Segoe UI", 12, "italic")).pack(pady=10)

    def _show_winner(self, entry):
        self._trophy_header(entry)
        tk.Label(self._stage, text="AND THE WINNER IS…", bg=CHARCOAL,
                 fg=GOLD, font=("Segoe UI", 15, "bold")).pack(pady=(0, 12))
        w = entry["winner"]
        name = _player_name(w) if not isinstance(w, str) else w
        card = tk.Frame(self._stage, bg=PANEL, padx=50, pady=30)
        card.pack(pady=8)
        # Trophy glyph as the visual anchor (no emoji chrome elsewhere,
        # but the ceremony stage earns one celebratory mark).
        tk.Label(card, text="🏆", bg=PANEL, fg=GOLD,
                 font=("Segoe UI", 44)).pack()
        tk.Label(card, text=name, bg=PANEL, fg="white",
                 font=("Segoe UI", 24, "bold"), wraplength=700,
                 justify="center").pack(pady=(6, 2))
        if entry.get("winner_team"):
            tk.Label(card, text=entry["winner_team"], bg=PANEL, fg=TEAL,
                     font=("Segoe UI", 15, "bold")).pack()
        if entry.get("winner_stats"):
            tk.Label(card, text=entry["winner_stats"], bg=PANEL,
                     fg="#c8cdd3", font=("Segoe UI", 13)).pack(pady=(6, 0))
        # Electorate line: who would decide this award
        story = self._electorate_story(entry)
        if story:
            tk.Label(self._stage, text=story, bg=CHARCOAL, fg="#8a9199",
                     font=("Segoe UI", 12, "italic"), wraplength=800,
                     justify="center").pack(pady=(16, 0))

    def _electorate_story(self, entry) -> str:
        if entry.get("vote_story"):
            return entry["vote_story"]
        electorate = entry.get("electorate")
        if not electorate:
            # Pure-stat coronation.
            stats = entry.get("winner_stats", "")
            if entry["award_key"] == "rocket":
                return f"No vote — the goals speak for themselves: {stats}."
            if entry["award_key"] == "art_ross":
                return f"No vote — the scoring title is decided on the ice: {stats}."
            if entry["award_key"] == "jennings":
                return "No vote — fewest goals against wins it outright."
            return ""
        if entry["award_key"] == "conn_smythe":
            return ("Decided by the PHWA at the Final — "
                    "the playoff story in one name.")
        if entry["award_key"] == "ted_lindsay":
            return ("Voted on by his fellow players — "
                    "the one the dressing room respects most.")
        return f"Voted on by the {electorate}."

    def _show_finale(self):
        self._progress.configure(text="Ceremony complete")
        for d in self._dot_labels:
            d.configure(fg=TEAL)
        self._clear_stage()
        tk.Label(self._stage, text="🏆", bg=CHARCOAL, fg=GOLD,
                 font=("Segoe UI", 52)).pack(pady=(10, 4))
        tk.Label(self._stage, text="That concludes this year's NHL Awards.",
                 bg=CHARCOAL, fg="white",
                 font=("Segoe UI", 20, "bold")).pack(pady=(0, 16))
        # Full winners table
        tbl = tk.Frame(self._stage, bg=CHARCOAL)
        tbl.pack()
        for s in self.script:
            w = s["winner"]
            name = _player_name(w) if not isinstance(w, str) else w
            row = tk.Frame(tbl, bg=CHARCOAL)
            row.pack(fill="x", pady=2)
            tk.Label(row, text=s["trophy"], bg=CHARCOAL, fg=GOLD,
                     font=("Segoe UI", 12), width=38, anchor="e").pack(
                         side="left", padx=(0, 14))
            tk.Label(row, text=name, bg=CHARCOAL, fg="white",
                     font=("Segoe UI", 12, "bold"), anchor="w").pack(
                         side="left")
            if s.get("winner_team"):
                tk.Label(row, text=f"({s['winner_team']})", bg=CHARCOAL,
                         fg="#8a9199", font=("Segoe UI", 11)).pack(
                             side="left", padx=(8, 0))
        self._btn_reveal.configure(state="disabled")
        self._btn_next.configure(state="disabled")

    # -- controls ----------------------------------------------------
    def _reveal(self):
        if self.phase == "finalists":
            self.phase = "winner"
            self._show_current()

    def _next(self):
        if self.phase == "finalists":
            self.phase = "winner"
            self._show_current()
            return
        self.idx += 1
        self.phase = "finalists"
        self._show_current()

    def _reveal_all(self):
        # Jump straight to the full winners table.
        self.idx = len(self.script)
        self._show_finale()


def open_awards_ceremony(gui):
    """Build the ceremony script and open the stage window."""
    try:
        script = build_ceremony_data(gui)
    except Exception:
        script = []
    if not script:
        try:
            from tkinter import messagebox
            messagebox.showinfo("Awards Ceremony",
                                "No awards data available yet — "
                                "finish a season first.")
        except Exception:
            pass
        return None
    win = AwardsCeremonyWindow(gui, gui, script)
    try:
        win.grab_set()
    except Exception:
        pass
    return win


class VezinaBallotWindow(tk.Toplevel):
    """The human GM's Vezina ballot: rank your top 3 goaltenders.

    Real Vezina rules: GMs rank three goalies, 5-3-1 points. Your ballot
    counts as one of 32 (31 AI GMs vote their own). Modal: returns the
    ranked list via .result, or None if abstained.
    """

    def __init__(self, parent, candidates):
        super().__init__(parent)
        self.candidates = candidates[:8]
        self.result = None
        self.title("Vezina Trophy — Your Ballot")
        self.configure(bg=CHARCOAL)
        self.geometry("560x640")
        self.resizable(False, False)

        tk.Label(self, text="VEZINA TROPHY", bg=CHARCOAL, fg=GOLD,
                 font=("Segoe UI", 18, "bold")).pack(pady=(18, 2))
        tk.Label(self, text="Rank your top 3 goaltenders.\n"
                            "31 fellow GMs are voting too — 5-3-1 points.",
                 bg=CHARCOAL, fg="#8a9199", font=("Segoe UI", 11),
                 justify="center").pack(pady=(0, 12))

        # Candidate list with stats
        list_frame = tk.Frame(self, bg=CHARCOAL)
        list_frame.pack(padx=24, fill="x")
        for i, r in enumerate(self.candidates):
            p = r.get("player")
            name = _player_name(p)
            team = _player_team(p)
            sv = r.get("sv_pct", 0) or 0
            line = (f"{name} ({team}) — {r.get('wins', 0)}W, "
                    f".{int(sv * 1000):03d} SV%, {r.get('gaa', 0):.2f} GAA, "
                    f"{r.get('shutouts', 0)} SO")
            tk.Label(list_frame, text=f"{i + 1}. {line}", bg=CHARCOAL,
                     fg="#c8cdd3", font=("Segoe UI", 11), anchor="w",
                     wraplength=510, justify="left").pack(fill="x", pady=2)

        # Three rank pickers
        self._vars = []
        names = [f"{i + 1}. {_player_name(r.get('player'))}"
                 for i, r in enumerate(self.candidates)]
        pick_frame = tk.Frame(self, bg=CHARCOAL)
        pick_frame.pack(pady=16)
        for rank, label in (("1st", "1st place (5 pts)"),
                            ("2nd", "2nd place (3 pts)"),
                            ("3rd", "3rd place (1 pt)")):
            row = tk.Frame(pick_frame, bg=CHARCOAL)
            row.pack(fill="x", pady=4)
            tk.Label(row, text=label, bg=CHARCOAL, fg=TEAL,
                     font=("Segoe UI", 11, "bold"), width=16,
                     anchor="w").pack(side="left")
            var = tk.StringVar(value="")
            self._vars.append(var)
            menu = tk.OptionMenu(row, var, *names)
            menu.configure(bg=PANEL, fg="white", font=("Segoe UI", 11),
                           relief="flat", width=32)
            menu.pack(side="left", padx=8)

        self._err = tk.Label(self, text="", bg=CHARCOAL, fg="#ff6b6b",
                             font=("Segoe UI", 11))
        self._err.pack()

        btnf = tk.Frame(self, bg=CHARCOAL)
        btnf.pack(pady=12)
        tk.Button(btnf, text="Submit Ballot", command=self._submit,
                  bg=TEAL, fg="#0b0e11", font=("Segoe UI", 12, "bold"),
                  relief="flat", padx=24, pady=8,
                  cursor="hand2").pack(side="left", padx=6)
        tk.Button(btnf, text="Abstain", command=self._abstain,
                  bg=PANEL, fg="#8a9199", font=("Segoe UI", 11),
                  relief="flat", padx=18, pady=8,
                  cursor="hand2").pack(side="left", padx=6)

    def _submit(self):
        picks = [v.get() for v in self._vars]
        if any(not p for p in picks):
            self._err.configure(text="Rank all three spots.")
            return
        idxs = [int(p.split(".")[0]) - 1 for p in picks]
        if len(set(idxs)) != 3:
            self._err.configure(text="Pick three different goalies.")
            return
        self.result = [self.candidates[i].get("player") for i in idxs]
        self.destroy()

    def _abstain(self):
        # Abstain: ballot auto-fills with the model's ranking.
        self.result = [r.get("player") for r in self.candidates[:3]]
        self.destroy()


def collect_human_vezina_ballot(parent, candidates):
    """Modal ballot window. Returns ranked top-3 players or model default."""
    try:
        win = VezinaBallotWindow(parent, candidates)
        win.grab_set()
        parent.wait_window(win)
        res = win.result
    except Exception:
        res = None
    if not res:
        res = [r.get("player") for r in (candidates or [])[:3]
               if r.get("player") is not None]
    return res
