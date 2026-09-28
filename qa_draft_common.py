"""Shared builders for the draft QA suites (headless-safe)."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import game_classes as g
from ai_team_management import ManagementPriority


def make_league(year=2027):
    lg = g.League("NHL")
    nhl = [t for t in lg.teams
           if getattr(t, "league_name", "") == "National Hockey League"]
    lg.standings = {t.team_name: {"Points": i * 5} for i, t in enumerate(nhl)}
    lg.initialize_all_draft_picks()
    lg.season_year = year
    return lg, nhl


class StubStrategy:
    def __init__(self, priority):
        self.priority = priority


class StubAIMgr:
    def __init__(self, mapping):
        self.mapping = mapping

    def get_team_strategy(self, name):
        return StubStrategy(self.mapping.get(name, ManagementPriority.MAINTAIN))


class StubApp:
    def __init__(self, league, mapping):
        self.league = league
        self.ai_manager = StubAIMgr(mapping)
        self.news = []
        import datetime
        self.current_date = datetime.date(2027, 6, 28)
        self.user_team = None

    def add_news(self, s):
        self.news.append(s)


def mkprospect(pos, ranking, grade="B", ovr_attrs=None):
    p = g.Player(first_name="T", last_name="P", age=18,
                 primary_position=pos)
    p.draft_ranking = float(ranking)
    p.potential_grade = grade
    if ovr_attrs:
        for k, v in ovr_attrs.items():
            setattr(p, k, v)
    return p


def boost(p, val=88):
    """Pin the attributes overall_rating() reads so the rating is ~val."""
    for attr in ("skating", "shooting", "shooting_accuracy", "shooting_power",
                 "passing", "passing_accuracy", "passing_creativity",
                 "deking", "offensive_awareness", "defensive_awareness",
                 "stick_checking", "body_checking", "strength", "balance",
                 "aggression", "poise", "goaltending", "reflexes",
                 "positioning", "rebound_control", "puck_handling",
                 "glove_hand", "stick_side", "breakaway_skill", "confidence",
                 "focus", "composure"):
        try:
            setattr(p, attr, val)
        except Exception:
            pass
    return p
