#!/usr/bin/env python3
"""R8h: debuts bucket tests (S item).

Bucket under test: daily_news._debut_stories. Conventions: synthetic
SimpleNamespace app/team/player fixtures (same shape as the R8a-g
tests); assertions on premises, not phrasing.

Grounding under test:
  - NHL DEBUT: p.nhl_games_played == 1 (post-credit service time;
    preseason never credits) + a per-game game_stats line in a
    finished in-season NHL game on the game day.
  - FIRST NHL GOAL: skater, game line g >= 1 (g <= team goals), and
    the maximality gate proves zero prior NHL goals:
    p.stats.goals == g, nhl_games_played == p.stats.games_played,
    sum(prior_nhl_gp) == 0.
  - CALL-UP: production-silent by design (no dated production
    call-up log) -- asserted via the docstring, not a firing test.

Tests assert the bucket fires for debuts and provable first goals
with true names/teams/scores, and stays silent on unprovable or
degenerate state: prior NHL history, junk numerics, unknown
players/teams, out-of-window game days, malformed results, one-shot
re-fires, and the 2/day cap.
"""
import sys
import os
import types
import random
from datetime import date, timedelta

_REPO = os.environ.get("R8H_REPO", os.path.expanduser("~/workspace/hockey-manager"))
sys.path.insert(0, _REPO)

import daily_news as dn


def mkplayer(name, nhl_gp, pos="C", season_gp=0, season_goals=0,
             prior=None, pid=None):
    parts = name.split()
    p = types.SimpleNamespace(first_name=parts[0],
                              last_name=" ".join(parts[1:]) or parts[0])
    p.id = pid if pid is not None else abs(hash(name)) % 10 ** 9
    p.nhl_games_played = nhl_gp
    p.primary_position = pos  # plain string: _pos falls back to str(pp)
    p.stats = types.SimpleNamespace(games_played=season_gp,
                                    goals=season_goals,
                                    prior_nhl_gp=(list(prior)
                                                  if prior is not None
                                                  else []))
    return p


def mkteam(name, players, nhl=True):
    t = types.SimpleNamespace(team_name=name, roster=list(players))
    t.league_name = ("National Hockey League" if nhl
                     else "American Hockey League")
    return t


def mkresult(home, away, hs, aws, winner, lines, toi=None):
    res = {"home_team": home, "away_team": away,
           "home_score": hs, "away_score": aws,
           "winner": winner, "game_stats": lines}
    if toi is not None:
        # Production stamps result['player_toi'] = {pid: seconds}
        # (game_manager.py:8498/9546, main.py:13105/14496).
        res["player_toi"] = toi
    return res


def mkline(p, g=0, a=0, saves=0):
    return {"player": p, "g": g, "a": a, "saves": saves}


def mkapp(home, away, result, game_day, season_year=2026):
    league = types.SimpleNamespace(teams=[home, away],
                                   season_year=season_year,
                                   _results_by_date={game_day: [result]})
    return types.SimpleNamespace(league=league, _daily_news_recent={})


def run_bucket(app, day, seed=424242):
    rng = random.Random(seed)
    return dn._debut_stories(app, day, rng)


DAY = date(2027, 1, 15)          # mid-season news day
GAME_DAY = DAY - timedelta(days=1)


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        check.failed += 1
check.failed = 0


def debut_app(name="Rookie Star", nhl_gp=1, pos="C", g=0, a=0,
              season_gp=1, season_goals=0, prior=None, hs=3, aws=2,
              home_wins=True, saves=0, toi=900):
    """One-game app: Blades vs Wolves hs-aws on GAME_DAY, with `name`
    on the Blades holding a line. Production shape: the debutant has
    a TOI entry (skaters) or saves (goalies) proving he dressed."""
    p = mkplayer(name, nhl_gp, pos=pos, season_gp=season_gp,
                 season_goals=season_goals, prior=prior)
    home = mkteam("Blades", [p])
    away = mkteam("Wolves", [mkplayer("Veteran Foe", 300, season_gp=60,
                                     season_goals=20, prior=[70, 72])])
    res = mkresult(home, away, hs, aws, home if home_wins else away,
                   {"l1": mkline(p, g=g, a=a, saves=saves)},
                   toi={p.id: toi})
    return mkapp(home, away, res, GAME_DAY), p


# -- _debut_season_pair -------------------------------------------------------
p0 = mkplayer("Pair Ok", 5, season_gp=20, season_goals=5)
check("_debut_season_pair: real stats -> (20, 5)",
      dn._debut_season_pair(p0) == (20, 5))
p0.stats.goals = "5"
check("_debut_season_pair: junk str goals, flat junk -> (None, None)",
      dn._debut_season_pair(p0) == (None, None))
p0.stats.goals = True
check("_debut_season_pair: bool goals -> (None, None)",
      dn._debut_season_pair(p0) == (None, None))
p0.stats.goals = -1
check("_debut_season_pair: negative goals -> (None, None)",
      dn._debut_season_pair(p0) == (None, None))
p0.stats.goals = 5
p0.stats.games_played = 4.0
check("_debut_season_pair: float games -> (None, None)",
      dn._debut_season_pair(p0) == (None, None))
p1 = mkplayer("Flat Fallback", 5)
p1.stats = None
p1.games_played = 20
p1.goals = 5
check("_debut_season_pair: flat fallback -> (20, 5)",
      dn._debut_season_pair(p1) == (20, 5))
p1.goals = "x"
check("_debut_season_pair: junk flat -> (None, None)",
      dn._debut_season_pair(p1) == (None, None))

# -- _debut_prior_gp ----------------------------------------------------------
p2 = mkplayer("Prior Ok", 5, prior=[40, 38])
check("_debut_prior_gp: [40, 38] -> 78", dn._debut_prior_gp(p2) == 78)
p2.stats.prior_nhl_gp = None
check("_debut_prior_gp: None -> 0", dn._debut_prior_gp(p2) == 0)
p2.stats.prior_nhl_gp = [40, "x"]
check("_debut_prior_gp: junk entry -> None",
      dn._debut_prior_gp(p2) is None)
p2.stats.prior_nhl_gp = 40
check("_debut_prior_gp: non-list -> None",
      dn._debut_prior_gp(p2) is None)
p2.stats.prior_nhl_gp = [-3]
check("_debut_prior_gp: negative -> None",
      dn._debut_prior_gp(p2) is None)

# -- debut fires ---------------------------------------------------------------
app, p = debut_app()
stories = run_bucket(app, DAY)
check("debut (nhl_gp==1, has line) -> fires", len(stories) == 1)
if stories:
    s = stories[0]
    check("debut renders DEBUT", "DEBUT" in s)
    check("debut renders true name", "Rookie Star" in s)
    check("debut renders true team", "Blades" in s)
    check("debut renders true opp", "Wolves" in s)
    check("debut renders true score 3-2", "3-2" in s)
    check("debut no placeholder leakage", "Unknown" not in s)

# debut on a loss uses the loss template
app, p = debut_app(hs=1, aws=4, home_wins=False)
stories = run_bucket(app, DAY)
check("debut in a loss -> fires", len(stories) == 1)
if stories:
    check("debut loss renders 1-4", "1-4" in stories[0])

# goalie debut fires as a debut (skating the ice is the premise):
# the dressed proof for goalies is saves >= 1 (player_toi can't be
# used -- the snapshot fill-in stamps full-game TOI on every roster
# goalie, game_manager.py:14386)
app, p = debut_app(name="Rookie Tender", pos="G", saves=25,
                   toi=3600)
stories = run_bucket(app, DAY)
check("goalie debut (25 saves) -> fires as DEBUT", len(stories) == 1
      and "DEBUT" in stories[0])

# goalie credited but untested: saves=0 -> no dressed proof -> silent
app, p = debut_app(name="Backup Kid", nhl_gp=1, pos="G", saves=0,
                   toi=3600)
check("goalie debut with 0 saves stays silent",
      run_bucket(app, DAY) == [])

# -- debut silence gates --------------------------------------------------------
app, p = debut_app(nhl_gp=0)
check("nhl_gp==0 (pre-credit/corrupt) stays silent",
      run_bucket(app, DAY) == [])
app, p = debut_app(nhl_gp=2)
check("nhl_gp==2 stays silent", run_bucket(app, DAY) == [])

# credited scratch WITH a roster-wide line but no TOI: the reviewer B
# killshot shape (lines are initialized for the whole roster on both
# sim paths; TOI ledgers only admit dressed players). Must be silent.
p = mkplayer("Pressbox Pete", 1, season_gp=1)
home = mkteam("Blades", [p])
away = mkteam("Wolves", [mkplayer("Veteran Foe", 300)])
res = mkresult(home, away, 3, 2, home, {"l1": mkline(p)}, toi={})
check("scratch: line present, no TOI entry stays silent",
      run_bucket(mkapp(home, away, res, GAME_DAY), DAY) == [])
res = mkresult(home, away, 3, 2, home, {"l1": mkline(p)},
               toi={p.id: 0})
check("scratch: line present, TOI=0 stays silent",
      run_bucket(mkapp(home, away, res, GAME_DAY), DAY) == [])
res = mkresult(home, away, 3, 2, home, {"l1": mkline(p)})  # no key
check("missing player_toi stays silent (fail closed)",
      run_bucket(mkapp(home, away, res, GAME_DAY), DAY) == [])
res = mkresult(home, away, 3, 2, home, {"l1": mkline(p)},
               toi="junk")
check("junk player_toi stays silent",
      run_bucket(mkapp(home, away, res, GAME_DAY), DAY) == [])
res = mkresult(home, away, 3, 2, home, {"l1": mkline(p)},
               toi={p.id: True})
check("bool TOI stays silent",
      run_bucket(mkapp(home, away, res, GAME_DAY), DAY) == [])
# and the positive: same scratch shape WITH TOI fires
res = mkresult(home, away, 3, 2, home, {"l1": mkline(p)},
               toi={p.id: 780})
stories = run_bucket(mkapp(home, away, res, GAME_DAY), DAY)
check("dressed (TOI>0) debut fires", len(stories) == 1)

p = mkplayer("Junk Gp", "1")
home = mkteam("Blades", [p])
away = mkteam("Wolves", [mkplayer("Veteran Foe", 300)])
res = mkresult(home, away, 3, 2, home, {"l1": mkline(p)})
check("junk str nhl_games_played stays silent",
      run_bucket(mkapp(home, away, res, GAME_DAY), DAY) == [])
p.nhl_games_played = True
check("bool nhl_games_played stays silent",
      run_bucket(mkapp(home, away, res, GAME_DAY), DAY) == [])
p.nhl_games_played = -1
check("negative nhl_games_played stays silent",
      run_bucket(mkapp(home, away, res, GAME_DAY), DAY) == [])

# unknown player: no names at all
p = types.SimpleNamespace(id=12345, nhl_games_played=1,
                          primary_position="C",
                          stats=types.SimpleNamespace(games_played=1,
                                                    goals=0,
                                                    prior_nhl_gp=[]))
home = mkteam("Blades", [p])
away = mkteam("Wolves", [mkplayer("Veteran Foe", 300)])
res = mkresult(home, away, 3, 2, home, {"l1": mkline(p)})
check("nameless player stays silent",
      run_bucket(mkapp(home, away, res, GAME_DAY), DAY) == [])

# phantom: line names a player on neither roster
real = mkplayer("Real Bloke", 300, season_gp=60, season_goals=20,
                prior=[70])
ghost = mkplayer("Ghost Skater", 1, season_gp=1)
home = mkteam("Blades", [real])
away = mkteam("Wolves", [mkplayer("Veteran Foe", 300)])
res = mkresult(home, away, 3, 2, home, {"l1": mkline(ghost)})
check("phantom (not on either roster) stays silent",
      run_bucket(mkapp(home, away, res, GAME_DAY), DAY) == [])

# -- first NHL goal fires -------------------------------------------------------
# rookie game 5: scoreless in 4, scores tonight; all career NHL games
# this season, no archived prior NHL games
app, p = debut_app(name="Rookie Sniper", nhl_gp=5, g=1,
                   season_gp=5, season_goals=1)
stories = run_bucket(app, DAY)
check("provable first goal -> fires", len(stories) == 1)
if stories:
    s = stories[0]
    check("first-goal renders FIRST NHL GOAL", "FIRST NHL GOAL" in s)
    check("first-goal renders true name", "Rookie Sniper" in s)
    check("first-goal renders true score", "3-2" in s)
    check("first-goal has no debut note (not a debut)",
          "debut" not in s.lower())

# debut-scorer: one story, first_goal kind, debut noted, both keys
# marked so a regenerated news day cannot repeat either kind
app, p = debut_app(name="Dream Debut", nhl_gp=1, g=2,
                   season_gp=1, season_goals=2)
stories = run_bucket(app, DAY)
check("debut-scorer -> exactly one story", len(stories) == 1)
if stories:
    s = stories[0]
    check("debut-scorer story is FIRST NHL GOAL", "FIRST NHL GOAL" in s)
    check("debut-scorer story notes the debut",
          "in his NHL debut" in s)
    check("debut-scorer renders 2-goal truth", "2" in s)
regen = run_bucket(app, DAY)
check("debut-scorer regen day -> silent (both keys marked)",
      regen == [])

# first goal in a loss
app, p = debut_app(name="Tough Night", nhl_gp=5, g=1,
                   season_gp=5, season_goals=1, hs=1, aws=4,
                   home_wins=False)
stories = run_bucket(app, DAY)
check("first goal in a loss -> fires", len(stories) == 1)
if stories:
    check("first-goal loss renders 1-4", "1-4" in stories[0])

# -- first-goal silence gates ----------------------------------------------------
# veteran with prior-season goals: unprovable, stays silent
app, p = debut_app(name="Late Bloomer", nhl_gp=25, g=1,
                   season_gp=20, season_goals=1, prior=[70])
check("prior archived NHL games -> silent",
      run_bucket(app, DAY) == [])
# 6-seasons-ago vet shape: nhl_games_played != season games
app, p = debut_app(name="Old Return", nhl_gp=320, g=1,
                   season_gp=20, season_goals=1, prior=[])
check("career GP != season GP (prior career) -> silent",
      run_bucket(app, DAY) == [])
# season goals exceed tonight's: scored before, not a first
app, p = debut_app(name="Second Timer", nhl_gp=5, g=1,
                   season_gp=5, season_goals=2)
check("season_goals(2) != game goals(1) -> silent",
      run_bucket(app, DAY) == [])
# junk prior archive fails closed
p = mkplayer("Junk Prior", 5, season_gp=5, season_goals=1,
             prior=[40, "x"])
home = mkteam("Blades", [p])
away = mkteam("Wolves", [mkplayer("Veteran Foe", 300)])
res = mkresult(home, away, 3, 2, home, {"l1": mkline(p, g=1)})
check("junk prior archive -> silent",
      run_bucket(mkapp(home, away, res, GAME_DAY), DAY) == [])
# junk season stats fail closed
p = mkplayer("Junk Stats", 5, season_gp=5, season_goals="1")
home = mkteam("Blades", [p])
away = mkteam("Wolves", [mkplayer("Veteran Foe", 300)])
res = mkresult(home, away, 3, 2, home, {"l1": mkline(p, g=1)})
check("junk season goals -> silent",
      run_bucket(mkapp(home, away, res, GAME_DAY), DAY) == [])
# goalie "first goal" is not a story (debut kind still fires)
app, p = debut_app(name="Goalie Scorer", nhl_gp=5, pos="G", g=1,
                   season_gp=5, season_goals=1)
stories = run_bucket(app, DAY)
check("goalie with a goal -> silent (no goalie first-goal kind)",
      stories == [])
# line claims more goals than his team scored: corrupt, silent
app, p = debut_app(name="Stat Padder", nhl_gp=1, g=5,
                   season_gp=1, season_goals=5, hs=3, aws=2)
check("g(5) > team goals(3) -> silent", run_bucket(app, DAY) == [])
# scoreless vet: nothing to say
app, p = debut_app(name="Quiet Vet", nhl_gp=120, g=0,
                   season_gp=40, season_goals=8, prior=[70, 72])
check("scoreless non-debut stays silent", run_bucket(app, DAY) == [])

# -- window: the GAME day decides, never the news day -----------------------------
# Sept 30 preseason game, news runs Oct 1 -> silent
sept_game = date(2026, 9, 30)
oct_news = date(2026, 10, 1)
p = mkplayer("Camp Kid", 1, season_gp=1)
home = mkteam("Blades", [p])
away = mkteam("Wolves", [mkplayer("Veteran Foe", 300)])
res = mkresult(home, away, 3, 2, home, {"l1": mkline(p)})
check("Sept 30 preseason game (Oct 1 news) stays silent",
      run_bucket(mkapp(home, away, res, sept_game), oct_news) == [])
# May game -> silent
may_game = date(2027, 5, 3)
may_news = date(2027, 5, 4)
check("May game stays silent",
      run_bucket(mkapp(home, away, res, may_game), may_news) == [])
# August game -> silent
aug_game = date(2027, 8, 12)
aug_news = date(2027, 8, 13)
check("August game stays silent",
      run_bucket(mkapp(home, away, res, aug_game), aug_news) == [])

# -- degenerate results -----------------------------------------------------------
p = mkplayer("Degenerate Dan", 1, season_gp=1)
home = mkteam("Blades", [p])
away = mkteam("Wolves", [mkplayer("Veteran Foe", 300)])
good_lines = {"l1": mkline(p)}
res = mkresult(home, away, "3", 2, home, good_lines)  # str score
check("string score stays silent",
      run_bucket(mkapp(home, away, res, GAME_DAY), DAY) == [])
res = mkresult(home, away, -1, 2, home, good_lines)  # negative score
check("negative score stays silent",
      run_bucket(mkapp(home, away, res, GAME_DAY), DAY) == [])
res = mkresult(home, away, 3, 2, None, good_lines)  # no winner
check("no winner stays silent",
      run_bucket(mkapp(home, away, res, GAME_DAY), DAY) == [])
res = mkresult(home, away, 3, 2, mkteam("Ghosts", []), good_lines)
check("winner not a participant stays silent",
      run_bucket(mkapp(home, away, res, GAME_DAY), DAY) == [])
res = mkresult(home, home, 3, 2, home, good_lines)  # same team
check("same-team result stays silent",
      run_bucket(mkapp(home, away, res, GAME_DAY), DAY) == [])
ahl_home = mkteam("Farmhands", [p], nhl=False)
res = mkresult(ahl_home, away, 3, 2, ahl_home, good_lines)
check("non-NHL team stays silent",
      run_bucket(mkapp(ahl_home, away, res, GAME_DAY), DAY) == [])
res = mkresult(home, away, 3, 2, home, [mkline(p)])  # list, not dict
check("game_stats as list stays silent",
      run_bucket(mkapp(home, away, res, GAME_DAY), DAY) == [])
res = mkresult(home, away, 3, 2, home, {"l1": "junk"})
check("junk line stays silent",
      run_bucket(mkapp(home, away, res, GAME_DAY), DAY) == [])
league = types.SimpleNamespace(teams=[home, away], season_year=2026,
                               _results_by_date=None)
app = types.SimpleNamespace(league=league, _daily_news_recent={})
check("missing _results_by_date stays silent",
      run_bucket(app, DAY) == [])
league = types.SimpleNamespace(teams=[home, away], season_year=2026,
                               _results_by_date="junk")
app = types.SimpleNamespace(league=league, _daily_news_recent={})
check("junk _results_by_date stays silent",
      run_bucket(app, DAY) == [])

# -- one-shot, caps, identity ------------------------------------------------------
# same-day re-run: one-shot suppresses
app, p = debut_app()
first = run_bucket(app, DAY)
check("first run fires", len(first) == 1)
check("same-day re-run silent (one-shot)", run_bucket(app, DAY) == [])
# next season: fires again
league2 = types.SimpleNamespace(teams=app.league.teams,
                                season_year=2027,
                                _results_by_date=app.league._results_by_date)
app2 = types.SimpleNamespace(league=league2,
                             _daily_news_recent=app._daily_news_recent)
check("next season fires again", len(run_bucket(app2, DAY)) == 1)

# 2/day cap: three debutants -> exactly 2 stories
kids = [mkplayer(f"Kid {i}", 1, season_gp=1, pid=9000 + i)
        for i in range(3)]
home = mkteam("Blades", kids)
away = mkteam("Wolves", [mkplayer("Veteran Foe", 300)])
lines = {f"l{i}": mkline(k, g=1) for i, k in enumerate(kids)}
for k in kids:  # make them non-first-goal debutants: prior goals
    k.stats.goals = 3
    k.stats.games_played = 1
res = mkresult(home, away, 4, 2, home, lines,
               toi={k.id: 800 for k in kids})
stories = run_bucket(mkapp(home, away, res, GAME_DAY), DAY)
check("3 debutants -> capped at 2", len(stories) == 2)

# duplicate display names, different objects: identity by id()
a1 = mkplayer("Alex Smith", 1, season_gp=1, pid=11111)
a2 = mkplayer("Alex Smith", 1, season_gp=1, pid=22222)
home = mkteam("Blades", [a1, a2])
away = mkteam("Wolves", [mkplayer("Veteran Foe", 300)])
res = mkresult(home, away, 4, 2, home,
               {"l1": mkline(a1), "l2": mkline(a2)},
               toi={a1.id: 800, a2.id: 850})
stories = run_bucket(mkapp(home, away, res, GAME_DAY), DAY)
check("duplicate names, distinct ids -> both fire",
      len(stories) == 2)

# same player, two games the same day -> one story
p = mkplayer("Double Header", 1, season_gp=1)
home = mkteam("Blades", [p])
away = mkteam("Wolves", [mkplayer("Veteran Foe", 300)])
r1 = mkresult(home, away, 3, 2, home, {"l1": mkline(p)},
              toi={p.id: 800})
r2 = mkresult(away, home, 2, 5, home, {"l1": mkline(p)},
              toi={p.id: 820})
league = types.SimpleNamespace(teams=[home, away], season_year=2026,
                               _results_by_date={GAME_DAY: [r1, r2]})
app = types.SimpleNamespace(league=league, _daily_news_recent={})
stories = run_bucket(app, DAY)
check("same player two games one day -> one story per (game, player)",
      len(stories) == 2)

# -- insane season years ------------------------------------------------------------
p = mkplayer("Time Traveler", 1, season_gp=1)
home = mkteam("Blades", [p])
away = mkteam("Wolves", [mkplayer("Veteran Foe", 300)])
res = mkresult(home, away, 3, 2, home, {"l1": mkline(p)},
               toi={p.id: 800})
for bad_year in (0, 1999, 2101):
    league = types.SimpleNamespace(teams=[home, away],
                                   season_year=bad_year,
                                   _results_by_date={GAME_DAY: [res]})
    app = types.SimpleNamespace(league=league, _daily_news_recent={})
    if bad_year == 0:
        # _pr_season_year falls back to the calendar year on 0 (shared
        # helper behavior, same as R8d) -- a sane fallback, not silence.
        check("season_year=0 falls back to calendar year and fires",
              len(run_bucket(app, DAY)) == 1)
    else:
        check(f"season_year={bad_year} stays silent",
              run_bucket(app, DAY) == [])

# -- _debut_prior_gp: flat-attribute read order (production truth) -------------------
# The live rollover archives to flat p.prior_nhl_gp; the stats-level
# copy is never populated in production. The helper must read flat
# first (regression: it used to read only p.stats, making the check
# vacuous in production).
p3 = mkplayer("Flat Prior", 5, prior=[])   # stats copy: []
p3.prior_nhl_gp = [40, 38]                  # flat: the live archive
check("_debut_prior_gp: flat [40, 38] wins over stats [] -> 78",
      dn._debut_prior_gp(p3) == 78)
p3.prior_nhl_gp = "junk"
check("_debut_prior_gp: junk flat fails closed -> None",
      dn._debut_prior_gp(p3) is None)
p3.prior_nhl_gp = None
p3.stats.prior_nhl_gp = [25]
check("_debut_prior_gp: flat None falls back to stats [25] -> 25",
      dn._debut_prior_gp(p3) == 25)
p3.stats.prior_nhl_gp = [10, -2]
check("_debut_prior_gp: junk stats entry fails closed -> None",
      dn._debut_prior_gp(p3) is None)

# bucket-level: production-shaped player (flat archive populated,
# stats copy empty) with prior NHL games must NOT get a first-goal
# story -- the old stats-only read fired here (false "first").
# (nhl_gp == season_gp so gate (2) passes; only the flat archive
# distinguishes him from a true rookie.)
prod = mkplayer("Prod Vet", 40, season_gp=40, season_goals=1, prior=[])
prod.prior_nhl_gp = [70, 72]   # the live rollover archive
home = mkteam("Blades", [prod])
away = mkteam("Wolves", [mkplayer("Veteran Foe", 300)])
res = mkresult(home, away, 3, 2, home, {"l1": mkline(prod, g=1)})
check("flat prior archive [70, 72] -> first-goal stays silent",
      run_bucket(mkapp(home, away, res, GAME_DAY), DAY) == [])
# and the mirror: clean flat archive lets a true first goal fire
prod2 = mkplayer("Prod Rook", 5, season_gp=5, season_goals=1, prior=[])
prod2.prior_nhl_gp = []
home = mkteam("Blades", [prod2])
away = mkteam("Wolves", [mkplayer("Veteran Foe", 300)])
res = mkresult(home, away, 3, 2, home, {"l1": mkline(prod2, g=1)})
stories = run_bucket(mkapp(home, away, res, GAME_DAY), DAY)
check("flat prior [] + provable gate -> first-goal fires",
      len(stories) == 1 and "FIRST NHL GOAL" in stories[0])

# -- crash battery: never raises ------------------------------------------------------
check("app=None -> []", dn._debut_stories(None, DAY,
                                          random.Random(1)) == [])
app = types.SimpleNamespace(league=None, _daily_news_recent={})
check("league=None -> []", run_bucket(app, DAY) == [])
check("game_date=None -> []",
      dn._debut_stories(app, None, random.Random(1)) == [])
app = types.SimpleNamespace()
check("bare app -> []", dn._debut_stories(app, DAY,
                                          random.Random(1)) == [])

# -- registration ------------------------------------------------------------------
names = [g[0] for g in dn._GENERATORS]
check("bucket registered in _GENERATORS", "debuts" in names)

print()
if check.failed:
    print(f"{check.failed} FAILURES")
    sys.exit(1)
print("ALL CHECKS PASSED")
