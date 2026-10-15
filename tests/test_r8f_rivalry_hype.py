#!/usr/bin/env python3
"""R8f: rivalry-hype bucket tests (Press Box pregame buildup).

Bucket under test: daily_news._rivalry_hype_stories. Conventions: synthetic
SimpleNamespace app/team fixtures (same shape as the R8a..R8e tests);
assertions on premises, not phrasing.

The bucket is a presentation layer over
narrative_ledger.matchup_narrative (league.rivalries heat + ledger grudge
memory + playoff-series history + iconic games). Tests assert the bucket
fires for scheduled matchups at heat>=35 with the true W-L-OTL records and
the true heat band, renders REAL hype_tags, and stays silent on low heat,
unscheduled pairs, the offseason, malformed schedule entries, and
same-team matchups. Heat is rigged with reputation_system (add_rivalry for
exact intensities; record_game_incident for the low-heat narrative path).
"""
import sys
import os
import types
import random
from datetime import date

_REPO = os.environ.get("R8F_REPO", os.path.expanduser("~/workspace/hockey-manager"))
sys.path.insert(0, _REPO)

import daily_news as dn
import reputation_system as rs


def mkteam(name, w, l, otl):
    return types.SimpleNamespace(team_name=name, wins=w, losses=l,
                                 ot_losses=otl)


def mkapp(teams, schedule, rivalries=None, season_year=2026):
    league = types.SimpleNamespace(teams=list(teams),
                                   schedule=list(schedule),
                                   rivalries=(rivalries if rivalries is not None
                                              else []),
                                   season_year=season_year)
    app = types.SimpleNamespace(league=league, _daily_news_recent={})
    return app


def run_bucket(app, day, seed=424242):
    rng = random.Random(seed)
    return dn._rivalry_hype_stories(app, day, rng)


def heat_up(rivalries, a, b, intensity, origin="test", story="Test feud"):
    rs.add_rivalry(rivalries, a, b, "team_team", intensity, origin, story)


DAY = date(2027, 1, 15)  # mid-season


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        check.failed += 1
check.failed = 0


# -- helpers ----------------------------------------------------------------
check("band 35..64 is heated rivalry",
      all(dn._rivalry_heat_band(h) == "heated rivalry" for h in (35, 50, 64)))
check("band 65+ is bad blood",
      all(dn._rivalry_heat_band(h) == "bad blood" for h in (65, 80, 100)))
check("schedule day ok today", dn._rivalry_sched_day_ok(DAY, DAY))
check("schedule day ok tomorrow",
      dn._rivalry_sched_day_ok(date(2027, 1, 16), DAY))
check("schedule day rejects yesterday",
      not dn._rivalry_sched_day_ok(date(2027, 1, 14), DAY))
check("schedule day rejects junk", not dn._rivalry_sched_day_ok("nope", DAY))
check("resolve passes objects through",
      dn._rivalry_resolve_team(mkteam("X", 1, 2, 3), []) is not None)
check("resolve drops junk", dn._rivalry_resolve_team(42, []) is None)
check("resolve drops empty strings", dn._rivalry_resolve_team("", []) is None)

# -- firing / silence --------------------------------------------------------
h = mkteam("Bruins", 30, 15, 5)
a = mkteam("Canadiens", 28, 17, 4)
rivalries = []
heat_up(rivalries, h, a, 45)
app = mkapp([h, a], [(DAY, h, a)], rivalries)
stories = run_bucket(app, DAY)
check("heat>=35 scheduled matchup fires one story", len(stories) == 1)
s = stories[0]
check("story names both teams", "Bruins" in s and "Canadiens" in s)
check("story states home record", "30-15-5" in s)
check("story states away record", "28-17-4" in s)
check("story states the heated band", "heated rivalry" in s.lower())
check("no Unknown Team/Player", "Unknown" not in s)

# Low heat: a single brawl creates heat 15, below the 35 floor.
h2 = mkteam("Leafs", 20, 20, 5)
a2 = mkteam("Sens", 19, 21, 6)
cool_rivalries = []
rs.record_game_incident(cool_rivalries, h2, a2, "brawl", "line brawl")
app = mkapp([h2, a2], [(DAY, h2, a2)], cool_rivalries)
check("heat 15 (brawl only) is silent", run_bucket(app, DAY) == [])

# No rivalry record at all.
h3 = mkteam("Flames", 22, 18, 4)
a3 = mkteam("Oilers", 24, 16, 5)
app = mkapp([h3, a3], [(DAY, h3, a3)])
check("no rivalry -> silent", run_bucket(app, DAY) == [])

# Feud exists but the pair is not scheduled.
app = mkapp([h, a], [(DAY, h3, a3)], rivalries)
check("unscheduled pair is silent", run_bucket(app, DAY) == [])

# Same-team matchup never fires.
app = mkapp([h, a], [(DAY, h, h)], rivalries)
check("same-team matchup is silent", run_bucket(app, DAY) == [])

# Calendar gates.
app = mkapp([h, a], [(DAY, h, a)], rivalries)
check("offseason is silent", run_bucket(app, date(2027, 7, 15)) == [])
app = mkapp([h, a], [(DAY, h, a)], rivalries, season_year=0)
check("season_year falls back to calendar year",
      len(run_bucket(app, DAY)) == 1)

# Pregame buildup: tomorrow's game fires; day-after-tomorrow does not.
app = mkapp([h, a], [(date(2027, 1, 16), h, a)], rivalries)
check("next-day matchup fires (pregame buildup)",
      len(run_bucket(app, DAY)) == 1)
app = mkapp([h, a], [(date(2027, 1, 17), h, a)], rivalries)
check("two-days-out matchup is silent", run_bucket(app, DAY) == [])

# Malformed schedule entries: fail closed, never raise.
app = mkapp([h, a],
            [("All-Star", "skills", "contest"),   # 3-tuple, non-team payload
             (DAY, h),                            # wrong arity
             (DAY, h, a, "extra"),                # wrong arity
             None,
             "not a tuple"], rivalries)
check("malformed schedule entries are silent",
      run_bucket(app, DAY) == [])

# -- bands / tags ------------------------------------------------------------
h4 = mkteam("Wings", 33, 12, 4)
a4 = mkteam("Hawks", 31, 14, 5)
rivalries = []
heat_up(rivalries, h4, a4, 80, origin="playoff_series",
        story="Playoff series: 2026 semifinal, Seven games")
app = mkapp([h4, a4], [(DAY, h4, a4)], rivalries)
stories = run_bucket(app, DAY)
check("heat 80 fires", len(stories) == 1)
s = stories[0]
check("bad blood band stated", "bad blood" in s.lower())
check("real hype_tags rendered",
      "Playoff rematch" in s and "Seven-game war" in s)

# Empty hype_tags: story must still be true (teams + records + band only).
rivalries = []
heat_up(rivalries, h, a, 45, origin="regional", story="plain regional feud")
app = mkapp([h, a], [(DAY, h, a)], rivalries)
stories = run_bucket(app, DAY)
check("no history tags still fires one true story",
      len(stories) == 1 and "Bruins" in stories[0]
      and "Canadiens" in stories[0] and "30-15-5" in stories[0]
      and "28-17-4" in stories[0] and "heated rivalry" in stories[0].lower())

# -- one-shot semantics ------------------------------------------------------
rivalries = []
heat_up(rivalries, h, a, 45)
app = mkapp([h, a], [(DAY, h, a)], rivalries)
first = run_bucket(app, DAY)
second = run_bucket(app, DAY)
check("same pair does not re-fire same day", first and second == [])

# Keys marked only for stories actually returned (cap = 2 of 3 live).
t1, t2 = mkteam("A1", 1, 1, 0), mkteam("B1", 1, 1, 0)
t3, t4 = mkteam("A2", 1, 1, 0), mkteam("B2", 1, 1, 0)
t5, t6 = mkteam("A3", 1, 1, 0), mkteam("B3", 1, 1, 0)
rivalries = []
heat_up(rivalries, t1, t2, 40)
heat_up(rivalries, t3, t4, 70)
heat_up(rivalries, t5, t6, 55)
app = mkapp([t1, t2, t3, t4, t5, t6],
            [(DAY, t1, t2), (DAY, t3, t4), (DAY, t5, t6)], rivalries)
stories = run_bucket(app, DAY)
check("max 2 stories per day", len(stories) == 2)
keys = [k for (k, st) in app._daily_news_recent if st == "rivalry_hype"]
check("keys marked only for returned stories (2 keys)", len(keys) == 2)
check("hottest feud leads", "A2" in stories[0] and "bad blood" in stories[0].lower())
check("second-hottest is second", "A3" in stories[1])

# Duplicate pair names render once, not twice.
rivalries = []
heat_up(rivalries, t1, t2, 50)
heat_up(rivalries, t1, t2, 60)
app = mkapp([t1, t2], [(DAY, t1, t2), (DAY, t2, t1)], rivalries)
check("duplicate pair dedupes to one story",
      len(run_bucket(app, DAY)) == 1)

# -- robustness ---------------------------------------------------------------
# Teams with missing attributes never raise.
ghost = types.SimpleNamespace()  # no team_name, no record
app = mkapp([ghost], [(DAY, ghost, ghost)])
check("nameless teams do not raise", run_bucket(app, DAY) == [])
partial = types.SimpleNamespace(team_name="Ghosts")  # no wins/losses
plain = mkteam("Plains", 10, 10, 2)
rivalries = []
heat_up(rivalries, partial, plain, 50)
app = mkapp([partial, plain], [(DAY, partial, plain)], rivalries)
stories = run_bucket(app, DAY)
check("missing record attrs do not raise, story fires",
      len(stories) == 1 and "Ghosts" in stories[0] and "0-0-0" in stories[0])

# No league at all: fail closed.
app = types.SimpleNamespace(_daily_news_recent={})
check("no league -> silent, no raise", run_bucket(app, DAY) == [])

# -- registration ------------------------------------------------------------
names = [g[0] for g in dn._GENERATORS]
check("bucket registered in _GENERATORS", "rivalry_hype" in names)
entry = [g for g in dn._GENERATORS if g[0] == "rivalry_hype"][0]
check("weight in 0.55-0.65 range", 0.55 <= entry[2] <= 0.65)

print("FAILED: %d" % check.failed)
sys.exit(1 if check.failed else 0)
