"""QA: playoff hype cohesion — intensity, rivals, atmosphere.

Verifies, on a fake 32-team league through the REAL bracket code paths:
  1. Hype stamping at schedule time: a past 7-game playoff war between a
     round-1 pair yields "Playoff rematch" + "Seven-game war" tags and a
     marquee flag; declared heat yields "Bad blood"; a WC-vs-division-
     winner draw yields "Upset watch". Cold series stay unflagged.
  2. Calendar cohesion: playoff schedule entries carry marquee/hype_tags
     so views can mark the dates fans circle.
  3. News: one "circle the dates" roundup per round (single story, inside
     the daily cap), milestone-flagged for involved human managers;
     silent with no app (headless/bulk).
  4. Atmosphere: pregame_crowd reads rivalry_heat — grudge games are
     louder before puck drop; the sim wires the series' heat through.
  5. Feedback loop: completing a series records rivalry heat, so wars
     leave hype for future rounds/years.
  6. Save/load round-trips the hype fields.

No repo files modified.
"""
import sys
from types import SimpleNamespace
from datetime import date

sys.path.insert(0, "/home/hatch/workspace/hockey-push/HOCKEY-MANAGER")

from playoff_system import PlayoffBracket
from reputation_system import (record_playoff_series, add_rivalry,
                               rivalry_between)

PASS, FAIL = [], []

def check(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name +
          (f" [{extra}]" if extra else ""))

# ---------------------------------------------------------------- fake league
DIVS = {
    "Atlantic":     [("BOS",112),("TOR",108),("FLA",104),("TBL",100),
                     ("BUF",96),("DET",92),("MTL",80),("OTT",76)],
    "Metropolitan": [("CAR",110),("NYR",106),("PIT",88),("WSH",87),
                     ("NYI",84),("NJD",82),("PHI",80),("CBJ",78)],
    "Central":      [("COL",114),("DAL",109),("WPG",102),("MIN",99),
                     ("NSH",89),("STL",85),("UTA",81),("CHI",77)],
    "Pacific":      [("EDM",111),("VGK",107),("LAK",98),("VAN",95),
                     ("CGY",91),("ANA",87),("SEA",83),("SJS",79)],
}
DIV_CONF = {"Atlantic": "Eastern", "Metropolitan": "Eastern",
            "Central": "Western", "Pacific": "Western"}

teams, standings = [], {}
for div, rows in DIVS.items():
    for name, pts in rows:
        t = SimpleNamespace(
            team_name=name, league_name="National Hockey League",
            conference=DIV_CONF[div], division=div, roster=[],
            goals_for=260, goals_against=230)
        teams.append(t)
        standings[name] = {"Points": pts, "W": pts // 2}
by_name = {t.team_name: t for t in teams}

# Seed the rivalry store BEFORE bracket generation (last spring's wars).
rivalries = []
# BOS over BUF in 7 last year — and they draw each other again (DW1vWC2).
record_playoff_series(rivalries, by_name["BOS"], by_name["BUF"], games=7)
# TOR/FLA: declared hate, high heat (they meet as ATL 2v3).
add_rivalry(rivalries, by_name["TOR"], by_name["FLA"], "team_team", 70,
            "declared", "Declared hate: these two can't stand each other.",
            grudge=75)

sched = [{"date": date(2027, 4, 12), "home_team": teams[0],
          "away_team": teams[1]}]
league = SimpleNamespace(teams=teams, standings=standings,
                         season_year=2026, rivalries=rivalries,
                         schedule=sched, playoff_bracket=None)

b = PlayoffBracket(league)
league.playoff_bracket = b
b.generate_playoff_bracket()
r1 = b.playoff_series["wild_card"]

def _series(a, c):
    return next(s for s in r1
                if {s.team1.team_name, s.team2.team_name} == {a, c})

# ------------------------------------------------------- 1. hype stamping
s_war = _series("BOS", "BUF")
check("war rematch heat stamped", s_war.rivalry_heat >= 20,
      str(s_war.rivalry_heat))
check("war rematch tags",
      "Playoff rematch" in s_war.hype_tags
      and "Seven-game war" in s_war.hype_tags, str(s_war.hype_tags))
check("war rematch is marquee", s_war.marquee is True)
check("WC-vs-DW1 upset watch", "Upset watch" in s_war.hype_tags,
      str(s_war.hype_tags))

s_blood = _series("TOR", "FLA")
check("declared heat stamped", s_blood.rivalry_heat >= 65,
      str(s_blood.rivalry_heat))
check("bad blood tag", "Bad blood" in s_blood.hype_tags,
      str(s_blood.hype_tags))
check("bad blood is marquee", s_blood.marquee is True)

s_cold = _series("CAR", "TBL")
check("cold series not marquee", s_cold.marquee is False)
check("cold series no tags", s_cold.hype_tags == [],
      str(s_cold.hype_tags))

# ------------------------------------------------------- 2. calendar carries hype
po = [e for e in league.schedule
      if isinstance(e, dict) and e.get("playoff")]
war_entries = [e for e in po if e.get("series_id") == s_war.series_id]
cold_entries = [e for e in po if e.get("series_id") == s_cold.series_id]
check("war series entries flagged marquee",
      war_entries and all(e.get("marquee") for e in war_entries))
check("war entries carry hype tags",
      war_entries and all(e.get("hype_tags") for e in war_entries),
      str(war_entries[0].get("hype_tags")))
check("cold entries not marquee",
      cold_entries and not any(e.get("marquee") for e in cold_entries))

# ------------------------------------------------------- 3. news roundup
class FakeInbox:
    def __init__(self):
        self.messages = []
    def add_message(self, m):
        self.messages.append(m)

news = []
user_team = by_name["TOR"]
user_team.inbox = FakeInbox()
app = SimpleNamespace(user_team=user_team, current_date=date(2027, 4, 13),
                      news=news)
app.add_news = news.append
b.app = app
b._announce_round_hype("wild_card")
check("one roundup story in news feed", len(news) == 1, str(news))
check("roundup subject circles dates",
      news and "CIRCLE THE DATES" in news[0], str(news[:1]))
check("roundup names both grudge series",
      user_team.inbox.messages
      and "BOS" in user_team.inbox.messages[0].content
      and "TOR" in user_team.inbox.messages[0].content,
      str(user_team.inbox.messages[0].subject if user_team.inbox.messages
          else ""))
check("involved manager gets milestone copy",
      any(getattr(m, "is_milestone", False)
          for m in user_team.inbox.messages),
      str(len(user_team.inbox.messages)))
check("daily cap respected (1 headline used)",
      getattr(app, "_headline_daily", {}).get("count") == 1,
      str(getattr(app, "_headline_daily", {})))

# Single-series format: only one marquee -> full treatment.
import headlines
msg = headlines.make_headline(
    "playoff_series_preview", date(2027, 4, 13), round_name="First Round",
    items=[{"t1": "BOS", "t2": "BUF",
            "tags": ["Bad blood", "Playoff rematch", "Seven-game war"],
            "heat": 70.0, "game1_fmt": "Apr 14", "game2_fmt": "Apr 16"}])
check("single preview builds", msg is not None)
check("single preview subject", msg is not None and "BAD BLOOD" in msg.subject,
      msg.subject if msg else "")
check("single preview circles Game 1",
      msg is not None and "Apr 14" in msg.content)

# Silent with no app (headless/bulk sims): no crash, no delivery.
b.app = None
news2 = []
try:
    b._announce_round_hype("wild_card")
    check("no-app announce is silent", news2 == [] and len(news) == 1)
except Exception as e:  # noqa: BLE001
    check("no-app announce is silent", False, repr(e))

# ------------------------------------------------------- 4. atmosphere reads heat
from arena_atmosphere import pregame_crowd
t1, t2 = SimpleNamespace(team_name="BOS"), SimpleNamespace(team_name="BUF")
cold = pregame_crowd(t1, t2, is_playoff=True, series_game=1)
hot = pregame_crowd(t1, t2, is_playoff=True, series_game=1, rivalry_heat=70.0)
warm = pregame_crowd(t1, t2, is_playoff=True, series_game=1, rivalry_heat=40.0)
check("grudge game louder", hot["energy"] > cold["energy"] + 5,
      f"{cold['energy']:.0f} -> {hot['energy']:.0f}")
check("bad-blood driver present",
      "Bad blood in this building" in hot["drivers"], str(hot["drivers"]))
check("grudge game is big_game", hot["big_game"] is True)
check("heated rivalry driver", "Heated rivalry" in warm["drivers"],
      str(warm["drivers"]))
# No duplicate driver when ledger memory AND heat both fire.
class HotLedger:
    def memory_weight(self, a, c):
        return 80.0
both = pregame_crowd(t1, t2, ledger=HotLedger(), is_playoff=True,
                     series_game=1, rivalry_heat=70.0)
check("no duplicate bad-blood driver",
      both["drivers"].count("Bad blood in this building") == 1,
      str(both["drivers"]))

# The sim wires the series' heat into the crowd (integration lock).
import pathlib
src = pathlib.Path("/home/hatch/workspace/hockey-push/HOCKEY-MANAGER/"
                   "playoff_system.py").read_text()
check("sim passes series heat to pregame_crowd",
      "rivalry_heat=getattr(series, 'rivalry_heat'" in src)

# ------------------------------------------------------- 5. feedback loop
for s in r1:
    s.is_complete = True
    if s.team1.team_name in ("BOS", "TOR", "CAR", "NYR"):
        s.winner, s.team1_wins, s.games_played = s.team1, 4, 4
    else:
        s.winner, s.team2_wins, s.games_played = s.team2, 4, 4
    s.end_date = date(2027, 4, 20)
pre = (rivalry_between(rivalries, by_name["BOS"], by_name["BUF"],
                       "team_team") or {}).get("intensity", 0)
b.app = app  # main thread: round-2 hype story may deliver
ok = b.advance_to_next_round("wild_card")
post = (rivalry_between(rivalries, by_name["BOS"], by_name["BUF"],
                        "team_team") or {}).get("intensity", 0)
check("advance succeeds", ok is True)
check("completed war refreshes rivalry heat", post >= pre > 0,
      f"{pre} -> {post}")
r2 = b.playoff_series["division_semifinals"]
check("round 2 created", len(r2) == 4, str(len(r2)))
check("round 2 series hype-computed",
      all(hasattr(s, "hype_tags") and hasattr(s, "marquee") for s in r2))

# ------------------------------------------------------- 6. save/load hype
from save_load_system import GameSaveManager
mgr = GameSaveManager.__new__(GameSaveManager)
blob = mgr._serialize_playoff_bracket(league)
sb = next(s for s in blob["series"] if s["series_id"] == s_war.series_id)
check("serialized heat", sb["rivalry_heat"] == s_war.rivalry_heat,
      str(sb["rivalry_heat"]))
check("serialized tags", sb["hype_tags"] == s_war.hype_tags,
      str(sb["hype_tags"]))
check("serialized marquee", sb["marquee"] is True)

league2 = SimpleNamespace(teams=teams, standings=standings,
                          season_year=2026, rivalries=[], schedule=[],
                          playoff_bracket=None)
mgr._restore_playoff_bracket(league2, blob)
rb = league2.playoff_bracket
rs = next(s for sl in rb.playoff_series.values() for s in sl
          if s.series_id == s_war.series_id)
check("restored heat", rs.rivalry_heat == s_war.rivalry_heat)
check("restored tags", rs.hype_tags == s_war.hype_tags)
check("restored marquee", rs.marquee is True)

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
