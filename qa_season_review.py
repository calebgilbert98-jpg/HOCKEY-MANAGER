"""QA: season_review.py -- the end-of-season inbox card.

Builds a fake completed season (standings, ledger moments, bracket
result, board review, prospects, preseason poll) and asserts the card
renders every section, the email delivers, season_story events land,
last-season lines are stashed, and missing data degrades gracefully.
"""
from types import SimpleNamespace
from datetime import date

import season_review as sr
from narrative_ledger import NarrativeLedger
from league_history import LeagueHistory


class FP:
    """Fake player with everything the review reads."""
    _ids = [0]

    def __init__(self, name, **kw):
        FP._ids[0] += 1
        self.id = f"fp-{FP._ids[0]}"
        self.name = name
        self.team_name = "Chicago Blackhawks"
        self.games_played = kw.get("gp", 70)
        self.goals = kw.get("g", 0)
        self.assists = kw.get("a", 0)
        self.points = self.goals + self.assists
        self.plus_minus = kw.get("pm", 5)
        self.career_games = kw.get("cgp", self.games_played + 300)
        self.career_goals = kw.get("cg", self.goals + 90)
        self.career_assists = kw.get("ca", self.assists + 130)
        self.career_points = self.career_goals + self.career_assists
        self.morale = kw.get("morale", 70)
        self.is_rookie = kw.get("rookie", False)
        self.age = kw.get("age", 27)
        self.primary_position = kw.get("pos", "CENTER")
        self._ovr = kw.get("ovr", 80)
        self.prior_nhl_gp = kw.get("prior", [70, 72])
        self.saves = kw.get("saves", 0)
        self.shots_against = kw.get("sa", 0)
        self.wins = kw.get("w", 0)
        self.save_percentage = kw.get("svp", 0)
        self.goals_against_avg = kw.get("gaa", 0)
        self.shutouts = kw.get("so", 0)
        # prospect-development attrs
        self.potential = kw.get("potential", 14)
        for attr in ("skating", "shooting", "passing", "checking",
                     "defense", "hockey_iq", "determination",
                     "leadership", "strength", "conditioning"):
            setattr(self, attr, kw.get(attr, 13))

    def overall_rating(self):
        return self._ovr


def make_team():
    star = FP("Star Center", gp=70, g=38, a=44, pm=22, ovr=91, morale=85,
              cgp=370, cg=128, ca=174)          # ~1.0 ppg career -> +12 season
    rookie = FP("Rookie Winger", gp=82, g=50, a=32, age=20, rookie=True,
                ovr=84, morale=90, cgp=82, cg=50, ca=32, prior=[])
    washed = FP("Veteran Winger", gp=75, g=6, a=9, pm=-18, age=34, ovr=76,
                morale=45, cgp=975, cg=260, ca=340)  # 0.8 ppg -> -45
    goalie = FP("Starter", gp=55, pos="GOALIE", w=30, saves=1500, sa=1640,
                svp=0.915, gaa=2.61, so=4, ovr=88, morale=75)
    filler = FP("Depth Guy", gp=60, g=8, a=10, ovr=76)
    roster = [star, rookie, washed, goalie, filler]
    p1 = FP("Top Prospect", age=19, ovr=76, potential=17, pos="DEFENSE")
    p2 = FP("Longshot", age=22, ovr=68, potential=12)
    team = SimpleNamespace(
        team_name="Chicago Blackhawks", league_name="National Hockey League",
        roster=roster, ahl_roster=[], prospects=[p1, p2],
        longest_win_streak=10, win_streak=0,
        dynamics_log=[
            {"tone": "up", "text": "fleece cheer"},
            {"tone": "up", "text": "win streak joy"},
            {"tone": "down", "text": "selling low groan"},
        ])
    # team_chemistry is a property on the real Team; fake it.
    team.team_chemistry = 72
    return team


def make_app():
    team = make_team()
    standings = {"Chicago Blackhawks": {"W": 44, "L": 30, "OTL": 8, "Points": 96}}
    # 31 filler clubs so rank math is real (Chicago 12th of 32).
    for i in range(31):
        standings[f"Club {i:02d}"] = {"W": 50 - i, "L": 20 + i, "OTL": 5,
                                      "Points": 105 - 2 * i}
    league = SimpleNamespace(
        teams=[team] + [SimpleNamespace(team_name=f"Club {i:02d}",
                                        league_name="National Hockey League",
                                        longest_win_streak=3)
                        for i in range(31)],
        standings=standings, season_year=2027,
        preseason_predictions={"Chicago Blackhawks": {"rank": 20,
                                                      "strength": 80.1,
                                                      "season": 2027}},
        get_all_players=lambda: list(team.roster))
    led = NarrativeLedger()
    led.season = 2027
    led.record(kind="hat_trick", weight=75, teams=["Chicago Blackhawks"],
               players=["Rookie Winger"], season=2027,
               text="Rookie Winger nets a hat trick vs Detroit")
    led.record(kind="ot_thriller", weight=70, teams=["Chicago Blackhawks"],
               season=2027, text="OT thriller: Chicago 4, Boston 3")
    hist = LeagueHistory()
    hist.record_season(year=2027, champion="Winnipeg Jets",
                       runner_up="Edmonton Oilers", series_score="4-2",
                       presidents_trophy="Club 00", conn_smythe="Somebody",
                       awards={"Hart": "Star Center", "Vezina": "Other Goalie",
                               "Calder": "Rookie Winger"},
                       standings_snapshot=[])
    sent = []

    app = SimpleNamespace(
        user_team=team, league=league, narrative_ledger=led,
        league_history=hist, current_date=date(2027, 6, 20),
        _season_review_board={
            "headline": "Met expectations", "body": "", "delta": 8,
            "made_playoffs": True, "playoff_rounds_won": 1, "won_cup": False,
            "expectation": "playoffs", "confidence": 68, "season_number": 2},
        send_email_to_user=lambda m: sent.append(m))
    app._sent = sent
    return app


passed = failed = 0


def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ok   {name}")
    else:
        failed += 1
        print(f"  FAIL {name} {detail}")


def main():
    app = make_app()
    review = sr.build_review(app)
    check("review builds", review is not None)
    content = "\n".join(review["lines"])

    check("header has record + rank",
          "44-30-8 (96 pts)" in content and "6th" in content, content[:200])
    check("media beat-the-poll note",
          "20th" in content and "ABOVE expectations" in content)
    check("10-game streak in story", "10 games" in content)
    check("playoff run noted", "Won 1 playoff round" in content)
    check("ledger moments listed",
          "hat trick vs Detroit" in content and "OT thriller" in content)
    check("standout named with career-year note",
          "Star Center" in content and "career year" in content)
    _stood = content.split("STOOD OUT")[1].split("TOUGH GO")[0]
    check("no contradiction: tough-go vet not a standout",
          "Veteran Winger" not in _stood and "Depth Guy" not in _stood)
    check("tough go named", "Veteran Winger" in content)
    check("rookie watch: 50-goal rookie",
          "Rookie Winger" in content and "50" in content)
    check("hardware: Hart flagged as YOURS",
          "Hart: Star Center <-- YOURS" in content)
    check("pipeline report", "PIPELINE REPORT" in content
          and "Top Prospect" in content)
    check("four-corner grade", "SEASON GRADE:" in content
          and "Media:" in content and "Fans:" in content
          and "Owner:" in content and "Room:" in content)

    ok = sr.deliver_season_review(app)
    check("delivers", ok is True)
    check("email sent to inbox", len(app._sent) == 1)
    msg = app._sent[0]
    check("email metadata",
          msg.category == "League" and msg.is_important
          and msg.is_milestone and "2027-28" in msg.subject,
          msg.subject)
    check("last-season lines stashed",
          getattr(app.user_team.roster[0], "last_season", {}).get("pts") == 82)
    stories = [e for e in app.narrative_ledger.events
               if e.get("kind") == "season_story"]
    check("season_story per club", len(stories) == 32, str(len(stories)))

    # Preseason snapshot on a fake league.
    lg = SimpleNamespace(
        teams=[SimpleNamespace(team_name="A",
                               league_name="National Hockey League",
                               roster=[FP("x", ovr=90)]),
               SimpleNamespace(team_name="B",
                               league_name="National Hockey League",
                               roster=[FP("y", ovr=70)])],
        season_year=2028)
    sr.snapshot_preseason_predictions(lg)
    check("preseason snapshot ranks by strength",
          lg.preseason_predictions["A"]["rank"] == 1
          and lg.preseason_predictions["B"]["rank"] == 2)

    # Graceful degradation: empty app.
    bare = SimpleNamespace(user_team=None, league=None)
    check("no crash without team/league",
          sr.build_review(bare) is None and sr.deliver_season_review(bare) is False)

    thin_team = SimpleNamespace(team_name="Ghosts",
                                league_name="National Hockey League",
                                roster=[], ahl_roster=[], prospects=[],
                                longest_win_streak=0, win_streak=0,
                                dynamics_log=[])
    thin_team.team_chemistry = 50
    thin_app = SimpleNamespace(
        user_team=thin_team,
        league=SimpleNamespace(teams=[thin_team], standings={},
                               season_year=2027, get_all_players=lambda: []),
        narrative_ledger=NarrativeLedger(), league_history=LeagueHistory(),
        current_date=date(2027, 6, 20),
        send_email_to_user=lambda m: None)
    thin = sr.build_review(thin_app)
    check("thin roster still builds", thin is not None
          and "SEASON GRADE:" in "\n".join(thin["lines"]))

    # --- Archive: the card is stored on the team for later seasons ---
    card = app.user_team.season_reviews.get(2027)
    check("card archived on team", card is not None
          and card["label"] == "2027-28"
          and "SEASON GRADE:" in "\n".join(card["lines"]),
          str(card["label"] if card else None))
    check("archived scores match",
          card["scores"].get("composite") == review["scores"]["composite"])

    # A later season keeps its own card alongside the old one.
    app.league.season_year = 2028
    sr.deliver_season_review(app)
    check("two seasons, two cards",
          set(app.user_team.season_reviews.keys()) == {2027, 2028})

    # --- Every club keeps its own history ---
    club0 = app.league.teams[1]  # first fake AI club
    check("AI club card archived",
          2027 in getattr(club0, "season_reviews", {})
          and 2028 in getattr(club0, "season_reviews", {}),
          str(list(getattr(club0, "season_reviews", {}).keys())))
    club_card = "\n".join(club0.season_reviews[2027]["lines"])
    check("AI club card is its own (not the user's)",
          "SEASON REVIEW -- Club 00" in club_card
          and "Hart: Star Center" in club_card      # league-wide hardware shown
          and "<-- YOURS" not in club_card,         # ...but not claimed
          club_card[:80])
    check("all 32 clubs archived",
          all(2027 in getattr(t, "season_reviews", {})
              for t in app.league.teams),
          str(sum(2027 in getattr(t, "season_reviews", {}) for t in app.league.teams)))

    # --- League History -> Season Reviews tab renders headless ---
    import tkinter as tk
    from tkinter import ttk
    import main as main_mod
    root = tk.Tk(); root.withdraw()
    gm = SimpleNamespace(user_team=app.user_team,
                         league_history=app.league_history,
                         league=app.league,
                         teams=app.league.teams)
    view = main_mod.LeagueHistoryView.__new__(main_mod.LeagueHistoryView)
    view.game_manager = gm
    frame = ttk.Frame(root)
    frame.pack()
    view._build_season_reviews(frame)
    root.update_idletasks()

    combos = []
    texts = []
    def walk(w):
        for c in w.winfo_children():
            if c.winfo_class() == "TCombobox":
                combos.append(c)
            elif c.winfo_class() == "Text":
                texts.append(c)
            walk(c)
    walk(frame)
    check("tab has team + season pickers and a card view",
          len(combos) == 2 and len(texts) == 1,
          f"combos={len(combos)} texts={len(texts)}")
    team_combo, season_combo = combos
    check("team picker defaults to user's club",
          team_combo.get() == "Chicago Blackhawks", team_combo.get())
    check("user card shown by default",
          "SEASON GRADE:" in texts[0].get("1.0", "end"))
    check("season picker lists both archived years",
          len(season_combo["values"]) == 2, str(season_combo["values"]))
    # Switch club -> that club's own card renders.
    team_combo.set("Club 00")
    team_combo.event_generate("<<ComboboxSelected>>")
    root.update_idletasks()
    check("switching club shows its own card",
          "SEASON REVIEW -- Club 00" in texts[0].get("1.0", "end"),
          texts[0].get("1.0", "end")[:70])
    root.destroy()

    print(f"\n{passed} passed, {failed} failed")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
